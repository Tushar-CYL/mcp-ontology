"""Any database in: relational, document, graph, object store, lakehouse.

Everything arrives through the same door as a folder of files: the source is
read with its own driver, each table is written to a Parquet (or NDJSON)
file in a scratch folder, and the normal file reader turns that into a
Schema - with the keys the source itself declares kept, not re-guessed.
Discovery, the graph build, the ontology and the agents then never learn
which product the data came from.

URL forms and what reads them
-----------------------------
    postgres://user:pw@host/db            DuckDB's postgres extension, or the
    postgresql+psycopg://...              psycopg driver through SQLAlchemy
    mysql://user:pw@host/db               pymysql through SQLAlchemy
    mssql://user:pw@host/db?driver=...    pyodbc through SQLAlchemy
    oracle://user:pw@host/?service_name=  oracledb through SQLAlchemy
    sqlite:///C:/data/shop.db             SQLAlchemy (also works as a plain path)
    <dialect>[+driver]://...              anything SQLAlchemy has a dialect for:
                                          trino, clickhouse, bigquery, redshift,
                                          db2, teradata, access, ...
    odbc://DSN=Sales;UID=..;PWD=..        any ODBC driver, read through pyodbc
    odbc://Driver={SQL Server};Server=..  (raw ODBC connection string)
    mongodb://user:pw@host/db             pymongo; every collection is a table
    mongodb+srv://...
    neo4j://user:pw@host  bolt://...      the neo4j driver; nodes become
                                          entities, relationships become links
    s3://bucket/prefix  gs://  az://      DuckDB httpfs; every Parquet / CSV /
                                          JSON object under the prefix
    delta://C:/lake/orders  (or a folder  DuckDB's delta extension
      containing _delta_log)
    C:/data/sales.accdb  .mdb             the Access ODBC driver

A missing driver is reported with the exact package to install; nothing here
is imported until a matching URL is used.
"""

from __future__ import annotations

import base64
import datetime as dt
import decimal
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BATCH = 50_000
SQLALCHEMY_ALIASES = {
    "postgres": "postgresql+psycopg", "postgresql": "postgresql+psycopg",
    "mysql": "mysql+pymysql", "mariadb": "mysql+pymysql",
    "mssql": "mssql+pyodbc", "sqlserver": "mssql+pyodbc",
    "oracle": "oracle+oracledb", "access": "access+pyodbc",
}
DRIVER_HINT = {
    "psycopg": "psycopg[binary]", "pymysql": "pymysql", "pyodbc": "pyodbc",
    "oracledb": "oracledb", "trino": "trino[sqlalchemy]", "clickhouse": "clickhouse-sqlalchemy",
    "bigquery": "sqlalchemy-bigquery", "redshift": "sqlalchemy-redshift", "db2": "ibm-db-sa",
    "teradata": "teradatasqlalchemy", "access": "sqlalchemy-access", "snowflake": "snowflake-sqlalchemy",
}
OBJECT_STORES = ("s3", "gs", "gcs", "az", "azure", "abfss", "r2")
MONGO = ("mongodb", "mongodb+srv")
NEO4J = ("neo4j", "neo4j+s", "neo4j+ssc", "bolt", "bolt+s", "bolt+ssc")
ACCESS_FILES = {".accdb", ".mdb"}


SUPPORTED_URLS = (
    "  Supported: postgres://, mysql://, mssql://, oracle://, sqlite://, odbc://, mongodb://,\n"
    "  neo4j://, bolt://, s3://, gs://, az://, delta://, snowflake://, databricks://,\n"
    "  and any SQLAlchemy dialect whose driver is installed (trino://, clickhouse://, ...)")


class AnyDbError(Exception):
    """A connector failure with a message a person can act on."""


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(name)).strip("_").lower() or "table"


def scratch(prefix: str) -> Path:
    """Where a source's copied tables live until the build has read them."""
    root = os.environ.get("STRATA_SCRATCH") or tempfile.gettempdir()
    return Path(tempfile.mkdtemp(prefix=f"strata_{prefix}_", dir=root))


