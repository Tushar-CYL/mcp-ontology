"""The one shape every data source is read into.

Postgres, SQL Server, a CSV folder, a spreadsheet and an API all arrive here
as the same four objects. Everything above this file is written once and
works for all of them; everything that knows about a particular source lives
in connect.py and stops at this boundary.

These are plain data holders on purpose. They carry no database handle and
no connection, which is what lets the discovery rules be tested on shapes
that would be tedious to produce from a real source.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str                      # the source's own type name, uppercased
    nullable: bool = True
    distinct: int | None = None    # filled in only when profiled; costs a scan


@dataclass(frozen=True)
class ForeignKey:
    """A link the SOURCE declares. Anything we work out ourselves is not one
    of these - it becomes a relation marked `derived`, and the difference is
    carried all the way to the final answer."""
    column: str
    ref_table: str
    ref_column: str


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    row_count: int | None = None

    def column(self, name: str) -> Column | None:
        lowered = name.lower()
        return next((c for c in self.columns if c.name.lower() == lowered), None)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


@dataclass
class Schema:
    """Everything one connected source contains.

    `origin` is what was passed to connect() - a path or a URL. It is kept
    so later layers can re-open the same source without being handed a live
    connection, which would tie them to one database driver.
    `readers` maps table name -> the SQL expression that reads it, for
    sources that are files rather than databases.
    """
    tables: list[Table] = field(default_factory=list)
    name: str = "source"
    origin: str = ""
    readers: dict = field(default_factory=dict)

    def table(self, name: str) -> Table | None:
        lowered = name.lower()
        return next((t for t in self.tables if t.name.lower() == lowered), None)


# Type families, so the rules never match on a vendor's spelling. Postgres
# says `int4`, DuckDB says `BIGINT`, SQLite says `INTEGER`, Snowflake says
# `NUMBER` - all of them are numbers, and a rule that cared which would need
# rewriting for every new source.
NUMERIC = ("INT", "SERIAL", "DECIMAL", "NUMERIC", "NUMBER", "FLOAT", "DOUBLE",
           "REAL", "MONEY", "BIGNUM")
TEMPORAL = ("DATE", "TIME", "TIMESTAMP", "DATETIME", "YEAR")
TEXTUAL = ("CHAR", "TEXT", "STRING", "CLOB", "ENUM", "UUID")
BOOLEAN = ("BOOL", "BIT", "LOGICAL")


def _family(type_name: str, family: tuple[str, ...]) -> bool:
    t = (type_name or "").upper()
    return any(k in t for k in family)


def is_numeric(c: Column) -> bool:
    # BOOLEAN first: SQL Server spells a boolean `BIT`, which contains "IT"
    # but is not a measure, and averaging it would be meaningless.
    return not is_boolean(c) and _family(c.type, NUMERIC)


def is_temporal(c: Column) -> bool:
    return _family(c.type, TEMPORAL)


def is_textual(c: Column) -> bool:
    return _family(c.type, TEXTUAL) or (c.type or "").upper() == "VARCHAR"


def is_boolean(c: Column) -> bool:
    return _family(c.type, BOOLEAN)
