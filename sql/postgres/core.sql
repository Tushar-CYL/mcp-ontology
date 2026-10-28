-- Observability Knowledge Graph - core schema
-- Postgres 17 + pgvector. Loaded by: python graph/apply_schema.py
--
-- TIME MODEL
-- The trace carries *relative* timestamps (milliseconds from trace start),
-- not wall-clock. Everything is anchored to a declared epoch so we get real
-- timestamptz columns, interval arithmetic and range indexes. The epoch is an
-- anchor, not a claim about when this traffic happened.
--
-- PARTITIONING - deviation from the original plan, on purpose:
-- The plan said partition `edges` hourly. That is wrong for this data. Edge
-- validity is an *interval* (a container can sit on a node for hours), so
-- range-partitioning on valid_from only prunes the upper bound: a
-- "valid at T" query still scans every earlier partition. A GiST index over
-- tstzrange(valid_from, valid_to) answers containment directly and is the
-- right tool. `calls` is the opposite case - 25M+ rows stamped at a *point*
-- in time - so that one is partitioned hourly, where pruning actually works.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ---------------------------------------------------------------- settings
CREATE TABLE IF NOT EXISTS meta (
    key    text PRIMARY KEY,
    value  text NOT NULL
);
INSERT INTO meta(key, value) VALUES
    ('trace_epoch', '2022-01-01T00:00:00+00'),
    ('dataset',     'alibaba/cluster-trace-microservices-v2022')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION trace_epoch() RETURNS timestamptz
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT (SELECT value FROM meta WHERE key = 'trace_epoch')::timestamptz $$;

-- trace milliseconds -> absolute timestamp
CREATE OR REPLACE FUNCTION tms(ms bigint) RETURNS timestamptz
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT '2022-01-01T00:00:00+00'::timestamptz + (ms * interval '1 millisecond') $$;

-- ------------------------------------------------------- ontology registry
-- The ontology is the source of truth; these tables are its projection into
-- the database so that every row can be traced back to a versioned class.
CREATE TABLE IF NOT EXISTS ontology_version (
    version     text PRIMARY KEY,
    dataset     text NOT NULL,
    loaded_at   timestamptz NOT NULL DEFAULT now(),
    source_sha  text
);

CREATE TABLE IF NOT EXISTS class_registry (
    code        smallint PRIMARY KEY,
    name        text UNIQUE NOT NULL,
    provenance  text NOT NULL CHECK (provenance IN ('measured','derived','external')),
    key_spec    text,
    description text,
    version     text NOT NULL REFERENCES ontology_version(version)
);

CREATE TABLE IF NOT EXISTS relation_registry (
    code        smallint PRIMARY KEY,
    name        text UNIQUE NOT NULL,
    domain      text[] NOT NULL,
    range       text[] NOT NULL,
    temporal    boolean NOT NULL DEFAULT false,
    transitive  boolean NOT NULL DEFAULT false,
    provenance  text NOT NULL CHECK (provenance IN ('measured','derived','external')),
    description text,
    version     text NOT NULL REFERENCES ontology_version(version)
);

CREATE TABLE IF NOT EXISTS rule_registry (
    id          text PRIMARY KEY,
    severity    smallint NOT NULL CHECK (severity BETWEEN 1 AND 3),
    applies_to  text NOT NULL,
    repair      text NOT NULL,
    description text,
    version     text NOT NULL REFERENCES ontology_version(version)
);

-- ------------------------------------------------------------------- graph
-- Node ids are DETERMINISTIC: hash of (class, canonical key). This makes
-- ingest idempotent and parallel-safe - a streaming COPY worker can emit
-- edge rows without a round trip to look up surrogate keys. Collisions are
-- checked explicitly in the verification step rather than assumed away.
CREATE OR REPLACE FUNCTION node_id(cls smallint, nkey text) RETURNS bigint
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT hashtextextended(cls::text || ':' || nkey, 0) $$;

-- Registry lookups by name. Queries say rel_code('calls') instead of a bare
-- 3, so a traversal stays readable and cannot silently target the wrong
-- relation if codes are ever extended.
CREATE OR REPLACE FUNCTION rel_code(n text) RETURNS smallint
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT code FROM relation_registry WHERE name = n $$;

CREATE OR REPLACE FUNCTION class_code(n text) RETURNS smallint
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT code FROM class_registry WHERE name = n $$;

