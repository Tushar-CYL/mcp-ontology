-- Executable shapes for the rules declared in ontology.yaml (DuckDB).
--
-- Each shape is a SELECT returning exactly two columns:
--     row_key  VARCHAR - identifies the offending row
--     detail   JSON    - enough context to understand the violation
--
-- The validator wraps each one twice: once in count(*) for the exact number
-- of violations, once with a LIMIT for a stored sample.
--
-- PORTABILITY NOTE
-- The plan assumed one shared shapes.sql for both engines. That turned out
-- to be wrong, and the file is split per dialect. What does not port:
--   * the JSON constructor (json_object vs jsonb_build_object)
--   * regex extraction (regexp_extract vs substring(x from '...'))
--   * interval overlap (plain comparison here vs tstzrange && in Postgres)
--   * row identity in a self-join (no ctid in DuckDB)
-- The rule SET, their ids, severities and meanings are shared; only the
-- expressions differ. That distinction is the useful one.
--
-- These are expected to FIRE. The source is real production telemetry with
-- documented defects, and measuring them is the deliverable.


-- @rule: msname_present
-- @stage: staging
-- Placeholder identities must never become nodes. This release uses
-- several: empty, NaN, "(?)" and the literal UNKNOWN (with matching
-- UNKNOWN_POD_* container ids).
SELECT k AS row_key,
       json_object('column', col, 'value', k, 'src_file', src) AS detail
FROM (
    SELECT um AS k, 'callgraph.um' AS col, src_file AS src
      FROM stg_callgraph WHERE is_placeholder(um)
    UNION ALL
    SELECT dm, 'callgraph.dm', src_file
      FROM stg_callgraph WHERE is_placeholder(dm)
    UNION ALL
    SELECT msname, 'msmetrics.msname', src_file
      FROM stg_msmetrics WHERE is_placeholder(msname)
)


-- @rule: call_has_parent
-- @stage: staging
-- rpc_id is a dotted path: the parent of 0.1.1 is 0.1. A non-root call
-- whose parent is absent from the same trace is an orphan span. This is the
-- inconsistency class ICPE 2024 reported, and this anti-join is the
-- headline measurement of the validation step.
-- An earlier version exempted parent = '0', assuming the root was implicit.
-- It is not: 1,055,701 rows carry rpc_id = '0' (USER -> first service).
-- Only 43.3% of traces have one though, so the rest genuinely begin
-- mid-tree, and the exemption was hiding exactly those. No exemption now.
SELECT c.traceid || '#' || c.rpc_id AS row_key,
       json_object('traceid', c.traceid, 'rpc_id', c.rpc_id,
                   'missing_parent', c.parent) AS detail
FROM (
    SELECT traceid, rpc_id,
           nullif(regexp_extract(rpc_id, '^(.*)\.[^.]*$', 1), '') AS parent
      FROM stg_callgraph
     WHERE rpc_id IS NOT NULL AND traceid IS NOT NULL
) c
WHERE c.parent IS NOT NULL
  AND NOT EXISTS (
        SELECT 1 FROM stg_callgraph p
         WHERE p.traceid = c.traceid AND p.rpc_id = c.parent)


-- @rule: trace_acyclic
-- @stage: staging
-- A dotted-path id scheme cannot encode a structural cycle, so at staging
-- this measures the degenerate case that CAN occur and does: a microservice
-- calling itself. Deeper ancestor cycles are a graph-stage concern.
SELECT traceid || '#' || rpc_id AS row_key,
       json_object('ms', um, 'rpctype', rpctype,
                   'um_pod', uminstanceid, 'dm_pod', dminstanceid) AS detail
FROM stg_callgraph
WHERE um IS NOT NULL AND um = dm


