"""The Ontology Accelerator: the journey, step by step, as one runnable unit.

Input: several sources, each with a role (source system, MDM hub, data mart,
reference), an owner team and a refresh SLA, plus the problem statement.
Output: one governed, versioned enterprise ontology published where any tool
can use it, with an honest maturity scorecard.

The steps below are the single definition the API, the UI stepper and the
tests share. Every step writes proposals with evidence to the registry; a
person approves; publishing freezes a version.
"""

from __future__ import annotations

import time
from importlib import import_module

from ontology import maturity
from ontology import registry as reg

STEPS = [
    {"id": "intake", "title": "Intake", "level": 1, "kinds": [],
     "what": "The problem, the business questions, and each source's role, owner "
             "and refresh SLA. Every later suggestion is judged against these."},
    {"id": "profile", "title": "Connect and profile", "level": 1, "kinds": ["profile"],
     "module": "ontology.profile", "func": "profile_ontology",
     "what": "Every column measured: type, nulls, distinct values, ranges, top "
             "values, and how fresh each table is."},
    {"id": "concepts", "title": "Shared concepts", "level": 3,
     "kinds": ["concept", "member"], "module": "ontology.concepts",
     "func": "propose_concepts",
     "what": "Tables in different systems that are the same business thing "
             "(CRM account, ERP customer, MDM golden customer) become one concept, "
             "on crosswalk or attribute evidence."},
    {"id": "mapping", "title": "Properties with meaning", "level": 3,
     "kinds": ["mapping", "property"], "module": "ontology.mapping",
     "func": "map_properties",
     "what": "Every column mapped to a defined property with its unit. The amount "
             "solver uses names, row arithmetic (net + tax = gross) and "
             "reconciliation against other systems."},
    {"id": "structure", "title": "Relationships and hierarchies", "level": 1,
     "kinds": ["relationship", "hierarchy"], "module": "ontology.structure",
     "func": "propose_structure",
     "what": "Links between concepts with measured cardinality and optionality; "
             "drill paths (Region > Country) from functional dependencies."},
    {"id": "identity", "title": "Identity across sources", "level": 3,
     "kinds": ["identity"], "module": "ontology.identity", "func": "resolve_identities",
     "what": "Which records in which systems are one entity: the hub's "
             "cross-references first, then tax id and name + country. Duplicate "
             "golden records are found."},
    {"id": "survivorship", "title": "Conflicts, freshness, survivorship", "level": 4,
     "kinds": ["freshness", "conflict", "survivorship"], "module": "ontology.survivorship",
     "func": "assess",
     "what": "How far behind each source is against its SLA, where systems disagree "
             "about the same entity, and which source should win each property."},
    {"id": "rules", "title": "Rules and actions", "level": 4, "kinds": ["rule", "action"],
     "module": "ontology.rules", "func": "propose_rules",
     "what": "Validation rules derived from what the data proved, checked live; "
             "action types an agent may propose but never execute."},
    {"id": "govern", "title": "Ownership and approval", "level": 2, "kinds": [],
     "what": "Core concepts owned by governance, extensions by their system's team; "
             "approvers decide, every decision is audited."},
    {"id": "publish", "title": "Publish", "level": 3, "kinds": ["contract"],
     "what": "A numbered version with data contracts, a diff, OWL/Turtle + SHACL "
             "exports and a Git folder; MCP and REST serve the pinned version."},
    {"id": "drift", "title": "Drift watch", "level": 5, "kinds": ["drift"],
     "what": "On reload, sources are compared with their contracts; changes and "
             "agents' unanswered questions become proposals."},
]
RUNNABLE = [s for s in STEPS if s.get("module")]


def _summary(step_id: str, out: dict) -> str:
    if step_id == "profile":
        return f"{len(out)} tables, {sum(p['rows'] for p in out):,} rows profiled"
    if step_id == "concepts":
        return ", ".join(f"{c['name']} ({len(c['members'])})" for c in out["concepts"])
    if step_id == "mapping":
        amounts = sum(1 for c in out["columns"].values() if "amount" in c["property"].split("_"))
        return (f"{len(out['columns'])} columns mapped ({amounts} money columns); "
                f"{len(out['findings'])} finding(s)")
    if step_id == "structure":
        return (f"{len(out['relationships'])} relationship(s), "
                f"{len(out['hierarchies'])} hierarchy(ies)")
    if step_id == "identity":
        parts = [f"{name}: {r['records']:,} records -> {r['entities']:,} entities"
                 for name, r in out["concepts"].items()]
        return "; ".join(parts) + f"; {len(out['findings'])} duplicate(s)"
    if step_id == "survivorship":
        breaches = [f["source"] for f in out["freshness"] if f["breach"]]
        conflicts = sum(c["entities_in_conflict"] for c in out["conflicts"])
        return (f"{len(breaches)} source(s) behind SLA"
                + (f" ({', '.join(breaches)})" if breaches else "")
                + f"; {conflicts} conflicting value(s)")
    if step_id == "rules":
        broken = sum(1 for r in out["rules"] if r["violations"])
        return f"{len(out['rules'])} rules ({broken} with violations), " \
               f"{len(out['actions'])} action types"
    return ""