def handles(url: str) -> bool:
    kind = url.split("://", 1)[0].lower() if "://" in url else ""
    return bool(kind) and kind not in ("http", "https", "file")


# -------------------------------------------------------------- parquet
def _pa_type(py_type):
    import pyarrow as pa
    return {int: pa.int64(), float: pa.float64(), bool: pa.bool_(), str: pa.string(),
            bytes: pa.binary(), dt.date: pa.date32(), dt.datetime: pa.timestamp("us"),
            dt.time: pa.string(), decimal.Decimal: pa.float64()}.get(py_type, pa.string())


def _coerce(value, py_type):
    if value is None:
        return None
    if py_type is dt.datetime:
        if isinstance(value, dt.datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        return None
    if py_type is dt.date:
        return value.date() if isinstance(value, dt.datetime) else value
    if py_type in (int, float, bool, bytes):
        try:
            return py_type(value)
        except (TypeError, ValueError):
            return None
    if py_type is decimal.Decimal:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, str) else str(value)


_KINDS = (bool, int, float, decimal.Decimal, dt.datetime, dt.date, dt.time, bytes, str)


def _infer(hint, values) -> type:
    """The Python type a column's values actually have. Drivers describe a
    column one way and hand back another (a legacy ODBC driver returns DATE
    as text); values decide, the description is only the fallback."""
    seen = set()
    for v in values:
        if v is None:
            continue
        for kind in _KINDS:
            if isinstance(v, kind):
                seen.add(kind)
                break
        else:
            seen.add(str)
    if not seen:
        return hint if hint in _KINDS else str
    if seen <= {int, bool}:
        return bool if seen == {bool} else int
    if seen <= {int, float, decimal.Decimal, bool}:
        return float
    if seen <= {dt.datetime, dt.date}:
        return dt.datetime if dt.datetime in seen else dt.date
    return next(iter(seen)) if len(seen) == 1 else str


