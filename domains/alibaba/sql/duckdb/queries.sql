-- The queries that justify building a graph at all (DuckDB dialect).
--
-- Defined as table MACROS, not as loose SELECTs in .sql files, so that the
-- notebook, the FastAPI service, the visualisation and the agent all invoke
-- one identical definition. A query copy-pasted into four consumers becomes
-- four subtly different queries within a month.
--
-- Every one takes an `as_of` timestamp. That is the entire point of the
-- temporal edges: topology at 03:05 is not topology now, and an incident is
-- always investigated after it ended.
--
-- The parameter is named as_of, never `at`: AT is reserved by DuckDB for
-- AT TIME ZONE and a macro parameter called `at` fails to parse.
--
-- All validity tests go through the valid_at() macro, which is plain
-- comparison. That is what lets the Postgres port add a GiST range index to
-- accelerate this exact expression without rewriting a single query.

-- ------------------------------------------------------------ blast radius
-- "NODE_x degraded at time T. What was affected, and how far out?"
--
-- node -> containers resident AT T -> their microservices -> transitively
-- UPSTREAM through callers as they were AT T. Upstream is deliberate: when
-- a node dies, the damage propagates to whoever DEPENDS on what it hosted.
CREATE OR REPLACE MACRO blast_radius(node_key, as_of, cap) AS TABLE (
    WITH RECURSIVE seed AS (
        SELECT io.dst AS ms, count(DISTINCT ro.src) AS containers
        FROM edges ro
        JOIN edges io
          ON io.rel = rel_code('instance_of')
         AND io.src = ro.src
         AND valid_at(io.valid_from, io.valid_to, as_of)
        WHERE ro.rel = rel_code('runs_on')
          AND ro.dst = node_id(class_code('Node'), node_key)
          AND valid_at(ro.valid_from, ro.valid_to, as_of)
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
         AND valid_at(e.valid_from, e.valid_to, as_of)
        WHERE w.depth < cap
    )
    SELECT min(w.depth)                     AS depth,
           n.nkey                           AS microservice,
           n.id                             AS ms_id,
           coalesce(max(s.containers), 0)   AS via_containers
    FROM walk w
    JOIN nodes n ON n.id = w.ms
    LEFT JOIN seed s ON s.ms = w.ms
    GROUP BY n.nkey, n.id
    ORDER BY 1, 2
);

-- -------------------------------------------------------------- time travel
-- One container's residency history. One row per interval, so a migration
-- is visible rather than averaged away.
CREATE OR REPLACE MACRO placement_history(container_key) AS TABLE (
    SELECT n.nkey AS node,
           e.valid_from,
           e.valid_to,
           round(date_diff('second', e.valid_from, e.valid_to) / 60.0, 2)
               AS minutes
    FROM edges e
    JOIN nodes n ON n.id = e.dst
    WHERE e.rel = rel_code('runs_on')
      AND e.src = node_id(class_code('Container'), container_key)
    ORDER BY e.valid_from
);

-- Containers that actually moved between nodes during the slice. The
-- shortlist worth pointing a time slider at.
-- The min_nodes filter sits in an outer WHERE, not in HAVING: DuckDB binds
-- a macro parameter inside HAVING as if it were a column and demands it in
-- the GROUP BY.
CREATE OR REPLACE MACRO migrations(min_nodes) AS TABLE (
    SELECT * FROM (
        SELECT c.nkey                        AS container,
               count(DISTINCT e.dst)         AS distinct_nodes,
               count(*)                      AS intervals,
               min(e.valid_from)             AS first_seen,
               max(coalesce(e.valid_to, e.valid_from)) AS last_seen
        FROM edges e
        JOIN nodes c ON c.id = e.src
        WHERE e.rel = rel_code('runs_on')
        GROUP BY c.nkey
    )
    WHERE distinct_nodes >= min_nodes
    ORDER BY distinct_nodes DESC, intervals DESC
);

-- Topology around one service, as it stood at an instant.
CREATE OR REPLACE MACRO topology_at(ms_key, as_of, depth) AS TABLE (
    WITH RECURSIVE down(id, hop) AS (
        SELECT node_id(class_code('Microservice'), ms_key), 0
        UNION
        SELECT e.dst, d.hop + 1
        FROM down d
        JOIN edges e ON e.src = d.id AND e.rel = rel_code('calls')
                    AND valid_at(e.valid_from, e.valid_to, as_of)
        WHERE d.hop < depth
    ),
    up(id, hop) AS (
        SELECT node_id(class_code('Microservice'), ms_key), 0
        UNION
        SELECT e.src, u.hop + 1
        FROM up u
        JOIN edges e ON e.dst = u.id AND e.rel = rel_code('calls')
                    AND valid_at(e.valid_from, e.valid_to, as_of)
        WHERE u.hop < depth
    )
    SELECT 'downstream' AS direction, d.hop, ns.nkey AS src, nd.nkey AS dst,
           e.weight AS call_count, e.stat_p99 AS rt_p99, e.tag AS rpctype
    FROM down d
    JOIN edges e ON e.src = d.id AND e.rel = rel_code('calls')
                AND valid_at(e.valid_from, e.valid_to, as_of)
    JOIN nodes ns ON ns.id = e.src
    JOIN nodes nd ON nd.id = e.dst
    WHERE d.hop < depth
    UNION ALL
    SELECT 'upstream', u.hop, ns.nkey, nd.nkey,
           e.weight, e.stat_p99, e.tag
    FROM up u
    JOIN edges e ON e.dst = u.id AND e.rel = rel_code('calls')
                AND valid_at(e.valid_from, e.valid_to, as_of)
    JOIN nodes ns ON ns.id = e.src
    JOIN nodes nd ON nd.id = e.dst
    WHERE u.hop < depth
);

