-- Typed time-series fact tables behind the semantic layer.
--
-- These are NOT part of the graph. The graph answers "what is connected to
-- what"; these answer "what was this thing doing at 03:05". Keeping them
-- apart stops millions of per-minute samples from bloating the topology
-- indexes that the traversal queries depend on.
--
-- Two storage choices that matter on a 3.8 GB VM:
--   * `real` not `double precision` for utilisation. These are normalised
--     ratios; 4 bytes is ample and halves the table.
--   * BRIN not btree on ts. The data is appended in rough time order, so a
--     BRIN index covers 14M rows in a few dozen KB where a btree would cost
--     hundreds of MB and evict the pages we actually want cached.

\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS node_metrics (
    ts                 timestamptz NOT NULL,
    node               bigint      NOT NULL,
    cpu_utilization    real,
    memory_utilization real
);

CREATE TABLE IF NOT EXISTS ms_metrics (
    ts                 timestamptz NOT NULL,
    ms                 bigint,
    container          bigint,
    node               bigint,
    cpu_utilization    real,
    memory_utilization real
);

CREATE TABLE IF NOT EXISTS ms_rt_mcr (
    ts              timestamptz NOT NULL,
    ms              bigint,
    container       bigint,
    node            bigint,
    providerrpc_rt  real, providerrpc_mcr  real,
    consumerrpc_rt  real, consumerrpc_mcr  real,
    writemc_rt      real, writemc_mcr      real,
    readmc_rt       real, readmc_mcr       real,
    writedb_rt      real, writedb_mcr      real,
    readdb_rt       real, readdb_mcr       real,
    consumermq_rt   real, consumermq_mcr   real,
    providermq_rt   real, providermq_mcr   real,
    http_rt         real, http_mcr         real
);

-- A tolerant numeric cast: the staging columns are text because the source
-- is not uniformly numeric. Anything unparseable becomes NULL here and is
-- counted by the validator rather than aborting the build.
CREATE OR REPLACE FUNCTION to_real(s text) RETURNS real
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN s ~ '^\s*-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?\s*$'
        THEN btrim(s)::real
    END
$$;

TRUNCATE node_metrics, ms_metrics, ms_rt_mcr;

INSERT INTO node_metrics (ts, node, cpu_utilization, memory_utilization)
SELECT tms(ts), node_id(2::smallint, nodeid),
       to_real(cpu_utilization), to_real(memory_utilization)
FROM stg_nodemetrics
WHERE ts IS NOT NULL AND NOT is_placeholder(nodeid);

INSERT INTO ms_metrics (ts, ms, container, node,
                        cpu_utilization, memory_utilization)
SELECT tms(ts),
       CASE WHEN is_placeholder(msname) THEN NULL
            ELSE node_id(4::smallint, msname) END,
       CASE WHEN is_placeholder(msinstanceid) THEN NULL
            ELSE node_id(3::smallint, msinstanceid) END,
       CASE WHEN is_placeholder(nodeid) THEN NULL
            ELSE node_id(2::smallint, nodeid) END,
       to_real(cpu_utilization), to_real(memory_utilization)
FROM stg_msmetrics
WHERE ts IS NOT NULL;

INSERT INTO ms_rt_mcr
SELECT tms(ts),
       CASE WHEN is_placeholder(msname) THEN NULL
            ELSE node_id(4::smallint, msname) END,
       CASE WHEN is_placeholder(msinstanceid) THEN NULL
            ELSE node_id(3::smallint, msinstanceid) END,
       CASE WHEN is_placeholder(nodeid) THEN NULL
            ELSE node_id(2::smallint, nodeid) END,
       to_real(providerrpc_rt), to_real(providerrpc_mcr),
       to_real(consumerrpc_rt), to_real(consumerrpc_mcr),
       to_real(writemc_rt),     to_real(writemc_mcr),
       to_real(readmc_rt),      to_real(readmc_mcr),
       to_real(writedb_rt),     to_real(writedb_mcr),
       to_real(readdb_rt),      to_real(readdb_mcr),
       to_real(consumermq_rt),  to_real(consumermq_mcr),
       to_real(providermq_rt),  to_real(providermq_mcr),
       to_real(http_rt),        to_real(http_mcr)
FROM stg_msrtmcr
WHERE ts IS NOT NULL;

SET maintenance_work_mem = '512MB';

CREATE INDEX IF NOT EXISTS node_metrics_ts_brin ON node_metrics
    USING brin (ts) WITH (pages_per_range = 64);
CREATE INDEX IF NOT EXISTS node_metrics_node ON node_metrics (node, ts);

CREATE INDEX IF NOT EXISTS ms_metrics_ts_brin ON ms_metrics
    USING brin (ts) WITH (pages_per_range = 64);
CREATE INDEX IF NOT EXISTS ms_metrics_ms ON ms_metrics (ms, ts);
CREATE INDEX IF NOT EXISTS ms_metrics_node ON ms_metrics (node, ts);

CREATE INDEX IF NOT EXISTS ms_rt_mcr_ts_brin ON ms_rt_mcr
    USING brin (ts) WITH (pages_per_range = 64);
CREATE INDEX IF NOT EXISTS ms_rt_mcr_ms ON ms_rt_mcr (ms, ts);

RESET maintenance_work_mem;

ANALYZE node_metrics;
ANALYZE ms_metrics;
ANALYZE ms_rt_mcr;
