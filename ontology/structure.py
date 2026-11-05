"""Relationships done properly: cardinality, optionality and hierarchies.

Relationships come from the crosswalks found in the concept step. Each one
is measured rather than assumed:

* **cardinality**: the most child rows that share one parent value (1 means
  one-to-one, more means many-to-one);
* **required**: whether every child row finds its parent (no nulls, no
  orphans); orphans are a data-quality fact worth showing;
* **parents used**: what share of parents have at least one child (not every
  order is invoiced yet).

Hierarchies come from functional dependencies: if every country value sits
under exactly one region value, Region > Country is a drill path. Only
categorical columns qualify; identifiers, names and dates never do.
"""

from __future__ import annotations

import re

from knowledge_graph.build import qi
from ontology import registry as reg
from ontology.concepts import _tables

FD_HOLDS = 0.98            # share of child values with exactly one parent value
MAX_LEVEL_VALUES = 1000
_NOT_A_LEVEL = {"identifier", "tax_id", "period", "date", "snapshot_date",
                "sync_timestamp", "last_updated", "attribute", "record_owner"}


def _snake(concept: str) -> str:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", concept)
    return spaced.lower()


def measure_relationship(graph, t: dict, u: dict, col: str, key: str) -> dict:
    c, k = qi(col), qi(key)
    rows, non_null, distinct, max_children = graph.sql(
        f"SELECT (SELECT count(*) FROM {t['ref']}), coalesce(sum(n), 0), count(*),"
        f" max(n) FROM (SELECT CAST({c} AS VARCHAR) v, count(*) n FROM {t['ref']}"
        f" WHERE {c} IS NOT NULL GROUP BY 1) g")[0]
    matched_rows, used, parents = graph.sql(
        f"SELECT (SELECT count(*) FROM {t['ref']} a WHERE CAST(a.{c} AS VARCHAR) IN"
        f" (SELECT CAST({k} AS VARCHAR) FROM {u['ref']})),"
        f" (SELECT count(DISTINCT CAST(b.{k} AS VARCHAR)) FROM {u['ref']} b WHERE"
        f" CAST(b.{k} AS VARCHAR) IN (SELECT CAST({c} AS VARCHAR) FROM {t['ref']})),"
        f" (SELECT count(DISTINCT {k}) FROM {u['ref']})")[0]
    rows, non_null = int(rows or 0), int(non_null or 0)
    matched = round(matched_rows / rows, 4) if rows else 0.0
    max_children = int(max_children or 0)
    return {
        "rows": rows, "null_ratio": round(1 - non_null / rows, 4) if rows else 0.0,
        "distinct": int(distinct or 0), "max_children": max_children,
        "avg_children": round(non_null / distinct, 2) if distinct else 0.0,
        "matched": matched, "orphans": non_null - int(matched_rows or 0),
        "parents_used": round(used / parents, 4) if parents else 0.0,
        "cardinality": "one-to-one" if max_children <= 1 else "many-to-one",
        "required": non_null == rows and matched >= 0.999,
    }


def find_hierarchies(graph, t: dict, props: dict) -> list[dict]:
    """Functional dependencies between categorical columns of one table."""
    rows = t["rows"] or 0
    cands = []
    for c in t["table"].columns:
        prop = props.get(c.name, "")
        if c.name.startswith("__") or prop in _NOT_A_LEVEL or prop.endswith("_name") \
                or prop.endswith("_date") or prop.endswith("amount"):
            continue
        if "VARCHAR" not in str(c.type).upper() and "TEXT" not in str(c.type).upper():
            continue
        n = graph.sql(f"SELECT count(DISTINCT {qi(c.name)}) FROM {t['ref']}")[0][0]
        if 2 <= n <= min(MAX_LEVEL_VALUES, max(2, rows // 2)):
            cands.append((c.name, int(n)))
    found = []
    for child, nc in cands:
        for parent, np_ in cands:
            if parent == child or np_ >= nc:
                continue
            single = graph.sql(
                f"SELECT avg(CASE WHEN k = 1 THEN 1.0 ELSE 0.0 END) FROM (SELECT"
                f" {qi(child)}, count(DISTINCT {qi(parent)}) k FROM {t['ref']}"
                f" WHERE {qi(child)} IS NOT NULL GROUP BY 1) g")[0][0]
            if single is None or single < FD_HOLDS:
                continue
            mapping = {str(a): str(b) for a, b in graph.sql(
                f"SELECT {qi(child)}, mode({qi(parent)}) FROM {t['ref']}"
                f" WHERE {qi(child)} IS NOT NULL GROUP BY 1 ORDER BY 1")}
            found.append({"parent": parent, "child": child, "parent_values": np_,
                          "child_values": nc, "holds": round(float(single), 4),
                          "parent_of": mapping})
    return found


def propose_structure(layer, ontology_id: str) -> dict:
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    tables = {t["key"]: t for t in _tables(layer, onto)}
    props: dict = {}
    for m in reg.items(graph, ontology_id, kind="mapping"):
        props.setdefault(m["payload"]["table"], {})[m["payload"]["column"]] = \
            m["payload"]["property"]
    concept_of = {m["payload"]["table"]: m["payload"]["concept"]
                  for m in reg.items(graph, ontology_id, kind="member")
                  if m["status"] != "rejected"}

    relationships = []
    for item in reg.items(graph, ontology_id, kind="relationship"):
        if item["status"] == "rejected":
            continue
        p = dict(item["payload"])
        t_key, col = p["from"].rsplit(".", 1)
        u_key, key = p["to"].rsplit(".", 1)
        if t_key not in tables or u_key not in tables:
            continue
        stats = measure_relationship(graph, tables[t_key], tables[u_key], col, key)
        p.update(stats)
        p["name"] = _snake(p["to_concept"])
        p["evidence"] = [
            f"up to {stats['max_children']} {t_key} rows per parent "
            f"(average {stats['avg_children']}) -> {stats['cardinality']}",
            f"{stats['matched']:.1%} of {t_key} rows find their parent in {u_key}"
            + (f"; {stats['orphans']} orphans" if stats["orphans"] else ""),
            f"{stats['parents_used']:.1%} of {u_key} rows have at least one child"]
        reg.put(graph, ontology_id, "relationship", item["key"],
                {k: v for k, v in p.items() if k != "evidence"},
                confidence=item["confidence"], evidence=p["evidence"])
        relationships.append(p)

    merged: dict = {}
    for t_key, t in tables.items():
        concept = concept_of.get(t_key, t["class"])
        for fd in find_hierarchies(graph, t, props.get(t_key, {})):
            levels = [props[t_key].get(fd["parent"], fd["parent"]),
                      props[t_key].get(fd["child"], fd["child"])]
            k = (concept, tuple(levels))
            h = merged.setdefault(k, {"concept": concept, "levels": levels,
                                      "parent_of": fd["parent_of"], "tables": [],
                                      "evidence": []})
            h["tables"].append(t_key)
            h["evidence"].append(
                f"in {t_key}, each of {fd['child_values']} {fd['child']} values has "
                f"exactly one {fd['parent']} ({fd['holds']:.0%} of values)")
    hierarchies = list(merged.values())
    keep = set()
    for h in hierarchies:
        key = f"{h['concept']}:{'>'.join(h['levels'])}"
        keep.add(key)
        reg.put(graph, ontology_id, "hierarchy", key,
                {k: h[k] for k in ("concept", "levels", "parent_of", "tables")},
                confidence=0.9, evidence=h["evidence"])
    reg.prune(graph, ontology_id, "hierarchy", keep)
    return {"relationships": relationships, "hierarchies": hierarchies}
