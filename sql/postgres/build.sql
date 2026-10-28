-- Canonicalise staging into the knowledge graph.
--
-- Runs entirely server-side as set-based SQL. Python never sees a row: at
-- 13M+ rows per slice on a 3.8 GB VM, shipping rows to a client and back
-- would be the slowest possible way to do this.
--
-- Order matters:
--   1. nodes      - canonical identities, placeholders excluded
--   2. aliases    - every surface form, including contradictions
--   3. calls      - the span table, resolved to node ids
--   4. edges      - topology, with validity intervals
--
-- ENTITY RESOLUTION POLICY
-- Container ids embed a microservice name (MS_58845_POD_0 -> MS_58845) which
-- sometimes contradicts the declared msname on the same row. Neither source
-- is verifiable from the data alone, so the policy is:
--   * the DECLARED msname wins for instance_of
--   * the embedded name is recorded in node_alias with reason
--     'embedded_conflict', so the choice is auditable and reversible
-- The validator counts these separately under container_has_microservice.

\set ON_ERROR_STOP on

-- ------------------------------------------------------------ 0. helpers
-- Placeholder identities seen in this release. Excluded from the graph but
-- counted by the msname_present rule first, so nothing vanishes silently.
CREATE OR REPLACE FUNCTION is_placeholder(s text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT s IS NULL
        OR btrim(s) = ''
        OR upper(btrim(s)) IN ('NAN', '(?)', '?', 'NULL', 'UNKNOWN')
$$;

-- Aggregation window for microservice-level `calls` edges.
INSERT INTO meta(key, value) VALUES ('calls_window_seconds', '60')
ON CONFLICT (key) DO NOTHING;

-- ------------------------------------------------------------- 1. nodes
-- Microservice: union of every place a service identity appears.
INSERT INTO nodes (id, class, nkey)
SELECT node_id(4::smallint, k), 4::smallint, k
FROM (
    SELECT DISTINCT um AS k FROM stg_callgraph WHERE NOT is_placeholder(um)
    UNION
    SELECT DISTINCT dm FROM stg_callgraph
     WHERE NOT is_placeholder(dm)
       AND lower(btrim(coalesce(rpctype, ''))) IN ('rpc', 'http', '')
    UNION
    SELECT DISTINCT msname FROM stg_msmetrics WHERE NOT is_placeholder(msname)
    UNION
    SELECT DISTINCT msname FROM stg_msrtmcr  WHERE NOT is_placeholder(msname)
) q
ON CONFLICT (class, nkey) DO NOTHING;

-- Datastore / MessageQueue: dm under a non-remote paradigm is a store, not
-- a service. Keeping these out of Microservice is what stops the call graph
-- from sprouting thousands of fake leaf "services".
INSERT INTO nodes (id, class, nkey)
SELECT node_id(9::smallint, k), 9::smallint, k
FROM (
    SELECT DISTINCT dm AS k FROM stg_callgraph
     WHERE NOT is_placeholder(dm)
       AND lower(btrim(coalesce(rpctype, ''))) IN ('db', 'mc')
) q
ON CONFLICT (class, nkey) DO NOTHING;

-- Container
INSERT INTO nodes (id, class, nkey)
SELECT node_id(3::smallint, k), 3::smallint, k
FROM (
    SELECT DISTINCT uminstanceid AS k FROM stg_callgraph
     WHERE NOT is_placeholder(uminstanceid)
    UNION
    SELECT DISTINCT dminstanceid FROM stg_callgraph
     WHERE NOT is_placeholder(dminstanceid)
    UNION
    SELECT DISTINCT msinstanceid FROM stg_msmetrics
     WHERE NOT is_placeholder(msinstanceid)
    UNION
    SELECT DISTINCT msinstanceid FROM stg_msrtmcr
     WHERE NOT is_placeholder(msinstanceid)
) q
ON CONFLICT (class, nkey) DO NOTHING;

-- Node (bare metal)
INSERT INTO nodes (id, class, nkey)
SELECT node_id(2::smallint, k), 2::smallint, k
FROM (
    SELECT DISTINCT nodeid AS k FROM stg_nodemetrics WHERE NOT is_placeholder(nodeid)
    UNION
    SELECT DISTINCT nodeid FROM stg_msmetrics       WHERE NOT is_placeholder(nodeid)
    UNION
    SELECT DISTINCT nodeid FROM stg_msrtmcr         WHERE NOT is_placeholder(nodeid)
) q
ON CONFLICT (class, nkey) DO NOTHING;

-- OnlineService
INSERT INTO nodes (id, class, nkey)
SELECT node_id(5::smallint, k), 5::smallint, k
FROM (SELECT DISTINCT service AS k FROM stg_callgraph
       WHERE NOT is_placeholder(service)) q
ON CONFLICT (class, nkey) DO NOTHING;

-- Interface, keyed by owning service so the same name on two services stays
-- two distinct interfaces.
INSERT INTO nodes (id, class, nkey)
SELECT node_id(6::smallint, k), 6::smallint, k
FROM (
    SELECT DISTINCT dm || '|' || interface AS k
      FROM stg_callgraph
     WHERE NOT is_placeholder(dm)
       AND NOT is_placeholder(interface)
       AND lower(btrim(coalesce(rpctype, ''))) IN ('rpc', 'http')
) q
ON CONFLICT (class, nkey) DO NOTHING;

ANALYZE nodes;

-- ----------------------------------------------------------- 2. aliases
-- Record the embedded-name conflicts rather than resolving them silently.
INSERT INTO node_alias (alias, class, node_id, reason)
SELECT DISTINCT ON (inst)
       inst, 3::smallint, node_id(3::smallint, inst), 'embedded_conflict'
FROM (
    SELECT msinstanceid AS inst, msname AS declared,
           split_part(msinstanceid, '_POD_', 1) AS embedded
      FROM stg_msmetrics WHERE msinstanceid LIKE 'MS!_%!_POD!_%' ESCAPE '!'
    UNION ALL
    SELECT uminstanceid, um, split_part(uminstanceid, '_POD_', 1)
      FROM stg_callgraph WHERE uminstanceid LIKE 'MS!_%!_POD!_%' ESCAPE '!'
) q
WHERE embedded <> declared
  AND EXISTS (SELECT 1 FROM nodes n WHERE n.id = node_id(3::smallint, inst))
ON CONFLICT (class, alias) DO NOTHING;

-- ------------------------------------------------------------- 3. calls
-- Create the hourly partitions the slice actually needs.
DO $$
DECLARE lo timestamptz; hi timestamptz; t timestamptz;
BEGIN
    SELECT tms(min(ts)), tms(max(ts)) INTO lo, hi FROM stg_callgraph;
    IF lo IS NULL THEN RETURN; END IF;
    t := date_trunc('hour', lo);
    WHILE t <= hi LOOP
        PERFORM ensure_calls_partition(t);
        t := t + interval '1 hour';
    END LOOP;
END $$;

INSERT INTO calls (ts, traceid, service, rpc_id, parent_rpc_id,
                   um, dm, um_container, dm_container, rpctype, interface, rt)
SELECT
    tms(c.ts),
    c.traceid,
    nullif(c.service, ''),
    c.rpc_id,
    nullif(substring(c.rpc_id from '^(.*)\.[^.]*$'), ''),
    CASE WHEN is_placeholder(c.um) THEN NULL
         ELSE node_id(4::smallint, c.um) END,
    CASE WHEN is_placeholder(c.dm) THEN NULL
         WHEN lower(btrim(coalesce(c.rpctype, ''))) IN ('db', 'mc')
              THEN node_id(9::smallint, c.dm)
         ELSE node_id(4::smallint, c.dm) END,
    CASE WHEN is_placeholder(c.uminstanceid) THEN NULL
         ELSE node_id(3::smallint, c.uminstanceid) END,
    CASE WHEN is_placeholder(c.dminstanceid) THEN NULL
         ELSE node_id(3::smallint, c.dminstanceid) END,
    lower(nullif(btrim(coalesce(c.rpctype, '')), '')),
    nullif(btrim(coalesce(c.interface, '')), ''),
    -- rt arrives as text and is not always numeric; a non-numeric value is
    -- a data defect, recorded as NULL here and counted by the validator.
    CASE WHEN c.rt ~ '^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$'
         THEN c.rt::double precision END
FROM stg_callgraph c
WHERE c.ts IS NOT NULL AND c.traceid IS NOT NULL AND c.rpc_id IS NOT NULL;

-- -------------------------------------------------------------- 4. edges
-- instance_of: declared msname wins (see policy note at the top).
INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(3::smallint, inst), 1::smallint, node_id(4::smallint, ms),
       min(t), max(t) + interval '60 seconds'
FROM (
    SELECT msinstanceid AS inst, msname AS ms, tms(ts) AS t
      FROM stg_msmetrics
     WHERE NOT is_placeholder(msinstanceid) AND NOT is_placeholder(msname)
    UNION ALL
    SELECT uminstanceid, um, tms(ts) FROM stg_callgraph
     WHERE NOT is_placeholder(uminstanceid) AND NOT is_placeholder(um)
) q
GROUP BY inst, ms;

-- runs_on: the container-to-node residency interval. This is the edge that
-- makes time travel work, so it is derived properly with gaps-and-islands
-- rather than collapsed to "latest node wins".
--
-- Samples arrive every 60s. A change of node, or a gap of more than 180s
-- (three missed samples), closes the current interval and opens a new one.
INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(3::smallint, msinstanceid), 2::smallint,
       node_id(2::smallint, nodeid),
       min(t), max(t) + interval '60 seconds'
FROM (
    SELECT msinstanceid, nodeid, t,
           sum(is_new) OVER (PARTITION BY msinstanceid ORDER BY t
                             ROWS UNBOUNDED PRECEDING) AS island
    FROM (
        SELECT msinstanceid, nodeid, tms(ts) AS t,
               CASE WHEN lag(nodeid) OVER w IS DISTINCT FROM nodeid
                      OR ts - lag(ts) OVER w > 180000
                    THEN 1 ELSE 0 END AS is_new
        FROM stg_msmetrics
        WHERE NOT is_placeholder(msinstanceid) AND NOT is_placeholder(nodeid)
        WINDOW w AS (PARTITION BY msinstanceid ORDER BY ts)
    ) s
) g
GROUP BY msinstanceid, nodeid, island;

-- calls: microservice-level dependency, aggregated per window. This is the
-- edge the blast-radius traversal walks; the raw spans stay in `calls`.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, props)
SELECT um, 3::smallint, dm, w,
       w + (SELECT value::int FROM meta WHERE key = 'calls_window_seconds')
            * interval '1 second',
       jsonb_build_object(
           'call_count', count(*),
           'rpctype', rpctype,
           'rt_p50', round(percentile_cont(0.5) WITHIN GROUP (ORDER BY rt)::numeric, 3),
           'rt_p99', round(percentile_cont(0.99) WITHIN GROUP (ORDER BY rt)::numeric, 3))
