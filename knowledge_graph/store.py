"""Where the graph lives. Three tables, and they never change shape.

`nodes` and `edges` are the same for every dataset, which is the whole
reason one engine serves any source. A customer, an airport and a
microservice are all rows in `nodes`; what differs is only the class code,
and that comes from the ontology rather than from code.

Edges carry an interval, not a timestamp. `valid_from`/`valid_to` is what
makes the graph rewindable - "what did this look like in January" - and a
dashboard built on current state can never answer that.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    code        SMALLINT PRIMARY KEY,
    name        VARCHAR UNIQUE NOT NULL,
    source_table VARCHAR,
    key_column  VARCHAR,
    provenance  VARCHAR NOT NULL,
    time_column VARCHAR
);

CREATE TABLE IF NOT EXISTS relations (
    code        SMALLINT PRIMARY KEY,
    name        VARCHAR UNIQUE NOT NULL,
    domain      VARCHAR NOT NULL,
    range       VARCHAR NOT NULL,
    provenance  VARCHAR NOT NULL,
    confidence  DOUBLE NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS nodes (
    id      BIGINT PRIMARY KEY,
    class   SMALLINT NOT NULL,
    nkey    VARCHAR NOT NULL,
    props   JSON,
    UNIQUE (class, nkey)
);

CREATE TABLE IF NOT EXISTS edges (
    src         BIGINT NOT NULL,
    rel         SMALLINT NOT NULL,
    dst         BIGINT NOT NULL,
    valid_from  TIMESTAMP,
    valid_to    TIMESTAMP,
    PRIMARY KEY (src, rel, dst, valid_from)
);

CREATE TABLE IF NOT EXISTS findings (
    rule      VARCHAR NOT NULL,
    severity  SMALLINT NOT NULL,
    subject   VARCHAR,
    detail    JSON
);
"""

# An id derived from (class, key) rather than a counter, so the same row
# always gets the same id and a rebuild is idempotent. md5 and not hash():
# DuckDB's hash() produced 5,878 collisions in 921,622 keys on real data
# because the keys shared long prefixes, and the primary key above is what
# caught it.
NODE_ID = ("(md5_number_lower(CAST({cls} AS VARCHAR) || ':' || {key}) "
           "% 4611686018427387904)::BIGINT")