def write_parquet(path: Path, columns: list[str], py_types: list, batches) -> int:
    """Stream row batches (lists of tuples) to one Parquet file. Returns rows."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    batches = iter(batches)
    first = next(batches, None)
    if first:
        py_types = [_infer(t, [r[i] for r in first]) for i, t in enumerate(py_types)]
    schema = pa.schema([(c, _pa_type(t)) for c, t in zip(columns, py_types)])
    total = 0
    with pq.ParquetWriter(str(path), schema) as writer:
        for rows in ([first] if first else []) + [None]:
            if rows is None:
                break
            arrays = [pa.array([_coerce(r[i], py_types[i]) for r in rows], type=schema[i].type)
                      for i in range(len(columns))]
            writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
            total += len(rows)
        for rows in batches:
            if not rows:
                continue
            arrays = [pa.array([_coerce(r[i], py_types[i]) for r in rows], type=schema[i].type)
                      for i in range(len(columns))]
            writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
            total += len(rows)
    return total


def _finish(con, folder: Path, name: str, url: str, keys: dict, warnings: list[str],
            counts: dict | None = None):
    """Files -> Schema, then put back the keys the source declared."""
    from ontology.connect import _from_files
    from ontology.schema import ForeignKey
    files = sorted(p for p in folder.iterdir() if p.suffix in (".parquet", ".ndjson"))
    if not files:
        raise AnyDbError(f"no tables were read from {_redact(url)}")
    schema = _from_files(con, files, name, warnings)
    schema.origin = _redact(url)
    by_name = {t.name: t for t in schema.tables}
    for table, (pk, fks) in keys.items():
        t = by_name.get(_safe(table))
        if t is None:
            continue
        cols = {c.name for c in t.columns}
        if pk and all(c in cols for c in pk):
            t.primary_key = list(pk)
        t.foreign_keys = [ForeignKey(c, _safe(rt), rc) for c, rt, rc in fks
                          if c in cols and _safe(rt) in by_name]
        if counts and table in counts and counts[table] is not None:
            t.row_count = counts[table]
    return schema


def _redact(url: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]*@", r"\1***@", url)


# ---------------------------------------------------------------- sqlite
def _sqlite_type(declared: str) -> type:
    """SQLite type affinity rules, enough to pick a Parquet type; values decide."""
    d = (declared or "").upper()
    if "INT" in d:
        return int
    if any(k in d for k in ("REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")):
        return float
    if "BOOL" in d:
        return bool
    if "BLOB" in d:
        return bytes
    return str


def sqlite_schema(con, path: Path, name: str | None):
    """A SQLite file through Python's own sqlite3: no DuckDB extension and no
    compiled driver, so it works where application control blocks both."""
    import sqlite3
    db = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    folder = scratch("sqlite")
    keys, counts, warnings = {}, {}, []
    try:
        objects = db.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if not objects:
            raise AnyDbError(f"no tables found in {path}")
        for table, kind in objects:
            q = '"' + table.replace('"', '""') + '"'
            info = db.execute(f"PRAGMA table_info({q})").fetchall()
            names = [r[1] for r in info]
            py_types = [_sqlite_type(r[2]) for r in info]
            pk = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5]]
            fks = [(r[3], r[2], r[4] or "id")
                   for r in db.execute(f"PRAGMA foreign_key_list({q})").fetchall()] if kind == "table" else []
            keys[table] = (pk, fks)
            out = folder / f"{_safe(table)}.parquet"
            try:
                cur = db.execute(f"SELECT * FROM {q}")

                def batches(cur=cur):
                    while True:
                        rows = cur.fetchmany(BATCH)
                        if not rows:
                            break
                        yield rows
                counts[table] = write_parquet(out, names, py_types, batches())
            except Exception as exc:               # noqa: BLE001 - per table
                out.unlink(missing_ok=True)
                warnings.append(f"skipped {table}: {type(exc).__name__}: {str(exc)[:200]}")
    finally:
        db.close()
    return _finish(con, folder, name or Path(path).stem, str(path), keys, warnings, counts)


# ----------------------------------------------------------- sqlalchemy
def normalise_sqlalchemy_url(url: str) -> str:
    kind, rest = url.split("://", 1)
    base = kind.lower().split("+", 1)[0]
    if "+" in kind:
        return url
    return f"{SQLALCHEMY_ALIASES.get(base, base)}://{rest}"


def sqlalchemy_schema(con, url: str, name: str | None):
    try:
        import sqlalchemy as sa
        from sqlalchemy import inspect
    except ImportError as exc:
        raise AnyDbError("install SQLAlchemy to read this database:  pip install sqlalchemy") from exc
    full = normalise_sqlalchemy_url(url)
    try:
        options = {"use_setinputsizes": False} if full.startswith("mssql+pyodbc") else {}
        engine = sa.create_engine(full, **options)
    except sa.exc.NoSuchModuleError as exc:
        driver = full.split("://", 1)[0].split("+")[-1]
        if driver not in DRIVER_HINT:
            # Not a database SQLAlchemy or we know: say what is supported
            # instead of inventing a package name to install.
            raise AnyDbError(f"unknown kind of database URL: {url.split('://', 1)[0]}://\n"
                             + SUPPORTED_URLS) from exc
        raise AnyDbError(f"no driver for {full.split('://', 1)[0]}: pip install {DRIVER_HINT[driver]}") from exc
    except ImportError as exc:
        # The dialect is known but its driver package is not installed.
        missing = (getattr(exc, "name", None) or full.split("://", 1)[0].split("+")[-1]).split(".")[0]
        hint = DRIVER_HINT.get(missing, missing)
        raise AnyDbError(f"no driver for {full.split('://', 1)[0]}: pip install {hint}") from exc
    except Exception as exc:                       # noqa: BLE001 - bad URL
        raise AnyDbError(f"could not understand the database URL: {exc}") from exc
    folder = scratch("sql")
    keys, counts, warnings = {}, {}, []
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            tables = insp.get_table_names()
            views = []
            try:
                views = insp.get_view_names()
            except Exception:                      # noqa: BLE001 - optional
                pass
            if not tables and not views:
                raise AnyDbError(f"no tables found in {_redact(url)}")
            for table in tables + views:
                cols = insp.get_columns(table)
                names = [c["name"] for c in cols]
                py_types = []
                for c in cols:
                    try:
                        py_types.append(c["type"].python_type)
                    except (NotImplementedError, AttributeError):
                        py_types.append(str)
                pk, fks = [], []
                if table in tables:
                    try:
                        pk = list((insp.get_pk_constraint(table) or {}).get("constrained_columns") or [])
                        for fk in insp.get_foreign_keys(table):
                            for c, rc in zip(fk.get("constrained_columns") or [],
                                             fk.get("referred_columns") or []):
                                fks.append((c, fk["referred_table"], rc))
                    except Exception:              # noqa: BLE001 - keys are a bonus
                        pass
                keys[table] = (pk, fks)
                quoted = conn.dialect.identifier_preparer.quote(table)
                result = conn.execution_options(stream_results=True).execute(sa.text(f"SELECT * FROM {quoted}"))

                def batches(res=result):
                    while True:
                        rows = res.fetchmany(BATCH)
                        if not rows:
                            break
                        yield [tuple(r) for r in rows]
                try:
                    counts[table] = write_parquet(folder / f"{_safe(table)}.parquet", names, py_types, batches())
                except Exception as exc:           # noqa: BLE001 - per table
                    (folder / f"{_safe(table)}.parquet").unlink(missing_ok=True)
                    warnings.append(f"skipped {table}: {type(exc).__name__}: {str(exc)[:200]}")
    finally:
        engine.dispose()
    return _finish(con, folder, name or _db_name(full), url, keys, warnings, counts)


def sqlalchemy_keys(url: str) -> dict | None:
    """{table: (primary_key, [(column, ref_table, ref_column)])} read through
    the SQLAlchemy inspector, without copying any data. None when no driver
    is installed: the caller keeps whatever keys it already has."""
    try:
        import sqlalchemy as sa
        from sqlalchemy import inspect
        engine = sa.create_engine(normalise_sqlalchemy_url(url))
    except Exception:                              # noqa: BLE001 - optional
        return None
    out = {}
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            for table in insp.get_table_names():
                pk = list((insp.get_pk_constraint(table) or {}).get("constrained_columns") or [])
                fks = []
                for fk in insp.get_foreign_keys(table):
                    for c, rc in zip(fk.get("constrained_columns") or [], fk.get("referred_columns") or []):
                        fks.append((c, fk["referred_table"], rc))
                out[table] = (pk, fks)
    except Exception:                              # noqa: BLE001 - optional
        return None
    finally:
        engine.dispose()
    return out


def overlay_keys(schema, keys: dict | None) -> None:
    """Put declared keys onto a Schema that has none (or fewer)."""
    if not keys:
        return
    from ontology.schema import ForeignKey
    by_name = {t.name: t for t in schema.tables}
    for table, (pk, fks) in keys.items():
        t = by_name.get(table)
        if t is None:
            continue
        cols = {c.name for c in t.columns}
        if pk and all(c in cols for c in pk) and not t.primary_key:
            t.primary_key = list(pk)
        have = {(f.column, f.ref_table, f.ref_column) for f in t.foreign_keys}
        for c, rt, rc in fks:
            if c in cols and rt in by_name and (c, rt, rc) not in have:
                t.foreign_keys.append(ForeignKey(c, rt, rc))


def _db_name(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return _safe(path.split("/")[-1]) if path else url.split("://", 1)[0].split("+")[0]


# ----------------------------------------------------------------- odbc
def odbc_schema(con, connection_string: str, name: str | None, origin: str | None = None):
    try:
        import pyodbc
    except ImportError as exc:
        raise AnyDbError("install pyodbc to read through ODBC:  pip install pyodbc") from exc
    db = None
    last = None
    for options in ({"readonly": True, "autocommit": True, "timeout": 15},
                    {"autocommit": True, "timeout": 15}, {"timeout": 15}):
        try:
            db = pyodbc.connect(connection_string, **options)
            break
        except Exception as exc:                   # noqa: BLE001 - try plainer
            last = exc
    if db is None:
        raise AnyDbError(f"ODBC could not connect: {str(last)[:300]}") from last
    folder = scratch("odbc")
    keys, counts, warnings = {}, {}, []
    quote = "[{}]" if re.search(r"SQL Server|Access|Excel|Text", connection_string, re.I) else '"{}"'
    try:
        cur = db.cursor()
        tables = [(r.table_schem, r.table_name) for r in cur.tables()
                  if (r.table_type or "").upper() in ("TABLE", "VIEW")
                  and not str(r.table_name).startswith(("MSys", "sys"))
                  and str(r.table_schem or "").lower() not in ("sys", "information_schema")]
        if not tables:
            raise AnyDbError("no tables found through this ODBC connection")
        for schema_name, table in tables:
            try:
                pk = [r.column_name for r in cur.primaryKeys(table=table, schema=schema_name)]
            except Exception:                      # noqa: BLE001 - driver optional
                pk = []
            fks = []
            try:
                for r in cur.foreignKeys(foreignTable=table, foreignSchema=schema_name):
                    fks.append((r.fkcolumn_name, r.pktable_name, r.pkcolumn_name))
            except Exception:                      # noqa: BLE001
                pass
            keys[table] = (pk, fks)
            ref = quote.format(table)
            if schema_name and not re.search(r"Access|Excel|Text", connection_string, re.I):
                ref = quote.format(schema_name) + "." + ref
            try:
                # A fresh cursor per table, read by iteration: fetchmany on a
                # cursor that just served catalogue calls returned nothing on
                # the legacy SQL Server driver.
                rs = db.cursor().execute(f"SELECT * FROM {ref}")
                names = [d[0] for d in rs.description]
                py_types = [d[1] if isinstance(d[1], type) else str for d in rs.description]

                def batches(rs=rs):
                    chunk = []
                    for row in rs:
                        chunk.append(tuple(row))
                        if len(chunk) >= BATCH:
                            yield chunk
                            chunk = []
                    if chunk:
                        yield chunk
                counts[table] = write_parquet(folder / f"{_safe(table)}.parquet", names, py_types, batches())
            except Exception as exc:               # noqa: BLE001 - per table
                (folder / f"{_safe(table)}.parquet").unlink(missing_ok=True)   # no half file
                warnings.append(f"skipped {table}: {type(exc).__name__}: {str(exc)[:200]}")
    finally:
        db.close()
    return _finish(con, folder, name or "odbc", origin or "odbc://" + re.sub(r"PWD=[^;]*", "PWD=***", connection_string, flags=re.I),
                   keys, warnings, counts)


# ---------------------------------------------------------------- mongo
def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:                                            # ObjectId, Decimal128, UUID ...
        return float(value) if type(value).__name__ == "Decimal128" else str(value)
    except Exception:                               # noqa: BLE001
        return str(value)


def mongo_client(url: str):
    """Replaced in tests."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise AnyDbError("install pymongo to read MongoDB:  pip install pymongo") from exc
    return MongoClient(url, serverSelectionTimeoutMS=8000)


