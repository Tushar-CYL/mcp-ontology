-- Canonicalise staging into the knowledge graph (DuckDB dialect).
--
-- Runs entirely inside the engine as set-based SQL. Python never sees a
-- row: at 13.3M rows per slice, shipping them to a client and back would
-- be the slowest possible way to do this.
--
-- Order matters:
--   1. nodes    - canonical identities, placeholders excluded
--   2. aliases  - every surface form, including the contradictions
--   3. calls    - the span table, resolved to node ids
--   4. edges    - topology, with validity intervals
--
-- ENTITY RESOLUTION POLICY
-- Container ids embed a microservice name (MS_58845_POD_0 -> MS_58845)
-- which sometimes contradicts the declared msname on the same row - e.g.
-- msname=MS_66860 with msinstanceid=MS_43316_POD_3. Neither source is
-- verifiable from the data alone, so:
--   * the DECLARED msname wins for instance_of
--   * the embedded name is recorded in node_alias with reason
--     'embedded_conflict', so the choice is auditable and reversible
-- The validator counts these under container_has_microservice.
--
-- NOTE ON NO HASH-COLLISION GUARD
-- Node ids are hashed, and these INSERTs have no ON CONFLICT clause on
-- purpose. Each statement selects DISTINCT keys within one class, so the
-- only way to violate the primary key is a genuine hash collision - and
-- that should stop the build loudly rather than silently drop a node.

-- Idempotent: a re-run rebuilds the graph from staging rather than
-- appending to it.
DELETE FROM edges;
DELETE FROM calls;
DELETE FROM node_alias;
DELETE FROM nodes;

-- ------------------------------------------------- 1. resolve name -> class
-- ONE class per name, decided globally and once.
--
-- An earlier version classed each row independently: dm under db/mc became
-- a Datastore, otherwise a Microservice. That is wrong, because the same
-- name appears under BOTH paradigms in different rows. The node insert
-- would make it a Microservice while the calls table minted a Datastore id
-- for it, producing 10,969 edges pointing at ids that were never created -
-- dangling references that no query would ever match and no constraint
-- would catch.
--
-- The rule now: a name is a Microservice if it is EVER seen acting as one
-- (as an upstream caller, as a remote callee, or reporting resource
-- metrics). Only names that exclusively appear as the target of db/mc
-- calls are Datastores. Deterministic, order-independent, and auditable as
-- a table rather than buried in a CASE expression.
CREATE OR REPLACE TABLE entity_class AS
SELECT name,
       CASE WHEN name = 'USER' THEN 12      -- ExternalActor, not a service
            WHEN ever_service THEN 4
            ELSE 9 END AS class
FROM (
    SELECT k AS name, bool_or(as_service) AS ever_service
    FROM (
        SELECT um AS k, true AS as_service
          FROM stg_callgraph WHERE NOT is_placeholder(um)
        UNION ALL
        SELECT dm, lower(coalesce(trim(rpctype), '')) NOT IN ('db', 'mc')
          FROM stg_callgraph WHERE NOT is_placeholder(dm)
        UNION ALL
        SELECT msname, true
          FROM stg_msmetrics WHERE NOT is_placeholder(msname)
        UNION ALL
        SELECT msname, true
          FROM stg_msrtmcr WHERE NOT is_placeholder(msname)
    )
    GROUP BY k
);

-- --------------------------------------------------------------- 2. nodes
INSERT INTO nodes (id, class, nkey)
SELECT node_id(4, name), 4, name FROM entity_class WHERE class = 4;

-- Datastore: a name only ever seen as the target of db/mc traffic. Keeping
-- these out of Microservice is what stops the call graph sprouting
-- thousands of fake leaf "services" that would distort every fan-out and
-- blast-radius number.
INSERT INTO nodes (id, class, nkey)
SELECT node_id(9, name), 9, name FROM entity_class WHERE class = 9;

-- ExternalActor: traffic from outside the system.
INSERT INTO nodes (id, class, nkey)
SELECT node_id(12, name), 12, name FROM entity_class WHERE class = 12;

-- Container
INSERT INTO nodes (id, class, nkey)
SELECT node_id(3, k), 3, k FROM (
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
);

-- Node (bare metal)
INSERT INTO nodes (id, class, nkey)
SELECT node_id(2, k), 2, k FROM (
    SELECT DISTINCT nodeid AS k FROM stg_nodemetrics
     WHERE NOT is_placeholder(nodeid)
    UNION
    SELECT DISTINCT nodeid FROM stg_msmetrics WHERE NOT is_placeholder(nodeid)
    UNION
    SELECT DISTINCT nodeid FROM stg_msrtmcr   WHERE NOT is_placeholder(nodeid)
);

-- OnlineService
INSERT INTO nodes (id, class, nkey)
SELECT node_id(5, k), 5, k FROM (
    SELECT DISTINCT service AS k FROM stg_callgraph
     WHERE NOT is_placeholder(service)
);

