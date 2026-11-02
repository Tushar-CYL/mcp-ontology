"""Where the graph lives. Fixed tables, one row per source, and nothing that
changes shape per dataset.

`nodes` and `edges` are the same for every dataset — that is why one engine
serves any source. A customer, an airport and a microservice are all rows in
`nodes`; what differs is only the class code, and that comes from the ontology.

Multi-source (2026-10-29): every source owns its classes, relations, nodes and
edges (`source_id` on each row). The id of a node includes the source, so the
same class+key in two sources cannot collide. Queries that predate multi-source
still work when the graph has exactly one source: the source is resolved
automatically, and an ambiguous name raises a clear error instead of silently
returning the wrong source's rows.

Edges carry an interval, not a timestamp. `valid_from`/`valid_to` is what makes
the graph rewindable. History is never overwritten.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id   VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    origin      VARCHAR,
    kind        VARCHAR,
    signature   VARCHAR,
    built_at    TIMESTAMP,
    status      VARCHAR,
    tables      INTEGER,
    rows        BIGINT
);

CREATE TABLE IF NOT EXISTS classes (
    code        SMALLINT PRIMARY KEY,
    name        VARCHAR NOT NULL,
    source_id   VARCHAR NOT NULL DEFAULT '',
    source_table VARCHAR,
    key_column  VARCHAR,
    provenance  VARCHAR NOT NULL,
    time_column VARCHAR,
    UNIQUE (source_id, name)
);

CREATE TABLE IF NOT EXISTS relations (
    code        SMALLINT PRIMARY KEY,
    name        VARCHAR NOT NULL,
    domain      VARCHAR NOT NULL,
    range       VARCHAR NOT NULL,
    source_id   VARCHAR NOT NULL DEFAULT '',
    provenance  VARCHAR NOT NULL,
    confidence  DOUBLE NOT NULL DEFAULT 1.0,
    UNIQUE (source_id, name)
);

CREATE TABLE IF NOT EXISTS nodes (
    id          BIGINT PRIMARY KEY,
    class       SMALLINT NOT NULL,
    nkey        VARCHAR NOT NULL,
    source_id   VARCHAR NOT NULL DEFAULT '',
    props       JSON,
    UNIQUE (source_id, class, nkey)
);

CREATE TABLE IF NOT EXISTS edges (
    src         BIGINT NOT NULL,
    rel         SMALLINT NOT NULL,
    dst         BIGINT NOT NULL,
    source_id   VARCHAR NOT NULL DEFAULT '',
    -- '-infinity' means "no start recorded", so the edge is true at every
    -- instant. NOT NULL because it is part of the key: the same link can
    -- exist on many days and each is its own row.
    valid_from  TIMESTAMP NOT NULL DEFAULT '-infinity',
    valid_to    TIMESTAMP,
    PRIMARY KEY (src, rel, dst, valid_from)
);

-- What each graph was built from, so an unchanged source opens instantly.
CREATE TABLE IF NOT EXISTS build_info (
    key    VARCHAR PRIMARY KEY,
    value  VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    rule      VARCHAR NOT NULL,
    severity  SMALLINT NOT NULL,
    subject   VARCHAR,
    source_id VARCHAR NOT NULL DEFAULT '',
    detail    JSON
);

-- Human-in-the-loop (phase 2). Kept here so the review workflow uses the same
-- store as the graph and an approved decision survives a rebuild.
CREATE TABLE IF NOT EXISTS review_items (
    item_id    VARCHAR PRIMARY KEY,
    kind       VARCHAR NOT NULL,
    source_id  VARCHAR NOT NULL DEFAULT '',
    subject    VARCHAR,
    payload    JSON,
    confidence DOUBLE,
    status     VARCHAR NOT NULL DEFAULT 'proposed',
    created_at TIMESTAMP,
    proposed_by VARCHAR
);

CREATE TABLE IF NOT EXISTS review_decisions (
    item_id    VARCHAR NOT NULL,
    decision   VARCHAR NOT NULL,
    reviewer   VARCHAR,
    rationale  VARCHAR,
    decided_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_state (
    artifact   VARCHAR NOT NULL,
    source_id  VARCHAR NOT NULL DEFAULT '',
    state      VARCHAR NOT NULL,
    signature  VARCHAR,
    published_at TIMESTAMP,
    PRIMARY KEY (artifact, source_id)
);

-- Cross-source identity. `same_as` is a link, never a silent merge: the
-- per-source nodes stay, so an answer can always show where a fact came from.
CREATE TABLE IF NOT EXISTS entity_links (
    a_source VARCHAR NOT NULL,
    a_class  VARCHAR NOT NULL,
    a_key    VARCHAR NOT NULL,
    b_source VARCHAR NOT NULL,
    b_class  VARCHAR NOT NULL,
    b_key    VARCHAR NOT NULL,
    method   VARCHAR,
    confidence DOUBLE,
    status   VARCHAR NOT NULL DEFAULT 'proposed',
    PRIMARY KEY (a_source, a_class, a_key, b_source, b_class, b_key)
);

-- Which source wins per attribute, for the source-of-truth decision.
CREATE TABLE IF NOT EXISTS attribute_rules (
    source_id  VARCHAR NOT NULL,
    class      VARCHAR NOT NULL,
    attribute  VARCHAR,
    precedence INTEGER NOT NULL,
    reason     VARCHAR
);

-- Business semantic layer: approved metric definitions, not auto-proposals.
CREATE TABLE IF NOT EXISTS metric_definitions (
    id          VARCHAR PRIMARY KEY,
    source_id   VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,
    title       VARCHAR NOT NULL,
    description VARCHAR,
    unit        VARCHAR,
    base_sql    VARCHAR NOT NULL,
    value_expr  VARCHAR NOT NULL,
    time_column VARCHAR,
    dimensions  JSON,
    owner       VARCHAR,
    status      VARCHAR NOT NULL DEFAULT 'approved',
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMP,
    UNIQUE (source_id, name)
);

-- Agents built on top of the four layers.
CREATE TABLE IF NOT EXISTS agents (
    id            VARCHAR PRIMARY KEY,
    name          VARCHAR NOT NULL,
    purpose       VARCHAR,
    problem_statement VARCHAR,
    instructions  VARCHAR,
    source_id     VARCHAR,
    metrics       JSON,
    skills        JSON,
    guardrails    JSON,
    status        VARCHAR NOT NULL DEFAULT 'draft',
    created_at    TIMESTAMP,
    updated_at    TIMESTAMP
);

-- Reusable analysis skills. A custom skill is a safe recipe over approved
-- tools (no raw SQL, no code execution), stored next to the built-ins.
CREATE TABLE IF NOT EXISTS skill_definitions (
    id          VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    description VARCHAR,
    source_id   VARCHAR NOT NULL,
    kind        VARCHAR NOT NULL,
    metric      VARCHAR,
    dimension   VARCHAR,
    owner       VARCHAR,
    status      VARCHAR NOT NULL DEFAULT 'active',
    created_at  TIMESTAMP
);

-- Policies attached to a source, not only to one agent. Every agent built on
-- the source inherits them.
CREATE TABLE IF NOT EXISTS source_guardrails (
    source_id  VARCHAR PRIMARY KEY,
    rules      JSON,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id          VARCHAR PRIMARY KEY,
    agent_id    VARCHAR NOT NULL,
    question    VARCHAR NOT NULL,
    answer      VARCHAR,
    evidence    JSON,
    trace       JSON,
    status      VARCHAR NOT NULL,
    latency_ms  DOUBLE,
    created_at  TIMESTAMP
);
"""