def mongo_schema(con, url: str, name: str | None):
    client = mongo_client(url)
    folder = scratch("mongo")
    keys, counts, warnings = {}, {}, []
    try:
        db_name = urlparse(url).path.strip("/").split("/")[0]
        if not db_name:
            names = [d for d in client.list_database_names() if d not in ("admin", "local", "config")]
            if len(names) != 1:
                raise AnyDbError("add the database name to the URL (mongodb://host/DATABASE); "
                                 f"found: {', '.join(names) or 'none'}")
            db_name = names[0]
        db = client[db_name]
        collections = [c for c in db.list_collection_names() if not c.startswith("system.")]
        if not collections:
            raise AnyDbError(f"no collections in database {db_name!r}")
        for coll in collections:
            path = folder / f"{_safe(coll)}.ndjson"
            n = 0
            with path.open("w", encoding="utf-8") as f:
                for doc in db[coll].find():
                    f.write(json.dumps(_json_safe(doc), ensure_ascii=False) + "\n")
                    n += 1
            if n == 0:
                path.unlink()
                warnings.append(f"skipped {coll}: empty collection")
                continue
            keys[coll] = (["_id"], [])
            counts[coll] = n
    finally:
        client.close()
    return _finish(con, folder, name or _safe(db_name), url, keys, warnings, counts)


