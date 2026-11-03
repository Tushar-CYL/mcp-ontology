"""Layer 2: rows become nodes and edges, one source at a time.

Generated from the discovered ontology, so no dataset needs its own build
script. Three things are deliberately baked in here rather than left to be
remembered per dataset:

  EVERY SOURCE TABLE IS COPIED IN.
      A file source is read through `read_csv`/`read_parquet`/...; a database
      source is attached just long enough to copy its tables. After the build
      the graph is self-contained, so reopening an unchanged graph works
      without re-attaching anything (the old attach-on-build design broke the
      second process: `s.<table>` did not exist).

  JOIN ON THE NATURAL KEY, NEVER ON A COMPUTED ID.
      An expression in a join condition cannot be hash-joined, so a build that
      joined on `node_id(...)` ran for over ten minutes instead of 0.04
      seconds. Matching on `nkey`, a plain column, keeps it a hash join.

  EDGES ONLY BETWEEN NODES THAT EXIST.
      The join enforces it, and anything that falls out is counted rather than
      silently dropped — a row pointing at a missing customer is a finding
      about the data, not a row to lose.

Multi-source: `build_many` builds several sources into one graph. Every row
carries its `source_id`; class/relation codes and node ids include the source,
so two sources can both have a `Customer` and a key of `1` without colliding.
"""

from __future__ import annotations

import hashlib
import json
import time

from ontology.discover import Ontology, stable_code
from ontology.schema import Schema

# Every source table is materialised under this prefix.
SRC = "src"

# The separator for composite keys. The unit separator cannot appear in a
# normal business value; keep it escaped (never a raw control character in the
# source) so an editor cannot silently mangle it.
KEY_SEP = "\u001f"


# ------------------------------------------------------------------ naming
def source_slug(source: str) -> str:
    """A filesystem/SQL-safe id for a source. Stable for the same input."""
    slug = "".join(c if c.isalnum() else "_" for c in str(source or "source"))
    slug = slug.strip("_")
    return (slug[-40:] or "source")


def _dest(slug: str, table: str) -> str:
    return qi(f"{SRC}_{slug}__{table}")


def _keyed(slug: str, table: str) -> str:
    return qi(f"keyed_{slug}__{table}")


def _table_exists(graph, name: str) -> bool:
    return bool(graph.one(
        "SELECT count(*) FROM duckdb_tables() WHERE table_name = ?", [name]))


def _drop_prefix(graph, prefix: str) -> None:
    for (name,) in graph.sql("SELECT table_name FROM duckdb_tables()"):
        if name.startswith(prefix):
            graph.con.execute(f'DROP TABLE IF EXISTS {qi(name)}')