-- Interface, keyed by owning service so the same interface name on two
-- services stays two distinct interfaces.
INSERT INTO nodes (id, class, nkey)
SELECT node_id(6, k), 6, k FROM (
    SELECT DISTINCT dm || '|' || interface AS k FROM stg_callgraph
     WHERE NOT is_placeholder(dm)
       AND NOT is_placeholder(interface)
       AND lower(coalesce(trim(rpctype), '')) IN ('rpc', 'http')
);

-- ------------------------------------------------------------- 2. aliases
-- Record the embedded-name conflicts instead of resolving them silently.
INSERT INTO node_alias (alias, class, node_id, reason)
SELECT DISTINCT ON (inst) inst, 3, node_id(3, inst), 'embedded_conflict'
FROM (
    SELECT msinstanceid AS inst, msname AS declared,
           split_part(msinstanceid, '_POD_', 1) AS embedded
      FROM stg_msmetrics
     WHERE msinstanceid LIKE 'MS\_%\_POD\_%' ESCAPE '\'
    UNION ALL
    SELECT uminstanceid, um, split_part(uminstanceid, '_POD_', 1)
      FROM stg_callgraph
     WHERE uminstanceid LIKE 'MS\_%\_POD\_%' ESCAPE '\'
)
WHERE embedded <> declared
  AND inst IN (SELECT nkey FROM nodes WHERE class = 3);

-- --------------------------------------------------------------- 3. calls
-- TRY_CAST replaces the regex-guarded cast the Postgres version needs:
-- a value that is not a number becomes NULL instead of aborting the
-- statement, and the validator counts how many did.
INSERT INTO calls (ts, traceid, service, rpc_id, parent_rpc_id,
                   um, dm, um_container, dm_container, rpctype, interface, rt)
SELECT
    tms(c.ts),
    c.traceid,
    nullif(c.service, ''),
    c.rpc_id,
    nullif(regexp_extract(c.rpc_id, '^(.*)\.[^.]*$', 1), ''),
    CASE WHEN is_placeholder(c.um) THEN NULL
         ELSE node_id(eu.class, c.um) END,
    CASE WHEN is_placeholder(c.dm) THEN NULL
         ELSE node_id(ec.class, c.dm) END,
    CASE WHEN is_placeholder(c.uminstanceid) THEN NULL
         ELSE node_id(3, c.uminstanceid) END,
    CASE WHEN is_placeholder(c.dminstanceid) THEN NULL
         ELSE node_id(3, c.dminstanceid) END,
    lower(nullif(trim(coalesce(c.rpctype, '')), '')),
    nullif(trim(coalesce(c.interface, '')), ''),
    TRY_CAST(c.rt AS DOUBLE)
FROM stg_callgraph c
LEFT JOIN entity_class ec ON ec.name = c.dm
LEFT JOIN entity_class eu ON eu.name = c.um
WHERE c.ts IS NOT NULL AND c.traceid IS NOT NULL AND c.rpc_id IS NOT NULL;

-- --------------------------------------------------------------- 4. edges
-- instance_of: declared msname wins (see the policy note at the top).
INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(3, inst), 1, node_id(4, ms),
       min(t), max(t) + INTERVAL 60 SECOND
FROM (
    SELECT msinstanceid AS inst, msname AS ms, tms(ts) AS t
      FROM stg_msmetrics
     WHERE NOT is_placeholder(msinstanceid) AND NOT is_placeholder(msname)
    UNION ALL
    SELECT uminstanceid, um, tms(ts) FROM stg_callgraph
     WHERE NOT is_placeholder(uminstanceid) AND NOT is_placeholder(um)
) q
-- Declared range is Microservice. Without this join, USER - which appears
-- as `um` but is an ExternalActor - produced an instance_of edge pointing
-- at a Microservice id that was never created.
JOIN entity_class ec ON ec.name = q.ms AND ec.class = 4
GROUP BY inst, ms;

-- runs_on: container-to-node residency. THE edge that makes time travel
-- work, so it is derived properly with gaps-and-islands rather than
-- collapsed to "latest node wins".
--
-- Samples arrive every 60s. A change of node, or a gap longer than 180s
-- (three missed samples), closes the current interval and opens a new one.
--
-- REPAIR FIRST: the source reports 60 container-instants on two nodes at
-- once (see rule placement_conflict). Feeding those straight into
-- gaps-and-islands produces overlapping intervals - a container apparently
-- resident on two machines simultaneously - which then corrupts every
-- point-in-time traversal that walks through it.
--
-- So one row per (container, instant) is chosen deterministically by lowest
-- nodeid. Deterministic matters: an arbitrary pick would make the graph
-- differ between rebuilds of identical input. The discarded alternative is
-- still counted by the validator.
INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(3, msinstanceid), 2, node_id(2, nodeid),
       min(t), max(t) + INTERVAL 60 SECOND