# ---------------------------------------------------------------- neo4j
def neo4j_driver(url: str):
    """Replaced in tests. Credentials come from the URL's user:password."""
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise AnyDbError("install the neo4j driver:  pip install neo4j") from exc
    u = urlparse(url)
    clean = f"{u.scheme}://{u.hostname}{':' + str(u.port) if u.port else ''}"
    auth = (unquote(u.username), unquote(u.password or "")) if u.username else None
    return GraphDatabase.driver(clean, auth=auth)


def neo4j_schema(con, url: str, name: str | None):
    driver = neo4j_driver(url)
    folder = scratch("neo4j")
    q = parse_qs(urlparse(url).query)
    database = (q.get("database") or [None])[0]
    try:
        with driver.session(**({"database": database} if database else {})) as session:
            ids = "elementId(n)"
            try:
                session.run("RETURN elementId(null)").consume()
            except Exception:                      # noqa: BLE001 - Neo4j 4.x
                ids = "toString(id(n))"

            def nodes():
                skip = 0
                while True:
                    rows = [(r["id"], r["labels"], r["props"]) for r in session.run(
                        f"MATCH (n) RETURN {ids} AS id, labels(n) AS labels, properties(n) AS props "
                        f"ORDER BY id SKIP $s LIMIT $l", s=skip, l=BATCH)]
                    if not rows:
                        break
                    out = []
                    for nid, labels, props in rows:
                        props = props or {}
                        label = next((str(props[k]) for k in ("name", "title", "label", "id")
                                      if props.get(k) not in (None, "")), str(nid))
                        out.append((str(nid), label, labels[0] if labels else "Node",
                                    json.dumps(_json_safe(props), ensure_ascii=False)))
                    yield out
                    skip += BATCH

            def edges():
                skip = 0
                a_id, b_id = ids.replace("(n)", "(a)"), ids.replace("(n)", "(b)")
                while True:
                    rows = [(str(r["s"]), r["p"], str(r["t"])) for r in session.run(
                        f"MATCH (a)-[r]->(b) RETURN {a_id} AS s, type(r) AS p, {b_id} AS t "
                        f"SKIP $s LIMIT $l", s=skip, l=BATCH)]
                    if not rows:
                        break
                    yield rows
                    skip += BATCH
            n_nodes = write_parquet(folder / "entities.parquet", ["id", "label", "type", "properties"],
                                    [str, str, str, str], nodes())
            n_edges = write_parquet(folder / "links.parquet", ["source", "predicate", "target"],
                                    [str, str, str], edges())
    finally:
        driver.close()
    if not n_nodes:
        raise AnyDbError("the graph has no nodes")
    keys = {"entities": (["id"], []),
            "links": ([], [("source", "entities", "id"), ("target", "entities", "id")])}
    schema = _finish(con, folder, name or "neo4j", url, keys, [], {"entities": n_nodes, "links": n_edges})
    schema.warnings.append(f"read as a graph: {n_nodes:,} nodes (typed by their first label) and "
                           f"{n_edges:,} relationships")
    return schema


