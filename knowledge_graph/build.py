"""Layer 2: rows become nodes and edges.

Generated from the discovered ontology, so no dataset needs its own build
script. Two things are deliberately baked in here rather than left to be
remembered per dataset:

  JOIN ON THE NATURAL KEY, NEVER ON A COMPUTED ID.
      Written as `JOIN nodes n ON n.id = node_id(...)`, one such statement
      ran for over ten minutes instead of 0.04 seconds: an expression in a
      join condition cannot be hash-joined, so the engine falls back to a
      nested loop and hashes MD5 at every comparison. Matching on `nkey`,
      a plain column, keeps it a hash join. Generating the SQL means this
      is decided once, correctly, for every source that will ever connect.

  EDGES ONLY BETWEEN NODES THAT EXIST.
      The join enforces it, and anything that falls out is counted rather
      than silently dropped - a row pointing at a missing customer is a
      finding about the data, not a row to lose.
"""

from __future__ import annotations

import hashlib
import time

from ontology.discover import Ontology
from ontology.schema import Schema

# The source is attached under this alias so a table name can never collide
# with one of ours.
SRC = "s"


def signature(schema: Schema, onto: Ontology) -> str:
    """What this graph was built FROM, in one short string.

    Covers the source, every table and its row count, and the ontology -
    the same rows modelled differently is a different graph. Row counts
    rather than file mtimes, because a copied or re-exported file changes
    its timestamp without changing a thing.
    """
    parts = [schema.origin, schema.name]
    for t in sorted(schema.tables, key=lambda x: x.name):
        parts.append(f"{t.name}:{t.row_count}:{len(t.columns)}")
    for c in sorted(onto.classes.values(), key=lambda x: x.name):
        parts.append(f"{c.name}:{c.code}:{c.key}")
    for r in sorted(onto.relations.values(), key=lambda x: x.name):
        parts.append(f"{r.name}:{r.domain}>{r.range}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def is_current(graph, schema: Schema, onto: Ontology) -> bool:
    """Is this graph already built from exactly this source and ontology?"""
    try:
        got = graph.one("SELECT value FROM build_info WHERE key = ?",
                        ["signature"])
    except Exception:
        return False
    return bool(got) and got == signature(schema, onto)


def build(graph, schema: Schema, onto: Ontology,
          echo: bool = False, progress=None) -> dict:
    """Populate the graph. Returns counts, so a caller can report honestly.

    `progress` is called with a line of text after each step. Building a
    large source takes minutes, and a program that prints nothing for
    minutes looks hung - people kill it and report it as broken.
    """
    say = progress or (lambda _: None)
    t0 = time.monotonic()

    _register(graph, onto)
    say(f"  reading the source ({len(schema.tables)} tables)")
    _attach(graph, schema, say)
    _materialise_keys(graph, schema, onto, say)

    stats = {"nodes": 0, "edges": 0, "skipped_edges": 0}
    for cls in onto.classes.values():
        t = time.monotonic()
        n = _nodes(graph, schema, cls, echo)
        stats["nodes"] += n
        say(f"  {cls.name:<22} {n:>10,} things      "
            f"{time.monotonic() - t:5.1f}s")
    for rel in onto.relations.values():
        t = time.monotonic()
        made, missed = _edges(graph, schema, onto, rel, echo)
        stats["edges"] += made
        stats["skipped_edges"] += missed
        extra = f"  ({missed:,} had no match)" if missed else ""
        say(f"  {rel.name:<22} {made:>10,} links       "
            f"{time.monotonic() - t:5.1f}s{extra}")
    graph.con.execute("DELETE FROM build_info WHERE key = 'signature'")
    graph.con.execute("INSERT INTO build_info(key, value) VALUES (?, ?)",
                      ["signature", signature(schema, onto)])
    say(f"  built in {time.monotonic() - t0:,.0f}s")
    return stats


# ------------------------------------------------------------- registry
def _register(graph, onto: Ontology) -> None:
    """The ontology is stored next to the data it describes, so the graph is
    self-explaining: anyone opening the file can see what the codes mean."""
    graph.con.execute("DELETE FROM classes")
    graph.con.execute("DELETE FROM relations")
    for c in onto.classes.values():
        graph.con.execute(
            "INSERT INTO classes(code, name, source_table, key_column,"
            " provenance, time_column) VALUES (?,?,?,?,?,?)",
            [c.code, c.name, c.table, c.key, c.provenance, c.time_column])
    for r in onto.relations.values():
        graph.con.execute(
            "INSERT INTO relations(code, name, domain, range, provenance,"
            " confidence) VALUES (?,?,?,?,?,?)",
            [r.code, r.name, r.domain, r.range, r.provenance, r.confidence])


def _attach(graph, schema: Schema, say=lambda _: None) -> None:
    """Make the source readable from inside the graph database.

    Two cases, and after this point nothing above cares which:
      a database  -> ATTACH it read-only
      files       -> a view per file over read_csv / read_parquet / ...

    Read-only is not politeness. The source belongs to someone else, and a
    tool that reads your warehouse should be incapable of writing to it.
    """
    if schema.readers:
        # A TABLE, not a view. A view re-parses the file on every query, and
        # the build asks several questions per table - so a 1M-row CSV was
        # being read from disk a dozen times and the build never finished.
        # One parse up front, then every later query is a scan of a column
        # store.
        for table, reader in schema.readers.items():
            t = time.monotonic()
            graph.con.execute(f'DROP TABLE IF EXISTS "{SRC}_{table}"')
            graph.con.execute(
                f'CREATE TABLE "{SRC}_{table}" AS SELECT * FROM {reader}')
            say(f"    loaded {table:<34} {time.monotonic() - t:5.1f}s")
        return

    origin = schema.origin
    if not origin:
        return                      # caller already made the tables visible

    if graph.one("SELECT count(*) FROM duckdb_databases() "
                 "WHERE database_name = ?", [SRC]):
        return                      # already attached by an earlier build

    kind = ""
    low = origin.lower()
    if low.startswith(("postgres://", "postgresql://")):
        kind, ext = "TYPE postgres, ", "postgres"
    elif low.startswith("mysql://"):
        kind, ext = "TYPE mysql, ", "mysql"
    elif low.endswith((".db", ".sqlite", ".sqlite3")):
        kind, ext = "TYPE sqlite, ", "sqlite"
    else:
        kind, ext = "", None
    if ext:
        graph.con.execute(f"INSTALL {ext}; LOAD {ext}")
    graph.con.execute(f"ATTACH '{_esc(origin)}' AS {SRC} ({kind}READ_ONLY)")


def _materialise_keys(graph, schema: Schema, onto: Ontology,
                      say=lambda _: None) -> None:
    """Give keyless tables a real, stored row number.

    A table with no unique column still has to become nodes AND be the
    source of edges. Computing `row_number()` separately in each query is
    wrong twice over: the column does not exist in the raw table at all,
    and two row_number() calls are not guaranteed to produce the same
    order, so ids could silently drift between the nodes and the edges
    that point at them.

    Storing it once removes both problems, and makes the ids stable across
    rebuilds as a side effect.
    """
    # Per-graph, never module-level. A module global survived between
    # builds in the same process, so one source's rewritten tables were
    # still being looked for while building the next - which failed loudly
    # here but would have been silent corruption if the names had matched.
    for cls in onto.classes.values():
        if not cls.key_is_synthetic:
            continue
        src = _raw_ref(graph, schema, cls.table)
        dest = f"{SRC}_keyed_{cls.table}"
        graph.con.execute(f"DROP TABLE IF EXISTS {qi(dest)}")
        graph.con.execute(
            f"CREATE TABLE {qi(dest)} AS SELECT *, "
            f"CAST(row_number() OVER () AS VARCHAR) AS __row FROM {src}")
        say(f"    numbered rows of {cls.table} (it has no key of its own)")


def _ref(graph, schema: Schema, table: str) -> str:
    """How to address a source table, preferring a keyed rewrite if one
    was made."""
    # Ask the DATABASE whether a rewritten table exists, rather than a
    # dict on this object. The dict only exists in the process that did
    # the build, so reopening an unchanged graph - which is the normal
    # case once a source is built - found the raw table and looked for a
    # column that only the rewrite has.
    dest = f"{SRC}_keyed_{table}"
    if graph.one("SELECT count(*) FROM duckdb_tables() "
                 "WHERE table_name = ?", [dest]):
        return qi(dest)
    return _raw_ref(graph, schema, table)


def _raw_ref(graph, schema: Schema, table: str) -> str:
    """The source table as it actually arrived."""
    if schema.readers:
        return f'"{SRC}_{table}"'
    if graph.one("SELECT count(*) FROM duckdb_databases() "
                 "WHERE database_name = ?", [SRC]):
        return f'{SRC}."{table}"'
    return f'"{table}"'


# ---------------------------------------------------------------- nodes
def _nodes(graph, schema: Schema, cls, echo: bool) -> int:
    """One node per row. Columns that are not keys or links become props,
    so the node carries enough to be readable without re-reading the source.
    """
    tbl = _ref(graph, schema, cls.table)

    # _materialise_keys has already stored a __row column for a keyless
    # table, so both this query and the edge query below read the same
    # values. Recomputing it here is what made the ids drift.
    src = tbl
    if cls.key_is_synthetic:
        key = qi("__row")
    elif len(cls.key_columns) > 1:
        # A composite key is one identity spread over several columns.
        # Joined with a separator that cannot appear in a value, so
        # ('a|b', 'c') and ('a', 'b|c') stay distinct.
        parts = " || '' || ".join(
            f"coalesce(CAST({qi(c)} AS VARCHAR), '')" for c in cls.key_columns)
        key = f"({parts})"
    else:
        key = qi(cls.key)

    prop_cols = [c for c in cls.measures + cls.dimensions]
    if cls.time_column:
        prop_cols.append(cls.time_column)
    props = ("to_json({" +
             ", ".join(f"{ql(c)}: {qi(c)}" for c in prop_cols) + "})") \
        if prop_cols else "NULL"

    # LEFT JOIN + IS NULL, not ON CONFLICT DO NOTHING.
    #
    # ON CONFLICT probes the primary-key index once PER ROW, so each insert
    # got slower as the table filled: on a real export the first class took
    # 1.5s and a later one with the SAME row count took 117s. An anti-join
    # is a single hash build, which is what a columnar engine is good at.
    sql = f"""
    INSERT INTO nodes (id, class, nkey, props)
    SELECT {_node_id(cls.code, 'q.k')}, {cls.code}, q.k, q.p
    FROM (
        SELECT CAST({key} AS VARCHAR) AS k, {props} AS p,
               row_number() OVER (PARTITION BY CAST({key} AS VARCHAR)) AS rn
        FROM {src}
    ) q
    LEFT JOIN nodes ex ON ex.class = {cls.code} AND ex.nkey = q.k
    WHERE q.rn = 1 AND q.k IS NOT NULL AND q.k <> '' AND ex.id IS NULL"""
    if echo:
        print(sql)
    before = graph.one("SELECT count(*) FROM nodes") or 0
    graph.con.execute(sql)
    return (graph.one("SELECT count(*) FROM nodes") or 0) - before


# ---------------------------------------------------------------- edges
def _edges(graph, schema: Schema, onto: Ontology, rel,
           echo: bool) -> tuple[int, int]:
    src_cls = onto.classes[rel.domain]
    dst_cls = onto.classes[rel.range]
    tbl = _ref(graph, schema, src_cls.table)

    # The row's own time, if it has one. Without it the edge is open-ended,
    # which is the honest encoding of "true, but we do not know since when".
    # An edge with no date is valid for all time, which is '-infinity',
    # not NULL. NULL would say "unknown" and then fail the primary key;
    # worse, a sentinel like 1970-01-01 would claim the link STARTED then,
    # which is a invented fact. -infinity reads correctly in every
    # point-in-time query without asserting anything.
    tcol = src_cls.time_column
    FOREVER = "'-infinity'::TIMESTAMP"
    vfrom = (f"coalesce(TRY_CAST({qi(tcol)} AS TIMESTAMP), {FOREVER})"
             if tcol else FOREVER)

    if src_cls.key_is_synthetic:
        src_key = f"CAST({qi('__row')} AS VARCHAR)"
    elif len(src_cls.key_columns) > 1:
        parts = " || '' || ".join(
            f"coalesce(CAST({qi(c)} AS VARCHAR), '')"
            for c in src_cls.key_columns)
        src_key = f"({parts})"
    else:
        src_key = f"CAST({qi(src_cls.key)} AS VARCHAR)"
    dst_key = f"CAST({qi(rel.column)} AS VARCHAR)"

    # Note the joins: ON n.nkey = ..., never ON n.id = node_id(...).
    sql = f"""
    INSERT INTO edges (src, rel, dst, valid_from, valid_to)
    SELECT a.id, {rel.code}, b.id, q.vf, NULL
    FROM (
        SELECT {src_key} AS sk, {dst_key} AS dk, {vfrom} AS vf
        FROM {tbl}
        WHERE {dst_key} IS NOT NULL
    ) q
    JOIN nodes a ON a.class = {src_cls.code} AND a.nkey = q.sk
    JOIN nodes b ON b.class = {dst_cls.code} AND b.nkey = q.dk
    LEFT JOIN edges ex ON ex.src = a.id AND ex.rel = {rel.code}
                      AND ex.dst = b.id AND ex.valid_from = q.vf
    WHERE ex.src IS NULL"""
    if echo:
        print(sql)

    before = graph.one("SELECT count(*) FROM edges") or 0
    graph.con.execute(sql)
    made = (graph.one("SELECT count(*) FROM edges") or 0) - before

    # Rows whose link points at something absent. Counted, never discarded:
    # "412 orders reference a customer that does not exist" is a fact worth
    # reporting, and losing it is how data quality problems stay invisible.
    missed = graph.one(f"""
        SELECT count(*) FROM (
            SELECT {dst_key} AS dk FROM {tbl} WHERE {dst_key} IS NOT NULL
        ) q
        LEFT JOIN nodes b ON b.class = {dst_cls.code} AND b.nkey = q.dk
        WHERE b.id IS NULL""") or 0
    if missed:
        graph.con.execute(
            "INSERT INTO findings(rule, severity, subject, detail) "
            "VALUES ('orphan_reference', 2, ?, ?)",
            [rel.name, f'{{"rows": {missed}, "relation": "{rel.name}", '
                       f'"points_at": "{rel.range}"}}'])
    return made, missed


def qi(name: str) -> str:
    """Quote an identifier. Real exports have columns called `order`,
    `select`, and `it's_here`; unquoted or naively quoted, each one is a
    parser error rather than a column."""
    return '"' + str(name).replace('"', '""') + '"'


def ql(value: str) -> str:
    """Quote a string literal, doubling any embedded apostrophe."""
    return "'" + str(value).replace("'", "''") + "'"


def _node_id(code: int, key_expr: str) -> str:
    return (f"(md5_number_lower('{code}:' || {key_expr}) "
            f"% 4611686018427387904)::BIGINT")


def _esc(s: str) -> str:
    return s.replace("'", "''")


# ----------------------------------------------------------- reading back
def source_rows(graph, schema: Schema, table: str,
                limit: int = 50) -> tuple[list[str], list[tuple]]:
    """A sample of the ACTUAL rows behind a table.

    Counts and hashed ids are abstractions. Showing the real row is what
    turns "1,550,922 things" from a claim into something a person can
    check.
    """
    ref = _ref(graph, schema, table)
    cur = graph.con.execute(f"SELECT * FROM {ref} LIMIT {int(limit)}")
    cols = [d[0] for d in cur.description]
    return [c for c in cols if c != "__row"], \
           [tuple(v for c, v in zip(cols, r) if c != "__row")
            for r in cur.fetchall()]


def row_for(graph, schema: Schema, onto: Ontology,
            cls_name: str, key: str) -> dict:
    """The one source row a node came from, as {column: value}."""
    cls = onto.classes.get(cls_name)
    if cls is None:
        return {}
    ref = _ref(graph, schema, cls.table)
    if cls.key_is_synthetic:
        key_expr = qi("__row")
    elif len(cls.key_columns) > 1:
        key_expr = "(" + " || '\u001f' || ".join(
            f"coalesce(CAST({qi(c)} AS VARCHAR), '')"
            for c in cls.key_columns) + ")"
    else:
        key_expr = f"CAST({qi(cls.key)} AS VARCHAR)"
    cur = graph.con.execute(
        f"SELECT * FROM {ref} WHERE {key_expr} = ? LIMIT 1", [str(key)])
    row = cur.fetchone()
    if row is None:
        return {}
    return {d[0]: v for d, v in zip(cur.description, row)
            if d[0] != "__row"}