# --------------------------------------------------------------- signature
def signature(schema: Schema, onto: Ontology, source: str = "") -> str:
    """What this graph was built FROM, in one short string.

    Covers the source name, every table and its row count, and the ontology -
    the same rows modelled differently is a different graph. Row counts rather
    than file mtimes, because a copied or re-exported file changes its
    timestamp without changing a thing.
    """
    parts = [source or schema.name, schema.origin, schema.name]
    for t in sorted(schema.tables, key=lambda x: x.name):
        parts.append(f"{t.name}:{t.row_count}:{len(t.columns)}")
    for c in sorted(onto.classes.values(), key=lambda x: x.name):
        parts.append(f"{c.name}:{c.key}")
    for r in sorted(onto.relations.values(), key=lambda x: x.name):
        parts.append(f"{r.name}:{r.domain}>{r.range}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def _signature_key(slug: str) -> str:
    return f"signature:{slug}"


def is_current(graph, schema: Schema, onto: Ontology,
               source: str = "") -> bool:
    """Is this graph already built from exactly this source and ontology?"""
    slug = source_slug(source or schema.name)
    try:
        got = graph.one("SELECT value FROM build_info WHERE key = ?",
                        [_signature_key(slug)])
    except Exception:                             # noqa: BLE001 - old graph
        return False
    return bool(got) and got == signature(schema, onto, source)


# ------------------------------------------------------------------- build
def build(graph, schema: Schema, onto: Ontology, source: str = "",
          echo: bool = False, progress=None) -> dict:
    """Populate one source in the graph. Returns counts.

    The build runs on its own connection inside one transaction (see
    `Graph.writer`): readers are never blocked and see the previous data
    until the new data commits; a failed build rolls back completely.
    """
    writer = graph.writer() if hasattr(graph, "writer") else graph
    if writer is graph:
        with graph.lock:
            return _build(graph, schema, onto, source, echo, progress)
    src = source or schema.name
    slug = source_slug(src)
    say = progress or (lambda _: None)
    try:
        # Phase 1, outside the transaction: copy the raw tables under fresh
        # names. Attached databases (SQLite, Postgres) cannot be detached
        # while a transaction has touched them, and the copies are new tables
        # that no reader depends on yet.
        say(f"  reading the source ({len(schema.tables)} tables)")
        _materialise(writer, schema, src, slug, say)
        _materialise_keys(writer, schema, onto, src, slug, say)
        # Phase 2, atomic: replace the graph rows. Readers keep the previous
        # graph until COMMIT; a failure rolls back to it.
        writer.con.execute("BEGIN TRANSACTION")
        stats = _build(writer, schema, onto, source, echo, progress,
                       materialised=True)
        writer.con.execute("COMMIT")
        return stats
    except Exception:
        try:
            writer.con.execute("ROLLBACK")
        except Exception:                          # noqa: BLE001 - already closed
            pass
        raise
    finally:
        writer.con.close()


def _build(graph, schema: Schema, onto: Ontology, source: str,
           echo: bool, progress, materialised: bool = False) -> dict:
    """The build itself (called with the graph lock held).

    `progress` is called with a line of text after each step. Building a large
    source takes minutes, and a program that prints nothing for minutes looks
    hung - people kill it and report it as broken.
    """
    src = source or schema.name
    slug = source_slug(src)
    say = progress or (lambda _: None)
    t0 = time.monotonic()

    clear_source(graph, src, drop_tables=not materialised)
    _register_source(graph, schema, src)

    if not materialised:
        say(f"  reading the source ({len(schema.tables)} tables)")
        _materialise(graph, schema, src, slug, say)
        _materialise_keys(graph, schema, onto, src, slug, say)

    class_codes, relation_codes = _register(graph, onto, src, slug)

    stats = {"source": src, "nodes": 0, "edges": 0, "skipped_edges": 0,
             "rejected": []}
    for cls in onto.classes.values():
        t = time.monotonic()
        n = _nodes(graph, schema, cls, class_codes[cls.name], src, slug, echo)
        stats["nodes"] += n
        say(f"  {cls.name:<22} {n:>10,} things      "
            f"{time.monotonic() - t:5.1f}s")
    for rel in onto.relations.values():
        if getattr(rel, "custom", False):
            continue                 # built from the triples table below
        t = time.monotonic()
        made, missed = _edges(graph, schema, onto, rel,
                              relation_codes[rel.name], class_codes,
                              src, slug, echo)
        # A GUESSED link is checked against the data: if most rows point at
        # nothing, it was a coincidence of column names, not a relationship.
        if rel.provenance != "measured" and made < LINK_MATCH * (made + missed):
            graph.con.execute(
                "DELETE FROM edges WHERE source_id = ? AND rel = ?",
                [src, relation_codes[rel.name]])
            stats["rejected"].append(rel.name)
            say(f"  {rel.name:<22} rejected: only {made:,} of "
                f"{made + missed:,} rows matched")
            continue
        stats["edges"] += made
        stats["skipped_edges"] += missed
        extra = f"  ({missed:,} had no match)" if missed else ""
        say(f"  {rel.name:<22} {made:>10,} links       "
            f"{time.monotonic() - t:5.1f}s{extra}")

    if getattr(schema, "triples", None):
        t = time.monotonic()
        made, missed = _triple_edges(graph, schema, onto, src, slug,
                                     class_codes, relation_codes, echo)
        stats["edges"] += made
        stats["skipped_edges"] += missed
        extra = f"  ({missed:,} could not be matched)" if missed else ""
        say(f"  triples               {made:>10,} links       "
            f"{time.monotonic() - t:5.1f}s{extra}")

    sig = signature(schema, onto, src)
    _set_info(graph, _signature_key(slug), sig)
    _set_info(graph, f"rejected:{slug}", json.dumps(stats["rejected"]))
    _set_info(graph, f"source:{slug}", src)
    graph.con.execute(
        "UPDATE sources SET signature = ?, built_at = now(), status = 'built',"
        " tables = ?, rows = ? WHERE source_id = ?",
        [sig, len(schema.tables), sum(t.row_count or 0 for t in schema.tables),
         src])
    say(f"  built in {time.monotonic() - t0:,.0f}s")
    return stats


LINK_MATCH = 0.5        # a guessed link must match at least half its rows


def rejected_links(graph, source: str) -> list[str]:
    """Guessed links the last build rejected for this source."""
    raw = graph.one("SELECT value FROM build_info WHERE key = ?",
                    [f"rejected:{source_slug(source)}"])
    return json.loads(raw) if raw else []


def build_many(graph, bundles, echo: bool = False, progress=None) -> dict:
    """Build several sources into one graph.

    `bundles` is a list of `(schema, ontology, source_name)` tuples. One bad
    source must not take the others down: its error is recorded in the graph's
    findings and the remaining sources still build.
    """
    results: dict = {}
    for schema, onto, source in bundles:
        try:
            results[source] = build(graph, schema, onto, source,
                                    echo=echo, progress=progress)
        except Exception as exc:                  # noqa: BLE001 - isolate it
            results[source] = {"source": source, "error": f"{type(exc).__name__}: {exc}"}
            graph.con.execute(
                "INSERT INTO findings(rule, severity, subject, source_id, detail)"
                " VALUES ('source_build_failed', 2, ?, ?, ?)",
                [source, source, f'{{"error": "{_esc_json(str(exc))}"}}'])
    return results


def clear_source(graph, source: str, drop_tables: bool = True) -> None:
    """Remove one source's rows (and, unless told otherwise, its
    materialised tables) before a rebuild."""
    if not source:
        return
    slug = source_slug(source)
    graph.con.execute("DELETE FROM edges WHERE source_id = ?", [source])
    graph.con.execute("DELETE FROM nodes WHERE source_id = ?", [source])
    graph.con.execute("DELETE FROM classes WHERE source_id = ?", [source])
    graph.con.execute("DELETE FROM relations WHERE source_id = ?", [source])
    graph.con.execute("DELETE FROM findings WHERE source_id = ?", [source])
    graph.con.execute("DELETE FROM build_info WHERE key = ?",
                      [_signature_key(slug)])
    graph.con.execute("DELETE FROM sources WHERE source_id = ?", [source])
    if drop_tables:
        _drop_prefix(graph, f"{SRC}_{slug}__")
        _drop_prefix(graph, f"keyed_{slug}__")


# ------------------------------------------------------------- registry
def _set_info(graph, key: str, value: str) -> None:
    graph.con.execute("DELETE FROM build_info WHERE key = ?", [key])
    graph.con.execute("INSERT INTO build_info(key, value) VALUES (?, ?)",
                      [key, value])


def _register_source(graph, schema: Schema, source: str) -> None:
    graph.con.execute("DELETE FROM sources WHERE source_id = ?", [source])
    graph.con.execute(
        "INSERT INTO sources(source_id, name, origin, kind, status)"
        " VALUES (?, ?, ?, ?, 'building')",
        [source, source, schema.origin,
         "files" if schema.readers else "database"])


def _register(graph, onto: Ontology, source: str, slug: str) -> tuple[dict, dict]:
    """Store the ontology next to the data it describes, so the graph is
    self-explaining: anyone opening the file can see what the codes mean.

    Codes are derived from `source|name`, not from the ontology's own numbering,
    so two sources cannot collide on a code and a rebuild cannot renumber the
    existing rows.
    """
    graph.con.execute("DELETE FROM classes WHERE source_id = ?", [source])
    graph.con.execute("DELETE FROM relations WHERE source_id = ?", [source])
    taken = {r[0] for r in graph.sql(
        "SELECT code FROM classes UNION SELECT code FROM relations")}

    class_codes: dict[str, int] = {}
    for c in onto.classes.values():
        code = stable_code(f"{slug}|{c.name}", taken)
        taken.add(code)
        class_codes[c.name] = code
        graph.con.execute(
            "INSERT INTO classes(code, name, source_id, source_table,"
            " key_column, provenance, time_column) VALUES (?,?,?,?,?,?,?)",
            [code, c.name, source, c.table, c.key, c.provenance,
             c.time_column])

    relation_codes: dict[str, int] = {}
    for r in onto.relations.values():
        code = stable_code(f"{slug}|{r.domain}.{r.name}", taken)
        taken.add(code)
        relation_codes[r.name] = code
        graph.con.execute(
            "INSERT INTO relations(code, name, domain, range, source_id,"
            " provenance, confidence) VALUES (?,?,?,?,?,?,?)",
            [code, r.name, r.domain, r.range, source, r.provenance,
             r.confidence])
    return class_codes, relation_codes


# ------------------------------------------------------------ materialise
def _origin_kind(origin: str) -> tuple[str, str]:
    """(TYPE clause, extension to install) for a database origin."""
    low = (origin or "").lower()
    if low.startswith(("postgres://", "postgresql://")):
        return "TYPE postgres, ", "postgres"
    if low.startswith("mysql://"):
        return "TYPE mysql, ", "mysql"
    if low.endswith((".db", ".sqlite", ".sqlite3")):
        return "TYPE sqlite, ", "sqlite"
    return "", ""


def _materialise(graph, schema: Schema, source: str, slug: str,
                 say=lambda _: None) -> None:
    """Copy every source table into the graph.

    File sources are read through the reader recorded by `connect`; database
    sources are attached read-only just long enough to copy and then detached.
    After this the graph owns its data, which is what makes the second process
    work without rebuilding.
    """
    _drop_prefix(graph, f"{SRC}_{slug}__")
    # The row-numbered copies of keyless tables are rebuilt from these, so
    # they go too: reading a stale one would re-number from old rows.
    _drop_prefix(graph, f"keyed_{slug}__")

    if schema.readers:
        for table, reader in schema.readers.items():
            t = time.monotonic()
            dest = _dest(slug, table)
            query = reader.strip()
            # A file reader is a table function (`read_csv(...)`); an RDF
            # reader is a full query (`WITH ... SELECT`), which is valid after
            # AS but not after FROM.
            if query.upper().startswith(("WITH", "SELECT")):
                statement = f"CREATE TABLE {dest} AS {query}"
            else:
                statement = f"CREATE TABLE {dest} AS SELECT * FROM {query}"
            try:
                graph.con.execute(statement)
            except Exception as exc:              # noqa: BLE001 - per table
                raise RuntimeError(
                    f"could not materialise {table!r} from the reader: {exc}"
                ) from exc
            say(f"    loaded {table:<34} {time.monotonic() - t:5.1f}s")
        return

    origin = schema.origin
    if not origin:
        return                                  # caller made tables visible

    alias = f"att_{slug}"
    if graph.one("SELECT count(*) FROM duckdb_databases() "
                 "WHERE database_name = ?", [alias]):
        graph.con.execute(f"DETACH {qi(alias)}")
    kind, ext = _origin_kind(origin)
    if ext:
        graph.con.execute(f"INSTALL {ext}; LOAD {ext}")
    graph.con.execute(
        f"ATTACH '{_esc(origin)}' AS {qi(alias)} ({kind}READ_ONLY)")
    try:
        for table in schema.tables:
            t = time.monotonic()
            graph.con.execute(
                f"CREATE TABLE {_dest(slug, table.name)} AS "
                f"SELECT * FROM {qi(alias)}.{qi(table.name)}")
            say(f"    copied {table.name:<34} {time.monotonic() - t:5.1f}s")
    finally:
        graph.con.execute(f"DETACH {qi(alias)}")


def _materialise_keys(graph, schema: Schema, onto: Ontology, source: str,
                      slug: str, say=lambda _: None) -> None:
    """Give keyless tables a real, stored row number.

    A table with no unique column still has to become nodes AND be the source
    of edges. Computing `row_number()` separately in each query is wrong twice
    over: the column does not exist in the raw table at all, and two
    row_number() calls are not guaranteed to produce the same order, so ids
    could silently drift between the nodes and the edges that point at them.

    Storing it once removes both problems, and makes the ids stable across
    rebuilds as a side effect.
    """
    for cls in onto.classes.values():
        if not cls.key_is_synthetic:
            continue
        src = _ref(graph, schema, cls.table, source, slug)
        dest = _keyed(slug, cls.table)
        graph.con.execute(f"DROP TABLE IF EXISTS {dest}")
        graph.con.execute(
            f"CREATE TABLE {dest} AS SELECT *, "
            f"CAST(row_number() OVER () AS VARCHAR) AS __row FROM {src}")
        say(f"    numbered rows of {cls.table} (it has no key of its own)")


# ---------------------------------------------------------------- naming
def source_name(schema: Schema, source: str = "") -> str:
    return source or schema.name


def table_ref(graph, schema: Schema, table: str, source: str = "") -> str:
    """How to address a source table in SQL, whatever kind of source it is.

    Every table is materialised by `build`; the keyless rewrite is preferred
    when it exists. Anything that wants to read source rows — the builder, the
    metric compiler, the row lookup — asks here rather than assuming a shape.
    """
    src = source_name(schema, source)
    return _ref(graph, schema, table, src, source_slug(src))


def _ref(graph, schema: Schema, table: str, source: str, slug: str) -> str:
    keyed = f"keyed_{slug}__{table}"
    if _table_exists(graph, keyed):
        return qi(keyed)
    dest = f"{SRC}_{slug}__{table}"
    if _table_exists(graph, dest):
        return qi(dest)
    # Before a build, or for a source whose build failed, name the table the
    # build would create; the caller gets a clear "table not found" instead of
    # a silent empty answer.
    return qi(dest)


def _raw_ref(graph, schema: Schema, table: str, source: str = "") -> str:
    return table_ref(graph, schema, table, source)


# ---------------------------------------------------------------- nodes
def _nodes(graph, schema: Schema, cls, code: int, source: str, slug: str,
           echo: bool) -> int:
    """One node per row. Columns that are not keys or links become props, so
    the node carries enough to be readable without re-reading the source.
    """
    tbl = _ref(graph, schema, cls.table, source, slug)

    # _materialise_keys has already stored a __row column for a keyless table,
    # so both this query and the edge query below read the same values.
    if cls.key_is_synthetic:
        key = qi("__row")
    elif len(cls.key_columns) > 1:
        # A composite key is one identity spread over several columns, joined
        # with a separator that cannot appear in a value.
        parts = f" || '{KEY_SEP}' || ".join(
            f"coalesce(CAST({qi(c)} AS VARCHAR), '')" for c in cls.key_columns)
        key = f"({parts})"
    else:
        key = qi(cls.key)

    prop_cols = list(cls.measures) + list(cls.dimensions)
    if cls.time_column:
        prop_cols.append(cls.time_column)
    props = ("to_json({" +
             ", ".join(f"{ql(c)}: {qi(c)}" for c in prop_cols) + "})") \
        if prop_cols else "NULL"

    # LEFT JOIN + IS NULL, not ON CONFLICT DO NOTHING: an anti-join is a
    # single hash build; ON CONFLICT probes the primary-key index once per row
    # and each insert got slower as the table filled.
    sql = f"""
    INSERT INTO nodes (id, class, nkey, source_id, props)
    SELECT {_node_id(code, source, 'q.k')}, {code}, q.k, {ql(source)}, q.p
    FROM (
        SELECT CAST({key} AS VARCHAR) AS k, {props} AS p,
               row_number() OVER (PARTITION BY CAST({key} AS VARCHAR)) AS rn
        FROM {tbl}
    ) q
    LEFT JOIN nodes ex ON ex.source_id = {ql(source)}
                      AND ex.class = {code} AND ex.nkey = q.k
    WHERE q.rn = 1 AND q.k IS NOT NULL AND q.k <> '' AND ex.id IS NULL"""
    if echo:
        print(sql)
    before = graph.one("SELECT count(*) FROM nodes") or 0
    graph.con.execute(sql)
    return (graph.one("SELECT count(*) FROM nodes") or 0) - before


# ---------------------------------------------------------------- edges
def _edges(graph, schema: Schema, onto: Ontology, rel, code: int,
           class_codes: dict, source: str, slug: str,
           echo: bool) -> tuple[int, int]:
    src_cls = onto.classes[rel.domain]
    dst_cls = onto.classes[rel.range]
    tbl = _ref(graph, schema, src_cls.table, source, slug)

    # The row's own time, if it has one. Without it the edge is open-ended,
    # which is the honest encoding of "true, but we do not know since when".
    # An edge with no date is valid for all time, which is '-infinity', not
    # NULL. NULL would say "unknown" and then fail the primary key; a sentinel
    # like 1970-01-01 would claim the link STARTED then, which is an invented
    # fact. -infinity reads correctly in every point-in-time query.
    tcol = src_cls.time_column
    forever = "'-infinity'::TIMESTAMP"
    vfrom = (f"coalesce(TRY_CAST({qi(tcol)} AS TIMESTAMP), {forever})"
             if tcol else forever)

    if src_cls.key_is_synthetic:
        src_key = f"CAST({qi('__row')} AS VARCHAR)"
    elif len(src_cls.key_columns) > 1:
        parts = f" || '{KEY_SEP}' || ".join(
            f"coalesce(CAST({qi(c)} AS VARCHAR), '')"
            for c in src_cls.key_columns)
        src_key = f"({parts})"
    else:
        src_key = f"CAST({qi(src_cls.key)} AS VARCHAR)"
    dst_key = f"CAST({qi(rel.column)} AS VARCHAR)"

    # Note the joins: ON n.nkey = ..., never ON n.id = node_id(...).
    sql = f"""
    INSERT INTO edges (src, rel, dst, source_id, valid_from, valid_to)
    SELECT a.id, {code}, b.id, {ql(source)}, q.vf, NULL
    FROM (
        SELECT {src_key} AS sk, {dst_key} AS dk, {vfrom} AS vf
        FROM {tbl}
        WHERE {dst_key} IS NOT NULL
    ) q
    JOIN nodes a ON a.source_id = {ql(source)}
                AND a.class = {class_codes[rel.domain]}
                AND a.nkey = q.sk
    JOIN nodes b ON b.source_id = {ql(source)}
                AND b.class = {class_codes[rel.range]}
                AND b.nkey = q.dk
    LEFT JOIN edges ex ON ex.src = a.id AND ex.rel = {code}
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
        LEFT JOIN nodes b ON b.source_id = {ql(source)}
                         AND b.class = {class_codes[rel.range]}
                         AND b.nkey = q.dk
        WHERE b.id IS NULL""") or 0
    if missed:
        graph.con.execute(
            "INSERT INTO findings(rule, severity, subject, source_id, detail) "
            "VALUES ('orphan_reference', 2, ?, ?, ?)",
            [rel.name, source,
             f'{{"rows": {missed}, "relation": "{rel.name}", '
             f'"points_at": "{rel.range}", "source": "{_esc_json(source)}"}}'])
    return made, missed


