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

-- ------------------------------------------------------------ shared views
-- These two are DOMAIN-INDEPENDENT: they name no class and no relation, only
-- the registries and the nodes/edges tables every domain shares. Anything
-- that has to name a class belongs in domains/<name>/sql/, not here.

CREATE OR REPLACE MACRO graph_summary() AS TABLE (
    SELECT 'class' AS kind, cr.name, cr.provenance, count(n.id) AS n
    FROM class_registry cr
    LEFT JOIN nodes n ON n.class = cr.code
    GROUP BY cr.name, cr.provenance
    UNION ALL
    SELECT 'relation', rr.name, rr.provenance, count(e.src)
    FROM relation_registry rr
    LEFT JOIN edges e ON e.rel = rr.code
    GROUP BY rr.name, rr.provenance
    ORDER BY kind, n DESC
);

-- Forward reachability from one node along one relation, as of one instant.
-- The relation is a PARAMETER, so the same walk serves "which services are
-- affected" and "which airports become unreachable" without being written
-- twice. UNION (not UNION ALL) terminates on a cyclic graph; both real
-- networks here are cyclic.
CREATE OR REPLACE MACRO reach_from(cls, nkey, rel, as_of, cap) AS TABLE (
    WITH RECURSIVE r(id, depth) AS (
        SELECT node_id(class_code(cls), nkey), 0
        UNION
        SELECT e.dst, r.depth + 1
        FROM r
        JOIN edges e ON e.src = r.id AND e.rel = rel_code(rel)
                    AND valid_at(e.valid_from, e.valid_to, as_of)
        WHERE r.depth < cap
    )
    SELECT n.nkey AS node, min(r.depth) AS hops
    FROM r JOIN nodes n ON n.id = r.id
    WHERE r.depth > 0
    GROUP BY n.nkey
);
