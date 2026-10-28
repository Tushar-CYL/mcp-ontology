"""The dialect layer: one tiny interface, one implementation per engine.

This exists because the project is built twice - DuckDB now, Postgres on the
32 GB box later - and that is only worth doing if the second time is cheap.
So everything above this file is engine-agnostic, and everything
engine-specific lives either here or in sql/<engine>/.

It is deliberately NOT an ORM or a query builder. Four methods, plain SQL,
`?` placeholders everywhere (translated to %s for Postgres). Hiding SQL
behind an abstraction would defeat the point of the exercise, which is to
find out which SQL actually ports.

Usage:
    from db import connect
    with connect() as db:
        db.script("sql/duckdb/schema.sql")
        rows = db.query("SELECT * FROM nodes WHERE class = ?", [4])

Engine is chosen by OKG_ENGINE (duckdb | postgres), default duckdb.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from common import DOMAIN, DOMAIN_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parent
ENGINE = os.environ.get("OKG_ENGINE", "duckdb").lower()

# One database per domain. Class codes come from the domain's ontology, so
# Microservice=4 in one and Route=4 in another would collide inside a shared
# `nodes` table and nothing would warn you.
DUCKDB_PATH = Path(os.environ.get("OKG_DUCKDB",
                                  ROOT / "data" / f"{DOMAIN}.duckdb"))
PG_DSN = os.environ.get(
    "OKG_DSN",
    f"host=localhost port=5432 dbname=okg_{DOMAIN} user=okg password=okg")

# Split a .sql file on semicolons that end a statement. Good enough because
# our SQL files never contain a semicolon inside a string literal or a
# dollar-quoted body on the DuckDB side; the Postgres side keeps plpgsql in
# its own file and is executed whole.
_STMT = re.compile(r";\s*(?:\n|$)")


class Database:
    """Minimal uniform surface over DuckDB and Postgres."""

    engine: str

    def __init__(self, engine: str, conn: Any) -> None:
        self.engine = engine
        self._conn = conn

    # ---------------------------------------------------------- lifecycle
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def raw(self) -> Any:
        """The underlying driver connection, for engine-specific work."""
        return self._conn

    # ------------------------------------------------------------- queries
    def _sql(self, sql: str) -> str:
        # Callers always write `?`; psycopg wants `%s`.
        if self.engine == "postgres":
            return sql.replace("%", "%%").replace("?", "%s")
        return sql

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        if self.engine == "duckdb":
            self._conn.execute(self._sql(sql), list(params or []))
        else:
            with self._conn.cursor() as cur:
                cur.execute(self._sql(sql), list(params or []))
            self._conn.commit()

    def query(self, sql: str,
              params: Sequence[Any] | None = None) -> list[tuple]:
        if self.engine == "duckdb":
            return self._conn.execute(self._sql(sql),
                                      list(params or [])).fetchall()
        with self._conn.cursor() as cur:
            cur.execute(self._sql(sql), list(params or []))
            return cur.fetchall()

    def one(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        rows = self.query(sql, params)
        return rows[0][0] if rows else None

    def columns(self, sql: str,
                params: Sequence[Any] | None = None) -> list[str]:
        if self.engine == "duckdb":
            rel = self._conn.execute(self._sql(sql), list(params or []))
            return [d[0] for d in rel.description]
        with self._conn.cursor() as cur:
            cur.execute(self._sql(sql), list(params or []))
            return [d.name for d in cur.description]

    # --------------------------------------------------------- sql scripts
    def script(self, path: str | Path, echo: bool = False) -> None:
        """Run a .sql file. Path is resolved against the repo root."""
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        text = p.read_text(encoding="utf-8")
        # psql-only directives mean nothing to either driver.
        text = re.sub(r"^\\\\?set\s+.*$", "", text, flags=re.M)

        for stmt in _STMT.split(text):
            stmt = stmt.strip()
            # Emptiness is judged on the CODE only. Testing the raw chunk
            # would skip any statement preceded by a comment block -- which
            # silently swallowed the first CREATE TABLE in every file.
            code = "\n".join(ln for ln in stmt.splitlines()
                             if not ln.strip().startswith("--")).strip()
            if not code:
                continue
            label = next((ln for ln in code.splitlines() if ln.strip()),
                         "")[:78]
            t0 = time.monotonic()
            try:
                self.execute(stmt)
            except Exception as e:                            # noqa: BLE001
                head = "\n".join(code.splitlines()[:6])
                raise RuntimeError(
                    f"{p.name}: statement failed:\n{head}\n--> {e}") from e
            if echo:
                print(f"  {time.monotonic() - t0:7.2f}s  {label}")

    def sql_dir(self) -> Path:
        """Where this domain's SQL lives: staging, build, facts, queries, shapes."""
        return DOMAIN_DIR / "sql" / self.engine

    def core_sql_dir(self) -> Path:
        """Where the SHARED SQL lives: nodes, edges, registries, validation.

        Identical for every domain. If something needs to move from here into
        a domain folder, that is a finding about the architecture, not a
        detail - it means the core was not as general as claimed.
        """
        return ROOT / "sql" / self.engine


def connect(engine: str | None = None, read_only: bool = False) -> Database:
    eng = (engine or ENGINE).lower()
    if eng == "duckdb":
        import duckdb
        DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=read_only)
        # The progress bar writes escape codes into stdout, which corrupts
        # captured output and log files for no benefit in a script.
        conn.execute("SET enable_progress_bar = false")
        return Database("duckdb", conn)
    if eng in ("postgres", "postgresql", "pg"):
        import psycopg
        return Database("postgres", psycopg.connect(PG_DSN))
    raise ValueError(f"unknown engine: {eng!r}")


def bootstrap() -> None:
    """Put the repo root on sys.path for scripts in subdirectories."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def human(n: float) -> str:
    f = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if f < 1024 or unit == "TiB":
            return f"{f:,.1f} {unit}"
        f /= 1024
    return f"{f:,.1f} TiB"
