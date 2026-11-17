"""Strata Model v1: the ontology as one open JSON document.

This is the hand-over format between the layers, and between Strata and
anything else. Our ontology writes it; a team with its own ontology can write
it by hand (or from their tool) and use Strata's Knowledge graph, Semantic
and Context layers on top. The JSON Schema is ``docs/spec/strata-model.schema.json``.

    {"spec": "strata.model/v1", "name": "Shop", "version": 3,
     "things": [{"name": "Order", "description": "...", "tables": ["shop.orders"],
                 "key": ["order_id"],
                 "fields": [{"name": "Order Status", "column": "status",
                             "table": "shop.orders", "role": "category",
                             "type": "VARCHAR", "unit": null, "meaning": "...",
                             "personal": null, "check": "verified", "proof": "..."}]}],
     "links": [{"from_thing": "Order", "to_thing": "Customer",
                "from": {"table": "shop.orders", "column": "customer_id"},
                "to": {"table": "shop.customers", "column": "id"},
                "cardinality": "many-to-one", "match": 1.0}],
     "notes": [{"text": "Gross Amount is in euros"}]}

Only ``spec``, ``name`` and ``things`` (each with ``name`` and ``tables``) are
required. A table is written ``source.table``; on import only the table part
is matched, so the document works on the importer's own copy of the data.
Everything a document says is used as written ("your model wins") and then
checked against the data, like any other claim.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ontology import meaning as mn

SPEC = "strata.model/v1"
ROLES = tuple(mn.ROLES)
CHECKS = ("verified", "conflict", "unchecked")
CARDINALITIES = ("many-to-one", "one-to-one", "one-to-many", "many-to-many")


class ContractError(ValueError):
    """A Strata Model document that cannot be used, with every reason listed."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("not a valid Strata Model: " + "; ".join(problems[:8])
                         + (f" (and {len(problems) - 8} more)" if len(problems) > 8 else ""))


# ------------------------------------------------------------------ export
def to_contract(graph, ontology_id: str, version: int | None = None) -> dict:
    """The ontology (live, or a pinned version) as a Strata Model document."""
    from ontology import simple
    v = simple.view(graph, ontology_id, version=version)
    things = []
    for t in v["things"]:
        keys = [f["column"] for f in t["fields"] if f["role"] == "identifier"]
        things.append({
            "name": t["name"], "description": t["description"], "tables": list(t["tables"]),
            "records": t["records"], "key": keys[:1], "by": t["by"],
            "fields": [{"name": f["label"], "column": f["column"], "table": f["table"],
                        "role": f["role"], "type": f["type"], "unit": f["unit"],
                        "meaning": f["meaning"], "personal": f["personal"],
                        "links_to": f["links_to"], "check": f["check"], "proof": f["proof"],
                        "by": f["by"]}
                       for f in t["fields"]]})
    links = []
    for link in v["links"]:
        if not link.get("from") or not link.get("to") or "#" in str(link["from"]):
            continue
        ft, fc = str(link["from"]).rsplit(".", 1)
        tt, tc = str(link["to"]).rsplit(".", 1)
        links.append({"from_thing": link["from_thing"], "to_thing": link["to_thing"],
                      "from": {"table": ft, "column": fc}, "to": {"table": tt, "column": tc},
                      "cardinality": link["cardinality"], "label": link["label"],
                      "match": link.get("match"), "declared": bool(link.get("declared"))})
    return {
        "spec": SPEC, "id": v["id"], "name": v["name"], "domain": v.get("domain") or "",
        "version": v.get("version"), "published_at": v.get("published_at"),
        "generated_by": "Strata", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": list(v["sources"]),
        "confirmed_pct": v["summary"]["confirmed_pct"],
        "things": things, "links": links,
        "notes": [{"text": n.get("text", ""), "at": n.get("at")} for n in v["notes"]],
    }


# ---------------------------------------------------------------- validate
def _is_str(x) -> bool:
    return isinstance(x, str) and x.strip() != ""


