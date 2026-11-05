"""Conflicts, freshness and survivorship: "three sources of truth".

Three questions, each answered from the data:

* **How far behind is each source?** A table's freshness is its latest
  business timestamp (a sync time, a snapshot date, a last-updated, else its
  document dates; never a due date, which points into the future). Each
  source is compared with the latest source in the ontology and with its own
  refresh SLA from the intake.
* **Where do systems disagree about the same entity?** Through the identity
  crosswalk every shared property is compared after normalising (case,
  punctuation, "G.m.b.H." vs "GmbH" are not conflicts). A disagreement is a
  *hub override* when the hub differs from source systems that agree among
  themselves - a steward's correction the sources never received - and a
  *source disagreement* otherwise.
* **Which source should win each property?** Proposed survivorship rules with
  reasons and caveats: the hub wins what stewards correct (but its lag is
  stated), the system of record wins what only it holds.
"""

from __future__ import annotations

import re
from datetime import date

from knowledge_graph.build import qi
from ontology import registry as reg
from ontology.concepts import _tables

_FRESHNESS_ORDER = ("sync_timestamp", "snapshot_date", "last_updated")
_NOT_COMPARED = {"identifier", "attribute", "number", "date", "amount_unclassified",
                 "record_count", "period", "snapshot_date", "sync_timestamp",
                 "last_updated", "due_date"}
SURVIVORSHIP_FINDINGS = ("stale_source|", "corrections_not_in_sources|")
EXAMPLES_KEPT = 10


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _date_sql(column: str) -> str:
    q = qi(column)
    return (f"coalesce(TRY_CAST({q} AS DATE),"
            f" CAST(TRY_CAST(CAST({q} AS VARCHAR) AS TIMESTAMP) AS DATE))")


def _mappings(graph, ontology_id) -> dict:
    out: dict = {}
    for m in reg.items(graph, ontology_id, kind="mapping"):
        if m["status"] != "rejected":
            p = m["payload"]
            out.setdefault(p["table"], {})[p["column"]] = p["property"]
    return out


def _freshness_column(props: dict) -> str | None:
    for wanted in _FRESHNESS_ORDER:
        for col, prop in props.items():
            if prop == wanted:
                return col
    dated = [c for c, p in props.items() if p.endswith("_date") and p != "due_date"]
    return dated[0] if dated else None


def measure_freshness(graph, onto, tables, maps, as_of: str | None = None) -> tuple:
    per_source: dict = {}
    for t in tables.values():
        col = _freshness_column(maps.get(t["key"], {}))
        if not col:
            continue
        latest = graph.sql(f"SELECT CAST(max({_date_sql(col)}) AS VARCHAR)"
                           f" FROM {t['ref']}")[0][0]
        if not latest:
            continue
        cur = per_source.get(t["source"])
        if cur is None or latest > cur["latest"]:
            per_source[t["source"]] = {"latest": latest, "table": t["key"], "column": col}
    if not per_source:
        return None, []
    as_of = as_of or max(v["latest"] for v in per_source.values())
    out = []
    for src in onto["sources"]:
        info = per_source.get(src["source_id"])
        if not info:
            continue
        lag = (date.fromisoformat(as_of[:10]) - date.fromisoformat(info["latest"][:10])).days
        out.append({"source": src["source_id"], "role": src["role"],
                    "latest": info["latest"][:10], "measured_on": f"{info['table']}.{info['column']}",
                    "lag_days": lag, "sla_days": src["cadence_days"],
                    "breach": lag > src["cadence_days"], "owner_team": src["owner_team"]})
    return as_of[:10], out


def _crosswalk(graph, ontology_id, concept) -> dict:
    """{entity_id: {table: [records]}} for one concept."""
    out: dict = {}
    if not graph.one("SELECT count(*) FROM information_schema.tables"
                     " WHERE table_name = 'eo_crosswalk'"):
        return out
    for entity, table, record in graph.sql(
            "SELECT entity_id, table_key, record FROM eo_crosswalk WHERE ontology_id = ?"
            " AND concept = ?", [ontology_id, concept]):
        out.setdefault(entity, {}).setdefault(table, []).append(record)
    return out