-- @rule: interface_present
-- @stage: staging
-- Asserts interface is populated on EVERY call.
--
-- This replaces an earlier rule that encoded the published spec -
-- "interface iff rpctype in (rpc, http)". Measured, that flagged 6,948,782
-- rows (52% of the slice), which is the signature of a wrong rule rather
-- than a broken dataset: in v2022 mc, db and mq calls all carry an
-- interface. A rule that fires on half the corpus buries every real signal
-- next to it, so it now checks something the data can actually violate.
SELECT coalesce(traceid, '') || '#' || coalesce(rpc_id, '') AS row_key,
       json_object('rpctype', rpctype, 'interface', interface) AS detail
FROM stg_callgraph
WHERE interface IS NULL OR trim(interface) = ''


-- @rule: rt_sign
-- @stage: staging
-- Negative rt is legal ONLY on the downstream side of an RPC pair. A
-- negative value under any other paradigm is unexplained by the spec.
SELECT coalesce(traceid, '') || '#' || coalesce(rpc_id, '') AS row_key,
       json_object('rt', rt, 'rpctype', rpctype) AS detail
FROM stg_callgraph
WHERE rt LIKE '-%'
  AND lower(coalesce(trim(rpctype), '')) <> 'rpc'


-- @rule: container_has_microservice
-- @stage: staging
-- Container ids embed their microservice: MS_58845_POD_0 belongs to
-- MS_58845. Where the embedded name disagrees with the declared msname the
-- two sources contradict each other and entity resolution must choose.
-- split_part rather than a regex: four passes over 13M+ rows.
SELECT inst AS row_key,
       json_object('msinstanceid', inst, 'declared_ms', ms,
                   'embedded_ms', emb, 'column', col) AS detail
FROM (
    SELECT msinstanceid AS inst, msname AS ms,
           split_part(msinstanceid, '_POD_', 1) AS emb, 'msmetrics' AS col
      FROM stg_msmetrics WHERE msinstanceid LIKE 'MS\_%\_POD\_%' ESCAPE '\'
    UNION ALL
    SELECT msinstanceid, msname,
           split_part(msinstanceid, '_POD_', 1), 'msrtmcr'
      FROM stg_msrtmcr WHERE msinstanceid LIKE 'MS\_%\_POD\_%' ESCAPE '\'
    UNION ALL
    SELECT uminstanceid, um,
           split_part(uminstanceid, '_POD_', 1), 'callgraph.um'
      FROM stg_callgraph WHERE uminstanceid LIKE 'MS\_%\_POD\_%' ESCAPE '\'
    UNION ALL
    SELECT dminstanceid, dm,
           split_part(dminstanceid, '_POD_', 1), 'callgraph.dm'
      FROM stg_callgraph WHERE dminstanceid LIKE 'MS\_%\_POD\_%' ESCAPE '\'
)
WHERE emb <> ms


-- @rule: placement_conflict
-- @stage: staging
-- The SOURCE contradicting itself: one container reported on more than one
-- node at the same instant. A container cannot be in two places, so these
-- are duplicate identities in the release, not migrations - and feeding
-- them into the interval deriver would produce a container apparently
-- resident on two machines at once, corrupting every traversal through it.
-- build.sql repairs this deterministically (lowest nodeid wins); this
-- counts what was repaired.
SELECT msinstanceid || '@' || CAST(ts AS VARCHAR) AS row_key,
       json_object('container', msinstanceid, 'ts', ts,
                   'nodes', string_agg(DISTINCT nodeid, ',')) AS detail
FROM stg_msmetrics
WHERE NOT is_placeholder(msinstanceid) AND NOT is_placeholder(nodeid)
GROUP BY msinstanceid, ts
HAVING count(DISTINCT nodeid) > 1


-- @rule: single_placement
-- @stage: graph
-- OUR derivation being wrong, as opposed to the source being wrong above.
-- After repair, no container may have two runs_on intervals covering the
-- same instant. If this fires, gaps-and-islands is broken - hence
-- severity 1, which stops the build.
SELECT CAST(a.src AS VARCHAR) AS row_key,
       json_object('container', a.src, 'node_a', a.dst, 'node_b', b.dst,
                   'a_from', CAST(a.valid_from AS VARCHAR),
                   'a_to',   CAST(a.valid_to   AS VARCHAR),
                   'b_from', CAST(b.valid_from AS VARCHAR),
                   'b_to',   CAST(b.valid_to   AS VARCHAR)) AS detail
