-- Observability Knowledge Graph - core schema (DuckDB dialect)
-- Applied by: python graph/apply_schema.py
--
-- The Postgres counterpart lives in sql/postgres/schema.sql. Keeping both
-- under the same filename is deliberate: the diff between the two
-- directories is the answer to "which SQL actually ports", which is a
-- deliverable of this project.
--
-- TIME MODEL
-- The trace carries relative timestamps (milliseconds from trace start),
-- not wall clock. Everything is anchored to a declared epoch so we get real
-- TIMESTAMP columns and interval arithmetic. The epoch is an anchor, not a
-- claim about when this traffic happened.
--
-- Plain TIMESTAMP, not TIMESTAMPTZ: the anchor is arbitrary, so attaching a
-- time zone would imply a precision the data does not have, and it keeps
-- results identical regardless of the session's zone.
--
-- NO PARTITIONING, NO RANGE INDEX - unlike the Postgres version.
-- DuckDB is columnar with per-rowgroup zone maps, so a scan with a
-- timestamp predicate already skips irrelevant blocks. Postgres needs
-- explicit partitioning and a GiST range index to achieve the same thing.
-- That difference is the point of building it twice.

-- ---------------------------------------------------------------- settings
CREATE TABLE IF NOT EXISTS meta (
    key    VARCHAR PRIMARY KEY,
    value  VARCHAR NOT NULL
);
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

-- Point-in-time validity, written ONCE so every traversal asks the question
-- the same way. Half-open [valid_from, valid_to) so adjacent intervals never
-- both match at the boundary instant.
--
-- This predicate is also why the Postgres port stays cheap: it is plain
-- comparison, so the GiST range index added there accelerates this exact
-- expression instead of requiring the queries to be rewritten.
CREATE OR REPLACE MACRO valid_at(vf, vt, as_of) AS
    (vf <= as_of AND (vt IS NULL OR vt > as_of));

-- Placeholder identities present in this release. Excluded from the graph,
-- but only AFTER the validator has counted them, so nothing vanishes
-- silently.
-- MEASURED placeholders in this release: UNKNOWN (2,334,998 rows) and
-- UNAVAILABLE (494,564). Neither is documented. NaN and (?) are listed
-- because the 2021 docs mention them; they do not occur in this slice.
--
-- USER is deliberately NOT here. It is the third non-MS_ identity
-- (1,055,701 rows) but it is a real external actor, not a missing value,
-- and it gets its own class rather than being discarded.
CREATE OR REPLACE MACRO is_placeholder(s) AS
    (s IS NULL OR trim(s) = ''
     OR upper(trim(s)) IN ('NAN', '(?)', '?', 'NULL',
                           'UNKNOWN', 'UNAVAILABLE'));

-- ------------------------------------------------------- ontology registry
CREATE TABLE IF NOT EXISTS ontology_version (
    version     VARCHAR PRIMARY KEY,
    dataset     VARCHAR NOT NULL,
    loaded_at   TIMESTAMP NOT NULL DEFAULT now(),
    source_sha  VARCHAR
);

