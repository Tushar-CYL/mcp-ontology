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

from ontology.discover import Ontology
from ontology.schema import Schema

# The source is attached under this alias so a table name can never collide
# with one of ours.
SRC = "s"


def build(graph, schema: Schema, onto: Ontology,
          echo: bool = False) -> dict:
    """Populate the graph. Returns counts, so a caller can report honestly."""
    _register(graph, onto)
    _attach(graph, schema)
    _materialise_keys(graph, schema, onto)

    stats = {"nodes": 0, "edges": 0, "skipped_edges": 0}
    for cls in onto.classes.values():
        stats["nodes"] += _nodes(graph, schema, cls, echo)
    for rel in onto.relations.values():
        made, missed = _edges(graph, schema, onto, rel, echo)
        stats["edges"] += made
        stats["skipped_edges"] += missed
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


def _attach(graph, schema: Schema) -> None:
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
            graph.con.execute(f'DROP TABLE IF EXISTS "{SRC}_{table}"')
            graph.con.execute(
                f'CREATE TABLE "{SRC}_{table}" AS SELECT * FROM {reader}')
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


def _materialise_keys(graph, schema: Schema, onto: Ontology) -> None:
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
    for cls in onto.classes.values():
        if not cls.key_is_synthetic:
            continue
        src = _raw_ref(graph, schema, cls.table)
        dest = f"{SRC}_keyed_{cls.table}"
        graph.con.execute(f'DROP TABLE IF EXISTS "{dest}"')
        graph.con.execute(
            f'CREATE TABLE "{dest}" AS SELECT *, '
            f'CAST(row_number() OVER () AS VARCHAR) AS __row FROM {src}')
        _KEYED[cls.table] = f'"{dest}"'


# Tables rewritten with a stored synthetic key, by original table name.
_KEYED: dict[str, str] = {}


def _ref(graph, schema: Schema, table: str) -> str:
    """How to address a source table, preferring a keyed rewrite if one
    was made."""
    if table in _KEYED:
        return _KEYED[table]
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
    key = '"__row"' if cls.key_is_synthetic else f'"{cls.key}"'

    prop_cols = [c for c in cls.measures + cls.dimensions]
    if cls.time_column:
        prop_cols.append(cls.time_column)
    props = ("to_json({" +
             ", ".join(f"'{c}': \"{c}\"" for c in prop_cols) + "})") \
        if prop_cols else "NULL"

    sql = f"""
    INSERT INTO nodes (id, class, nkey, props)
    SELECT {_node_id(cls.code, 'k')}, {cls.code}, k, p
    FROM (
        SELECT CAST({key} AS VARCHAR) AS k, {props} AS p,
               row_number() OVER (PARTITION BY CAST({key} AS VARCHAR)) AS rn
        FROM {src}
    ) q
    WHERE rn = 1 AND k IS NOT NULL AND k <> ''
    ON CONFLICT DO NOTHING"""
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
    vfrom = (f'coalesce(TRY_CAST("{tcol}" AS TIMESTAMP), {FOREVER})'
             if tcol else FOREVER)

    src_key = f'CAST("{src_cls.key}" AS VARCHAR)'
    dst_key = f'CAST("{rel.column}" AS VARCHAR)'

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
    ON CONFLICT DO NOTHING"""
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


def _node_id(code: int, key_expr: str) -> str:
    return (f"(md5_number_lower('{code}:' || {key_expr}) "
            f"% 4611686018427387904)::BIGINT")


def _esc(s: str) -> str:
    return s.replace("'", "''")