def validate(doc) -> list[str]:
    """Every problem in the document, in plain words. Empty means usable."""
    if not isinstance(doc, dict):
        return ["the document must be a JSON object"]
    out = []
    if doc.get("spec") != SPEC:
        out.append(f'"spec" must be "{SPEC}"')
    if not _is_str(doc.get("name")):
        out.append('"name" is required')
    things = doc.get("things")
    if not isinstance(things, list) or not things:
        out.append('"things" must be a non-empty list')
        things = []
    names = set()
    for i, t in enumerate(things):
        where = f"things[{i}]"
        if not isinstance(t, dict):
            out.append(f"{where} must be an object")
            continue
        if not _is_str(t.get("name")):
            out.append(f"{where}.name is required")
        elif t["name"].lower() in names:
            out.append(f"{where}.name {t['name']!r} is used twice")
        else:
            names.add(t["name"].lower())
            where = f"thing {t['name']!r}"
        tables = t.get("tables")
        if not isinstance(tables, list) or not tables or not all(_is_str(x) for x in tables):
            out.append(f"{where}: tables must be a non-empty list of table names")
        for j, f in enumerate(t.get("fields") or []):
            fw = f"{where} fields[{j}]"
            if not isinstance(f, dict):
                out.append(f"{fw} must be an object")
                continue
            if not _is_str(f.get("column")):
                out.append(f"{fw}.column is required")
            else:
                fw = f"{where} field {f['column']!r}"
            if f.get("role") not in (None, "") and f["role"] not in ROLES:
                out.append(f"{fw}: role must be one of {', '.join(ROLES)}")
            if f.get("check") not in (None, "") and f["check"] not in CHECKS:
                out.append(f"{fw}: check must be one of {', '.join(CHECKS)}")
            if f.get("table") not in (None, "") and isinstance(tables, list) and f["table"] not in tables:
                out.append(f"{fw}: table {f['table']!r} is not one of the thing's tables")
    for i, link in enumerate(doc.get("links") or []):
        where = f"links[{i}]"
        if not isinstance(link, dict):
            out.append(f"{where} must be an object")
            continue
        for end in ("from", "to"):
            e = link.get(end)
            if not isinstance(e, dict) or not _is_str(e.get("table")) or not _is_str(e.get("column")):
                out.append(f"{where}.{end} needs a table and a column")
        if link.get("cardinality") not in (None, "") and link["cardinality"] not in CARDINALITIES:
            out.append(f"{where}: cardinality must be one of {', '.join(CARDINALITIES)}")
    for i, n in enumerate(doc.get("notes") or []):
        if not isinstance(n, dict) or not _is_str(n.get("text")):
            out.append(f"notes[{i}] needs a text")
    return out


def is_contract(data) -> bool:
    return isinstance(data, dict) and data.get("spec") == SPEC


# ------------------------------------------------------------------ import
def _bare(table: str) -> str:
    """'shop.orders' -> 'orders': the importer's source id is its own."""
    return str(table).split(".", 1)[1] if "." in str(table) else str(table)


def to_metadata(doc: dict, path: Path | str = "model.json") -> dict:
    """The document in the shape ``ontology.metadata`` reads, marked
    ``exact``: build exactly these things, fields and links."""
    problems = validate(doc)
    if problems:
        raise ContractError(problems)
    name = Path(path).name
    out = {"kind": "strata", "file": name, "exact": True, "tables": {}, "relationships": [],
           "measures": [], "notes": [n["text"] for n in doc.get("notes") or []]}
    for t in doc["things"]:
        for table in t["tables"]:
            entry = out["tables"].setdefault(_bare(table), {"description": "", "columns": {}})
            entry["thing"] = t["name"]
            entry["description"] = t.get("description") or entry["description"]
            entry["key"] = list(t.get("key") or [])
            entry["listed"] = bool(t.get("fields"))
        for f in t.get("fields") or []:
            table = _bare(f.get("table") or t["tables"][0])
            out["tables"].setdefault(table, {"description": "", "columns": {}, "thing": t["name"]})
            out["tables"][table]["columns"][f["column"]] = {
                "label": f.get("name") or "", "description": f.get("meaning") or "",
                "type": f.get("type") or "", "unit": f.get("unit") or "",
                "role": f.get("role") or ""}
    for link in doc.get("links") or []:
        out["relationships"].append({
            "from_table": _bare(link["from"]["table"]), "from_column": link["from"]["column"],
            "to_table": _bare(link["to"]["table"]), "to_column": link["to"]["column"],
            "active": True, "cardinality": link.get("cardinality") or "many-to-one"})
    return out


def read(path: str | Path) -> dict:
    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise ContractError([f"{p.name} is not valid JSON: {exc}"]) from exc
    return to_metadata(doc, p)