class Graph:
    """A thin, honest wrapper. No ORM, no query builder - the SQL stays
    visible because the point of this layer is that you can read what it
    did."""

    def __init__(self, con) -> None:
        self.con = con
        self.con.execute("SET enable_progress_bar = false")
        for stmt in filter(str.strip, SCHEMA.split(";")):
            self.con.execute(stmt)

    # ------------------------------------------------------------ basics
    def sql(self, q: str, args: list | None = None) -> list[tuple]:
        return self.con.execute(q, args or []).fetchall()

    def one(self, q: str, args: list | None = None):
        r = self.con.execute(q, args or []).fetchone()
        return r[0] if r else None

    def class_code(self, name: str) -> int | None:
        return self.one("SELECT code FROM classes WHERE name = ?", [name])

    def relation_code(self, name: str) -> int | None:
        return self.one("SELECT code FROM relations WHERE name = ?", [name])

    def node_id(self, cls: str, key: str) -> int | None:
        return self.one(
            "SELECT id FROM nodes WHERE class = ? AND nkey = ?",
            [self.class_code(cls), str(key)])

    # ------------------------------------------------------- inspection
    def count_class(self, name: str) -> int:
        return self.one("SELECT count(*) FROM nodes WHERE class = ?",
                        [self.class_code(name)]) or 0

    def count_relation(self, name: str) -> int:
        return self.one("SELECT count(*) FROM edges WHERE rel = ?",
                        [self.relation_code(name)]) or 0

    def keys_of(self, cls: str) -> set[str]:
        return {r[0] for r in self.sql(
            "SELECT nkey FROM nodes WHERE class = ?", [self.class_code(cls)])}

    def props_of(self, cls: str, key: str) -> dict:
        raw = self.one(
            "SELECT props FROM nodes WHERE class = ? AND nkey = ?",
            [self.class_code(cls), str(key)])
        if raw is None:
            return {}
        return json.loads(raw) if isinstance(raw, str) else dict(raw)

    def dangling_edges(self) -> int:
        """An edge pointing at a node that does not exist.

        Severity 1: it means OUR build is wrong, not that the data is messy.
        A traversal through a dangling edge does not crash - it quietly
        returns less - so nothing but this check finds it.
        """
        return self.one("""
            SELECT count(*) FROM edges e
            LEFT JOIN nodes a ON a.id = e.src
            LEFT JOIN nodes b ON b.id = e.dst
            WHERE a.id IS NULL OR b.id IS NULL""") or 0

    # ------------------------------------------------------------- time
    def active_relations(self, rel: str, as_of: str) -> int:
        return self.one("""
            SELECT count(*) FROM edges
            WHERE rel = ?
              AND (valid_from IS NULL OR valid_from <= CAST(? AS TIMESTAMP))
              AND (valid_to IS NULL OR valid_to > CAST(? AS TIMESTAMP))""",
                        [self.relation_code(rel), as_of, as_of]) or 0

    def edge_time(self, cls: str, key: str, rel: str):
        return self.one("""
            SELECT valid_from FROM edges
            WHERE src = ? AND rel = ? LIMIT 1""",
                        [self.node_id(cls, key), self.relation_code(rel)])

    def neighbours(self, cls: str, key: str, rel: str) -> dict:
        rows = self.sql("""
            SELECT n.nkey, e.valid_from FROM edges e
            JOIN nodes n ON n.id = e.dst
            WHERE e.src = ? AND e.rel = ?""",
                        [self.node_id(cls, key), self.relation_code(rel)])
        return {k: t for k, t in rows}

    # -------------------------------------------------------- traversal
    def reach(self, cls: str, key: str, rel: str | None,
              depth: int = 3, as_of: str | None = None) -> set[str]:
        """Everything reachable from one node, optionally along one relation
        and as of one moment. Returns qualified keys: "Book:1".

        QUALIFIED, not bare. A key is only unique WITHIN a class: book 1 and
        author 1 are different things that both answer to "1", and returning
        bare keys silently merged them - two hops looked like one. Any source
        with per-table integer keys, which is most of them, hits this.

        UNION, not UNION ALL: real graphs contain cycles, and UNION ALL would
        never terminate on one.
        """
        start = self.node_id(cls, key)
        if start is None or depth <= 0:
            return set()
        rel_code = self.relation_code(rel) if rel else None
        rel_filter = "AND e.rel = ?" if rel_code is not None else ""
        time_filter = ("AND (e.valid_from IS NULL OR e.valid_from <= CAST(? AS TIMESTAMP)) "
                       "AND (e.valid_to IS NULL OR e.valid_to > CAST(? AS TIMESTAMP))"
                       if as_of else "")
        args = [start, depth]
        if rel_code is not None:
            args.append(rel_code)
        if as_of:
            args += [as_of, as_of]

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
            WHERE w.d > 0""", args)
        return {f"{cls_name}:{key}" for cls_name, key in rows}

    def summary(self) -> list[tuple]:
        return self.sql("""
            SELECT 'class' AS kind, c.name, c.provenance, count(n.id)
            FROM classes c LEFT JOIN nodes n ON n.class = c.code
            GROUP BY c.name, c.provenance
            UNION ALL
            SELECT 'relation', r.name, r.provenance, count(e.src)
            FROM relations r LEFT JOIN edges e ON e.rel = r.code
            GROUP BY r.name, r.provenance
            ORDER BY kind, 4 DESC""")

    def close(self) -> None:
        self.con.close()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def open_graph(path: str | Path | None = None) -> Graph:
    """Open or create a graph. No path means in-memory, for tests."""
    import duckdb
    if path is None:
        return Graph(duckdb.connect(":memory:"))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return Graph(duckdb.connect(str(p)))
