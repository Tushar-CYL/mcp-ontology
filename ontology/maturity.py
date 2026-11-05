"""The ontology maturity scorecard (Modern Data 101's five levels).

1. Infrastructure - object, link and action types exist over connected data.
2. Ownership - every concept has an owner; core vs extension is clear; people
   with the approver role make the decisions.
3. Standardisation - "Customer means the same everywhere": shared concepts
   across systems, columns mapped to one glossary, data contracts, a standard
   output API.
4. Governed - versioned releases, an audit trail, access control, freshness
   SLAs measured, validation rules checked.
5. Autonomous - drift is detected and proposed, proposals come from the data
   with evidence, usage feeds back into the ontology.

Each check is computed from the registry, never asserted. A level counts
only when it and every level below it pass, which is how most ontologies end
up stuck at 1-2: the scorecard shows exactly which checks hold them there.
"""

from __future__ import annotations

from ontology import registry as reg

LEVELS = [(1, "Infrastructure"), (2, "Ownership"), (3, "Standardisation"),
          (4, "Governed"), (5, "Autonomous")]
GLOSSARY_SHARE = 0.9
_UNMAPPED = {"attribute", "number", "date", "amount_unclassified"}


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def score(graph, ontology_id: str) -> dict:
    onto = reg.get(graph, ontology_id)
    every = reg.items(graph, ontology_id)
    by_kind: dict = {}
    for item in every:
        by_kind.setdefault(item["kind"], []).append(item)

    def of(kind):
        return by_kind.get(kind, [])

    concepts = of("concept")
    roles = reg.roles(graph, ontology_id)
    audit = reg.audit(graph, ontology_id)
    versions = reg.versions(graph, ontology_id)
    decisions = [a for a in audit if a["decision"] in ("approved", "edited", "rejected")]
    mappings = of("mapping")
    glossary = [m for m in mappings if m["payload"].get("property") not in _UNMAPPED]
    share = len(glossary) / len(mappings) if mappings else 0.0
    shared = [c for c in concepts
              if len({m.split(".", 1)[0] for m in c["payload"].get("members", [])}) > 1]
    tables = {p["key"] for p in of("profile")}
    contracts = {c["key"] for c in of("contract")}
    fresh_sources = {f["key"] for f in of("freshness")}
    sources = [s["source_id"] for s in onto["sources"]]
    last_check = next((d for d in of("drift") if d["key"] == "_last_check"), None)
    latest_publish = versions[-1]["published_at"] if versions else None
    drift_after_publish = bool(last_check and latest_publish
                               and last_check["payload"]["at"] >= latest_publish)
    gaps = [d for d in of("drift") if d["payload"].get("type") == "usage_gap"]
    evidenced = [i for i in every if i["evidence"] and i["kind"] not in
                 ("profile", "freshness", "conflict", "contract")]
    approvers = [r for r in roles if r["role"] == "approver"]

    checks = {
        1: [_check("Sources connected", len(sources) >= 1,
                   f"{len(sources)} source(s) in the intake"),
            _check("Object types (concepts)", bool(concepts), f"{len(concepts)} concept(s)"),
            _check("Link types (relationships)", bool(of("relationship")),
                   f"{len(of('relationship'))} relationship(s)"),
            _check("Action types declared", bool(of("action")),
                   f"{len(of('action'))} action type(s)"),
            _check("Data profiled", bool(tables), f"{len(tables)} table(s) profiled")],
        2: [_check("Every concept has an owner",
                   bool(concepts) and all(c["owner"] for c in concepts),
                   f"{sum(1 for c in concepts if c['owner'])} of {len(concepts)} "
                   f"concepts owned"),
            _check("Core vs extension tiers",
                   bool(concepts) and all(c["payload"].get("tier") for c in concepts),
                   ", ".join(f"{c['key']}: {c['payload'].get('tier', 'unset')}"
                             for c in concepts) or "no concepts"),
            _check("Approver role assigned", bool(approvers),
                   ", ".join(r["user"] for r in approvers) or "no approver granted"),
            _check("Decisions made by people", bool(decisions),
                   f"{len(decisions)} decision(s) in the audit trail")],
        3: [_check("Shared concepts across systems", bool(shared),
                   ", ".join(c["key"] for c in shared) or "every concept is single-system"),
            _check("Columns mapped to the glossary",
                   share >= GLOSSARY_SHARE,
                   f"{share:.0%} of {len(mappings)} columns (needs {GLOSSARY_SHARE:.0%})"),
            _check("Data contract per source table",
                   bool(tables) and tables <= contracts,
                   f"{len(tables & contracts)} of {len(tables)} tables"),
            _check("Standard output API (published version)", bool(versions),
                   f"MCP and REST serve version {versions[-1]['version']}" if versions
                   else "nothing published yet")],
        4: [_check("Versioned releases", bool(versions),
                   f"{len(versions)} version(s)"),
            _check("Audit trail", bool(audit) and any(a["decision"] == "published"
                                                      for a in audit),
                   f"{len(audit)} audited event(s)"),
            _check("Access control", bool(roles), f"{len(roles)} role grant(s)"),
            _check("Freshness SLAs measured",
                   bool(sources) and set(sources) <= fresh_sources,
                   f"{len(fresh_sources & set(sources))} of {len(sources)} sources measured"),
            _check("Validation rules checked",
                   any(r["status"] == "approved" for r in of("rule")),
                   f"{sum(1 for r in of('rule') if r['status'] == 'approved')} approved "
                   f"rule(s)")],
        5: [_check("Drift watch ran after the last publish", drift_after_publish,
                   f"last check {last_check['payload']['at']}" if last_check
                   else "drift has never been checked"),
            _check("Proposals come from the data with evidence", bool(evidenced),
                   f"{len(evidenced)} evidenced proposal(s)"),
            _check("Usage feeds back into the ontology", bool(gaps),
                   f"{len(gaps)} usage gap(s) recorded" if gaps
                   else "no agent usage recorded yet")],
    }
    levels, achieved, blocked = [], 0, False
    for number, name in LEVELS:
        passed = all(c["passed"] for c in checks[number])
        if passed and not blocked:
            achieved = number
        else:
            blocked = True
        levels.append({"level": number, "name": name, "passed": passed,
                       "checks": checks[number]})
    nxt = next((lv for lv in levels if lv["level"] == achieved + 1), None)
    return {"ontology": ontology_id, "level": achieved,
            "level_name": dict(LEVELS).get(achieved, "Not started"), "levels": levels,
            "next_steps": [f"{c['name']}: {c['detail']}" for c in nxt["checks"]
                           if not c["passed"]] if nxt else []}