CREATE TABLE IF NOT EXISTS nodes (
    id      bigint PRIMARY KEY,
    class   smallint NOT NULL REFERENCES class_registry(code),
    nkey    text NOT NULL,
    props   jsonb,
    UNIQUE (class, nkey)
);

-- Every surface form that resolved to a canonical node, so entity-resolution
-- decisions stay auditable and reversible.
CREATE TABLE IF NOT EXISTS node_alias (
    alias     text NOT NULL,
    class     smallint NOT NULL REFERENCES class_registry(code),
    node_id   bigint NOT NULL REFERENCES nodes(id),
    reason    text NOT NULL,
    PRIMARY KEY (class, alias)
);

CREATE TABLE IF NOT EXISTS edges (
    src         bigint      NOT NULL,
    rel         smallint    NOT NULL REFERENCES relation_registry(code),
    dst         bigint      NOT NULL,
    valid_from  timestamptz NOT NULL,
    valid_to    timestamptz,                 -- NULL = still open
    props       jsonb,
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

-- Raw span rows. The volume driver. Partitioned hourly on a point timestamp,
-- where range pruning genuinely helps.
CREATE TABLE IF NOT EXISTS calls (
    ts            timestamptz NOT NULL,
    traceid       text        NOT NULL,
    service       text,
    rpc_id        text        NOT NULL,
    parent_rpc_id text,                       -- rpc_id with last segment trimmed
    um            bigint,                     -- Microservice node id, upstream
    dm            bigint,                     -- Microservice node id, downstream
    um_container  bigint,                     -- Container node id, upstream
    dm_container  bigint,                     -- Container node id, downstream
    rpctype       text,
    interface     text,
    rt            double precision
) PARTITION BY RANGE (ts);

-- Safety net so a COPY never fails on an unexpected timestamp; the verifier
-- reports anything that lands here, because it means the epoch math is off.
CREATE TABLE IF NOT EXISTS calls_default PARTITION OF calls DEFAULT;

CREATE OR REPLACE FUNCTION ensure_calls_partition(at timestamptz)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    lo   timestamptz := date_trunc('hour', at);
    hi   timestamptz := lo + interval '1 hour';
    part text        := 'calls_' || to_char(lo, 'YYYYMMDD_HH24');
BEGIN
    IF to_regclass(part) IS NULL THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF calls FOR VALUES FROM (%L) TO (%L)',
            part, lo, hi);
    END IF;
    RETURN part;
END $$;

-- ------------------------------------------------------------- validation
CREATE TABLE IF NOT EXISTS validation_findings (
    run_id      bigint      NOT NULL,
    rule_id     text        NOT NULL REFERENCES rule_registry(id),
    severity    smallint    NOT NULL,
    row_key     text,
    detail      jsonb,
    found_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS validation_findings_run_rule
    ON validation_findings (run_id, rule_id);

CREATE TABLE IF NOT EXISTS validation_run (
    run_id        bigserial PRIMARY KEY,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    ontology_ver  text,
    stage         text,                       -- 'staging' | 'graph'
    summary       jsonb
);



-- Records what was ingested, so a slice can be re-run or extended safely.
CREATE TABLE IF NOT EXISTS ingest_log (
    src_file      text PRIMARY KEY,
    table_name    text NOT NULL,
    rows_loaded   bigint NOT NULL,
    rows_rejected bigint NOT NULL DEFAULT 0,
    bytes_read    bigint,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz
);

-- Structurally malformed source lines: wrong number of fields, so they can
-- never be parsed into the staging table at all. The published release does
-- contain these (e.g. CallGraph_0.csv line 58754 emits rpc_id twice).
-- Exact counts live in stg_reject_count; stg_reject keeps a bounded sample
-- of the raw text so the defect can be inspected rather than guessed at.
CREATE TABLE IF NOT EXISTS stg_reject (
    src_file    text   NOT NULL,
    table_name  text   NOT NULL,
    line_no     bigint NOT NULL,
    raw_line    text   NOT NULL,
    reason      text   NOT NULL
);

CREATE TABLE IF NOT EXISTS stg_reject_count (
    src_file    text   NOT NULL,
    table_name  text   NOT NULL,
    reason      text   NOT NULL,
    n           bigint NOT NULL,
    PRIMARY KEY (src_file, reason)
);

COMMIT;