FROM (
    SELECT msinstanceid, nodeid, t,
           sum(is_new) OVER (PARTITION BY msinstanceid ORDER BY t
                             ROWS UNBOUNDED PRECEDING) AS island
    FROM (
        SELECT msinstanceid, nodeid, tms(ts) AS t,
               CASE WHEN lag(nodeid) OVER w IS DISTINCT FROM nodeid
                      OR ts - lag(ts) OVER w > 180000
                    THEN 1 ELSE 0 END AS is_new
        FROM (
            SELECT msinstanceid, nodeid, ts
            FROM (
                SELECT msinstanceid, nodeid, ts,
                       row_number() OVER (PARTITION BY msinstanceid, ts
                                          ORDER BY nodeid) AS rn
                FROM stg_msmetrics
                WHERE NOT is_placeholder(msinstanceid)
                  AND NOT is_placeholder(nodeid)
            )
            WHERE rn = 1
        )
        WINDOW w AS (PARTITION BY msinstanceid ORDER BY ts)
    )
)
GROUP BY msinstanceid, nodeid, island;

-- calls: microservice-level dependency, aggregated per window. This is the
-- edge blast_radius walks; the raw spans stay in `calls`.
INSERT INTO edges (src, rel, dst, valid_from, valid_to,
                   weight, stat_p50, stat_p99, tag)
SELECT um, 3, dm, w, w + INTERVAL 60 SECOND,
       count(*),
       quantile_cont(rt, 0.5),
       quantile_cont(rt, 0.99),
       rpctype
FROM (
    SELECT um, dm, rpctype, rt,
           time_bucket(INTERVAL 60 SECOND, ts,
                       TIMESTAMP '2022-01-01 00:00:00') AS w
    FROM calls
    WHERE um IS NOT NULL AND dm IS NOT NULL
      -- declared range is Microservice; db/mc traffic is carried by
      -- reads/writes instead, so it must not leak in here
      AND dm IN (SELECT node_id(4, name) FROM entity_class WHERE class = 4)
      AND um IN (SELECT node_id(4, name) FROM entity_class WHERE class = 4)
)
GROUP BY um, dm, rpctype, w;

-- exposes
INSERT INTO edges (src, rel, dst, valid_from, valid_to)
SELECT node_id(4, g.dm), 4, node_id(6, g.dm || '|' || g.interface),
       min(tms(g.ts)), max(tms(g.ts)) + INTERVAL 60 SECOND
FROM stg_callgraph g
JOIN entity_class ec ON ec.name = g.dm AND ec.class = 4
WHERE NOT is_placeholder(g.dm) AND NOT is_placeholder(g.interface)
  AND lower(coalesce(trim(g.rpctype), '')) IN ('rpc', 'http')
GROUP BY g.dm, g.interface;

-- entry_point: OnlineService -> the first INTERNAL service a request
-- reaches. Earlier this used `um` of rpc_id in ('0','0.1'), which pointed
-- 47,968 edges at USER - the external caller - instead of at anything
-- inside the system. The entered service is the CALLEE of the root span.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, weight)
SELECT node_id(5, g.service), 5, node_id(4, g.dm),
       min(tms(g.ts)), max(tms(g.ts)) + INTERVAL 60 SECOND, count(*)
FROM stg_callgraph g
JOIN entity_class ec ON ec.name = g.dm AND ec.class = 4
WHERE NOT is_placeholder(g.service) AND g.rpc_id = '0'
GROUP BY g.service, g.dm;

-- enters: ExternalActor -> first internal service. Kept out of `calls` so
-- that service-to-service centrality is not dominated by a pseudo-node
-- that every single request passes through.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, weight, tag)
SELECT node_id(12, g.um), 17, node_id(4, g.dm),
       min(tms(g.ts)), max(tms(g.ts)) + INTERVAL 60 SECOND,
       count(*), lower(trim(g.rpctype))
FROM stg_callgraph g
JOIN entity_class ea ON ea.name = g.um AND ea.class = 12
JOIN entity_class ec ON ec.name = g.dm AND ec.class = 4
WHERE g.rpc_id = '0'
GROUP BY g.um, g.dm, lower(trim(g.rpctype));

-- reads / writes against a datastore, split by paradigm.
INSERT INTO edges (src, rel, dst, valid_from, valid_to, weight, tag)
SELECT node_id(4, g.um),
       CASE WHEN lower(trim(g.rpctype)) = 'db' THEN 6 ELSE 7 END,
       node_id(9, g.dm),
       min(tms(g.ts)), max(tms(g.ts)) + INTERVAL 60 SECOND,
       count(*), lower(trim(g.rpctype))
FROM stg_callgraph g
JOIN entity_class eu ON eu.name = g.um AND eu.class = 4
WHERE NOT is_placeholder(g.um) AND NOT is_placeholder(g.dm)
  AND lower(coalesce(trim(g.rpctype), '')) IN ('db', 'mc')
  AND g.dm IN (SELECT name FROM entity_class WHERE class = 9)
GROUP BY g.um, g.dm, lower(trim(g.rpctype));