def _values(graph, t, key_col, col) -> dict:
    return {str(k): v for k, v in graph.sql(
        f"SELECT {qi(key_col)}, {qi(col)} FROM {t['ref']} WHERE {qi(key_col)} IS NOT NULL")}


def find_conflicts(graph, ontology_id, concept, tables, maps) -> list[dict]:
    members = [m for m in concept["members"] if m in tables]
    hub = concept.get("master")
    shared: dict = {}
    for m in members:
        for col, prop in maps.get(m, {}).items():
            if prop not in _NOT_COMPARED and not prop.endswith("amount"):
                shared.setdefault(prop, {})[m] = col
    xwalk = _crosswalk(graph, ontology_id, concept["name"])
    out = []
    for prop, cols in sorted(shared.items()):
        if len(cols) < 2:
            continue
        values = {m: _values(graph, tables[m], concept["keys"][m], c) for m, c in cols.items()}
        compared = 0
        by_kind: dict = {}
        by_pair: dict = {}
        examples = []
        for entity, recs in xwalk.items():
            seen = {}
            for m, records in recs.items():
                if m not in values:
                    continue
                # A non-surviving golden record is a duplicate, handled elsewhere.
                use = [r for r in records if m != hub or r == entity] or []
                if use and values[m].get(use[0]) not in (None, ""):
                    seen[m] = values[m][use[0]]
            if len(seen) < 2:
                continue
            compared += 1
            norms = {m: _norm(v) for m, v in seen.items()}
            if len(set(norms.values())) == 1:
                continue
            others = {v for m, v in norms.items() if m != hub}
            kind = "hub_override" if hub in norms and len(others) == 1 \
                and norms[hub] not in others else "source_disagreement"
            by_kind[kind] = by_kind.get(kind, 0) + 1
            ms = sorted(norms)
            for i, a in enumerate(ms):
                for b in ms[i + 1:]:
                    if norms[a] != norms[b]:
                        by_pair[f"{a} vs {b}"] = by_pair.get(f"{a} vs {b}", 0) + 1
            examples.append({"entity_id": entity, "kind": kind,
                             "values": {m: str(v) for m, v in seen.items()}})
        out.append({"concept": concept["name"], "property": prop, "columns": cols,
                    "entities_compared": compared,
                    "entities_in_conflict": sum(by_kind.values()), "by_kind": by_kind,
                    "by_pair": by_pair, "examples": examples[:EXAMPLES_KEPT],
                    "examples_all": examples})
    return out


def propose_survivorship(concepts, maps, tables, conflicts, freshness) -> list[dict]:
    fresh = {f["source"]: f for f in freshness}
    conflict_of = {(c["concept"], c["property"]): c for c in conflicts}
    rules = []
    for concept in concepts:
        hub = concept.get("master")
        props: dict = {}
        for m in concept["members"]:
            for col, prop in maps.get(m, {}).items():
                if prop not in _NOT_COMPARED:
                    props.setdefault(prop, []).append(m)
        for prop, members in sorted(props.items()):
            rule = {"concept": concept["name"], "property": prop, "caveat": ""}
            if len(members) == 1:
                src = tables[members[0]]["source"] if members[0] in tables else members[0]
                rule.update(rule="system_of_record", winner=src,
                            reason=f"only {members[0]} holds {prop}")
            elif hub and hub in members:
                c = conflict_of.get((concept["name"], prop))
                n = (c or {}).get("by_kind", {}).get("hub_override", 0)
                src = tables[hub]["source"]
                rule.update(rule="master_wins", winner=src,
                            reason=(f"the hub corrects {n} values that every source "
                                    f"system still has wrong" if n else
                                    "the hub holds the mastered (corrected) value"))
                f = fresh.get(src)
                if f and f["breach"]:
                    rule["caveat"] = (f"the hub is {f['lag_days']} days behind its "
                                      f"{f['sla_days']}-day SLA: changes made in source "
                                      f"systems after {f['latest']} are not in it yet")
            else:
                rule.update(rule="most_common", winner=None,
                            reason="no hub; the value most systems agree on wins")
            rules.append(rule)
    return rules


