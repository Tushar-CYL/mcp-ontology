"""Optional cloud connectors: Snowflake and Databricks.

They are optional on purpose: the product must run with nothing but the base
requirements. Each connector imports its vendor driver only when a matching URL
is used, and says exactly what to install if it is missing.

URL forms
---------
    snowflake://USER:PASSWORD@ACCOUNT/DATABASE/SCHEMA?warehouse=WH&role=ROLE
    databricks://TOKEN@HOST?http_path=/sql/1.0/warehouses/xxx&catalog=main&schema=default

Both read tables through the vendor driver, stream them to temporary CSV files,
and hand them to the normal schema reader — so discovery, keys, graph build,
metrics and context work without a special path.

Credentials belong in the URL or environment for a local demo; this is not a
secrets manager. Do not put a production password in shell history.
"""

from __future__ import annotations

import csv
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

CLOUD_SCHEMES = ("snowflake", "databricks", "databricks+sql")


class CloudConnectorError(Exception):
    """A connector failure with a message a person can act on."""


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower() or "table"


def _write_csv(folder: Path, table: str, columns: list[str],
               rows: list[list]) -> Path:
    path = folder / f"{_safe_name(table)}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)
    return path


def _finish(con, files: list[Path], name: str, url: str,
            warnings: list[str]):
    # Imported here to avoid a circular import at module load time.
    from ontology.connect import _from_files
    schema = _from_files(con, files, name, warnings)
    schema.origin = url
    return schema


# ------------------------------------------------------------- snowflake
def _snowflake(con, url: str, name: str | None):
    try:
        import snowflake.connector
    except ImportError as exc:
        raise CloudConnectorError(
            "the snowflake:// connector needs the driver:\n"
            "  python -m pip install snowflake-connector-python"
        ) from exc

    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if not parsed.hostname or len(parts) < 1:
        raise CloudConnectorError(
            "snowflake URL must be snowflake://user:pass@account/database/"
            "[schema]?warehouse=...&role=...")
    database = unquote(parts[0])
    schema_name = unquote(parts[1]) if len(parts) > 1 else "PUBLIC"
    query = parse_qs(parsed.query)

    def opt(key, default=None):
        value = query.get(key)
        return unquote(value[0]) if value else default

    connection = snowflake.connector.connect(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        account=parsed.hostname,
        database=database,
        schema=schema_name,
        warehouse=opt("warehouse"),
        role=opt("role"),
    )
    folder = Path(tempfile.mkdtemp(prefix="ml_snowflake_"))
    files, warnings, tables = [], [], 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s ORDER BY table_name",
                (schema_name,))
            names = [row[0] for row in cursor.fetchall()]
            for table in names:
                cursor.execute(
                    f'SELECT * FROM "{database}"."{schema_name}"."{table}"')
                columns = [d[0] for d in cursor.description]
                rows = cursor.fetchmany(5000)
                if not rows:
                    continue
                all_rows = list(rows)
                while True:
                    chunk = cursor.fetchmany(5000)
                    if not chunk:
                        break
                    all_rows.extend(chunk)
                files.append(_write_csv(folder, table, columns, all_rows))
                tables += 1
    finally:
        connection.close()
    if not files:
        raise CloudConnectorError(
            f"no rows found in {database}.{schema_name} (Snowflake)")
    warnings.append(
        f"Snowflake {database}.{schema_name}: {tables} table(s) copied to "
        f"temporary CSV for the local build")
    return _finish(con, files, name or f"snowflake_{_safe_name(database)}",
                   url, warnings)


# ------------------------------------------------------------ databricks
def _databricks(con, url: str, name: str | None):
    try:
        import databricks.sql
    except ImportError as exc:
        raise CloudConnectorError(
            "the databricks:// connector needs the driver:\n"
            "  python -m pip install databricks-sql-connector"
        ) from exc

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    token = unquote(parsed.password or parsed.username or "")
    host = parsed.hostname or ""
    http_path = unquote((query.get("http_path") or [""])[0])
    catalog = unquote((query.get("catalog") or ["main"])[0])
    schema_name = unquote((query.get("schema") or ["default"])[0])
    if not host or not http_path or not token:
        raise CloudConnectorError(
            "databricks URL must be "
            "databricks://TOKEN@HOST?http_path=...&catalog=...&schema=...")

    connection = databricks.sql.connect(
        server_hostname=host, http_path=http_path, access_token=token)
    folder = Path(tempfile.mkdtemp(prefix="ml_databricks_"))
    files, warnings, tables = [], [], 0
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT table_name FROM "
                f"{catalog}.information_schema.tables "
                f"WHERE table_schema = '{schema_name}' ORDER BY table_name")
            names = [row[0] for row in cursor.fetchall()]
            for table in names:
                cursor.execute(
                    f"SELECT * FROM `{catalog}`.`{schema_name}`.`{table}`")
                columns = [d[0] for d in cursor.description]
                rows = cursor.fetchall()
                if not rows:
                    continue
                files.append(_write_csv(folder, table, columns,
                                        [list(r) for r in rows]))
                tables += 1
        finally:
            cursor.close()
    finally:
        connection.close()
    if not files:
        raise CloudConnectorError(
            f"no rows found in {catalog}.{schema_name} (Databricks)")
    warnings.append(
        f"Databricks {catalog}.{schema_name}: {tables} table(s) copied to "
        f"temporary CSV for the local build")
    return _finish(con, files, name or f"databricks_{_safe_name(catalog)}",
                   url, warnings)


def schema_from_url(con, url: str, name: str | None = None):
    scheme = url.split("://", 1)[0].lower().replace("+sql", "")
    if scheme == "snowflake":
        return _snowflake(con, url, name)
    if scheme == "databricks":
        return _databricks(con, url, name)
    raise CloudConnectorError(f"unknown cloud connector {scheme!r}")