def _class_code(graph, source: str, name: str) -> int:
    return graph.one(
        "SELECT code FROM classes WHERE source_id = ? AND name = ?",
        [source, name]) or 0


def _triple_edges(graph, schema: Schema, onto, source: str, slug: str,
                  class_codes: dict, relation_codes: dict,
                  echo: bool) -> tuple[int, int]:
    """Turn a triples table (head, relation, tail) into typed Entity edges.

    The generic edge builder needs a target column on the source row; a triple
    row has the relation in a column instead. This pass resolves head/tail to
    Entity nodes once, then inserts one edge per predicate code.
    """
    spec = schema.triples or {}
    entity_cls = onto.class_for_table(spec.get("entities", ""))
    if entity_cls is None:
        return 0, 0
    entity_code = class_codes.get(entity_cls.name)
    if entity_code is None:
        return 0, 0
    triples_ref = _ref(graph, schema, spec["triples"], source, slug)
    relations_ref = _ref(graph, schema, spec["relations"], source, slug)

    graph.con.execute("DROP TABLE IF EXISTS triple_stage")
    graph.con.execute(f"""
        CREATE TEMP TABLE triple_stage AS
        SELECT DISTINCT h.id AS src, t.id AS dst,
               CAST(rel.name AS VARCHAR) AS relname
        FROM {triples_ref} q
        JOIN {relations_ref} rel
          ON CAST(rel.id AS VARCHAR) = CAST(q.relation AS VARCHAR)
        JOIN nodes h ON h.source_id = ? AND h.class = ?
                    AND h.nkey = CAST(q.head AS VARCHAR)
        JOIN nodes t ON t.source_id = ? AND t.class = ?
                    AND t.nkey = CAST(q.tail AS VARCHAR)""",
        [source, entity_code, source, entity_code])

    made = 0
    for rel in onto.relations.values():
        if not getattr(rel, "custom", False):
            continue
        code = relation_codes[rel.name]
        before = graph.one("SELECT count(*) FROM edges") or 0
        graph.con.execute("""
            INSERT INTO edges(src, rel, dst, source_id, valid_from, valid_to)
            SELECT s.src, ?, s.dst, ?, '-infinity'::TIMESTAMP, NULL
            FROM triple_stage s
            LEFT JOIN edges ex ON ex.src = s.src AND ex.rel = ?
                              AND ex.dst = s.dst
                              AND ex.valid_from = '-infinity'::TIMESTAMP
            WHERE ex.src IS NULL AND s.relname = ?""",
            [code, source, code, rel.source_name or rel.name])
        made += (graph.one("SELECT count(*) FROM edges") or 0) - before

    # Rows that could not become an edge: unknown relation id, missing head or
    # tail node. Counted once, never silently dropped.
    missed = graph.one(f"""
        SELECT count(*) FROM {triples_ref} q
        LEFT JOIN {relations_ref} rel
          ON CAST(rel.id AS VARCHAR) = CAST(q.relation AS VARCHAR)
        LEFT JOIN nodes h ON h.source_id = ? AND h.class = ?
                         AND h.nkey = CAST(q.head AS VARCHAR)
        LEFT JOIN nodes t ON t.source_id = ? AND t.class = ?
                         AND t.nkey = CAST(q.tail AS VARCHAR)
        WHERE q.head IS NULL OR q.tail IS NULL OR q.relation IS NULL
           OR rel.id IS NULL OR h.id IS NULL OR t.id IS NULL""",
        [source, entity_code, source, entity_code]) or 0
    graph.con.execute("DROP TABLE IF EXISTS triple_stage")
    if missed:
        graph.con.execute(
            "INSERT INTO findings(rule, severity, subject, source_id, detail)"
            " VALUES ('orphan_reference', 2, 'triples', ?, ?)",
            [source, f'{{"rows": {missed}, "relation": "triples"}}'])
    return made, missed