FROM (
    SELECT um, dm, rpctype, rt,
           date_bin((SELECT value::int FROM meta
                      WHERE key = 'calls_window_seconds') * interval '1 second',
                    ts, trace_epoch()) AS w
    FROM calls
    WHERE um IS NOT NULL AND dm IS NOT NULL
) c
GROUP BY um, dm, rpctype, w;

-- exposes / entry_point: cheap structural edges, no interval needed beyond
-- the slice itself.
INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(4::smallint, dm), 4::smallint,
       node_id(6::smallint, dm || '|' || interface),
       min(tms(ts)), max(tms(ts))
FROM stg_callgraph
WHERE NOT is_placeholder(dm) AND NOT is_placeholder(interface)
  AND lower(btrim(coalesce(rpctype, ''))) IN ('rpc', 'http')
GROUP BY dm, interface;

INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(5::smallint, service), 5::smallint, node_id(4::smallint, um),
       min(tms(ts)), max(tms(ts))
FROM stg_callgraph
WHERE NOT is_placeholder(service) AND NOT is_placeholder(um)
  AND rpc_id IN ('0.1', '0')          -- entry span of the call graph
GROUP BY service, um;

-- reads / writes against a datastore, split by paradigm.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, props)
SELECT node_id(4::smallint, um),
       CASE WHEN lower(btrim(rpctype)) = 'db' THEN 6::smallint
            ELSE 7::smallint END,
       node_id(9::smallint, dm),
       min(tms(ts)), max(tms(ts)),
       jsonb_build_object('call_count', count(*))
FROM stg_callgraph
WHERE NOT is_placeholder(um) AND NOT is_placeholder(dm)
  AND lower(btrim(coalesce(rpctype, ''))) IN ('db', 'mc')
GROUP BY um, dm, CASE WHEN lower(btrim(rpctype)) = 'db' THEN 6 ELSE 7 END;

ANALYZE edges;
ANALYZE calls;
