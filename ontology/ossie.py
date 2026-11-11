"""Apache Ossie (Open Semantic Interchange) YAML, in and out.

Ossie is the interchange format NVIDIA Auto Ontology, Snowflake and others
read and write (spec 0.3.0.dev0: one model per document; `datasets` with
`fields` and `metrics`; `relationships` from the many side to the one side;
`ai_context` for synonyms and instructions; `nonportable_extensions` for
anything vendor-specific).

* ``to_ossie(graph, ontology_id)`` writes the published ontology: one dataset
  per source table, every field with its meaning, unit and data check, the
  proven links as relationships, calculations as metrics, and a ``strata``
  extension with the confirmed share and the thing names.
* ``parse_ossie(data, path)`` reads an Ossie document into the metadata
  shape ``ontology.metadata`` already understands, so a model written by
  another tool flows into a build like a Power BI model or a dbt file.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSION = "0.3.0.dev0"
VENDOR = "strata"

_TO_OSSIE = {"BIGINT": "Integer", "INTEGER": "Integer", "INT": "Integer", "SMALLINT": "Integer",
             "TINYINT": "Integer", "HUGEINT": "Integer", "UBIGINT": "Integer",
             "DOUBLE": "Float", "FLOAT": "Float", "REAL": "Float", "DECIMAL": "Decimal",
             "NUMERIC": "Decimal", "BOOLEAN": "Boolean", "DATE": "Date", "TIME": "Time",
             "TIMESTAMP": "DateTime", "DATETIME": "DateTime",
             "TIMESTAMP WITH TIME ZONE": "DateTimeTz", "TIMESTAMPTZ": "DateTimeTz",
             "VARCHAR": "String", "TEXT": "String", "STRING": "String", "UUID": "String"}
_FROM_OSSIE = {"Integer": "BIGINT", "Decimal": "DECIMAL", "Float": "DOUBLE",
               "Boolean": "BOOLEAN", "Date": "DATE", "Time": "TIME", "DateTime": "TIMESTAMP",
               "DateTimeTz": "TIMESTAMPTZ", "String": "VARCHAR"}


def datatype(sql_type: str) -> str | None:
    t = re.sub(r"\(.*\)", "", str(sql_type or "")).strip().upper()
    return _TO_OSSIE.get(t)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(text).lower()).strip("_") or "x"


# ------------------------------------------------------------------ out
def build_model(graph, ontology_id: str, version: int | None = None) -> dict:
    """The Ossie document as a plain dict (YAML-ready)."""
    from ontology import simple
    v = simple.view(graph, ontology_id, version=version, published=True)
    datasets, names, dataset_of_table = [], set(), {}
    for thing in v["things"]:
        tables = [t for t in thing["tables"] if "#" not in t]      # graph things are not tables
        for table in tables:
            name = slug(thing["name"]) if len(tables) == 1 else slug(f"{thing['name']} {table.split('.', 1)[1]}")
            base, n = name, 2
            while name in names:
                name = f"{base}_{n}"
                n += 1
            names.add(name)
            dataset_of_table[table] = name
            fields = [f for f in thing["fields"] if f["table"] == table]
            ds = {"name": name, "source": table, "description": thing["description"]}
            keys = [f["column"] for f in fields if f["role"] == "identifier" and f["check"] == "verified"]
            if keys:
                ds["primary_key"] = keys[:1]
            ds["ai_context"] = {"synonyms": [thing["name"]],
                                "instructions": f"One row is one {thing['name']}. "
                                                f"{thing['records']:,} records."}
            ds["fields"] = []
            for f in fields:
                field = {"name": f["column"], "expression": {"sql": f["column"]},
                         "description": f["meaning"]}
                dt = datatype(f["type"])
                if dt:
                    field["datatype"] = dt
                notes = [f"Role: {f['role_label']}."]
                if f["unit"]:
                    notes.append(f"Unit: {f['unit']}.")
                notes.append({"verified": "Confirmed by the data", "conflict":
                              "The data disagreed with the AI", "unchecked": "Not checked"}
                             [f["check"]] + (f" ({f['proof']})." if f["proof"] else "."))
                field["ai_context"] = {"synonyms": [f["label"]], "instructions": " ".join(notes)}
                if f["role"] == "date":
                    field["dimension"] = {"is_time": True}
                ds["fields"].append(field)
            calcs = [c for c in v["calculations"] if c["thing"] == thing["name"]]
            if calcs:
                ds["metrics"] = [{"name": slug(c["name"]), "expression": {"sql": c["expression"]},
                                  **({"description": c["description"]} if c.get("description") else {})}
                                 for c in calcs]
            datasets.append(ds)
    relationships, seen = [], set()
    for link in v["links"]:
        if not link.get("from") or not link.get("to"):
            continue
        ft, fc = link["from"].rsplit(".", 1)
        tt, tc = link["to"].rsplit(".", 1)
        if ft not in dataset_of_table or tt not in dataset_of_table:
            continue
        name = slug(f"{dataset_of_table[ft]}_{fc}_to_{dataset_of_table[tt]}")
        if name in seen:
            continue
        seen.add(name)
        rel = {"name": name, "from": dataset_of_table[ft], "to": dataset_of_table[tt],
               "from_columns": [fc], "to_columns": [tc],
               "ai_context": {"instructions": link["label"] + (
                   f" Checked in the data: {link['match']:.0%} of rows match."
                   if isinstance(link.get("match"), (int, float)) else "")}}
        relationships.append(rel)
    model = {
        "version": VERSION, "name": slug(v["id"]),
        "description": v["name"] + (f" - {v['domain']}" if v["domain"] else ""),
        "ai_context": {"instructions": (
            f"Published ontology version {v['version']} built by Strata; "
            f"{v['summary']['confirmed_pct']}% of fields confirmed by the data. Prefer fields "
            "whose instructions say 'Confirmed by the data'."),
            "examples": [n["text"] for n in v.get("notes", [])][-5:]},
        "datasets": datasets,
    }
    if relationships:
        model["relationships"] = relationships
    model["nonportable_extensions"] = [{"vendor_name": VENDOR, "data": {
        "ontology": v["id"], "published_version": v["version"], "published_at": v["published_at"],
        "confirmed_pct": v["summary"]["confirmed_pct"], "fields_checked": v["summary"]["checks"],
        "things": [{"name": t["name"], "tables": t["tables"], "records": t["records"]}
                   for t in v["things"]]}}]
    return model


def to_ossie(graph, ontology_id: str, version: int | None = None) -> str:
    import yaml
    return yaml.safe_dump(build_model(graph, ontology_id, version), sort_keys=False,
                          allow_unicode=True, width=100)


# ------------------------------------------------------------------- in
def is_ossie(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("datasets"), list) \
        and "version" in data and "name" in data


def _synonym(ctx) -> str:
    if isinstance(ctx, dict):
        syn = ctx.get("synonyms") or []
        return str(syn[0]) if syn else ""
    return ""


def parse_ossie(data: dict, path: Path) -> dict:
    """An Ossie document in the ``ontology.metadata`` shape."""
    from ontology.metadata import MetadataError, _empty, _table, _text
    if not is_ossie(data):
        raise MetadataError(f"{path.name} is not an Ossie document (needs version, name, datasets)")
    out = _empty("ossie", path)
    source_of = {}
    for ds in data["datasets"]:
        if not isinstance(ds, dict) or not ds.get("name"):
            continue
        source = str(ds.get("source") or ds["name"])
        table_name = source.split(".")[-1]
        source_of[ds["name"]] = table_name
        table = _table(out, table_name)
        table["description"] = _text(ds.get("description"))
        for f in ds.get("fields") or []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            expr = f.get("expression") or {}
            column = str(expr.get("sql") or f["name"]) if isinstance(expr, dict) else f["name"]
            unit = ""
            ctx = f.get("ai_context")
            if isinstance(ctx, dict):
                m = re.search(r"Unit:\s*([^.;]+)", str(ctx.get("instructions") or ""))
                unit = m.group(1).strip() if m else ""
            table["columns"][f["name"]] = {
                "description": _text(f.get("description")),
                "type": _FROM_OSSIE.get(str(f.get("datatype") or ""), ""),
                "label": _synonym(ctx), "unit": unit,
                "source_column": column if re.fullmatch(r"[A-Za-z_][\w]*", column) else f["name"]}
        for m in ds.get("metrics") or []:
            if isinstance(m, dict) and m.get("name"):
                expr = m.get("expression") or {}
                out["measures"].append({"table": table_name, "name": m["name"],
                                        "expression": str(expr.get("sql") or "")
                                        if isinstance(expr, dict) else str(expr),
                                        "description": _text(m.get("description"))})
    for m in data.get("metrics") or []:
        if isinstance(m, dict) and m.get("name"):
            expr = m.get("expression") or {}
            out["measures"].append({"table": "*", "name": m["name"],
                                    "expression": str(expr.get("sql") or "")
                                    if isinstance(expr, dict) else str(expr),
                                    "description": _text(m.get("description"))})
    for r in data.get("relationships") or []:
        if not isinstance(r, dict) or not (r.get("from") and r.get("to")):
            continue
        fc, tc = list(r.get("from_columns") or []), list(r.get("to_columns") or [])
        if not fc or not tc:
            continue
        out["relationships"].append({
            "from_table": source_of.get(r["from"], str(r["from"])),
            "from_column": str(fc[0]), "to_table": source_of.get(r["to"], str(r["to"])),
            "to_column": str(tc[0]), "active": True})
    return out