def run(layer, ontology_id: str, upto: str | None = None, progress=None) -> dict:
    """Run the accelerator's steps in order (up to `upto`), with timings."""
    say = progress or (lambda _line: None)
    reg.get(layer.graph, ontology_id)
    steps = []
    for step in RUNNABLE:
        say(f"{step['title']}...")
        started = time.perf_counter()
        out = getattr(import_module(step["module"]), step["func"])(layer, ontology_id)
        seconds = round(time.perf_counter() - started, 2)
        summary = _summary(step["id"], out)
        say(f"{step['title']}: {summary} ({seconds}s)")
        steps.append({"id": step["id"], "title": step["title"], "seconds": seconds,
                      "summary": summary})
        if step["id"] == upto:
            break
    return {"ontology": ontology_id, "steps": steps,
            "seconds": round(sum(s["seconds"] for s in steps), 2)}


def state(graph, ontology_id: str) -> dict:
    """Everything the journey page needs, in one read."""
    onto = reg.get(graph, ontology_id)
    every = reg.items(graph, ontology_id)
    counts: dict = {}
    for item in every:
        c = counts.setdefault(item["kind"], {"proposed": 0, "approved": 0, "rejected": 0})
        c[item["status"]] = c.get(item["status"], 0) + 1
    versions = reg.versions(graph, ontology_id)
    steps = []
    for step in STEPS:
        kinds = step["kinds"]
        total = sum(sum(counts.get(k, {}).values()) for k in kinds)
        pending = sum(counts.get(k, {}).get("proposed", 0) for k in kinds)
        if step["id"] == "intake":
            status = "done"
        elif step["id"] == "govern":
            status = "done" if reg.roles(graph, ontology_id) else \
                ("ready" if counts.get("rule") else "waiting")
        elif step["id"] == "publish":
            status = "done" if versions else ("ready" if counts.get("rule") else "waiting")
        elif step["id"] == "drift":
            status = "done" if any(i["key"] == "_last_check" for i in every
                                   if i["kind"] == "drift") else \
                ("ready" if versions else "waiting")
        else:
            status = ("review" if pending else "done") if total else "waiting"
        steps.append({k: step[k] for k in ("id", "title", "level", "what", "kinds")}
                     | {"status": status, "items": total, "pending": pending})
    findings = [i["payload"] | {"key": i["key"], "status": i["status"]}
                for i in every if i["kind"] == "finding"]
    return {"ontology": onto, "steps": steps, "counts": counts, "findings": findings,
            "versions": versions, "roles": reg.roles(graph, ontology_id),
            "maturity": maturity.score(graph, ontology_id)}


def knowledge_map(graph, ontology_id: str) -> dict:
    """Concepts, the source tables behind them, links and drill paths, as a
    graph for the canvas."""
    nodes, edges = [], []
    for item in reg.items(graph, ontology_id, kind="concept"):
        if item["status"] == "rejected":
            continue
        c = item["payload"]
        nodes.append({"id": f"concept:{item['key']}", "type": "concept",
                      "label": item["key"], "status": item["status"],
                      "tier": c.get("tier"), "owner": item["owner"],
                      "description": c.get("description")})
        for m in c.get("members", []):
            nodes.append({"id": f"table:{m}", "type": "table", "label": m,
                          "source": m.split(".", 1)[0],
                          "master": m == c.get("master")})
            edges.append({"from": f"table:{m}", "to": f"concept:{item['key']}",
                          "type": "member", "label": "master" if m == c.get("master")
                          else "member"})
    for item in reg.items(graph, ontology_id, kind="relationship"):
        p = item["payload"]
        if item["status"] == "rejected":
            continue
        edges.append({"from": f"concept:{p['from_concept']}",
                      "to": f"concept:{p['to_concept']}", "type": "relationship",
                      "label": p.get("cardinality") or "links to",
                      "detail": f"{p['from']} -> {p['to']}"})
    for item in reg.items(graph, ontology_id, kind="hierarchy"):
        h = item["payload"]
        node = f"hierarchy:{item['key']}"
        nodes.append({"id": node, "type": "hierarchy", "label": " > ".join(h["levels"])})
        edges.append({"from": f"concept:{h['concept']}", "to": node, "type": "hierarchy",
                      "label": "drill path"})
    seen, unique = set(), []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            unique.append(n)
    return {"nodes": unique, "edges": edges}
