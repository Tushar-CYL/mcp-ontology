"""Drift watch: the ontology notices when the data changes under it.

Sources change without telling anyone: a team adds a column, drops one,
changes a type, or stops refreshing. Each published version freezes a data
contract per source table, and ``check_drift`` compares the data as it is
now with the contracts of the LATEST PUBLISHED version:

* a new column, and especially a new money column nobody has mapped (the
  "13th amount column" problem);
* a removed column, with the rules that read it;
* a retyped column;
* a large change in row count;
* a source behind its freshness SLA.

Every difference is filed as a ``drift`` proposal with a suggested change.
Nothing in the published ontology changes until a person approves - the
autonomy is in noticing and proposing, not in rewriting.

``record_usage_gap`` is the second half of maturity level 5: when an agent
asks what an unmapped column means, the gap is remembered as a proposal.
"""

from __future__ import annotations

from datetime import datetime, timezone

from knowledge_graph.build import qi
from ontology import registry as reg
from ontology.concepts import _tables
from ontology.mapping import AMOUNT_PROPS, name_meaning
from ontology.profile import _family
from ontology.survivorship import _mappings, measure_freshness

VOLUME_CHANGE = 0.5          # +/- 50% rows is worth a person's look
DRIFT_TYPES = ("new_column|", "new_amount_column|", "removed_column|",
               "retyped_column|", "missing_table|", "volume_change|",
               "freshness_breach|")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_drift(layer, ontology_id: str) -> dict:
    graph = layer.graph
    try:
        published = reg.version(graph, ontology_id)
    except KeyError:
        raise ValueError("nothing is published yet; publish a version before "
                         "checking drift (drift is measured against its contracts)")
    onto = reg.get(graph, ontology_id)
    contracts = {i["key"]: i["payload"] for i in published["items"]
                 if i["kind"] == "contract"}
    rules = [i["payload"] for i in published["items"] if i["kind"] == "rule"]
    mapped = {i["key"]: i["payload"] for i in published["items"] if i["kind"] == "mapping"}
    tables = {t["key"]: t for t in _tables(layer, onto)}
    concept_of = {m["payload"]["table"]: m["payload"]["concept"]
                  for m in reg.items(graph, ontology_id, kind="member")}
    changes = []

    for key, contract in sorted(contracts.items()):
        t = tables.get(key)
        if t is None:
            changes.append({"type": "missing_table", "table": key, "column": None,
                            "detail": f"{key} is in the published contract but no "
                                      f"longer in its source",
                            "suggestion": "confirm the table was retired, then remove "
                                          "its members and mappings"})
            continue
        was = {c["name"]: c for c in contract["columns"]}
        now = {c.name: c for c in t["table"].columns if not c.name.startswith("__")}
        for name in sorted(now.keys() - was.keys()):
            col = now[name]
            fam = _family(col)
            prop, conf, why = name_meaning(col, fam, concept_of.get(key, t["class"]),
                                           False)
            if fam == "numeric" and prop in AMOUNT_PROPS:
                changes.append({
                    "type": "new_amount_column", "table": key, "column": name,
                    "guess": prop, "confidence": conf,
                    "detail": f"new money column {key}.{name} ({col.type}); {why}",
                    "suggestion": f"map {name} to a property (first guess: {prop}) "
                                  f"and decide whether reports should use it"})
            else:
                changes.append({
                    "type": "new_column", "table": key, "column": name,
                    "detail": f"new column {key}.{name} ({col.type})",
                    "suggestion": f"map {name} (first guess: {prop})"})
        for name in sorted(was.keys() - now.keys()):
            ref = qi(name)
            impact = [r["key"] for r in rules if ref in r.get("sql", "")]
            meaning = mapped.get(f"{key}.{name}", {}).get("property")
            changes.append({
                "type": "removed_column", "table": key, "column": name,
                "property": meaning, "rules_affected": impact,
                "detail": f"{key}.{name}"
                          + (f" ({meaning})" if meaning else "") + " is gone"
                          + (f"; {len(impact)} rule(s) read it" if impact else ""),
                "suggestion": "retire its mapping and rules, or ask the source owner "
                              "why it was dropped"})
        for name in sorted(now.keys() & was.keys()):
            if str(now[name].type) != was[name]["type"]:
                changes.append({
                    "type": "retyped_column", "table": key, "column": name,
                    "was": was[name]["type"], "now": str(now[name].type),
                    "detail": f"{key}.{name} changed type from {was[name]['type']} "
                              f"to {now[name].type}",
                    "suggestion": "check the mapping and any rule that compares it"})
        before, after = contract.get("rows") or 0, t["rows"] or 0
        if before and abs(after - before) / before > VOLUME_CHANGE:
            changes.append({"type": "volume_change", "table": key, "column": None,
                            "was": before, "now": after,
                            "detail": f"{key} went from {before:,} to {after:,} rows",
                            "suggestion": "confirm the load was complete"})

    _as_of, freshness = measure_freshness(graph, onto, tables, _mappings(graph, ontology_id))
    for f in freshness:
        if f["breach"]:
            changes.append({"type": "freshness_breach", "table": None, "column": None,
                            "source": f["source"], "lag_days": f["lag_days"],
                            "sla_days": f["sla_days"],
                            "detail": f"{f['source']} is {f['lag_days']} days behind; "
                                      f"SLA {f['sla_days']} days",
                            "suggestion": f"ask {f['owner_team'] or 'the owner'} to "
                                          f"refresh it"})

    keep = set()
    for c in changes:
        key = f"{c['type']}|{c.get('table') or c.get('source')}|{c.get('column') or ''}"
        keep.add(key)
        reg.put(graph, ontology_id, "drift", key, {**c, "against_version":
                                                   published["version"]},
                confidence=0.9, evidence=[c["detail"]])
    reg.prune(graph, ontology_id, "drift", keep, prefixes=DRIFT_TYPES)
    checked_at = _now()
    reg.put(graph, ontology_id, "drift", "_last_check",
            {"type": "last_check", "at": checked_at, "against_version": published["version"],
             "changes": len(changes)}, fact=True, confidence=1.0,
            evidence=[f"{len(changes)} change(s) against version {published['version']}"])
    return {"version": published["version"], "checked_at": checked_at, "changes": changes}


def record_usage_gap(graph, ontology_id: str, column: str, asked_by: str = "agent") -> dict:
    """An agent asked about a column the published ontology does not map."""
    key = f"usage_gap|{column}"
    current = reg.get_item(graph, ontology_id, "drift", key, missing_ok=True)
    asked = (current or {}).get("payload", {}).get("asked", 0) + 1
    return reg.put(graph, ontology_id, "drift", key, {
        "type": "usage_gap", "column": column, "asked": asked, "asked_by": asked_by,
        "detail": f"{asked_by} asked what {column} means {asked} time(s); it is not mapped",
        "suggestion": f"map {column} so agents can use it"},
        confidence=0.8, evidence=[f"asked {asked} time(s)"])