# An id derived from (source, class, key), not a counter, so the same row always
# gets the same id and a rebuild is idempotent. md5, not DuckDB's hash():
# hash() produced 5,878 collisions in 921,622 keys on real data because the keys
# shared long prefixes.
NODE_ID = ("(md5_number_lower(CAST({cls} AS VARCHAR) || ':' || "
           "CAST({source} AS VARCHAR) || ':' || {key}) "
           "% 4611686018427387904)::BIGINT")

# The tables an older graph file may contain. They are all derived artifacts;
# a schema mismatch simply rebuilds instead of migrating.
_LEGACY_TABLES = ("findings", "edges", "nodes", "relations", "classes",
                  "build_info", "sources", "review_items", "review_decisions",
                  "publish_state", "entity_links", "attribute_rules")


class Graph:
    """A thin, honest wrapper. No ORM, no query builder — the SQL stays
    visible because the point of this layer is that you can read what it did.
    """

    def __init__(self, con) -> None:
        self.con = con
        # DuckDB refuses concurrent calls on one connection instead of
        # queueing them ("connection is busy with another call"). A Streamlit
        # app shares one Graph across tabs and sessions, so every read is
        # serialised here. RLock because some methods call others.
        self.lock = threading.RLock()
        self.con.execute("SET enable_progress_bar = false")
        self.rebuilt = self._migrate_if_needed()
        for stmt in filter(str.strip, SCHEMA.split(";")):
            self.con.execute(stmt)
        # Small additive migrations: existing graphs keep their data and
        # agents. A missing column is the only migration this code needs.
        for table, column, ddl in (
            ("agents", "problem_statement", "VARCHAR"),
            ("agents", "skills", "JSON"),
        ):
            try:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            except Exception:                      # noqa: BLE001 - already there
                pass

    # ------------------------------------------------------------- schema
    def _tables(self) -> set[str]:
        return {r[0] for r in self.con.execute(
            "SELECT table_name FROM duckdb_tables()").fetchall()}

    def _migrate_if_needed(self) -> bool:
        """A graph is derived data. If its shape is older than this code, drop
        it and recreate — no migration code to maintain, no half-migrated file.
        """
        tables = self._tables()
        if not tables:
            return False
        obsolete = False
        if "classes" not in tables:
            obsolete = True
        else:
            nkeys = self.con.execute("PRAGMA table_info('classes')").fetchall()
            cols = {r[1] for r in nkeys}
            obsolete = "source_id" not in cols or "sources" not in tables
        # Leftovers from the single-source build are also stale. New graphs
        # materialise under `src_`/`keyed_`, so only the old `s_` prefix means
        # an older layout.
        if any(t.startswith("s_") for t in tables):
            obsolete = True
        if not obsolete:
            return False
        for table in tables:
            self.con.execute(f'DROP TABLE IF EXISTS "{table}"')
        return True

    # ------------------------------------------------------------ basics
    def sql(self, q: str, args: list | None = None) -> list[tuple]:
        with self.lock:
            return self.con.execute(q, args or []).fetchall()

    def one(self, q: str, args: list | None = None):
        """One scalar value. The whole result is consumed: leaving a result
        open on the shared connection is what produces the busy error."""
        with self.lock:
            rows = self.con.execute(q, args or []).fetchall()
        return rows[0][0] if rows else None

    def query_with_columns(self, q: str,
                           args: list | None = None) -> tuple[list[str],
                                                             list[tuple]]:
        """Rows plus column names, consumed under the same lock.

        Used by `row_for`/`source_rows`, which need the description; doing this
        with a bare `con.execute` would bypass the lock and can collide with a
        tab that is reading at the same moment.
        """
        with self.lock:
            cursor = self.con.execute(q, args or [])
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        return columns, rows

    def close(self) -> None:
        with self.lock:
            self.con.close()

    # ---------------------------------------------------------- sources
    def sources(self) -> list[dict]:
        rows = self.sql(
            "SELECT source_id, name, origin, kind, signature, built_at, "
            "status, tables, rows FROM sources ORDER BY source_id")
        keys = ("source_id", "name", "origin", "kind", "signature", "built_at",
                "status", "tables", "rows")
        return [dict(zip(keys, row)) for row in rows]

    def source_ids(self) -> list[str]:
        return [r[0] for r in self.sql("SELECT source_id FROM sources "
                                       "ORDER BY source_id")]

    def resolve_source(self, source: str | None) -> str:
        """The source a query means when the caller did not name one.

        A single-source graph stays exactly as ergonomic as before. A
        multi-source graph refuses to guess — returning the wrong source's
        `Customer` silently is worse than an error.
        """
        if source is not None:
            return source
        ids = self.source_ids()
        if len(ids) == 1:
            return ids[0]
        if not ids:
            return ""
        raise KeyError(
            "this graph has several sources: "
            f"{', '.join(ids)}; pass source=<id> to choose one")

    # --------------------------------------------------------- registry
    def class_code(self, name: str, source: str | None = None) -> int | None:
        if source is None:
            rows = self.sql("SELECT code, source_id FROM classes WHERE name = ?",
                            [name])
            if len(rows) > 1:
                names = ", ".join(sorted(r[1] for r in rows))
                raise KeyError(
                    f"class {name!r} exists in several sources ({names}); "
                    "pass source=<id>")
            return rows[0][0] if rows else None
        return self.one(
            "SELECT code FROM classes WHERE name = ? AND source_id = ?",
            [name, source])

    def relation_code(self, name: str, source: str | None = None) -> int | None:
        if source is None:
            rows = self.sql(
                "SELECT code, source_id FROM relations WHERE name = ?", [name])
            if len(rows) > 1:
                names = ", ".join(sorted(r[1] for r in rows))
                raise KeyError(
                    f"relation {name!r} exists in several sources ({names}); "
                    "pass source=<id>")
            return rows[0][0] if rows else None
        return self.one(
            "SELECT code FROM relations WHERE name = ? AND source_id = ?",
            [name, source])

    def node_id(self, cls: str, key: str,
                source: str | None = None) -> int | None:
        source = self.resolve_source(source)
        code = self.class_code(cls, source)
        if code is None:
            return None
        return self.one(
            "SELECT id FROM nodes WHERE source_id = ? AND class = ? AND nkey = ?",
            [source, code, str(key)])

    # ------------------------------------------------------- inspection
    def count_class(self, name: str, source: str | None = None) -> int:
        source = self.resolve_source(source)
        code = self.class_code(name, source)
        if code is None:
            return 0
        return self.one(
            "SELECT count(*) FROM nodes WHERE source_id = ? AND class = ?",
            [source, code]) or 0

    def count_relation(self, name: str, source: str | None = None) -> int:
        source = self.resolve_source(source)
        code = self.relation_code(name, source)
        if code is None:
            return 0
        return self.one(
            "SELECT count(*) FROM edges WHERE source_id = ? AND rel = ?",
            [source, code]) or 0

    def keys_of(self, cls: str, limit: int | None = None,
                source: str | None = None) -> set[str]:
        """Keys of one kind. LIMIT in SQL, not a slice in Python: a caller
        showing 300 of them was pulling a million strings first."""
        source = self.resolve_source(source)
        code = self.class_code(cls, source)
        if code is None:
            return set()
        sql = ("SELECT nkey FROM nodes WHERE source_id = ? AND class = ?")
        args: list = [source, code]
        if limit:
            sql += f" LIMIT {int(limit)}"
        return {r[0] for r in self.sql(sql, args)}

    def props_of(self, cls: str, key: str,
                 source: str | None = None) -> dict:
        source = self.resolve_source(source)
        code = self.class_code(cls, source)
        if code is None:
            return {}
        raw = self.one(
            "SELECT props FROM nodes WHERE source_id = ? AND class = ? "
            "AND nkey = ?", [source, code, str(key)])
        if raw is None:
            return {}
        return json.loads(raw) if isinstance(raw, str) else dict(raw)

    def dangling_edges(self) -> int:
        """An edge pointing at a node that does not exist.

        Severity 1: it means OUR build is wrong, not that the data is messy.
        A traversal through a dangling edge does not crash — it quietly returns
        less — so nothing but this check finds it.
        """
        return self.one("""
            SELECT count(*) FROM edges e
            LEFT JOIN nodes a ON a.id = e.src
            LEFT JOIN nodes b ON b.id = e.dst
            WHERE a.id IS NULL OR b.id IS NULL""") or 0

    # ------------------------------------------------------------- time
    def active_relations(self, rel: str, as_of: str,
                         source: str | None = None) -> int:
        source = self.resolve_source(source)
        code = self.relation_code(rel, source)
        if code is None:
            return 0
        return self.one("""
            SELECT count(*) FROM edges
            WHERE source_id = ? AND rel = ?
              AND (valid_from IS NULL OR valid_from <= CAST(? AS TIMESTAMP))
              AND (valid_to IS NULL OR valid_to > CAST(? AS TIMESTAMP))""",
                        [source, code, as_of, as_of]) or 0

    def edge_time(self, cls: str, key: str, rel: str,
                  source: str | None = None):
        source = self.resolve_source(source)
        rel_code = self.relation_code(rel, source)
        node = self.node_id(cls, key, source)
        if rel_code is None or node is None:
            return None
        return self.one("""
            SELECT valid_from FROM edges
            WHERE src = ? AND rel = ? LIMIT 1""", [node, rel_code])

    def neighbours(self, cls: str, key: str, rel: str,
                   source: str | None = None) -> dict:
        source = self.resolve_source(source)
        rel_code = self.relation_code(rel, source)
        node = self.node_id(cls, key, source)
        if rel_code is None or node is None:
            return {}
        rows = self.sql("""
            SELECT n.nkey, e.valid_from FROM edges e
            JOIN nodes n ON n.id = e.dst
            WHERE e.src = ? AND e.rel = ?""", [node, rel_code])
        return {k: t for k, t in rows}

    # -------------------------------------------------------- traversal
    def reach(self, cls: str, key: str, rel: str | None,
              depth: int = 3, as_of: str | None = None,
              source: str | None = None) -> set[str]:
        """Everything reachable from one node, optionally along one relation
        and as of one moment. Returns qualified keys: "Book:1".

        QUALIFIED, not bare. A key is only unique WITHIN a class: book 1 and
        author 1 are different things that both answer to "1", and returning
        bare keys silently merged them.

        UNION, not UNION ALL: real graphs contain cycles, and UNION ALL would
        never terminate on one.
        """
        source = self.resolve_source(source)
        start = self.node_id(cls, key, source)
        if start is None or depth <= 0:
            return set()
        rel_code = self.relation_code(rel, source) if rel else None
        rel_filter = "AND e.rel = ?" if rel_code is not None else ""
        time_filter = ("AND (e.valid_from IS NULL OR e.valid_from <= CAST(? AS TIMESTAMP)) "
                       "AND (e.valid_to IS NULL OR e.valid_to > CAST(? AS TIMESTAMP))"
                       if as_of else "")
        # Order matters: the recursive CTE's placeholders come first, then the
        # final "only nodes of this source" filter.
        args: list = [start, depth]
        if rel_code is not None:
            args.append(rel_code)
        if as_of:
            args += [as_of, as_of]
        args.append(source)

        rows = self.sql(f"""
            WITH RECURSIVE walk(id, d) AS (
                SELECT ?::BIGINT, 0
                UNION
                SELECT e.dst, w.d + 1
                FROM walk w
                JOIN edges e ON e.src = w.id
                WHERE w.d < ? {rel_filter} {time_filter}
            )
            SELECT DISTINCT c.name, n.nkey FROM walk w
            JOIN nodes n ON n.id = w.id
            JOIN classes c ON c.code = n.class
            WHERE w.d > 0 AND n.source_id = ?""", args)
        return {f"{cls_name}:{key}" for cls_name, key in rows}

    def subgraph(self, limit: int = 250, relation: str | None = None,
                 as_of: str | None = None, source: str | None = None):
        """A slice of the real graph that LOOKS like the real graph.

        Two deliberate choices, both learned from a sample that lied:

        FAIR ACROSS RELATIONS. A plain LIMIT returns the first N rows, which
        all come from whichever relation was inserted first.

        HUBS FIRST, BUT NOT ONE HUB. Edges are taken from the most connected
        nodes in a pool that grows with the budget, so the picture shows shape
        instead of collapsing onto one product.

        Only edges whose BOTH ends are included are returned, so no arrow ever
        points off the picture.
        """
        source = self.resolve_source(source) if source is not None else None
        multi = len(self.source_ids()) > 1
        pairs: list[tuple[str, str]] = []
        if relation:
            if source is None:
                rows = self.sql("SELECT DISTINCT source_id FROM relations "
                                "WHERE name = ?", [relation])
                if len(rows) > 1:
                    raise KeyError(
                        f"relation {relation!r} exists in several sources; "
                        "pass source=<id>")
                if not rows:
                    return [], []
                source = rows[0][0]
            pairs = [(source, relation)]
        else:
            sql = "SELECT source_id, name FROM relations"
            args = []
            if source is not None:
                sql += " WHERE source_id = ?"
                args = [source]
            pairs = [(r[0], r[1]) for r in self.sql(
                sql + " ORDER BY source_id, name", args)]
        pairs = [p for p in pairs
                 if self.relation_code(p[1], p[0]) is not None]
        if not pairs:
            return [], []

        share = max(1, limit // len(pairs))
        pool = max(8, share // 4)
        per_hub = max(4, share // 6)
        rows: list[tuple] = []
        for rel_source, name in pairs:
            code = self.relation_code(name, rel_source)
            args: list = [code]
            extra = " AND e.source_id = ?"
            args.append(rel_source)
            if as_of:
                extra += (" AND (e.valid_from IS NULL OR e.valid_from <= "
                          "CAST(? AS TIMESTAMP)) AND (e.valid_to IS NULL "
                          "OR e.valid_to > CAST(? AS TIMESTAMP))")
                args += [as_of, as_of]
            rows += self.sql(f"""
                WITH hot AS (
                    SELECT dst, count(*) AS deg
                    FROM edges e
                    WHERE e.rel = ? {extra}
                    GROUP BY dst ORDER BY deg DESC
                    LIMIT {pool}
                )
                SELECT ns.nkey, cs.name, nd.nkey, cd.name, r.name,
                       r.provenance, e.source_id
                FROM edges e
                JOIN hot ON hot.dst = e.dst
                JOIN nodes ns ON ns.id = e.src
                JOIN nodes nd ON nd.id = e.dst
                JOIN classes cs ON cs.code = ns.class
                JOIN classes cd ON cd.code = nd.class
                JOIN relations r ON r.code = e.rel
                WHERE e.rel = ? {extra}
                QUALIFY row_number() OVER (PARTITION BY e.dst
                                           ORDER BY e.src) <= {per_hub}
                LIMIT {int(share)}""", args + [code] + args[1:])

        seen: dict[str, dict] = {}
        edges = []
        for sk, scls, dk, dcls, rel_name, prov, rel_source in rows[:limit]:
            if multi:
                a = f"{rel_source}:{scls}:{sk}"
                b = f"{rel_source}:{dcls}:{dk}"
            else:
                a, b = f"{scls}:{sk}", f"{dcls}:{dk}"
            for nid, key, cls_ in ((a, sk, scls), (b, dk, dcls)):
                n = seen.setdefault(
                    nid, {"id": nid, "key": key, "class": cls_, "degree": 0,
                          "source": rel_source})
                n["degree"] += 1
            edges.append({"source": a, "target": b,
                          "relation": rel_name, "provenance": prov})

        # A picture needs names, not internal ids: `Entity:https://...#E1`
        # becomes "Vannevar Bush" when the node carries a label/name/title.
        # One query per (source, class) pair, not one per node.
        groups: dict[tuple[str, str], list[str]] = {}
        for node in seen.values():
            groups.setdefault((node["source"], node["class"]),
                              []).append(node["key"])
        for (src, cls_name), keys in groups.items():
            code = self.class_code(cls_name, src)
            if code is None:
                continue
            marks = ",".join("?" * len(keys))
            got = self.sql(
                f"SELECT nkey, props FROM nodes WHERE source_id = ? "
                f"AND class = ? AND nkey IN ({marks})",
                [src, code] + keys)
            for key, props in got:
                nid = f"{src}:{cls_name}:{key}" if multi else \
                      f"{cls_name}:{key}"
                node = seen.get(nid)
                if node is None:
                    continue
                data = {}
                if isinstance(props, str) and props:
                    try:
                        data = json.loads(props)
                    except ValueError:
                        data = {}
                elif isinstance(props, dict):
                    data = props
                node["label"] = _display_label(data, key)
        for node in seen.values():
            node.setdefault("label", _short_key(node["key"]))
        return list(seen.values()), edges

    def class_counts(self, source: str | None = None) -> list[tuple[str, int]]:
        """How many of each kind of thing, biggest first."""
        if source is None and len(self.source_ids()) > 1:
            condition = ""
            args: list = []
        else:
            source = self.resolve_source(source)
            condition = "WHERE c.source_id = ?"
            args = [source]
        return self.sql(f"""
            SELECT c.name, count(n.id) AS n
            FROM classes c LEFT JOIN nodes n
              ON n.class = c.code AND n.source_id = c.source_id
            {condition}
            GROUP BY c.name, c.source_id ORDER BY n DESC, c.name""", args)

    def instances(self, cls: str, limit: int = 25,
                  source: str | None = None) -> list[tuple]:
        """A sample of real things of one kind, with their columns."""
        source = self.resolve_source(source)
        code = self.class_code(cls, source)
        if code is None:
            return []
        return self.sql(
            "SELECT nkey, props FROM nodes WHERE source_id = ? AND class = ? "
            "LIMIT ?", [source, code, int(limit)])

    def summary(self, source: str | None = None) -> list[tuple]:
        if source is None and len(self.source_ids()) > 1:
            cond, extra, args = "", "", []
        else:
            source = self.resolve_source(source)
            cond = " WHERE source_id = ?"
            extra = " AND e.source_id = ?"
            args = [source, source]
        out = []
        for kind, name, provenance, count in self.sql(f"""
            SELECT 'class' AS kind, c.name, c.provenance, count(n.id)
            FROM classes c LEFT JOIN nodes n
              ON n.class = c.code AND n.source_id = c.source_id
            {cond.replace("source_id", "c.source_id") if cond else ""}
            GROUP BY c.name, c.source_id, c.provenance""", [source] if cond else []):
            out.append((kind, name, provenance, count))
        for kind, name, provenance, count in self.sql(f"""
            SELECT 'relation', r.name, r.provenance, count(e.src)
            FROM relations r LEFT JOIN edges e
              ON e.rel = r.code AND e.source_id = r.source_id
            {cond.replace("source_id", "r.source_id") if cond else ""}
            GROUP BY r.name, r.source_id, r.provenance""", [source] if cond else []):
            out.append((kind, name, provenance, count))
        out.sort(key=lambda r: (r[0], -(r[3] or 0)))
        return out

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def _short_key(key: str) -> str:
    """The readable end of an IRI or path, for a node with no label."""
    text = str(key).rstrip("/")
    tail = text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return (tail or text)[:56]


def _display_label(props: dict, key: str) -> str:
    """The best human label a node's props can offer.

    RDF entities carry `label`; warehouse rows often carry `name`, `title` or
    `display_name`. Falling back to the key tail keeps the picture readable
    without inventing a name.
    """
    for candidate in ("label", "name", "title", "display_name", "term",
                      "label_en", "prefLabel", "predicate", "relation",
                      "type", "role"):
        value = props.get(candidate) if isinstance(props, dict) else None
        if value is not None and str(value).strip():
            return str(value)[:60]
    return _short_key(key)


def open_graph(path: str | Path | None = None) -> Graph:
    """Open or create a graph. No path means in-memory, for tests."""
    import duckdb
    if path is None:
        return Graph(duckdb.connect(":memory:"))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return Graph(duckdb.connect(str(p)))
