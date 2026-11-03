"""Keep copies of the same data out of the ontology and the graph.

Exports of real systems carry copies: machine-learning splits
(``I_SalesDocument_train`` / ``_test``) and exact duplicates under another
name (``salesdocuments.csv`` next to ``I_SalesDocument.parquet``). In SAP SALT
they doubled the graph to 10.4M records and produced guessed links between
copies. A copy is still loaded and queryable; it is only marked ``hidden`` so
discovery does not turn it into a second kind of thing.
"""

from __future__ import annotations

import re

_ML_SPLIT = re.compile(r"_(train|test|val|valid|validation|dev)$", re.I)


def _signature(table) -> frozenset:
    return frozenset(c.name.lower() for c in table.columns
                     if not c.name.startswith("__"))


def hide_copies(schema) -> list[str]:
    """Mark ML splits and exact duplicates as hidden. Returns their names."""
    visible = [t for t in schema.tables if not getattr(t, "hidden", False)]
    hidden: list[str] = []
    # ML splits are never the system of record - unless the whole dataset is
    # splits, in which case the largest of each split family stays.
    if any(not _ML_SPLIT.search(t.name) for t in visible):
        for table in visible:
            if _ML_SPLIT.search(table.name):
                table.hidden = True
                hidden.append(table.name)
    else:
        families: dict[str, list] = {}
        for table in visible:
            families.setdefault(_ML_SPLIT.sub("", table.name), []).append(table)
        for members in families.values():
            keep = max(members, key=lambda t: t.row_count or 0)
            for table in members:
                if table is not keep:
                    table.hidden = True
                    hidden.append(table.name)
    # Exact duplicates: same columns and same number of rows.
    groups: dict[tuple, list] = {}
    for table in schema.tables:
        if getattr(table, "hidden", False) or table.row_count is None:
            continue
        groups.setdefault((_signature(table), table.row_count), []).append(table)
    for members in groups.values():
        if len(members) < 2:
            continue
        keep = sorted(members, key=lambda t: (len(t.name), t.name))[0]
        for table in members:
            if table is not keep:
                table.hidden = True
                hidden.append(table.name)
    if hidden:
        schema.warnings.append(
            "Kept copies out of the graph (still loaded and queryable): "
            + ", ".join(sorted(hidden)))
    return hidden