# --------------------------------------------------------- object stores
def _remote_files(con, url: str, name: str | None, warnings: list[str]):
    """Tables from every data object under a URL DuckDB can list (s3://, gs://,
    az://, or a local folder: the same code is tested on local paths)."""
    from ontology.connect import FILE_TYPES, _escape
    from ontology.schema import Schema
    pattern = url.rstrip("/") + "/**"
    try:
        files = [r[0] for r in con.execute(f"SELECT file FROM glob('{_escape(pattern)}')").fetchall()]
    except Exception as exc:                       # noqa: BLE001 - creds, network
        raise AnyDbError(f"could not list {url}: {str(exc)[:240]}") from exc
    files = [f for f in files if Path(f).suffix.lower() in FILE_TYPES]
    if not files:
        raise AnyDbError(f"no Parquet, CSV or JSON objects under {url}")
    tables, readers, used = [], {}, set()
    for f in sorted(files):
        reader = FILE_TYPES[Path(f).suffix.lower()]
        ref = f"{reader}('{_escape(f)}')"
        base = _safe(Path(f).stem)
        table_name, n = base, 2
        while table_name in used:
            table_name = f"{base}_{n}"
            n += 1
        try:
            t = table_from_ref(con, table_name, ref)
        except Exception as exc:                   # noqa: BLE001 - per object
            warnings.append(f"skipped {f}: {str(exc)[:160]}")
            continue
        used.add(table_name)
        readers[table_name] = ref
        tables.append(t)
    if not tables:
        raise AnyDbError("none of the objects could be read:\n  " + "\n  ".join(warnings))
    return Schema(tables=tables, name=name or _safe(url.rstrip("/").split("/")[-1]), origin=url,
                  readers=readers, warnings=warnings)