CREATE TABLE IF NOT EXISTS class_registry (
    code        SMALLINT PRIMARY KEY,
    name        VARCHAR UNIQUE NOT NULL,
    provenance  VARCHAR NOT NULL CHECK (provenance IN ('measured','derived','external')),
    key_spec    VARCHAR,
    description VARCHAR,
    version     VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS relation_registry (
    code        SMALLINT PRIMARY KEY,
    name        VARCHAR UNIQUE NOT NULL,
    domain      VARCHAR[] NOT NULL,
    range       VARCHAR[] NOT NULL,
    temporal    BOOLEAN NOT NULL DEFAULT false,
    transitive  BOOLEAN NOT NULL DEFAULT false,
    provenance  VARCHAR NOT NULL CHECK (provenance IN ('measured','derived','external')),
    description VARCHAR,
    version     VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_registry (
    id          VARCHAR PRIMARY KEY,
    severity    SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 3),
    applies_to  VARCHAR NOT NULL,
    repair      VARCHAR NOT NULL,
    description VARCHAR,
    version     VARCHAR NOT NULL
);

-- Registry lookups by name, so a traversal says rel_code('calls') instead
-- of a bare 3 and cannot silently target the wrong relation.
CREATE OR REPLACE MACRO rel_code(n) AS
    (SELECT code FROM relation_registry WHERE name = n);
CREATE OR REPLACE MACRO class_code(n) AS
    (SELECT code FROM class_registry WHERE name = n);

-- ------------------------------------------------------------------- graph
-- Node ids are DETERMINISTIC: a hash of (class, canonical key). This makes
-- ingest idempotent and re-runnable, and lets edges be built by set-based
-- SQL with no lookup round trips.
--
-- DO NOT use DuckDB's built-in hash() here. Measured on this dataset, it
-- produced 5,878 collisions across 921,622 container keys - against the
-- ~1-in-20-million a well-distributed 64-bit hash would give. Every
-- collision was between container ids, which share a long common prefix
-- (MS_27536_POD_0 vs MS_27236_POD_5), so its avalanche is too weak for
-- structured keys. It is built for hash joins, not for identity.
--
-- md5_number_lower gives the low 64 bits of a real MD5: 0 collisions over
-- the same 1,070,591 keys. It returns UBIGINT, so the modulo is
-- non-negative by type rather than by luck, and 2^62 leaves ample room.
--
-- Ids are internal and regenerated per engine, so DuckDB and Postgres need
-- not agree on the VALUE - only on determinism within one database, which
-- is what makes ingest idempotent and re-runnable. The PRIMARY KEY on
-- nodes.id is the collision check, and it is load-bearing: it is what
-- caught hash() in the first place.
CREATE OR REPLACE MACRO node_id(cls, nkey) AS
    ((md5_number_lower(CAST(cls AS VARCHAR) || ':' || nkey)
      % 4611686018427387904)::BIGINT);

CREATE TABLE IF NOT EXISTS nodes (
    id      BIGINT PRIMARY KEY,
    class   SMALLINT NOT NULL,
    nkey    VARCHAR NOT NULL,
    props   JSON,
    UNIQUE (class, nkey)
);

-- Every surface form that resolved to a canonical node, so entity
-- resolution decisions stay auditable and reversible.
CREATE TABLE IF NOT EXISTS node_alias (
    alias     VARCHAR NOT NULL,
    class     SMALLINT NOT NULL,
    node_id   BIGINT NOT NULL,
    reason    VARCHAR NOT NULL,
    PRIMARY KEY (class, alias)
);

-- Edge properties are typed columns rather than JSON. In a columnar engine
-- a JSON extract per row would dominate every aggregate, and rt_p99 over
-- the call graph is a query we run constantly. `props` remains for anything
-- that does not fit the common shape.
CREATE TABLE IF NOT EXISTS edges (
    src         BIGINT   NOT NULL,
    rel         SMALLINT NOT NULL,
    dst         BIGINT   NOT NULL,
    valid_from  TIMESTAMP NOT NULL,
    valid_to    TIMESTAMP,              -- NULL = still open
    weight      BIGINT,                 -- call_count, container count, ...
    stat_p50    REAL,
    stat_p99    REAL,
    tag         VARCHAR,                -- rpctype and similar discriminators
    props       JSON
);

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

-- -------------------------------------------------------------- validation
CREATE SEQUENCE IF NOT EXISTS validation_run_seq START 1;

CREATE TABLE IF NOT EXISTS validation_run (
    run_id        BIGINT PRIMARY KEY
                  DEFAULT nextval('validation_run_seq'),
    started_at    TIMESTAMP NOT NULL DEFAULT now(),
    finished_at   TIMESTAMP,
    ontology_ver  VARCHAR,
    stage         VARCHAR,              -- 'staging' | 'graph'
    summary       JSON
);

CREATE TABLE IF NOT EXISTS validation_findings (
    run_id      BIGINT  NOT NULL,
    rule_id     VARCHAR NOT NULL,
    severity    SMALLINT NOT NULL,
    row_key     VARCHAR,
    detail      JSON,
    found_at    TIMESTAMP NOT NULL DEFAULT now()
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

-- Structurally malformed source lines, made DURABLE.
--
-- DuckDB's read_csv(store_rejects = true) writes to reject_errors, which is
-- session-scoped: close the connection and the evidence is gone. The counts
-- would survive in ingest_log but the actual bad lines would not, and
-- "1,089 rows are broken" is worth far less than being able to show one.
CREATE TABLE IF NOT EXISTS stg_reject (
    src_file      VARCHAR NOT NULL,
    table_name    VARCHAR NOT NULL,
    line_no       BIGINT,
    column_name   VARCHAR,
    error_type    VARCHAR,
    error_message VARCHAR,
    raw_line      VARCHAR
);

-- Records what was ingested, so a slice can be re-run or extended safely.
-- rows_rejected counts structurally malformed source lines; DuckDB's
-- read_csv(store_rejects = true) produces them natively, where the Postgres
-- path has to split lines by hand.
CREATE TABLE IF NOT EXISTS ingest_log (
    src_file      VARCHAR PRIMARY KEY,
    table_name    VARCHAR NOT NULL,
    rows_loaded   BIGINT NOT NULL,
    rows_rejected BIGINT NOT NULL DEFAULT 0,
    bytes_read    BIGINT,
    seconds       DOUBLE,
    loaded_at     TIMESTAMP NOT NULL DEFAULT now()
);
