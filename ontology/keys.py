"""Find the primary key of a table that never declared one.

Every CSV, and plenty of warehouse tables, arrive with no key. Without one
the whole thing collapses quietly rather than loudly: an edge is built by
matching a child's column against the parent's key, so a wrong key means
nothing joins and the graph comes out empty but valid-looking.

A key is readable from the data by counting - unique, never null - and the
counting is done once at connect time. What cannot be read is which of
several unique columns is the IDENTITY, so that is decided by name, in a
stated order of preference.
"""

from __future__ import annotations

from ontology.schema import Table, is_numeric, is_temporal


def _stem(table: str) -> str:
    from ontology.discover import core_name, singular
    return singular(core_name(table))


def candidates(table: Table) -> list[str]:
    """Columns that COULD identify a row: unique, never null, and not a
    measurement."""
    n = table.row_count or 0
    if n <= 0:
        return []
    out = []
    for c in table.columns:
        if c.distinct is None or c.nullable:
            continue
        if c.distinct != n:
            continue
        # A price or a timestamp can be accidentally unique in a small
        # sample. Using one as the key would be correct today and wrong as
        # soon as two rows share a value, so they are never eligible.
        if is_numeric(c) and not _looks_like_id(c.name):
            continue
        if is_temporal(c):
            continue
        out.append(c.name)
    return out


def _looks_like_id(name: str) -> bool:
    low = name.lower()
    return low == "id" or low.endswith(("_id", "id", "_key", "_code", "_no"))


def pick_key(table: Table) -> str | None:
    """The best identity column, or None if the data does not show one.

    None is an honest answer. The caller falls back to a synthetic row
    number and MARKS it synthetic, which is better than promoting a column
    that merely looks unique in this extract.
    """
    cands = candidates(table)
    if not cands:
        return None

    stem = _stem(table.name)

    def rank(name: str) -> tuple:
        low = name.lower()
        return (
            0 if low == f"{stem}_id" else            # customers.customer_id
            1 if low == "id" else                    # things.id
            2 if low == f"{stem}_key" else
            3 if low.endswith("_id") else
            4 if _looks_like_id(low) else 5,
            len(low),                                # shorter wins ties
            low,                                     # then alphabetical, so
        )                                            # the answer is stable

    return sorted(cands, key=rank)[0]


def profile_sql(table: str, columns: list[str], ref: str) -> str:
    """One query that counts rows, distincts and nulls for every column.

    One pass, not one per column: on a million-row file the difference is
    seconds against minutes, and this runs on every connect.
    """
    parts = ["count(*) AS __rows"]
    for i, c in enumerate(columns):
        parts.append(f'count(DISTINCT "{c}") AS d{i}')
        parts.append(f'count("{c}") AS n{i}')
    return f"SELECT {', '.join(parts)} FROM {ref}"
