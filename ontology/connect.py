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
        if p.suffix.lower() in FILE_TYPES:
            return _from_files(con, [p], name or p.stem)
        raise SourceError(
            f"do not know how to read {p.suffix or 'a file with no extension'}\n"
            f"  Readable: {', '.join(sorted(FILE_TYPES))}, "
            f"{', '.join(sorted(DB_FILES))}, or a database URL")
    finally:
        con.close()


# ------------------------------------------------------------------ files
def _from_folder(con, folder: Path, name: str | None) -> Schema:
    files = [f for f in sorted(folder.iterdir())
             if f.is_file() and f.suffix.lower() in FILE_TYPES]
    if not files:
        raise SourceError(
            f"no readable files in {folder}\n"
            f"  Looking for: {', '.join(sorted(FILE_TYPES))}")
    return _from_files(con, files, name or folder.name)


def _from_files(con, files: list[Path], name: str) -> Schema:
    tables, readers = [], {}
    for f in files:
        reader = FILE_TYPES[f.suffix.lower()]
        ref = f"{reader}('{_escape(str(f))}')"
        try:
            cols = con.execute(f"DESCRIBE SELECT * FROM {ref}").fetchall()
            rows = con.execute(f"SELECT count(*) FROM {ref}").fetchone()[0]
        except Exception as e:
            raise SourceError(f"could not read {f.name}: {e}") from e
        readers[f.stem.lower()] = ref
        tables.append(Table(
            name=f.stem.lower(),
            # A file declares no nullability, so every column is nullable
            # until something proves otherwise. Claiming NOT NULL here would
            # make the rule that checks it fire on data we never inspected.
            columns=[Column(c[0], str(c[1]).upper(), nullable=True)
                     for c in cols],
            primary_key=[], foreign_keys=[], row_count=rows))
    return Schema(tables=tables, name=name,
                  origin=str(files[0].parent if len(files) > 1 else files[0]),
                  readers=readers)


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
    ext = {"postgres": "postgres", "postgresql": "postgres",
           "mysql": "mysql"}.get(kind)
    if not ext:
        raise SourceError(
            f"unsupported database {kind!r}\n"
            f"  Supported URLs: postgres://, postgresql://, mysql://\n"
            f"  For others, export to Parquet or CSV and point at the folder.")
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