-- ------------------------------------------------------------ critical path
-- Within one trace, the chain of spans that actually consumed the latency.
-- Walks the rpc_id tree and accumulates response time along each path.
--
-- Roots are spans whose parent is absent - which includes the genuinely
-- orphaned ones the validator counts. Treating them as roots here is what
-- stops a known data defect from making whole traces invisible.
CREATE OR REPLACE MACRO critical_path(trace_key) AS TABLE (
    -- An RPC is reported TWICE under one rpc_id, once by each side of the
    -- call. Walking both makes the recursion fan out combinatorially - the
    -- same caller->callee hop came back repeatedly with cumulative values
    -- differing by the gap between the two measurements. So collapse to one
    -- row per rpc_id BEFORE walking, keeping the slowest side: that is the
    -- time the caller actually waited, which is what a critical path means.
    -- `sides` is published rather than hidden, so a reader can see which
    -- hops were measured twice and which only once.
    WITH RECURSIVE span AS (
        SELECT rpc_id, parent_rpc_id, um, dm, rpctype, interface, rt, sides
        FROM (
            SELECT rpc_id, parent_rpc_id, um, dm, rpctype, interface, rt,
                   count(*)     OVER (PARTITION BY rpc_id) AS sides,
                   row_number() OVER (PARTITION BY rpc_id
                                      ORDER BY rt DESC NULLS LAST) AS pick
            FROM calls WHERE traceid = trace_key
        ) WHERE pick = 1
    ),
    -- parent_rpc_id is rpc_id with the last segment trimmed, so '0.1.2'
    -- hangs off '0.1' and '0' has no parent at all. rpc_id = '0' IS emitted
    -- by this release, so exempting parent '0' here (as this once did)
    -- seeded every second-level span as a root AND joined it as a child of
    -- '0' - double counting before the fan-out even started. A span is a
    -- root only when its parent is genuinely absent from the trace.
    walk(rpc_id, depth, cumulative) AS (
        SELECT s.rpc_id, 0, greatest(coalesce(s.rt, 0), 0)
        FROM span s
        WHERE s.parent_rpc_id IS NULL
           OR s.parent_rpc_id NOT IN (SELECT rpc_id FROM span)
        UNION ALL
        SELECT s.rpc_id, w.depth + 1,
               w.cumulative + greatest(coalesce(s.rt, 0), 0)
        FROM walk w
        JOIN span s ON s.parent_rpc_id = w.rpc_id
        WHERE w.depth < 40
    )
    SELECT w.depth, w.rpc_id,
           nu.nkey AS caller, nd.nkey AS callee,
           s.rpctype, s.interface, s.rt, s.sides, w.cumulative
    FROM walk w
    JOIN span s ON s.rpc_id = w.rpc_id
    LEFT JOIN nodes nu ON nu.id = s.um
    LEFT JOIN nodes nd ON nd.id = s.dm
    ORDER BY w.cumulative DESC, w.depth
);

-- ------------------------------------------------------------- choke points
-- Which services sit on the most distinct online-service paths. These are
-- the least survivable failures, independent of how busy they look on a
-- dashboard.
CREATE OR REPLACE MACRO choke_points(as_of, top_n, cap) AS TABLE (
    WITH RECURSIVE entry AS (
        SELECT e.src AS svc, e.dst AS ms
        FROM edges e
        WHERE e.rel = rel_code('entry_point')
          AND valid_at(e.valid_from, e.valid_to, as_of)
    ),
    reach(svc, ms, depth) AS (
        SELECT svc, ms, 0 FROM entry
        UNION
        SELECT r.svc, e.dst, r.depth + 1
        FROM reach r
        JOIN edges e ON e.src = r.ms AND e.rel = rel_code('calls')
                    AND valid_at(e.valid_from, e.valid_to, as_of)
        WHERE r.depth < cap
    )
    SELECT n.nkey                 AS microservice,
           count(DISTINCT r.svc)  AS online_services,
           min(r.depth)           AS nearest_hop
    FROM reach r
    JOIN nodes n ON n.id = r.ms
    GROUP BY n.nkey
    ORDER BY online_services DESC, nearest_hop
    LIMIT top_n
);

-- ---------------------------------------------------------------- who pages
-- Reverse traversal to owning teams, deduplicated.
--
-- Team ownership is DERIVED by community detection, never measured, so the
-- result says so in a column. An on-call rota inferred from a call graph is
-- a plausible guess, not a fact, and whoever reads this has to be told
-- which it is.
CREATE OR REPLACE MACRO who_pages(node_key, as_of) AS TABLE (
    SELECT t.nkey AS team,
           'derived: community detection over the call graph' AS provenance,
           count(DISTINCT b.ms_id) AS n_services,
           list(DISTINCT b.microservice) AS services
    FROM blast_radius(node_key, as_of, 12) b
    JOIN edges o ON o.dst = b.ms_id AND o.rel = rel_code('owns')
                AND valid_at(o.valid_from, o.valid_to, as_of)
    JOIN nodes t ON t.id = o.src
    GROUP BY t.nkey
    ORDER BY n_services DESC
);

-- ------------------------------------------------------------------ summary
-- Row counts per class and relation, by ontology name. Used by the
-- verification step and by the notebooks.
