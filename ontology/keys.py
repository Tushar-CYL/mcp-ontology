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


# Identifier fields of the common enterprise systems. Real exports (SAP
# especially) name keys this way, and they are often numeric.
ERP_KEY_NAMES = {
    "kunnr", "vbeln", "matnr", "lifnr", "belnr", "ebeln", "aufnr", "pernr",
    "bukrs", "werks", "posnr", "vbelv", "kostl", "prctr", "saknr", "hkont",
}
_NAME_LIKE = ("name", "desc", "title", "label", "text", "comment", "note",
              "address", "street", "email", "phone", "city")


def _looks_like_id(name: str) -> bool:
    low = name.lower()
    return (low == "id" or low in ERP_KEY_NAMES
            or low.endswith(("_id", "id", "_key", "_code", "_no", "_nr",
                             "_number", "_ref", "ref", "_num")))


def _looks_like_name(name: str) -> bool:
    low = name.lower()
    return any(token in low for token in _NAME_LIKE)


_ID_SUFFIXES = ("_id", "_ref", "_no", "_nr", "_number", "_num", "_key", "_code")


def _abbreviates(column: str, stem: str) -> bool:
    """inv_id names an invoice, acct_id an account, po_no a purchase order:
    the part before the id suffix abbreviates the table's own name (same
    first letter, letters in order). order_ref in invoices does not."""
    for suffix in _ID_SUFFIXES:
        if column.endswith(suffix):
            prefix = column[: -len(suffix)].replace("_", "")
            break
    else:
        return False
    target = stem.lower().replace("_", "")
    if len(prefix) < 2 or not target or prefix[0] != target[0]:
        return False
    rest = iter(target)
    return all(ch in rest for ch in prefix)


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

    order = [c.name for c in table.columns]

    def rank(name: str) -> tuple:
        low = name.lower()
        # A unique name or description is an attribute, never the identity;
        # an attribute ending in _id (tax_id) ranks below a real identifier.
        if _looks_like_name(low) and not _looks_like_id(low):
            klass = 7
        elif low == f"{stem}_id" or _abbreviates(low, stem):
            klass = 0                                # customer_id, inv_id
        elif low == "id":
            klass = 1                                # things.id
        elif low == f"{stem}_key":
            klass = 2
        elif low in ERP_KEY_NAMES or low.endswith(("_ref", "_no", "_nr",
                                                   "_number", "_num")):
            klass = 3                                # KUNNR, billing_ref
        elif low.endswith("_id"):
            klass = 4
        elif _looks_like_id(low):
            klass = 5
        else:
            klass = 6
        return (klass,
                order.index(name) if name in order else 99,   # earlier column
                len(low), low)                                # stable ties

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