def assess(layer, ontology_id: str, as_of: str | None = None) -> dict:
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    tables = {t["key"]: t for t in _tables(layer, onto)}
    maps = _mappings(graph, ontology_id)
    as_of, freshness = measure_freshness(graph, onto, tables, maps, as_of)
    concepts = [i["payload"] for i in reg.items(graph, ontology_id, kind="concept")
                if i["status"] != "rejected"]
    conflicts = []
    for concept in concepts:
        if len(concept.get("members", [])) > 1:
            conflicts += find_conflicts(graph, ontology_id, concept, tables, maps)
    rules = propose_survivorship(concepts, maps, tables, conflicts, freshness)

    findings = []
    for f in freshness:
        reg.put(graph, ontology_id, "freshness", f["source"], f, fact=True,
                confidence=1.0, evidence=[f"latest {f['measured_on']} = {f['latest']}"])
        if f["breach"]:
            findings.append({
                "type": "stale_source", "column": f["source"], **f,
                "detail": (f"{f['source']} is {f['lag_days']} days behind (latest "
                           f"{f['latest']}, newest source {as_of}); its refresh SLA "
                           f"is {f['sla_days']} days")})
    for c in conflicts:
        key = f"{c['concept']}.{c['property']}"
        reg.put(graph, ontology_id, "conflict", key,
                {k: v for k, v in c.items() if k != "examples_all"}, fact=True,
                confidence=1.0, evidence=[f"{c['entities_in_conflict']} of "
                                          f"{c['entities_compared']} entities disagree"])
        n = c["by_kind"].get("hub_override", 0)
        if n:
            findings.append({
                "type": "corrections_not_in_sources", "column": key,
                "concept": c["concept"], "property": c["property"], "count": n,
                "detail": (f"{n} {c['property']} values were corrected in the MDM hub "
                           f"but every source system still has the old value; reports "
                           f"built on source systems show the uncorrected data")})
    for r in rules:
        reg.put(graph, ontology_id, "survivorship", f"{r['concept']}.{r['property']}", r,
                confidence=0.85, evidence=[r["reason"]] + ([r["caveat"]] if r["caveat"] else []))
    keep = set()
    for f in findings:
        key = f"{f['type']}|{f['column']}"
        keep.add(key)
        reg.put(graph, ontology_id, "finding", key, f, confidence=0.95, evidence=[f["detail"]])
    reg.prune(graph, ontology_id, "finding", keep, prefixes=SURVIVORSHIP_FINDINGS)
    return {"as_of": as_of, "freshness": freshness, "conflicts": conflicts,
            "survivorship": rules, "findings": findings}


def golden_record(layer, ontology_id: str, concept_name: str, entity_id: str) -> dict:
    """One entity's best values, by the (approved or proposed) survivorship rules."""
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    tables = {t["key"]: t for t in _tables(layer, onto)}
    concept = reg.get_item(graph, ontology_id, "concept", concept_name)["payload"]
    maps = _mappings(graph, ontology_id)
    recs = _crosswalk(graph, ontology_id, concept_name).get(entity_id, {})
    hub = concept.get("master")
    out = {}
    for item in reg.items(graph, ontology_id, kind="survivorship"):
        rule = item["payload"]
        if item["status"] == "rejected" or rule["concept"] != concept_name:
            continue
        candidates = []
        for m, records in recs.items():
            col = next((c for c, p in maps.get(m, {}).items() if p == rule["property"]), None)
            if not col or m not in tables:
                continue
            use = [r for r in records if m != hub or r == entity_id]
            if not use:
                continue
            value = _values(graph, tables[m], concept["keys"][m], col).get(use[0])
            if value not in (None, ""):
                candidates.append((m, value))
        if not candidates:
            continue
        pick = None
        if rule["rule"] in ("master_wins", "system_of_record"):
            pick = next(((m, v) for m, v in candidates
                         if tables[m]["source"] == rule["winner"]), None)
        if pick is None:
            counts: dict = {}
            for _m, v in candidates:
                counts[_norm(v)] = counts.get(_norm(v), 0) + 1
            best = max(counts, key=lambda k: counts[k])
            pick = next((m, v) for m, v in candidates if _norm(v) == best)
        out[rule["property"]] = {"value": pick[1], "source": pick[0], "rule": rule["rule"],
                                 "alternatives": {m: str(v) for m, v in candidates}}
    return out