def table_from_ref(con, table_name: str, ref: str):
    """A Table (columns, counts, declared-less key guess) for one reader expression."""
    from ontology.keys import pick_key, profile_sql
    from ontology.schema import Column, Table
    cols = con.execute(f"DESCRIBE SELECT * FROM {ref}").fetchall()
    rows = con.execute(f"SELECT count(*) FROM {ref}").fetchone()[0]
    names = [c[0] for c in cols]
    stats = {}
    if rows:
        try:
            got = con.execute(profile_sql(table_name, names, ref)).fetchone()
            stats = {c: (got[1 + i * 2], got[2 + i * 2]) for i, c in enumerate(names)}
        except Exception:                          # noqa: BLE001 - profiling is a bonus
            pass
    columns = [Column(c[0], str(c[1]).upper(),
                      nullable=(stats.get(c[0], (None, None))[1] or 0) < rows,
                      distinct=stats.get(c[0], (None, None))[0]) for c in cols]
    t = Table(name=table_name, columns=columns, primary_key=[], foreign_keys=[], row_count=rows)
    found = pick_key(t)
    if found:
        t.primary_key = [found]
    return t


def object_store_schema(con, url: str, name: str | None):
    try:
        con.execute("INSTALL httpfs; LOAD httpfs")
    except Exception as exc:                       # noqa: BLE001
        raise AnyDbError(f"DuckDB's httpfs extension is needed for {url.split('://')[0]}://: {exc}") from exc
    warnings = [f"{url}: read from object storage; credentials come from the environment "
                "(AWS_*, AZURE_*, GOOGLE_*) or a DuckDB secret"]
    return _remote_files(con, url, name, warnings)


# ---------------------------------------------------------------- delta
def is_delta_folder(path: Path) -> bool:
    return path.is_dir() and (path / "_delta_log").is_dir()


def delta_schema(con, path: Path, name: str | None):
    from ontology.connect import _escape
    from ontology.schema import Schema
    table_name = _safe(path.name)
    try:
        con.execute("INSTALL delta; LOAD delta")
        ref = f"delta_scan('{_escape(str(path))}')"
        t = table_from_ref(con, table_name, ref)
    except Exception as exc:                       # noqa: BLE001
        raise AnyDbError(f"could not read the Delta table {path}: {str(exc)[:240]}") from exc
    return Schema(tables=[t], name=name or table_name, origin=str(path), readers={table_name: ref},
                  warnings=[f"{path.name}: read as a Delta Lake table ({t.row_count:,} rows)"])


# ---------------------------------------------------------------- entry
def schema_from_url(con, url: str, name: str | None):
    """Dispatch on the URL scheme. Raises AnyDbError with a clear message."""
    kind = url.split("://", 1)[0].lower()
    if kind == "odbc":
        return odbc_schema(con, unquote(url.split("://", 1)[1]), name)
    if kind in MONGO:
        return mongo_schema(con, url, name)
    if kind in NEO4J:
        return neo4j_schema(con, url, name)
    if kind in OBJECT_STORES:
        return object_store_schema(con, url, name)
    if kind == "delta":
        return delta_schema(con, Path(url.split("://", 1)[1]), name)
    return sqlalchemy_schema(con, url, name)


def access_schema(con, path: Path, name: str | None):
    """An Access database file, through the Access ODBC driver (Windows)."""
    connection = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};"
    return odbc_schema(con, connection, name or _safe(path.stem), origin=str(path))
