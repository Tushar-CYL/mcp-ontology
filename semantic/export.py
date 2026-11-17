"""The semantic layer in other systems' own formats.

* **SQL views**: one ``CREATE VIEW`` per metric (certified by default), over
  the source tables by their own names, so the same number can be read in the
  client's warehouse with no Strata running. ``portable=False`` keeps Strata's
  internal table references (what Strata itself runs; used by the tests to
  prove the views give exactly the metric's value).
* **dbt MetricFlow YAML**: ``semantic_models`` (one per table: entities from
  keys and proven links, dimensions, the time dimension, measures) and
  ``metrics`` (simple metrics, with the filters a metric was defined with).

The joins stay what Strata proved: a metric only reaches a parent through a
many-to-one link, so no export can double count.
"""

from __future__ import annotations

import re

import yaml

from knowledge_graph import explore as kg
from knowledge_graph.build import qi
from ontology import simple
from semantic import definitions as defs
from semantic import model as sem

AGG = {"sum": "sum", "avg": "average", "count": "count", "count_distinct": "count_distinct"}


def _metrics(layer, ontology_id: str, status: str) -> list[dict]:
    want = {"certified": ("approved",), "all": ("approved", "draft")}[status]
    return [d for d in defs.list_definitions(layer.graph, sem.source_of(ontology_id))
            if d["status"] in want]


def _portable(sql: str, m: dict) -> str:
    """Strata's internal table references replaced by the tables' own names."""
    for s in sorted(m["sets"].values(), key=lambda x: -len(x["ref"])):
        sql = sql.replace(s["ref"], qi(s["table"]))
    return sql


def sql_views(layer, ontology_id: str, status: str = "certified", portable: bool = True) -> str:
    """One CREATE VIEW per metric. Each view returns the metric's value; group
    it by any listed dimension (the columns of the inner query)."""
    m = kg.model(layer, ontology_id)
    v = simple.view(layer.graph, ontology_id)
    out = [f"-- Governed metrics of the ontology \"{v['name']}\" (version {v.get('version')}),",
           "-- written by Strata. Each view is the metric exactly as defined there:",
           "-- the same filters and only many-to-one joins, so totals never double count.",
           "-- Tables are named as in the source; run where those tables are visible.", ""]
    for d in _metrics(layer, ontology_id, status):
        base = _portable(d["base_sql"], m) if portable else d["base_sql"]
        name = re.sub(r"[^a-z0-9_]", "_", d["name"].lower())
        dims = ", ".join(d.get("dimensions") or []) or "none"
        out += [f"-- {d['title']} ({'certified' if d['status'] == 'approved' else 'proposed'})"
                + (f", owner {d['owner']}" if d.get("owner") else ""),
                f"-- {d.get('description') or ''}".rstrip(),
                f"-- Group by: {dims}" + (f"; time: {d['time_column']}" if d.get("time_column") else ""),
                f"CREATE OR REPLACE VIEW {qi('metric_' + name)} AS",
                f"SELECT {d['value_expr']} AS {qi(name)}",
                f"FROM ({base}) m;", ""]
    return "\n".join(out)


def _sm_name(thing: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", thing.lower()).strip("_") or "model"


def metricflow(layer, ontology_id: str, status: str = "certified") -> str:
    """dbt MetricFlow YAML for the ontology's tables and its metrics."""
    m = kg.model(layer, ontology_id)
    metrics = _metrics(layer, ontology_id, status)
    metas = {d["name"]: sem._meta(layer.graph, ontology_id, d["name"]) for d in metrics}
    by_member: dict = {}
    for d in metrics:
        member = metas[d["name"]].get("member")
        if member in m["sets"]:
            by_member.setdefault(member, []).append(d)
    entity_of = {member: _sm_name(s["thing"]) for member, s in m["sets"].items()}
    models = []
    for member, s in m["sets"].items():
        if not s["key"]:
            continue
        entities = [{"name": entity_of[member], "type": "primary",
                     "expr": " || '|' || ".join(s["key_cols"]) if len(s["key_cols"]) > 1 else s["key_cols"][0]}]
        for link in m["links"]:
            if link["child"] == member and link["parent"] in entity_of:
                entities.append({"name": entity_of[link["parent"]], "type": "foreign",
                                 "expr": link["child_col"]})
        dims, time_dim = [], None
        for f in s["fields"]:
            if f["column"] in s["key_cols"] or f.get("personal"):
                continue
            if f.get("role") == "date":
                dims.append({"name": f["column"], "type": "time", "label": f["label"],
                             "type_params": {"time_granularity": "day"}})
                time_dim = time_dim or f["column"]
            elif f.get("role") in ("category", "flag", "location"):
                dims.append({"name": f["column"], "type": "categorical", "label": f["label"]})
        measures = []
        for d in by_member.get(member, []):
            meta = metas[d["name"]]
            agg = AGG.get(meta.get("agg"), "sum")
            col = str(meta.get("field") or "").rsplit(".", 1)[-1] or None
            measures.append({"name": d["name"], "agg": agg, "label": d["title"],
                             "expr": col if col else "1",
                             **({"agg_time_dimension": time_dim} if time_dim else {})})
        sm = {"name": entity_of[member], "description": f"{s['thing']} (one row per record).",
              "model": f"ref('{s['table']}')", "entities": entities, "dimensions": dims}
        if time_dim:
            sm["defaults"] = {"agg_time_dimension": time_dim}
        if measures:
            sm["measures"] = measures
        models.append(sm)
    out_metrics = []
    for d in metrics:
        meta = metas[d["name"]]
        entry = {"name": d["name"], "label": d["title"], "description": d.get("description") or "",
                 "type": "simple", "type_params": {"measure": d["name"]}}
        filters = []
        for flt in meta.get("filters") or []:
            col = str(flt.get("column") or "")
            filters.append(f"{{{{ Dimension('{entity_of.get(meta.get('member'), 'model')}__{col}') }}}}"
                           f" = '{str(flt.get('value')).replace(chr(39), chr(39) * 2)}'")
        if filters:
            entry["filter"] = " AND ".join(filters)
        if d.get("owner"):
            entry["meta"] = {"owner": d["owner"], "certified_by": "Strata"}
        out_metrics.append(entry)
    doc = {"semantic_models": models, "metrics": out_metrics}
    head = (f"# dbt MetricFlow semantic models and metrics, written by Strata for\n"
            f"# \"{m['ontology']['name']}\". Joins are the links Strata proved in the data.\n")
    return head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
