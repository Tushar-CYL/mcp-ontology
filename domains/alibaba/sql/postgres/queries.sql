-- The queries that justify building a graph at all.
--
-- Defined as FUNCTIONS, not as .sql files holding loose SELECTs, so that
-- psql, the notebooks, the FastAPI service, the visualisation and the agent
-- all invoke one identical definition. A query copy-pasted into four
-- consumers becomes four subtly different queries within a month.
--
-- Every one of these takes an `at` timestamp. That is the entire point of
-- the temporal edges: topology at 03:05 is not topology now, and an
-- incident is always investigated after it ended.

\set ON_ERROR_STOP on

-- ---------------------------------------------------------- blast radius
-- "NODE_x degraded at time T. What was affected, and how far out?"
--
-- Walks: node -> containers resident AT T -> their microservices ->
-- transitively upstream through callers AS THEY WERE AT T.
-- Direction is deliberately upstream: when a node dies, the damage
-- propagates to whoever DEPENDS on the services it was hosting.
CREATE OR REPLACE FUNCTION blast_radius(
    node_key   text,
    at         timestamptz,
    depth_cap  int DEFAULT 12)
RETURNS TABLE (
    depth         int,
    microservice  text,
    ms_id         bigint,
    via_containers bigint)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE seed AS (
        SELECT io.dst AS ms, count(DISTINCT ro.src) AS containers
        FROM edges ro
        JOIN edges io
          ON io.rel = rel_code('instance_of')
         AND io.src = ro.src
         AND tstzrange(io.valid_from, io.valid_to, '[)') @> at
        WHERE ro.rel = rel_code('runs_on')
          AND ro.dst = node_id(class_code('Node'), node_key)
          AND tstzrange(ro.valid_from, ro.valid_to, '[)') @> at
        GROUP BY io.dst
    ),
    walk(ms, depth) AS (
        SELECT ms, 0 FROM seed
        UNION
        SELECT e.src, w.depth + 1
        FROM walk w
        JOIN edges e
          ON e.dst = w.ms
         AND e.rel = rel_code('calls')
         AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
        WHERE w.depth < depth_cap
    )
    SELECT min(w.depth)::int AS depth,
           n.nkey            AS microservice,
           n.id              AS ms_id,
           coalesce(max(s.containers), 0)::bigint AS via_containers
    FROM walk w
    JOIN nodes n ON n.id = w.ms
    LEFT JOIN seed s ON s.ms = w.ms
    GROUP BY n.nkey, n.id
    ORDER BY 1, 2
$$;

-- ------------------------------------------------------------ time travel
-- The same container, asked about at two instants. Returns one row per
-- residency interval so a migration is visible rather than averaged away.
CREATE OR REPLACE FUNCTION placement_history(container_key text)
RETURNS TABLE (
    node        text,
    valid_from  timestamptz,
    valid_to    timestamptz,
    minutes     numeric)
LANGUAGE sql STABLE AS $$
    SELECT n.nkey, e.valid_from, e.valid_to,
           round(EXTRACT(epoch FROM e.valid_to - e.valid_from)::numeric / 60, 2)
    FROM edges e
    JOIN nodes n ON n.id = e.dst
    WHERE e.rel = rel_code('runs_on')
      AND e.src = node_id(class_code('Container'), container_key)
    ORDER BY e.valid_from
$$;

-- Topology around one service, as it stood at an instant.
CREATE OR REPLACE FUNCTION topology_at(
    ms_key  text,
    at      timestamptz,
    depth   int DEFAULT 2)
RETURNS TABLE (
    direction  text,
    hop        int,
    src        text,
    dst        text,
    call_count bigint,
    rt_p99     numeric)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE down(id, hop) AS (
        SELECT node_id(class_code('Microservice'), ms_key), 0
        UNION
        SELECT e.dst, d.hop + 1
        FROM down d
        JOIN edges e ON e.src = d.id AND e.rel = rel_code('calls')
                    AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
        WHERE d.hop < depth
    ),
    up(id, hop) AS (
        SELECT node_id(class_code('Microservice'), ms_key), 0
        UNION
        SELECT e.src, u.hop + 1
        FROM up u
        JOIN edges e ON e.dst = u.id AND e.rel = rel_code('calls')
                    AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
        WHERE u.hop < depth
    )
    SELECT 'downstream', d.hop, ns.nkey, nd.nkey,
           (e.props->>'call_count')::bigint,
           (e.props->>'rt_p99')::numeric
    FROM down d
    JOIN edges e ON e.src = d.id AND e.rel = rel_code('calls')
                AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
    JOIN nodes ns ON ns.id = e.src
    JOIN nodes nd ON nd.id = e.dst
    WHERE d.hop < depth
    UNION ALL
    SELECT 'upstream', u.hop, ns.nkey, nd.nkey,
           (e.props->>'call_count')::bigint,
           (e.props->>'rt_p99')::numeric
    FROM up u
    JOIN edges e ON e.dst = u.id AND e.rel = rel_code('calls')
                AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
    JOIN nodes ns ON ns.id = e.src
    JOIN nodes nd ON nd.id = e.dst
    WHERE u.hop < depth
$$;

-- ---------------------------------------------------------- critical path
-- Within one trace, the chain of spans that actually consumed the latency.
-- Walks the rpc_id tree and accumulates response time along each path.
CREATE OR REPLACE FUNCTION critical_path(trace_key text)
RETURNS TABLE (
    depth       int,
    rpc_id      text,
    caller      text,
    callee      text,
    rpctype     text,
    interface   text,
    rt          double precision,
    sides       bigint,
    cumulative  double precision)
