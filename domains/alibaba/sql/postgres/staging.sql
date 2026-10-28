-- ---------------------------------------------------------------- staging
-- Deliberately permissive: text columns, no constraints, no foreign keys.
-- Staging must be able to hold the data AS IT IS, including the NaN and
-- "(?)" placeholders and the known topological inconsistencies, so the
-- validator can measure them. Cleaning before validating would hide exactly
-- what this project is trying to show.
-- Column order is the ACTUAL CSV header order, which differs from the
-- published README (rpctype sits before um, not after interface). The parser
-- maps by header name regardless, but keeping the table in file order makes
-- COPY a straight pass-through with no reshuffling per row.
--   timestamp,traceid,service,rpc_id,rpctype,um,uminstanceid,interface,dm,dminstanceid,rt
CREATE UNLOGGED TABLE IF NOT EXISTS stg_callgraph (
    ts            bigint,
    traceid       text,
    service       text,
    rpc_id        text,
    rpctype       text,
    um            text,
    uminstanceid  text,
    interface     text,
    dm            text,
    dminstanceid  text,
    rt            text,
    src_file      text
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_msmetrics (
    ts                 bigint,
    msname             text,
    msinstanceid       text,
    nodeid             text,
    cpu_utilization    text,
    memory_utilization text,
    src_file           text
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_nodemetrics (
    ts                 bigint,
    nodeid             text,
    cpu_utilization    text,
    memory_utilization text,
    src_file           text
);

-- v2022 ships MSRTMCR in WIDE form (22 columns), not the long metric/value
-- shape v2021 used. One row per container per minute, carrying response time
-- and call rate for every communication paradigm.
--   rt  = response time in ms
--   mcr = call rate, normalised
CREATE UNLOGGED TABLE IF NOT EXISTS stg_msrtmcr (
    ts              bigint,
    msname          text,
    msinstanceid    text,
    nodeid          text,
    providerrpc_rt  text,
    providerrpc_mcr text,
    consumerrpc_rt  text,
    consumerrpc_mcr text,
    writemc_rt      text,
    writemc_mcr     text,
    readmc_rt       text,
    readmc_mcr      text,
    writedb_rt      text,
    writedb_mcr     text,
    readdb_rt       text,
    readdb_mcr      text,
    consumermq_rt   text,
    consumermq_mcr  text,
    providermq_rt   text,
    providermq_mcr  text,
    http_mcr        text,
    http_rt         text,
    src_file        text
);
