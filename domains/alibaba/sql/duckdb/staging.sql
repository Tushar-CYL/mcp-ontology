-- Alibaba domain: settings and tables the shared core must not carry.
-- `calls` has traceid and rpc_id in it, and tms() assumes a trace epoch -
-- both are facts about THIS dataset, not about knowledge graphs, so they
-- live here. Moving them out is what keeps sql/duckdb/core.sql honest.

INSERT INTO meta(key, value)
SELECT * FROM (VALUES
    ('trace_epoch',          '2022-01-01 00:00:00'),
    ('dataset',              'alibaba/cluster-trace-microservices-v2022'),
    ('calls_window_seconds', '60')
) v(k, x)
WHERE k NOT IN (SELECT key FROM meta);

-- Trace milliseconds -> absolute timestamp.
CREATE OR REPLACE MACRO tms(ms) AS
    TIMESTAMP '2022-01-01 00:00:00' + (ms * INTERVAL 1 MILLISECOND);

-- Raw span rows: the volume driver, ~13.3M per 3-minute slice.
CREATE TABLE IF NOT EXISTS calls (
    ts            TIMESTAMP NOT NULL,
    traceid       VARCHAR NOT NULL,
    service       VARCHAR,
    rpc_id        VARCHAR NOT NULL,
    parent_rpc_id VARCHAR,              -- rpc_id with the last segment trimmed
    um            BIGINT,               -- Microservice node id, upstream
    dm            BIGINT,               -- Microservice or Datastore, downstream
    um_container  BIGINT,
    dm_container  BIGINT,
    rpctype       VARCHAR,
    interface     VARCHAR,
    rt            DOUBLE
);

-- ------------------------------------------------------------------ staging
-- Deliberately permissive: VARCHAR columns, no constraints. Staging must
-- hold the data AS IT IS, including the NaN / (?) / UNKNOWN placeholders and
-- the documented topological inconsistencies, so the validator can measure
-- them. Cleaning before validating would hide exactly what this project
-- exists to show.
--
-- Column order is the ACTUAL CSV header order, which differs from the
-- published README: rpctype sits before um, not after interface.
CREATE TABLE IF NOT EXISTS stg_callgraph (
    ts            BIGINT,
    traceid       VARCHAR,
    service       VARCHAR,
    rpc_id        VARCHAR,
    rpctype       VARCHAR,
    um            VARCHAR,
    uminstanceid  VARCHAR,
    interface     VARCHAR,
    dm            VARCHAR,
    dminstanceid  VARCHAR,
    rt            VARCHAR,
    src_file      VARCHAR
);

CREATE TABLE IF NOT EXISTS stg_msmetrics (
    ts                 BIGINT,
    msname             VARCHAR,
    msinstanceid       VARCHAR,
    nodeid             VARCHAR,
    cpu_utilization    VARCHAR,
    memory_utilization VARCHAR,
    src_file           VARCHAR
);

CREATE TABLE IF NOT EXISTS stg_nodemetrics (
    ts                 BIGINT,
    nodeid             VARCHAR,
    cpu_utilization    VARCHAR,
    memory_utilization VARCHAR,
    src_file           VARCHAR
);

-- v2022 ships MSRTMCR WIDE (22 columns), not the long metric/value shape
-- the 2021 documentation describes. One row per container per minute.
CREATE TABLE IF NOT EXISTS stg_msrtmcr (
    ts              BIGINT,
    msname          VARCHAR,
    msinstanceid    VARCHAR,
    nodeid          VARCHAR,
    providerrpc_rt  VARCHAR, providerrpc_mcr VARCHAR,
    consumerrpc_rt  VARCHAR, consumerrpc_mcr VARCHAR,
    writemc_rt      VARCHAR, writemc_mcr     VARCHAR,
    readmc_rt       VARCHAR, readmc_mcr      VARCHAR,
    writedb_rt      VARCHAR, writedb_mcr     VARCHAR,
    readdb_rt       VARCHAR, readdb_mcr      VARCHAR,
    consumermq_rt   VARCHAR, consumermq_mcr  VARCHAR,
    providermq_rt   VARCHAR, providermq_mcr  VARCHAR,
    http_mcr        VARCHAR, http_rt         VARCHAR,
    src_file        VARCHAR
);