LANGUAGE sql STABLE AS $$
    -- An RPC is reported TWICE under one rpc_id, once by each side of the
    -- call. Walking both makes the recursion fan out combinatorially - the
    -- same caller->callee hop came back repeatedly with cumulative values
    -- differing by the gap between the two measurements. So collapse to one
    -- row per rpc_id BEFORE walking, keeping the slowest side: that is the
    -- time the caller actually waited, which is what a critical path means.
    -- `sides` is published rather than hidden, so a reader can see which
    -- hops were measured twice and which only once.
    WITH RECURSIVE span AS (
        SELECT q.rpc_id, q.parent_rpc_id, q.um, q.dm, q.rpctype,
               q.interface, q.rt, q.sides
        FROM (
            SELECT c.rpc_id, c.parent_rpc_id, c.um, c.dm, c.rpctype,
                   c.interface, c.rt,
                   count(*)     OVER (PARTITION BY c.rpc_id) AS sides,
                   row_number() OVER (PARTITION BY c.rpc_id
                                      ORDER BY c.rt DESC NULLS LAST) AS pick
            FROM calls c
            WHERE c.traceid = trace_key
        ) q WHERE q.pick = 1
    ),
    -- parent_rpc_id is rpc_id with the last segment trimmed, so '0.1.2'
    -- hangs off '0.1' and '0' has no parent at all. rpc_id = '0' IS emitted
    -- by this release, so exempting parent '0' here (as this once did)
    -- seeded every second-level span as a root AND joined it as a child of
    -- '0' - double counting before the fan-out even started. A span is a
    -- root only when its parent is genuinely absent from the trace.
    walk(rpc_id, parent_rpc_id, depth, cumulative) AS (
        SELECT s.rpc_id, s.parent_rpc_id, 0,
               GREATEST(coalesce(s.rt, 0), 0)
        FROM span s
        WHERE s.parent_rpc_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM span p WHERE p.rpc_id = s.parent_rpc_id)
        UNION ALL
        SELECT s.rpc_id, s.parent_rpc_id, w.depth + 1,
               w.cumulative + GREATEST(coalesce(s.rt, 0), 0)
        FROM walk w
        JOIN span s ON s.parent_rpc_id = w.rpc_id
        WHERE w.depth < 40
    )
    SELECT w.depth, w.rpc_id,
           nu.nkey, nd.nkey, s.rpctype, s.interface, s.rt, s.sides, w.cumulative
    FROM walk w
    JOIN span s  ON s.rpc_id = w.rpc_id
    LEFT JOIN nodes nu ON nu.id = s.um
    LEFT JOIN nodes nd ON nd.id = s.dm
    ORDER BY w.cumulative DESC, w.depth
$$;

-- ------------------------------------------------------------ choke point
-- Which services sit on the most distinct online-service paths. These are
-- the ones whose failure is least survivable, independent of how busy
-- they look on a dashboard.
CREATE OR REPLACE FUNCTION choke_points(
    at        timestamptz,
    top_n     int DEFAULT 25,
    depth_cap int DEFAULT 6)
RETURNS TABLE (
    microservice   text,
    online_services bigint,
    fan_in         bigint,
    fan_out        bigint)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE entry AS (
        SELECT e.src AS svc, e.dst AS ms
        FROM edges e
        WHERE e.rel = rel_code('entry_point')
          AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
    ),
    reach(svc, ms, depth) AS (
        SELECT svc, ms, 0 FROM entry
        UNION
        SELECT r.svc, e.dst, r.depth + 1
        FROM reach r
        JOIN edges e ON e.src = r.ms AND e.rel = rel_code('calls')
                    AND tstzrange(e.valid_from, e.valid_to, '[)') @> at
        WHERE r.depth < depth_cap
    )
    SELECT n.nkey,
           count(DISTINCT r.svc) AS online_services,
           (SELECT count(DISTINCT e.src) FROM edges e
             WHERE e.dst = n.id AND e.rel = rel_code('calls')
               AND tstzrange(e.valid_from, e.valid_to, '[)') @> at),
           (SELECT count(DISTINCT e.dst) FROM edges e
             WHERE e.src = n.id AND e.rel = rel_code('calls')
               AND tstzrange(e.valid_from, e.valid_to, '[)') @> at)
    FROM reach r
    JOIN nodes n ON n.id = r.ms
    GROUP BY n.nkey, n.id
    ORDER BY online_services DESC, 3 DESC
    LIMIT top_n
$$;

-- -------------------------------------------------------------- who pages
-- Reverse traversal to owning teams, deduplicated.
--
-- Team ownership is DERIVED by community detection, never measured, so the
-- result carries that provenance to the caller. An on-call rota inferred
-- from a call graph is a plausible guess, not a fact, and whoever reads
-- this output has to be told which it is.
CREATE OR REPLACE FUNCTION who_pages(node_key text, at timestamptz)
RETURNS TABLE (
    team        text,
    provenance  text,
    services    text[],
    n_services  bigint)
LANGUAGE sql STABLE AS $$
    SELECT t.nkey,
           'derived: community detection over the call graph',
           array_agg(DISTINCT b.microservice ORDER BY b.microservice),
           count(DISTINCT b.ms_id)
    FROM blast_radius(node_key, at) b
    JOIN edges o ON o.dst = b.ms_id AND o.rel = rel_code('owns')
                AND tstzrange(o.valid_from, o.valid_to, '[)') @> at
    JOIN nodes t ON t.id = o.src
    GROUP BY t.nkey
    ORDER BY n_services DESC
$$;