FROM edges a
JOIN edges b
  ON a.src = b.src
 AND a.rel = b.rel
 AND (a.valid_from, a.dst) < (b.valid_from, b.dst)
 AND a.valid_from < coalesce(b.valid_to, TIMESTAMP '9999-12-31')
 AND b.valid_from < coalesce(a.valid_to, TIMESTAMP '9999-12-31')
WHERE a.rel = rel_code('runs_on')


-- @rule: every_ms_has_team
-- @stage: graph
-- Completeness check on the DERIVED ownership layer, not on source data.
SELECT n.nkey AS row_key,
       json_object('microservice', n.nkey, 'node_id', n.id) AS detail
FROM nodes n
WHERE n.class = class_code('Microservice')
  AND NOT EXISTS (
        SELECT 1 FROM edges e
         WHERE e.dst = n.id AND e.rel = rel_code('owns'))


-- @rule: closure_truncated_at_cap
-- @stage: graph
-- Microservices whose outward closure is still expanding at the depth cap.
-- Measured at 5,897 of 36,888 (16%) - a dense cyclic call graph, not a bug.
-- The recursion is bounded by the cap either way; what matters is that
-- blast_radius is a LOWER BOUND for these services, and the context layer
-- has to say so.
SELECT CAST(start_ms AS VARCHAR) AS row_key,
       json_object('microservice', start_ms, 'depth_cap', 12,
                   'frontier_at_cap', n) AS detail
FROM (
    WITH RECURSIVE walk(start_ms, cur, depth) AS (
        SELECT e.src, e.dst, 1 FROM edges e WHERE e.rel = rel_code('calls')
        UNION
        SELECT w.start_ms, e.dst, w.depth + 1
          FROM walk w
          JOIN edges e ON e.src = w.cur AND e.rel = rel_code('calls')
         WHERE w.depth < 12
    )
    SELECT start_ms, count(*) AS n
      FROM walk WHERE depth = 12 GROUP BY start_ms
)


-- @rule: edge_endpoints_typed
-- @stage: graph
-- The registry is only binding if something enforces it. This compares
-- every edge against the domain and range declared in ontology.yaml, and
-- also catches dangling ids - edges whose endpoint was never created as a
-- node. Both classes of defect are invisible to queries: a traversal
-- through a dangling edge just returns fewer rows and looks healthy.
SELECT CAST(e.src AS VARCHAR) || ' -' || rr.name || '-> '
       || CAST(e.dst AS VARCHAR) AS row_key,
       json_object(
           'relation',  rr.name,
           'src_class', coalesce(cs.name, 'MISSING NODE'),
           'dst_class', coalesce(cd.name, 'MISSING NODE'),
           'expected_domain', array_to_string(rr.domain, '|'),
           'expected_range',  array_to_string(rr.range,  '|')) AS detail
FROM edges e
JOIN relation_registry rr ON rr.code = e.rel
LEFT JOIN nodes ns        ON ns.id = e.src
LEFT JOIN class_registry cs ON cs.code = ns.class
LEFT JOIN nodes nd        ON nd.id = e.dst
LEFT JOIN class_registry cd ON cd.code = nd.class
WHERE ns.id IS NULL
   OR nd.id IS NULL
   OR NOT list_contains(rr.domain, cs.name)
   OR NOT list_contains(rr.range,  cd.name)


-- @rule: rt_parseable
-- @stage: staging
-- rt arrives as text and is not always numeric. Every failing value in
-- this slice is the literal string "None" - a Python None that reached the
-- CSV writer. Counted here and stored as NULL by build.sql, never as 0.
SELECT coalesce(traceid, '') || '#' || coalesce(rpc_id, '') AS row_key,
       json_object('rt_raw', rt, 'rpctype', rpctype) AS detail
FROM stg_callgraph
WHERE rt IS NOT NULL AND TRY_CAST(rt AS DOUBLE) IS NULL
