"""Read any data source into one Schema. This is the only file that knows
what a particular source looks like.

    connect("shop.db")                     SQLite
    connect("data/")                       a folder of CSV / Parquet / Excel
    connect("sales.csv")                   one file
    connect("postgres://user@host/db")     Postgres
    connect("mysql://...")                 MySQL

One reader, not one per vendor. DuckDB attaches SQLite, Postgres and MySQL
and reads CSV, Parquet, JSON and Excel directly, so every source arrives
through the same code path and the layers above never learn the difference.

For a file with no declared schema, types are INFERRED from the values and
keys are inferred later by discovery. Both are marked as inferences - a
guess that reads like a fact is the one failure this system exists to
prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

from ontology.keys import pick_key, profile_sql
from ontology.rdf import RDF_TYPES, tables_for as rdf_tables
from ontology.schema import Column, ForeignKey, Schema, Table

# Extensions DuckDB reads directly. Anything else needs a real connector.
FILE_TYPES = {".csv": "read_csv", ".tsv": "read_csv", ".txt": "read_csv",
              ".parquet": "read_parquet", ".pq": "read_parquet",
              ".json": "read_json_auto", ".ndjson": "read_json_auto",
              ".xlsx": "read_xlsx", ".xls": "read_xlsx"}

DB_FILES = {".db", ".sqlite", ".sqlite3", ".duckdb"}


class SourceError(Exception):
    """Raised with an explanation a person can act on, never a stack trace."""


def connect(source: str, name: str | None = None) -> Schema:
    """Point this at anything. Get back a Schema."""
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute("SET enable_progress_bar = false")
    try:
        if re.match(r"^https?://", source, re.I):
            return _from_http(con, source, name)
        if re.match(r"^\w+://", source):
            return _from_url(con, source, name)
        p = Path(source)
        if not p.exists():
            raise SourceError(
                f"not found: {source}\n"
                f"  Give a file, a folder, or a database URL such as\n"
                f"  postgres://user:pass@host/dbname")
        if p.is_dir():
            return _from_folder(con, p, name)
        if p.suffix.lower() in DB_FILES:
            return _from_db_file(con, p, name)
        if p.suffix.lower() in RDF_TYPES:
            return _from_rdf_file(p, name or p.stem)
        if p.suffix.lower() in FILE_TYPES:
            return _from_files(con, [p], name or p.stem)
        raise SourceError(
            f"do not know how to read {p.suffix or 'a file with no extension'}\n"
            f"  Tabular: {', '.join(sorted(FILE_TYPES))}\n"
            f"  Graph:   {', '.join(sorted(RDF_TYPES))}\n"
            f"  Database files / URLs: {', '.join(sorted(DB_FILES))}, "
            f"postgres://, mysql://, snowflake://, databricks://\n"
            f"  Or an http(s) URL ending in one of the tabular/graph types.")
    finally:
        con.close()


# ------------------------------------------------------------------ files
def connect_many(sources: list[str],
                 names: list[str] | None = None) -> list[Schema]:
    """Read several sources. Each becomes its own Schema, so a bad source is
    isolated and the good ones still come through.

    `names` overrides the display name of each source (the build uses it as the
    source id). Default is the name `connect()` derives from the path.
    """
    out: list[Schema] = []
    for i, source in enumerate(sources):
        name = names[i] if names and i < len(names) else None
        out.append(connect(source, name=name))
    return out


def _from_folder(con, folder: Path, name: str | None) -> Schema:
    files, warnings = [], []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() in FILE_TYPES or f.suffix.lower() in RDF_TYPES:
            files.append(f)
        elif f.suffix.lower() in DB_FILES:
            warnings.append(
                f"ignored database file {f.name!r} inside the folder; "
                f"pass it directly to open it as its own source")
    if not files:
        raise SourceError(
            f"no readable files in {folder}\n"
            f"  Looking for: {', '.join(sorted(set(FILE_TYPES) | RDF_TYPES))}"
            + (f"\n  Warnings: {'; '.join(warnings)}" if warnings else ""))
    if len(files) == 1 and files[0].suffix.lower() in RDF_TYPES:
        return _from_rdf_file(files[0], name or folder.name)
    triple_schema = _from_triple_folder(con, folder, files, name)
    if triple_schema is not None:
        return triple_schema
    return _from_files(con, files, name or folder.name, warnings)


def _from_triple_folder(con, folder: Path, files: list[Path],
                        name: str | None) -> Schema | None:
    """A folder shaped like a triple store: entities + relations + splits.

    This is the common CSKG-style export: `entities.txt` (id, label),
    `relations.txt` (id, name), and `triples.txt` / `train.txt` / `test.txt` /
    `valid.txt` (head, relation, tail), all tab separated with no header.

    Generic table discovery would make six unrelated classes and zero links.
    The right answer is one Entity class and one relation per predicate, so the
    folder is detected and read as a graph. Returns None when the shape does not
    match, letting the normal file reader handle it.
    """
    by_stem = {f.stem.lower(): f for f in files}
    if "entities" not in by_stem or "relations" not in by_stem:
        return None
    splits = [by_stem[s] for s in ("triples", "train", "test", "valid")
              if s in by_stem]
    if not splits:
        return None

    def ref(path: Path) -> str:
        return f"{FILE_TYPES[path.suffix.lower()]}('{_escape(str(path))}')"

    entities_sql = f"SELECT column0 AS id, column1 AS label FROM {ref(by_stem['entities'])}"
    relations_sql = f"SELECT column0 AS id, column1 AS name FROM {ref(by_stem['relations'])}"
    triples_parts = [
        f"SELECT column0 AS head, column1 AS relation, column2 AS tail "
        f"FROM {ref(path)}" for path in splits]
    triples_sql = " UNION ALL ".join(triples_parts)

    # Confirm the shape before committing to it; otherwise fall back.
    try:
        entities_cols = [r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM ({entities_sql})").fetchall()]
        relations_cols = [r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM ({relations_sql})").fetchall()]
        triples_cols = [r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM ({triples_sql})").fetchall()]
    except Exception:                              # noqa: BLE001 - not this shape
        return None
    if entities_cols[:2] != ["id", "label"] or relations_cols[:2] != ["id", "name"]:
        return None
    if triples_cols[:3] != ["head", "relation", "tail"]:
        return None

    try:
        entity_rows = con.execute(
            f"SELECT count(*) FROM ({entities_sql})").fetchone()[0]
        relation_rows = con.execute(
            f"SELECT count(*) FROM ({relations_sql})").fetchone()[0]
        triple_rows = con.execute(
            f"SELECT count(*) FROM ({triples_sql})").fetchone()[0]
        relation_names = [r[1] for r in con.execute(
            f"SELECT DISTINCT id, name FROM ({relations_sql}) "
            f"ORDER BY id").fetchall()]
    except Exception as exc:                       # noqa: BLE001
        raise SourceError(f"could not read the triple folder {folder}: {exc}") from exc

    tables = [
        Table(name="entities",
              columns=[Column("id", "VARCHAR", nullable=False),
                       Column("label", "VARCHAR")],
              primary_key=["id"], row_count=entity_rows),
        Table(name="relations",
              columns=[Column("id", "VARCHAR"), Column("name", "VARCHAR")],
              hidden=True, row_count=relation_rows),
        Table(name="triples",
              columns=[Column("head", "VARCHAR"), Column("relation", "VARCHAR"),
                       Column("tail", "VARCHAR")],
              hidden=True, row_count=triple_rows),
    ]
    return Schema(
        tables=tables, name=name or folder.name, origin=str(folder),
        readers={"entities": entities_sql, "relations": relations_sql,
                 "triples": triples_sql},
        warnings=[f"{folder.name}: detected a triple-store folder "
                  f"({len(splits)} triple file(s), {relation_rows} relations); "
                  f"Entity nodes are linked with typed edges"],
        triples={"entities": "entities", "relations": "relations",
                 "triples": "triples", "relation_names": relation_names})


def _from_rdf_file(path: Path, name: str,
                   prefix: str = "") -> Schema:
    """A graph file becomes two relational tables with declared keys.

    The readers are SQL over the file itself, so a 4 GB N-Triples file is never
    loaded into Python; the build copies it once per table.
    """
    try:
        tables, readers = rdf_tables(path, prefix=prefix)
    except ValueError as exc:                      # rdflib missing, etc.
        raise SourceError(str(exc)) from exc
    except Exception as exc:                       # noqa: BLE001 - bad file
        raise SourceError(f"could not read {path.name}: {exc}") from exc
    return Schema(tables=tables, name=name, origin=str(path), readers=readers,
                  warnings=[
                      f"{path.name}: parsed as RDF ({'/'.join(sorted(RDF_TYPES))}); "
                      f"entities and links are derived from the triples"])


def _from_http(con, url: str, name: str | None) -> Schema:
    """Download an http(s) file, then read it by its extension.

    The download goes to a temporary file; large streams are not held in
    memory. A URL without a supported extension is refused with the same list
    as a local file.
    """
    import tempfile
    import urllib.error
    import urllib.parse
    import urllib.request

    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name or "download"
    suffix = Path(filename).suffix.lower()
    if suffix not in FILE_TYPES and suffix not in RDF_TYPES and suffix not in DB_FILES:
        raise SourceError(
            f"the URL has an unsupported file type {suffix or '(none)'!r}\n"
            f"  Tabular: {', '.join(sorted(FILE_TYPES))}\n"
            f"  Graph:   {', '.join(sorted(RDF_TYPES))}")
    folder = Path(tempfile.mkdtemp(prefix="ml_http_"))
    downloaded = folder / filename
    try:
        with urllib.request.urlopen(url, timeout=120) as response, \
                downloaded.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except (urllib.error.URLError, OSError) as exc:
        raise SourceError(f"could not download {url}: {exc}") from exc
    try:
        if suffix in RDF_TYPES:
            schema = _from_rdf_file(downloaded, name or Path(parsed.path).stem)
        elif suffix in DB_FILES:
            schema = _from_db_file(con, downloaded, name or Path(parsed.path).stem)
        else:
            schema = _from_files(con, [downloaded],
                                 name or Path(parsed.path).stem)
        schema.origin = url
        return schema
    except SourceError:
        raise
    except Exception as exc:                       # noqa: BLE001
        raise SourceError(f"could not read the downloaded file: {exc}") from exc


def _from_files(con, files: list[Path], name: str,
                warnings: list[str] | None = None) -> Schema:
    """Read a list of files into one Schema.

    One unreadable file must not lose the other ninety-nine. Each file is read
    on its own; a failure is recorded as a warning and skipped. CSV gets one
    retry with `ignore_errors` because free-text exports routinely contain a
    malformed row, and one bad line should not cost the whole source.
    """
    tables: list[Table] = []
    readers: dict[str, str] = {}
    warnings = list(warnings or [])
    used_names: set[str] = set()

    for f in files:
        # DuckDB is happy to read a zero-byte file as a one-column, zero-row
        # table. That is noise, not data; skip it and say so.
        try:
            if f.stat().st_size == 0:
                warnings.append(f"skipped {f.name}: the file is empty")
                continue
        except OSError:                             # pragma: no cover
            pass

        suffix = f.suffix.lower()
        if suffix in RDF_TYPES:
            prefix = f.stem if len(files) > 1 else ""
            try:
                rdf_tables_list, rdf_readers = rdf_tables(f, prefix=prefix)
            except ValueError as exc:                # rdflib missing
                warnings.append(f"skipped {f.name}: {exc}")
                continue
            except Exception as exc:                 # noqa: BLE001 - bad RDF
                warnings.append(f"skipped {f.name}: {exc}")
                continue
            renames: dict[str, str] = {}
            for table in rdf_tables_list:
                base, candidate, n = table.name, table.name, 2
                while candidate in used_names:
                    candidate = f"{base}_{n}"
                    n += 1
                used_names.add(candidate)
                readers[candidate] = rdf_readers[table.name]
                renames[table.name] = candidate
                table.name = candidate
                tables.append(table)
            if renames:
                for table in rdf_tables_list:
                    table.foreign_keys = [
                        ForeignKey(fk.column,
                                   renames.get(fk.ref_table, fk.ref_table),
                                   fk.ref_column)
                        for fk in table.foreign_keys]
            warnings.append(
                f"{f.name}: read as RDF; entities and links are derived "
                f"from the triples")
            continue

        reader = FILE_TYPES[suffix]
        ref = f"{reader}('{_escape(str(f))}')"
        try:
            cols = con.execute(f"DESCRIBE SELECT * FROM {ref}").fetchall()
        except Exception as first:                # noqa: BLE001 - per file
            if reader == "read_csv":
                tolerant = f"read_csv('{_escape(str(f))}', ignore_errors = true)"
                try:
                    cols = con.execute(
                        f"DESCRIBE SELECT * FROM {tolerant}").fetchall()
                    ref = tolerant
                    warnings.append(
                        f"{f.name}: malformed row(s) ignored so the file "
                        f"could still be read")
                except Exception:                 # noqa: BLE001
                    warnings.append(f"skipped {f.name}: {first}")
                    continue
            else:
                warnings.append(f"skipped {f.name}: {first}")
                continue

        if not cols:
            warnings.append(f"skipped {f.name}: no columns")
            continue
        try:
            rows = con.execute(f"SELECT count(*) FROM {ref}").fetchone()[0]
        except Exception as exc:                  # noqa: BLE001 - per file
            warnings.append(f"skipped {f.name}: {exc}")
            continue

        # Two files can share a stem (`orders.csv`, `orders.parquet`). Both are
        # legitimate; the second becomes orders_2 instead of silently
        # overwriting the first.
        base = (f.stem.lower() or "table")
        table_name, n = base, 2
        while table_name in used_names:
            table_name = f"{base}_{n}"
            n += 1
        used_names.add(table_name)

        readers[table_name] = ref
        # A file declares nothing - no key, no nullability. Both are readable
        # by counting, in ONE pass per file: on a million-row CSV a query per
        # column would be minutes instead of seconds.
        names = [c[0] for c in cols]
        stats: dict[str, tuple] = {}
        if rows:
            try:
                got = con.execute(profile_sql(table_name, names, ref)).fetchone()
                for i, column_name in enumerate(names):
                    # distinct, non-null
                    stats[column_name] = (got[1 + i * 2], got[2 + i * 2])
            except Exception:                     # noqa: BLE001
                # Profiling is an optimisation; never fail the read.
                warnings.append(
                    f"{f.name}: could not profile every column; keys may be "
                    f"less certain")

        columns = []
        for c in cols:
            d, nn = stats.get(c[0], (None, None))
            columns.append(Column(c[0], str(c[1]).upper(),
                                  nullable=(nn is None or nn < rows),
                                  distinct=d))
        t = Table(name=table_name, columns=columns,
                  primary_key=[], foreign_keys=[], row_count=rows)
        found = pick_key(t)
        if found:
            t.primary_key = [found]
        tables.append(t)

    if not tables:
        raise SourceError(
            "none of the files could be read as a table\n"
            "  " + "\n  ".join(warnings or ["(no warnings)"]))
    return Schema(tables=tables, name=name,
                  origin=str(files[0].parent if len(files) > 1 else files[0]),
                  readers=readers, warnings=warnings)


# -------------------------------------------------------------- databases
def _from_db_file(con, path: Path, name: str | None) -> Schema:
    if path.suffix.lower() == ".duckdb":
        con.execute(f"ATTACH '{_escape(str(path))}' AS src (READ_ONLY)")
        return _from_attached(con, "src", name or path.stem,
                              origin=str(path))
    con.execute("INSTALL sqlite; LOAD sqlite")
    con.execute(f"ATTACH '{_escape(str(path))}' AS src (TYPE sqlite, READ_ONLY)")
    return _from_attached(con, "src", name or path.stem,
                          sqlite_file=path, origin=str(path))


def _from_url(con, url: str, name: str | None) -> Schema:
    kind = url.split("://", 1)[0].lower()
    if kind in ("snowflake", "databricks", "databricks+sql"):
        from ontology.connectors import CloudConnectorError, schema_from_url
        try:
            return schema_from_url(con, url, name)
        except CloudConnectorError as exc:
            raise SourceError(str(exc)) from exc
        except Exception as exc:                  # noqa: BLE001 - driver error
            raise SourceError(
                f"could not connect to {kind}: {type(exc).__name__}: {exc}\n"
                f"  Check the URL, credentials and that the driver is "
                f"installed (see docs/API.md).") from exc
    ext = {"postgres": "postgres", "postgresql": "postgres",
           "mysql": "mysql"}.get(kind)
    if not ext:
        raise SourceError(
            f"unsupported database {kind!r}\n"
            f"  Supported URLs: postgres://, postgresql://, mysql://, "
            f"snowflake://, databricks://\n"
            f"  For anything else, export to Parquet or CSV and point at the "
            f"folder.")
    try:
        con.execute(f"INSTALL {ext}; LOAD {ext}")
        con.execute(f"ATTACH '{_escape(url)}' AS src (TYPE {ext}, READ_ONLY)")
    except Exception as e:
        raise SourceError(f"could not connect to {kind}: {e}") from e
    return _from_attached(con, "src", name or kind, origin=url)


def _from_attached(con, db: str, name: str,
                   sqlite_file: Path | None = None,
                   origin: str = '') -> Schema:
    rows = con.execute("""
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_catalog = ?
        ORDER BY table_name, ordinal_position""", [db]).fetchall()
    if not rows:
        raise SourceError(f"no tables found in {name}")

    by_table: dict[str, list[Column]] = {}
    for t, c, ty, nullable in rows:
        by_table.setdefault(t, []).append(
            Column(c, str(ty).upper(), str(nullable).upper() != "NO"))

    # Keys come from the source's own catalogue. DuckDB does not expose a
    # SQLite file's constraints through information_schema, so that one case
    # is read from SQLite itself rather than guessed at - a declared key is
    # worth far more than an inferred one and should not be thrown away.
    keys = _sqlite_keys(sqlite_file) if sqlite_file else _duck_keys(con, db)

    tables = []
    for t, cols in by_table.items():
        pk, fks = keys.get(t, ([], []))
        try:
            n = con.execute(f'SELECT count(*) FROM "{db}"."{t}"').fetchone()[0]
        except Exception:
            n = None
        tables.append(Table(name=t, columns=cols, primary_key=pk,
                            foreign_keys=fks, row_count=n))
    return Schema(tables=tables, name=name, origin=origin or '')


def _sqlite_keys(path: Path) -> dict[str, tuple[list[str], list[ForeignKey]]]:
    import sqlite3
    out: dict[str, tuple[list[str], list[ForeignKey]]] = {}
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        for t in names:
            pk = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")') if r[5]]
            fks = [ForeignKey(r[3], r[2], r[4] or "id")
                   for r in con.execute(f'PRAGMA foreign_key_list("{t}")')]
            out[t] = (pk, fks)
    finally:
        con.close()
    return out


def _duck_keys(con, db: str) -> dict[str, tuple[list[str], list[ForeignKey]]]:
    out: dict[str, tuple[list[str], list[ForeignKey]]] = {}
    try:
        rows = con.execute("""
            SELECT table_name, constraint_type, constraint_column_names,
                   referenced_table, referenced_column_names
            FROM duckdb_constraints() WHERE database_name = ?""",
                           [db]).fetchall()
    except Exception:
        return out
    for t, kind, cols, ref_t, ref_c in rows:
        pk, fks = out.get(t, ([], []))
        if str(kind).upper().startswith("PRIMARY"):
            pk = list(cols or [])
        elif str(kind).upper().startswith("FOREIGN") and ref_t:
            for i, c in enumerate(cols or []):
                rc = (ref_c or ["id"])[i] if i < len(ref_c or []) else "id"
                fks.append(ForeignKey(c, ref_t, rc))
        out[t] = (pk, fks)
    return out


def _escape(s: str) -> str:
    return s.replace("'", "''")
