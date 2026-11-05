"""Publish: where the ontology lives, and how every tool reads it.

The answer to "where does the ontology live?" has three parts:

1. **The registry** (``ontology/registry.py``) is the system of record:
   proposals, decisions, owners, audit, numbered versions.
2. **The customer's Git repo.** ``export_folder`` writes a published version
   as ontology-as-code - OWL/Turtle, SHACL shapes, JSON, one file per concept
   and per data contract, a README and a CHANGELOG - so a change is reviewed
   in a pull request like any other code (the Atlan AI Registry pattern).
3. **Live access.** The read functions at the bottom serve a PINNED version
   to the MCP tools and the REST API. Context, Semantic, Copilot, Databricks
   or Snowflake agents all read the same definitions through them, never the
   raw tables; that boundary is what keeps the four tools separable.

Governance (maturity levels 2 and 4): a concept shared across systems is
**core**, owned by the governance team; a single-system concept is an
**extension**, owned by that system's team. Data contracts per source table
are frozen into each version, which is what drift detection compares with.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ontology import registry as reg
from ontology.concepts import _tables
from ontology.mapping import AMOUNT_PROPS, ISO_CURRENCIES

BASE = "https://strata.example/ontology/"


# -------------------------------------------------------------- owners
def assign_owners(graph, ontology_id: str) -> dict:
    onto = reg.get(graph, ontology_id)
    team = {s["source_id"]: s["owner_team"] for s in onto["sources"]}
    governance = next((s["owner_team"] for s in onto["sources"]
                       if s["role"] == "mdm_hub"), "")
    concept_owner, table_owner = {}, {}
    for item in reg.items(graph, ontology_id, kind="concept"):
        c = item["payload"]
        sources = sorted({m.split(".", 1)[0] for m in c.get("members", [])})
        for m in c.get("members", []):
            table_owner[m] = team.get(m.split(".", 1)[0], "")
        if c.get("master") or len(sources) > 1:
            tier = "core"
            owner = team.get((c.get("master") or "").split(".", 1)[0]) or governance \
                or team.get(sources[0], "")
        else:
            tier = "extension"
            owner = team.get(sources[0], "") if sources else ""
        concept_owner[c["name"]] = owner
        reg.annotate(graph, ontology_id, "concept", item["key"], owner=owner, tier=tier)

    def owner_of(kind, item):
        p = item["payload"]
        if kind in ("mapping", "contract"):
            return table_owner.get(p.get("table", item["key"]), "")
        if kind == "member":
            return table_owner.get(p.get("table"), "")
        if kind in ("relationship", "rule"):
            ref = p.get("from") or p.get("table", "")
            return table_owner.get(ref.rsplit(".", 1)[0] if ref.count(".") > 1 else ref, "")
        if kind in ("identity", "hierarchy", "survivorship"):
            return concept_owner.get(p.get("concept", item["key"].split(".")[0]), "")
        if kind == "action":
            return p.get("approver", "")
        if kind == "property":
            return governance
        return ""

    for kind in ("member", "mapping", "relationship", "rule", "identity", "hierarchy",
                 "survivorship", "action", "property"):
        for item in reg.items(graph, ontology_id, kind=kind):
            owner = owner_of(kind, item)
            if owner:
                reg.annotate(graph, ontology_id, kind, item["key"], owner=owner)
    return concept_owner


# ----------------------------------------------------------- contracts
def build_contracts(layer, ontology_id: str) -> list[dict]:
    """What each source table promises: columns and types, its key, its size
    and how fresh it must be. Frozen into every published version."""
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    sla = {s["source_id"]: s for s in onto["sources"]}
    props: dict = {}
    for m in reg.items(graph, ontology_id, kind="mapping"):
        if m["status"] != "rejected":
            props.setdefault(m["payload"]["table"], {})[m["payload"]["column"]] = \
                m["payload"]["property"]
    out = []
    for t in _tables(layer, onto):
        src = sla[t["source"]]
        contract = {
            "table": t["key"], "source": t["source"], "key": t["id"],
            "rows": t["rows"], "freshness_sla_days": src["cadence_days"],
            "owner_team": src["owner_team"], "role": src["role"],
            "columns": [{"name": c.name, "type": str(c.type),
                         "nullable": bool(c.nullable),
                         "property": props.get(t["key"], {}).get(c.name)}
                        for c in t["table"].columns if not c.name.startswith("__")]}
        reg.put(graph, ontology_id, "contract", t["key"], contract, fact=True,
                confidence=1.0, owner=src["owner_team"],
                evidence=[f"{len(contract['columns'])} columns, {t['rows']:,} rows"])
        out.append(contract)
    return out


def publish_version(layer, ontology_id: str, by: str, notes: str = "") -> dict:
    assign_owners(layer.graph, ontology_id)
    build_contracts(layer, ontology_id)
    return reg.publish(layer.graph, ontology_id, by=by, notes=notes)


# --------------------------------------------------------------- exports
def _by_kind(version: dict) -> dict:
    out: dict = {}
    for item in version["items"]:
        out.setdefault(item["kind"], {})[item["key"]] = item
    return out


def _iri(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(text))


def _lit(text) -> str:
    s = str(text).replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s.replace("\n", "\\n").replace("\r", "") + '"'


def _prefixes(ontology_id: str) -> str:
    return (f"@prefix strata: <{BASE}{_iri(ontology_id)}#> .\n"
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
            "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
            "@prefix dcterms: <http://purl.org/dc/terms/> .\n\n")


def _datatype(prop: str, family_type: str = "") -> str:
    if prop in AMOUNT_PROPS or prop in ("quantity", "record_count"):
        return "xsd:decimal"
    if prop.endswith("_date") or prop in ("sync_timestamp", "last_updated"):
        return "xsd:date"
    return "xsd:string"


def to_turtle(graph, ontology_id: str, version: int | None = None) -> str:
    """The published ontology as OWL in Turtle."""
    v = reg.version(graph, ontology_id, version)
    onto = reg.get(graph, ontology_id)
    k = _by_kind(v)
    out = [_prefixes(ontology_id),
           f"<{BASE}{_iri(ontology_id)}> a owl:Ontology ;\n"
           f"    rdfs:label {_lit(onto['name'])} ;\n"
           f"    rdfs:comment {_lit(onto['problem'])} ;\n"
           f"    owl:versionInfo {_lit(v['version'])} ;\n"
           f"    dcterms:creator {_lit(v['by'])} .\n\n"]
    for key, item in sorted(k.get("concept", {}).items()):
        c = item["payload"]
        lines = [f"strata:{_iri(key)} a owl:Class", f"rdfs:label {_lit(key)}",
                 f"rdfs:comment {_lit(c.get('description', ''))}"]
        lines += [f"strata:sourceTable {_lit(m)}" for m in c.get("members", [])]
        if c.get("master"):
            lines.append(f"strata:masteredIn {_lit(c['master'])}")
        if item.get("owner"):
            lines.append(f"strata:owner {_lit(item['owner'])}")
        if c.get("tier"):
            lines.append(f"strata:tier {_lit(c['tier'])}")
        out.append(" ;\n    ".join(lines) + " .\n\n")
    props: dict = {}
    for key, item in k.get("mapping", {}).items():
        p = item["payload"]
        if p["property"] in ("identifier", "attribute", "date", "number"):
            continue
        entry = props.setdefault(p["property"], {"definition": p.get("definition", ""),
                                                 "columns": [], "concepts": set()})
        entry["columns"].append(key)
        entry["concepts"].add(p.get("concept"))
        entry["definition"] = p.get("definition") or entry["definition"]
    for prop, e in sorted(props.items()):
        lines = [f"strata:{_iri(prop)} a owl:DatatypeProperty",
                 f"rdfs:label {_lit(prop)}", f"rdfs:comment {_lit(e['definition'])}",
                 f"rdfs:range {_datatype(prop)}"]
        concepts = sorted(c for c in e["concepts"] if c)
        if len(concepts) == 1:
            lines.append(f"rdfs:domain strata:{_iri(concepts[0])}")
        lines += [f"strata:mappedFrom {_lit(c)}" for c in sorted(e["columns"])]
        out.append(" ;\n    ".join(lines) + " .\n\n")
    for key, item in sorted(k.get("relationship", {}).items()):
        p = item["payload"]
        name = f"{_iri(p['from_concept'])}_{_iri(p.get('name') or p['to_concept'])}"
        types = "owl:ObjectProperty" + (", owl:FunctionalProperty"
                                        if p.get("cardinality") else "")
        lines = [f"strata:{name} a {types}",
                 f"rdfs:domain strata:{_iri(p['from_concept'])}",
                 f"rdfs:range strata:{_iri(p['to_concept'])}",
                 "rdfs:comment " + _lit(p["from"] + " -> " + p["to"])]
        if p.get("cardinality"):
            lines.append(f"strata:cardinality {_lit(p['cardinality'])}")
        out.append(" ;\n    ".join(lines) + " .\n\n")
    for key, item in sorted(k.get("hierarchy", {}).items()):
        h = item["payload"]
        scheme = _iri(key)
        out.append(f"strata:{scheme} a skos:ConceptScheme ;\n    rdfs:label "
                   f"{_lit(' > '.join(h['levels']))} .\n")
        parent_level, child_level = h["levels"][0], h["levels"][-1]
        parents = sorted(set(h.get("parent_of", {}).values()))
        for value in parents:
            out.append(f"strata:{_iri(parent_level)}_{_iri(value)} a skos:Concept ;"
                       f" skos:prefLabel {_lit(value)} ; skos:inScheme strata:{scheme} .\n")
        for child, parent in sorted(h.get("parent_of", {}).items()):
            out.append(f"strata:{_iri(child_level)}_{_iri(child)} a skos:Concept ;"
                       f" skos:prefLabel {_lit(child)} ; skos:inScheme strata:{scheme} ;"
                       f" skos:broader strata:{_iri(parent_level)}_{_iri(parent)} .\n")
        out.append("\n")
    return "".join(out)


def to_shacl(graph, ontology_id: str, version: int | None = None) -> str:
    """SHACL shapes: what a valid instance of each concept looks like."""
    v = reg.version(graph, ontology_id, version)
    k = _by_kind(v)
    by_concept: dict = {}
    for item in k.get("mapping", {}).values():
        p = item["payload"]
        if p["property"] in ("identifier", "attribute", "date", "number"):
            continue
        by_concept.setdefault(p.get("concept"), {})[p["property"]] = p
    out = [_prefixes(ontology_id)]
    for concept in sorted(k.get("concept", {})):
        shapes = []
        for prop in sorted(by_concept.get(concept, {})):
            parts = [f"sh:path strata:{_iri(prop)}", f"sh:datatype {_datatype(prop)}"]
            if prop == "currency":
                parts.append("sh:in ( " + " ".join(_lit(c) for c in sorted(ISO_CURRENCIES))
                             + " )")
            elif prop == "country":
                parts.append('sh:pattern "^[A-Z]{2}$"')
            elif prop in AMOUNT_PROPS:
                parts.append("sh:maxCount 1")
            shapes.append("[ " + " ; ".join(parts) + " ]")
        body = [f"strata:{_iri(concept)}Shape a sh:NodeShape",
                f"sh:targetClass strata:{_iri(concept)}"]
        body += [f"sh:property {s}" for s in shapes]
        out.append(" ;\n    ".join(body) + " .\n\n")
    return "".join(out)


def export_folder(graph, ontology_id: str, path, version: int | None = None) -> Path:
    """Write a published version as an ontology-as-code folder for Git."""
    root = Path(path)
    v = reg.version(graph, ontology_id, version)
    onto = reg.get(graph, ontology_id)
    k = _by_kind(v)
    for sub in ("concepts", "contracts"):
        (root / sub).mkdir(parents=True, exist_ok=True)
        for old in (root / sub).glob("*.json"):
            old.unlink()

    def write(rel: str, text: str) -> None:
        (root / rel).write_text(text, encoding="utf-8", newline="\n")

    write("ontology.ttl", to_turtle(graph, ontology_id, v["version"]))
    write("shapes.ttl", to_shacl(graph, ontology_id, v["version"]))
    write("ontology.json", json.dumps({"ontology": onto, **v}, indent=2, default=str))
    for key, item in sorted(k.get("concept", {}).items()):
        mappings = {mk: m["payload"] for mk, m in k.get("mapping", {}).items()
                    if m["payload"].get("concept") == key}
        write(f"concepts/{_iri(key)}.json", json.dumps(
            {**item, "mappings": mappings}, indent=2, default=str))
    for key, item in sorted(k.get("contract", {}).items()):
        write(f"contracts/{_iri(key)}.json", json.dumps(item["payload"], indent=2,
                                                        default=str))
    numbers = [x["version"] for x in reg.versions(graph, ontology_id)
               if x["version"] <= v["version"]]
    log = [f"# Changelog: {onto['name']}\n"]
    for n in reversed(numbers):
        info = reg.version(graph, ontology_id, n)
        log.append(f"\n## Version {n} ({info['published_at']}, {info['by']})\n")
        if info["notes"]:
            log.append(f"\n{info['notes']}\n")
        if n > numbers[0]:
            d = reg.diff(graph, ontology_id, n - 1, n)
            for label in ("added", "changed", "removed"):
                for ref in d[label]:
                    log.append(f"- {label}: {ref['kind']} `{ref['key']}`\n")
        else:
            log.append(f"- first release: {len(info['items'])} approved items\n")
    write("CHANGELOG.md", "".join(log))
    counts = {kind: len(items) for kind, items in sorted(k.items())}
    write("README.md", (
        f"# {onto['name']} ontology, version {v['version']}\n\n"
        f"{onto['problem']}\n\n"
        f"Domain: {onto['domain']}. Published by {v['by']} on {v['published_at']}.\n\n"
        "## Contents\n\n"
        + "".join(f"- {n} {kind}(s)\n" for kind, n in counts.items())
        + "\n## Files\n\n"
        "- `ontology.ttl`: OWL classes, properties with definitions, relationships, "
        "taxonomies (SKOS)\n- `shapes.ttl`: SHACL shapes for validation\n"
        "- `ontology.json`: the full version, every item with its evidence\n"
        "- `concepts/`: one file per concept with its column mappings\n"
        "- `contracts/`: one data contract per source table\n\n"
        "## Live access\n\nAgents and tools read this version through Strata's MCP "
        "tools (`list_concepts`, `get_concept`, `map_column`, `resolve_entity`, "
        "`get_contract`, `validate_rules`, `ontology_version`) or the REST API "
        f"at `/api/eo/{ontology_id}`.\n"))
    return root


# ---------------------------------------------------------- read API
def version_info(graph, ontology_id: str, version: int | None = None) -> dict:
    v = reg.version(graph, ontology_id, version)
    counts: dict = {}
    for item in v["items"]:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {"ontology": ontology_id, "version": v["version"],
            "published_at": v["published_at"], "published_by": v["by"],
            "notes": v["notes"], "counts": counts,
            "versions": [x["version"] for x in reg.versions(graph, ontology_id)]}


def _meanings(k: dict) -> dict:
    """Plain meanings (simple flow) in a version: thing:<concept> and
    column:<source.table.column>."""
    return {key: item["payload"] for key, item in k.get("meaning", {}).items()}


def list_concepts(graph, ontology_id: str, version: int | None = None) -> dict:
    v = reg.version(graph, ontology_id, version)
    means = _meanings(_by_kind(v))
    concepts = [{"name": i["key"],
                 "label": means.get(f"thing:{i['key']}", {}).get("name") or i["key"],
                 "description": means.get(f"thing:{i['key']}", {}).get("description")
                 or i["payload"].get("description"),
                 "members": i["payload"].get("members", []),
                 "master": i["payload"].get("master"), "tier": i["payload"].get("tier"),
                 "owner": i.get("owner", "")}
                for i in v["items"] if i["kind"] == "concept"]
    return {"version": v["version"], "concepts": sorted(concepts, key=lambda c: c["name"])}


def get_concept(graph, ontology_id: str, concept: str, version: int | None = None) -> dict:
    v = reg.version(graph, ontology_id, version)
    k = _by_kind(v)
    if concept not in k.get("concept", {}):
        raise KeyError(f"no concept {concept!r} in version {v['version']}")
    item = k["concept"][concept]
    means = _meanings(k)
    thing = means.get(f"thing:{concept}", {})

    def prop(mk, m):
        out = {"column": mk, "property": m["payload"]["property"],
               "definition": m["payload"].get("definition"), "unit": m["payload"].get("unit")}
        plain = means.get(f"column:{mk}")
        if plain:
            out.update(label=plain.get("label"), meaning=plain.get("meaning"),
                       role=plain.get("role"), unit=plain.get("unit") or out["unit"],
                       check=plain.get("check"), proof=plain.get("proof"))
        return out
    return {
        "version": v["version"], "name": concept, **item["payload"],
        "label": thing.get("name") or concept,
        **({"description": thing["description"]} if thing.get("description") else {}),
        "owner": item.get("owner", ""), "evidence": item.get("evidence", []),
        "properties": sorted(
            (prop(mk, m) for mk, m in k.get("mapping", {}).items()
             if m["payload"].get("concept") == concept), key=lambda x: x["column"]),
        "relationships": [r["payload"] for r in k.get("relationship", {}).values()
                          if concept in (r["payload"].get("from_concept"),
                                         r["payload"].get("to_concept"))],
        "hierarchies": [h["payload"] for h in k.get("hierarchy", {}).values()
                        if h["payload"].get("concept") == concept],
        "survivorship": [s["payload"] for s in k.get("survivorship", {}).values()
                         if s["payload"].get("concept") == concept],
    }


def map_column(graph, ontology_id: str, column: str, version: int | None = None) -> dict:
    v = reg.version(graph, ontology_id, version)
    k = _by_kind(v)
    item = k.get("mapping", {}).get(column)
    if item is None:
        raise KeyError(f"column {column!r} is not mapped in version {v['version']}"
                       " (use source.table.column)")
    findings = [f["payload"] for f in reg.items(graph, ontology_id, kind="finding")
                if f["payload"].get("column") == column and f["status"] != "rejected"]
    plain = _meanings(k).get(f"column:{column}", {})
    extra = {f: plain[f] for f in ("label", "meaning", "role", "unit", "check", "proof")
             if plain.get(f) not in (None, "")}
    return {"version": v["version"], "column": column, **item["payload"], **extra,
            "confidence": item.get("confidence"), "evidence": item.get("evidence", []),
            "owner": item.get("owner", ""), "findings": findings}


def get_contract(graph, ontology_id: str, table: str, version: int | None = None) -> dict:
    v = reg.version(graph, ontology_id, version)
    item = _by_kind(v).get("contract", {}).get(table)
    if item is None:
        raise KeyError(f"no contract for {table!r} in version {v['version']}")
    return {"version": v["version"], **item["payload"]}


def validate_published_rules(layer, ontology_id: str, version: int | None = None) -> dict:
    from ontology.rules import _check
    v = reg.version(layer.graph, ontology_id, version)
    out = []
    for item in v["items"]:
        if item["kind"] != "rule":
            continue
        r = _check(layer.graph, item["payload"])
        out.append({"key": item["key"], "description": r["description"],
                    "severity": r.get("severity"), "violations": r["violations"],
                    "sample": r["violating"][:20]})
    return {"version": v["version"], "rules": out}
