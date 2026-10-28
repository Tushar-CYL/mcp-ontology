-- Executable shapes for the rules declared in ontology.yaml.
--
-- Each shape is a SELECT returning exactly two columns:
--     row_key  text   - identifies the offending row
--     detail   jsonb  - enough context to understand the violation
--
-- The validator wraps each one twice: once in count(*) for the exact number
-- of violations, once with a LIMIT for a stored sample. Shapes must
-- therefore be plain SELECTs with no trailing semicolon inside the body.
--
-- Markers:
--   -- @rule:  <id>                 must match a rule id in ontology.yaml
--   -- @stage: staging | graph      which build phase the shape can run in
--
-- These are expected to FIRE. The dataset is real production data with
-- documented defects; measuring them is the deliverable.


-- @rule: msname_present
-- @stage: staging
-- Placeholder identities must never become nodes. The release uses several:
-- empty, NaN, "(?)" and the literal UNKNOWN (with matching UNKNOWN_POD_*).
SELECT
    k AS row_key,
    jsonb_build_object('column', col, 'value', k, 'src_file', src) AS detail
FROM (
    SELECT um AS k, 'callgraph.um' AS col, src_file AS src
      FROM stg_callgraph
     WHERE um IS NULL OR btrim(um) = ''
        OR upper(btrim(um)) IN ('NAN', '(?)', '?', 'NULL', 'UNKNOWN')
    UNION ALL
    SELECT dm, 'callgraph.dm', src_file
      FROM stg_callgraph
     WHERE dm IS NULL OR btrim(dm) = ''
        OR upper(btrim(dm)) IN ('NAN', '(?)', '?', 'NULL', 'UNKNOWN')
    UNION ALL
    SELECT msname, 'msmetrics.msname', src_file
      FROM stg_msmetrics
     WHERE msname IS NULL OR btrim(msname) = ''
        OR upper(btrim(msname)) IN ('NAN', '(?)', '?', 'NULL', 'UNKNOWN')
) q


-- @rule: call_has_parent
-- @stage: staging
-- rpc_id is a dotted path: the parent of 0.1.1 is 0.1. A non-root call whose
-- parent is absent from the same trace is an orphan span. This is the
-- inconsistency class ICPE 2024 reported, and the anti-join below is the
-- headline measurement of the whole validation step.
-- "0" is the implicit trace root and is not emitted as a row, so a parent of
-- "0" is expected rather than missing.
SELECT
    c.traceid || '#' || c.rpc_id AS row_key,
    jsonb_build_object('traceid', c.traceid, 'rpc_id', c.rpc_id,
                       'missing_parent', c.parent) AS detail
FROM (
    SELECT traceid, rpc_id,
           substring(rpc_id from '^(.*)\.[^.]*$') AS parent
      FROM stg_callgraph
     WHERE rpc_id IS NOT NULL AND traceid IS NOT NULL
) c
WHERE c.parent IS NOT NULL
  AND c.parent <> '0'
  AND NOT EXISTS (
        SELECT 1 FROM stg_callgraph p
         WHERE p.traceid = c.traceid AND p.rpc_id = c.parent)


-- @rule: trace_acyclic
-- @stage: staging
-- Structural cycles cannot occur in a dotted-path id scheme, so at staging
-- this measures the degenerate case that CAN occur and does: a microservice
-- calling itself. Deeper ancestor cycles are a graph-stage check, once
-- microservice-level edges exist.
SELECT
    traceid || '#' || rpc_id AS row_key,
    jsonb_build_object('ms', um, 'rpctype', rpctype,
                       'um_pod', uminstanceid, 'dm_pod', dminstanceid) AS detail
FROM stg_callgraph
WHERE um IS NOT NULL AND um = dm


-- @rule: interface_iff_remote
-- @stage: staging
-- interface is populated for remote invocation only. Anything else is a
-- departure from the published spec.
SELECT
    coalesce(traceid, '') || '#' || coalesce(rpc_id, '') AS row_key,
    jsonb_build_object('rpctype', rpctype, 'interface', interface) AS detail
FROM stg_callgraph
WHERE (lower(btrim(coalesce(rpctype, ''))) IN ('rpc', 'http'))
   <> (interface IS NOT NULL AND btrim(interface) <> '')


