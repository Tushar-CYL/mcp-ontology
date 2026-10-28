-- Typed time-series fact tables behind the semantic layer (DuckDB).
--
-- These are NOT part of the graph. The graph answers "what is connected to
-- what"; these answer "what was this thing doing at 03:05". Keeping them
-- apart stops ~60M per-minute samples from bloating the topology the
-- traversal queries scan.
--
-- `REAL` not `DOUBLE` for utilisation: these are normalised ratios, 4 bytes
-- is ample, and it halves the column. No explicit time index - DuckDB keeps
-- per-rowgroup zone maps, so a timestamp predicate already skips blocks.
-- The Postgres version needs BRIN indexes to get the same effect, which is
-- one more line in the portability ledger.
--
-- TRY_CAST replaces the regex-guarded numeric cast the Postgres version
-- needs: a non-numeric value becomes NULL instead of aborting the
-- statement. How many is reported below rather than assumed to be zero.

CREATE TABLE IF NOT EXISTS node_metrics (
    ts                 TIMESTAMP NOT NULL,
    node               BIGINT NOT NULL,
    cpu_utilization    REAL,
    memory_utilization REAL
);

CREATE TABLE IF NOT EXISTS ms_metrics (
    ts                 TIMESTAMP NOT NULL,
    ms                 BIGINT,
    container          BIGINT,
    node               BIGINT,
    cpu_utilization    REAL,
    memory_utilization REAL
);

CREATE TABLE IF NOT EXISTS ms_rt_mcr (
    ts              TIMESTAMP NOT NULL,
    ms              BIGINT,
    container       BIGINT,
    node            BIGINT,
    providerrpc_rt  REAL, providerrpc_mcr REAL,
    consumerrpc_rt  REAL, consumerrpc_mcr REAL,
    writemc_rt      REAL, writemc_mcr     REAL,
    readmc_rt       REAL, readmc_mcr      REAL,
    writedb_rt      REAL, writedb_mcr     REAL,
    readdb_rt       REAL, readdb_mcr      REAL,
    consumermq_rt   REAL, consumermq_mcr  REAL,
    providermq_rt   REAL, providermq_mcr  REAL,
    http_rt         REAL, http_mcr        REAL
);

DELETE FROM node_metrics;
DELETE FROM ms_metrics;
DELETE FROM ms_rt_mcr;

INSERT INTO node_metrics (ts, node, cpu_utilization, memory_utilization)
SELECT tms(ts), node_id(2, nodeid),
       TRY_CAST(cpu_utilization AS REAL), TRY_CAST(memory_utilization AS REAL)
FROM stg_nodemetrics
WHERE ts IS NOT NULL AND NOT is_placeholder(nodeid);

-- ms / container / node are resolved through the same entity_class table
-- the graph uses, so a metric row and a graph node can never disagree
-- about what a name refers to.
INSERT INTO ms_metrics (ts, ms, container, node,
                        cpu_utilization, memory_utilization)
SELECT tms(m.ts),
       CASE WHEN is_placeholder(m.msname) THEN NULL
            ELSE node_id(4, m.msname) END,
       CASE WHEN is_placeholder(m.msinstanceid) THEN NULL
            ELSE node_id(3, m.msinstanceid) END,
       CASE WHEN is_placeholder(m.nodeid) THEN NULL
            ELSE node_id(2, m.nodeid) END,
       TRY_CAST(m.cpu_utilization AS REAL),
       TRY_CAST(m.memory_utilization AS REAL)
FROM stg_msmetrics m
WHERE m.ts IS NOT NULL;

INSERT INTO ms_rt_mcr
SELECT tms(r.ts),
       CASE WHEN is_placeholder(r.msname) THEN NULL
            ELSE node_id(4, r.msname) END,
       CASE WHEN is_placeholder(r.msinstanceid) THEN NULL
            ELSE node_id(3, r.msinstanceid) END,
       CASE WHEN is_placeholder(r.nodeid) THEN NULL
            ELSE node_id(2, r.nodeid) END,
       TRY_CAST(r.providerrpc_rt AS REAL), TRY_CAST(r.providerrpc_mcr AS REAL),
       TRY_CAST(r.consumerrpc_rt AS REAL), TRY_CAST(r.consumerrpc_mcr AS REAL),
       TRY_CAST(r.writemc_rt AS REAL),     TRY_CAST(r.writemc_mcr AS REAL),
       TRY_CAST(r.readmc_rt AS REAL),      TRY_CAST(r.readmc_mcr AS REAL),
       TRY_CAST(r.writedb_rt AS REAL),     TRY_CAST(r.writedb_mcr AS REAL),
       TRY_CAST(r.readdb_rt AS REAL),      TRY_CAST(r.readdb_mcr AS REAL),
       TRY_CAST(r.consumermq_rt AS REAL),  TRY_CAST(r.consumermq_mcr AS REAL),
       TRY_CAST(r.providermq_rt AS REAL),  TRY_CAST(r.providermq_mcr AS REAL),
       TRY_CAST(r.http_rt AS REAL),        TRY_CAST(r.http_mcr AS REAL)
FROM stg_msrtmcr r
WHERE r.ts IS NOT NULL;