# ------------------------------------------------------------ read back
def source_rows(graph, schema: Schema, table: str, limit: int = 50,
                source: str = "") -> tuple[list[str], list[tuple]]:
    """A sample of the ACTUAL rows behind a table.

    Counts and hashed ids are abstractions. Showing the real row is what turns
    "1,550,922 things" from a claim into something a person can check.
    """
    src = source_name(schema, source)
    ref = _ref(graph, schema, table, src, source_slug(src))
    cols, rows = graph.query_with_columns(
        f"SELECT * FROM {ref} LIMIT {int(limit)}")
    return [c for c in cols if c != "__row"], \
           [tuple(v for c, v in zip(cols, r) if c != "__row") for r in rows]


def row_for(graph, schema: Schema, onto: Ontology, cls_name: str, key: str,
            source: str = "") -> dict:
    """The one source row a node came from, as {column: value}."""
    cls = onto.classes.get(cls_name)
    if cls is None:
        return {}
    src = source_name(schema, source)
    ref = _ref(graph, schema, cls.table, src, source_slug(src))
    if cls.key_is_synthetic:
        key_expr = qi("__row")
    elif len(cls.key_columns) > 1:
        key_expr = "(" + f" || '{KEY_SEP}' || ".join(
            f"coalesce(CAST({qi(c)} AS VARCHAR), '')"
            for c in cls.key_columns) + ")"
    else:
        key_expr = f"CAST({qi(cls.key)} AS VARCHAR)"
    cols, rows = graph.query_with_columns(
        f"SELECT * FROM {ref} WHERE {key_expr} = ? LIMIT 1", [str(key)])
    if not rows:
        return {}
    return {name: value for name, value in zip(cols, rows[0])
            if name != "__row"}


# ---------------------------------------------------------------- helpers
def qi(name: str) -> str:
    """Quote an identifier. Real exports have columns called `order`,
    `select`, and `it's_here`; unquoted or naively quoted, each one is a
    parser error rather than a column."""
    return '"' + str(name).replace('"', '""') + '"'


def ql(value: str) -> str:
    """Quote a string literal, doubling any embedded apostrophe."""
    return "'" + str(value).replace("'", "''") + "'"


def _node_id(code: int, source: str, key_expr: str) -> str:
    prefix = ql(f"{code}:{source}:")
    return (f"(md5_number_lower({prefix} || {key_expr}) "
            f"% 4611686018427387904)::BIGINT")


def _esc(value: str) -> str:
    return str(value).replace("'", "''")


def _esc_json(value: str) -> str:
    return (str(value).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", " "))