-- @rule: rt_sign
-- @stage: staging
-- Negative rt is legal ONLY on the downstream side of an RPC pair. A
-- negative value on any other paradigm is unexplained by the spec.
SELECT
    coalesce(traceid, '') || '#' || coalesce(rpc_id, '') AS row_key,
    jsonb_build_object('rt', rt, 'rpctype', rpctype) AS detail
FROM stg_callgraph
WHERE rt LIKE '-%'
  AND lower(btrim(coalesce(rpctype, ''))) <> 'rpc'


-- @rule: container_has_microservice
-- @stage: staging
-- Container ids embed their microservice: MS_58845_POD_0 belongs to
-- MS_58845. Where the embedded name disagrees with the declared msname, the
-- two sources contradict each other and entity resolution has to choose.
-- split_part is used rather than a regex: four passes over 13M+ rows.
SELECT
    inst AS row_key,
    jsonb_build_object('msinstanceid', inst, 'declared_ms', ms,
                       'embedded_ms', emb, 'column', col) AS detail
FROM (
    SELECT msinstanceid AS inst, msname AS ms,
           split_part(msinstanceid, '_POD_', 1) AS emb, 'msmetrics' AS col
      FROM stg_msmetrics WHERE msinstanceid LIKE 'MS!_%!_POD!_%' ESCAPE '!'
    UNION ALL
    SELECT msinstanceid, msname,
           split_part(msinstanceid, '_POD_', 1), 'msrtmcr'
      FROM stg_msrtmcr WHERE msinstanceid LIKE 'MS!_%!_POD!_%' ESCAPE '!'
    UNION ALL
    SELECT uminstanceid, um,
           split_part(uminstanceid, '_POD_', 1), 'callgraph.um'
      FROM stg_callgraph WHERE uminstanceid LIKE 'MS!_%!_POD!_%' ESCAPE '!'
    UNION ALL
    SELECT dminstanceid, dm,
           split_part(dminstanceid, '_POD_', 1), 'callgraph.dm'
      FROM stg_callgraph WHERE dminstanceid LIKE 'MS!_%!_POD!_%' ESCAPE '!'
) q
WHERE emb <> ms


-- @rule: single_placement
-- @stage: graph
-- A container occupies one node at a time. Overlapping runs_on intervals
-- mean the placement deriver is wrong, not the data -- hence severity 1.
SELECT
    a.src::text AS row_key,
    jsonb_build_object('container', a.src, 'node_a', a.dst, 'node_b', b.dst,
                       'a_from', a.valid_from, 'a_to', a.valid_to,
                       'b_from', b.valid_from, 'b_to', b.valid_to) AS detail
FROM edges a
JOIN edges b
  ON a.src = b.src
 AND a.rel = b.rel
 AND a.ctid < b.ctid
 AND tstzrange(a.valid_from, a.valid_to, '[)')
  && tstzrange(b.valid_from, b.valid_to, '[)')
WHERE a.rel = (SELECT code FROM relation_registry WHERE name = 'runs_on')


-- @rule: every_ms_has_team
-- @stage: graph
-- Completeness check on the DERIVED ownership layer, not on source data.
SELECT
    n.nkey AS row_key,
    jsonb_build_object('microservice', n.nkey, 'node_id', n.id) AS detail
FROM nodes n
WHERE n.class = (SELECT code FROM class_registry WHERE name = 'Microservice')
  AND NOT EXISTS (
        SELECT 1 FROM edges e
         WHERE e.dst = n.id
           AND e.rel = (SELECT code FROM relation_registry WHERE name = 'owns'))


-- @rule: closure_terminates
-- @stage: graph
-- Guards the recursive traversals. Any microservice whose outward closure
-- is still expanding at the depth cap would make blast-radius queries
-- unbounded, so it is reported before those queries are ever run.
SELECT
    start_ms::text AS row_key,
    jsonb_build_object('microservice', start_ms, 'depth_cap', 12,
                       'frontier_at_cap', n) AS detail
FROM (
    WITH RECURSIVE walk(start_ms, cur, depth) AS (
        SELECT e.src, e.dst, 1
          FROM edges e
         WHERE e.rel = (SELECT code FROM relation_registry WHERE name = 'calls')
        UNION
        SELECT w.start_ms, e.dst, w.depth + 1
          FROM walk w
          JOIN edges e ON e.src = w.cur
         WHERE e.rel = (SELECT code FROM relation_registry WHERE name = 'calls')
           AND w.depth < 12
    )
    SELECT start_ms, count(*) AS n
      FROM walk WHERE depth = 12 GROUP BY start_ms
) q
