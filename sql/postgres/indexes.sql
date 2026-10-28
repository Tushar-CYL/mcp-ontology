-- Indexes, built AFTER the bulk load.
--
-- On a 3.8 GB VM this ordering is not a style preference: building these
-- during ingest would thrash, and maintenance_work_mem is raised per
-- statement and dropped again rather than left high globally.
--
-- The GiST index is the load-bearing one. Edge validity is an interval, so
-- "what was connected at 03:05" is a range-containment question. A btree on
-- valid_from can only bound one end of it and still scans everything older.

\set ON_ERROR_STOP on

SET maintenance_work_mem = '512MB';

-- --------------------------------------------------------------- nodes
CREATE INDEX IF NOT EXISTS nodes_class_idx ON nodes (class);
CREATE INDEX IF NOT EXISTS nodes_nkey_trgm ON nodes
    USING gin (nkey gin_trgm_ops);

-- --------------------------------------------------------------- edges
-- Forward traversal: "what does X call / where does X run".
CREATE INDEX IF NOT EXISTS edges_src_rel ON edges (src, rel)
    INCLUDE (dst, valid_from, valid_to);

-- Reverse traversal: "who calls X", "which containers are on this node",
-- "who owns X". The blast-radius query walks this direction.
CREATE INDEX IF NOT EXISTS edges_dst_rel ON edges (dst, rel)
    INCLUDE (src, valid_from, valid_to);

-- Point-in-time containment. btree_gist lets the smallint rel share one
-- index with the range, so a time-sliced traversal of a single relation
-- does not have to filter a whole relation's worth of candidates.
CREATE INDEX IF NOT EXISTS edges_valid_gist ON edges
    USING gist (rel, tstzrange(valid_from, valid_to, '[)'));

-- --------------------------------------------------------------- calls
-- Created on the partitioned parent, so Postgres propagates them to every
-- existing and future partition.
CREATE INDEX IF NOT EXISTS calls_trace_rpc ON calls (traceid, rpc_id);
CREATE INDEX IF NOT EXISTS calls_trace_parent ON calls (traceid, parent_rpc_id);
CREATE INDEX IF NOT EXISTS calls_um ON calls (um) WHERE um IS NOT NULL;
CREATE INDEX IF NOT EXISTS calls_dm ON calls (dm) WHERE dm IS NOT NULL;
CREATE INDEX IF NOT EXISTS calls_service ON calls (service) WHERE service IS NOT NULL;

RESET maintenance_work_mem;

ANALYZE nodes;
ANALYZE edges;
ANALYZE calls;
