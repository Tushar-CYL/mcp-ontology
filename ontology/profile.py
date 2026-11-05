"""Profile every table of an ontology's sources: the evidence base.

One scan per table computes, per column: type family, null ratio, approximate
distinct count, min/max (numbers and dates) and the top values of
low-cardinality columns; plus the table's freshness (its latest date). This
is what a data engineer checks first, and what every later proposal cites.
Profiles are facts, so they are stored as approved registry items.
"""

from __future__ import annotations

from knowledge_graph.build import qi, table_ref
from ontology import registry as reg
from ontology.schema import is_numeric, is_temporal

TOP_VALUES_MAX_DISTINCT = 50
TOP_N = 10


def _family(column) -> str:
    if is_temporal(column):
        return "temporal"
    if is_numeric(column):
        return "numeric"
    return "text"


def profile_table(graph, schema, table, source: str) -> dict:
    ref = table_ref(graph, schema, table.name, source=source)
    cols = [c for c in table.columns if not c.name.startswith("__")]
    parts = ["count(*)"]
    for c in cols:
        q = qi(c.name)
        parts += [f"count({q})", f"approx_count_distinct({q})"]
        if _family(c) == "temporal":
            # As text: a TIMESTAMPTZ fetched into Python needs pytz (not a
            # dependency), and only the date part is shown anyway.
            parts += [f"CAST(min({q}) AS VARCHAR)", f"CAST(max({q}) AS VARCHAR)"]
        elif _family(c) == "numeric":
            parts += [f"min({q})", f"max({q})"]
        else:
            parts += ["NULL", "NULL"]
    row = graph.sql(f"SELECT {', '.join(parts)} FROM {ref}")[0]
    rows = int(row[0] or 0)
    columns, freshness = [], None
    for i, c in enumerate(cols):
        non_null, distinct, lo, hi = row[1 + 4 * i: 5 + 4 * i]
        family = _family(c)
        item = {"name": c.name, "type": c.type, "family": family,
                "null_ratio": round(1 - (non_null or 0) / rows, 4) if rows else 0.0,
                "distinct": int(distinct or 0), "top_values": []}
        if family == "numeric":
            item["min"], item["max"] = lo, hi
        elif family == "temporal":
            item["min"] = str(lo)[:10] if lo is not None else None
            item["max"] = str(hi)[:10] if hi is not None else None
            if item["max"] and (freshness is None or item["max"] > freshness):
                freshness = item["max"]
        if 0 < item["distinct"] <= TOP_VALUES_MAX_DISTINCT:
            item["top_values"] = [
                {"value": str(v), "count": int(n)} for v, n in graph.sql(
                    f"SELECT {qi(c.name)}, count(*) FROM {ref}"
                    f" WHERE {qi(c.name)} IS NOT NULL GROUP BY 1"
                    f" ORDER BY 2 DESC LIMIT {TOP_N}")]
        columns.append(item)
    return {"table_key": f"{source}.{table.name}", "source": source,
            "table": table.name, "rows": rows, "columns": columns,
            "freshness": freshness}


def profile_ontology(layer, ontology_id: str) -> list[dict]:
    """Profile every table of every source in the ontology's intake."""
    onto = reg.get(layer.graph, ontology_id)
    out = []
    for src in onto["sources"]:
        bundle = layer._bundle(src["source_id"])
        for table in bundle.schema.tables:
            if getattr(table, "hidden", False):
                continue
            p = profile_table(layer.graph, bundle.schema, table, src["source_id"])
            reg.put(layer.graph, ontology_id, "profile", p["table_key"], p,
                    fact=True, confidence=1.0,
                    evidence=[f"{p['table_key']}: {p['rows']} rows scanned"])
            out.append(p)
    return out
