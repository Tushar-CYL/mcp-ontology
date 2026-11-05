"""Rules (constraints) and action types.

Rules are not typed in by hand; they are derived from what the earlier steps
proved about the data, then checked live:

* **key**: every concept member's identifier is present and unique;
* **sum**: where value structure showed net + tax = gross (or net + discount
  = list), every row must keep it;
* **allowed_values**: a currency column holds ISO 4217 codes, a country
  column ISO 3166 codes;
* **date_order**: across a relationship, the child's own date is on or after
  the parent's (an invoice is not dated before its order);
* **reconcile**: where two systems hold the same property for the same
  record (billing invoice amount and ERP gross), they must agree.

Every rule carries the SQL that finds its violations, so a person can run it
in their own tool and see the same rows.

Action types are the ontology's verbs (Palantir calls them actions; Modern
Data 101 level 1 asks for them). Each is declared with its parameters and the
team that must approve it. Agents may PROPOSE an action - never execute one.
"""

from __future__ import annotations

from knowledge_graph.build import qi
from ontology import registry as reg
from ontology.concepts import _tables
from ontology.mapping import ISO_CURRENCIES, LEGACY_CURRENCIES

MAX_VIOLATIONS_LISTED = 1000
SAMPLE_STORED = 20
_EVENT_DATE_EXCLUDED = {"due_date", "snapshot_date"}

ACTION_TYPES = {
    "merge_golden_records": {
        "description": "Merge a duplicate golden record into the one that survives.",
        "parameters": {"survivor": "record", "duplicate": "record"},
        "from_finding": "duplicate_golden_record", "approver_role": "mdm_hub"},
    "remap_report_column": {
        "description": "Rebuild a report or mart measure from the correct source column.",
        "parameters": {"column": "column", "from": "column", "to": "column"},
        "from_finding": "wrong_amount_column", "approver_role": "data_mart"},
    "push_master_correction": {
        "description": "Send values corrected in the MDM hub back to the source systems.",
        "parameters": {"concept": "concept", "property": "property", "count": "integer"},
        "from_finding": "corrections_not_in_sources", "approver_role": "mdm_hub"},
    "request_source_refresh": {
        "description": "Ask a source's owner to refresh it within its SLA.",
        "parameters": {"source": "source", "lag_days": "integer", "sla_days": "integer"},
        "from_finding": "stale_source", "approver_role": "self"},
    "correct_records": {
        "description": "Correct records that break a validation rule.",
        "parameters": {"rule": "rule", "records": "list"},
        "from_finding": None, "approver_role": "table_owner"},
}


def _maps(graph, ontology_id) -> dict:
    out: dict = {}
    for m in reg.items(graph, ontology_id, kind="mapping"):
        if m["status"] != "rejected":
            p = m["payload"]
            out.setdefault(p["table"], {})[p["column"]] = p["property"]
    return out


def _col(props: dict, prop: str) -> str | None:
    return next((c for c, p in props.items() if p == prop), None)


def _record(t) -> str:
    return f"CAST({qi(t['id'])} AS VARCHAR)" if t["id"] else "CAST(rowid AS VARCHAR)"


def _event_date(props: dict) -> tuple[str, str] | None:
    for c, p in props.items():
        if p.endswith("_date") and p not in _EVENT_DATE_EXCLUDED:
            return c, p
    return None


def derive_rules(graph, ontology_id, tables, maps) -> list[dict]:
    rules = []
    for key, t in tables.items():
        props = maps.get(key, {})
        rec = _record(t)
        if t["id"]:
            k = qi(t["id"])
            rules.append({
                "key": f"key:{key}", "kind": "key", "table": key, "severity": "error",
                "description": f"{key}.{t['id']} is present and unique",
                "sql": (f"SELECT {rec} AS record FROM {t['ref']} WHERE {k} IS NULL OR {k} IN"
                        f" (SELECT {k} FROM {t['ref']} GROUP BY {k} HAVING count(*) > 1)")})
        for a, b, total in (("net_amount", "tax_amount", "gross_amount"),
                            ("net_amount", "discount_amount", "list_amount")):
            ca, cb, cc = _col(props, a), _col(props, b), _col(props, total)
            if ca and cb and cc:
                rules.append({
                    "key": f"sum:{key}.{cc}", "kind": "sum", "table": key, "target": total,
                    "severity": "error",
                    "description": f"{cc} = {ca} + {cb} ({total} = {a} + {b}) within 0.01",
                    "sql": (f"SELECT {rec} AS record FROM {t['ref']} WHERE"
                            f" abs({qi(ca)} + {qi(cb)} - {qi(cc)}) > 0.011")})
        for c, p in props.items():
            value = f"trim(CAST({qi(c)} AS VARCHAR))"
            present = f"{qi(c)} IS NOT NULL AND {value} <> ''"
            blank = f"SELECT count(*) FROM {t['ref']} WHERE {qi(c)} IS NULL OR {value} = ''"
            if p == "currency":
                codes = ", ".join(f"'{x}'" for x in sorted(ISO_CURRENCIES))
                bad = f"{present} AND upper({value}) NOT IN ({codes})"
                severity, what = "error", "an ISO 4217 currency code"
            elif p == "country":
                bad = f"{present} AND NOT regexp_matches({value}, '^[A-Z]{{2}}$')"
                severity, what = "warning", "a two-letter ISO country code"
            else:
                continue
            rules.append({
                "key": f"allowed:{key}.{c}", "kind": "allowed_values", "table": key,
                "column": c, "property": p, "severity": severity,
                "description": f"{key}.{c} is {what} (blanks are counted as missing)",
                "sql": f"SELECT {rec} AS record FROM {t['ref']} WHERE {bad}",
                "offending_sql": (f"SELECT {value}, count(*) FROM {t['ref']} WHERE {bad}"
                                  f" GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10"),
                "blank_sql": blank})

    for item in reg.items(graph, ontology_id, kind="relationship"):
        if item["status"] == "rejected":
            continue
        p = item["payload"]
        t_key, link = p["from"].rsplit(".", 1)
        u_key, ukey = p["to"].rsplit(".", 1)
        if t_key not in tables or u_key not in tables:
            continue
        t, u = tables[t_key], tables[u_key]
        tp, up = maps.get(t_key, {}), maps.get(u_key, {})
        join = (f"FROM {t['ref']} a JOIN {u['ref']} b ON CAST(a.{qi(link)} AS VARCHAR) ="
                f" CAST(b.{qi(ukey)} AS VARCHAR)")
        rec = f"CAST(a.{qi(t['id'])} AS VARCHAR)" if t["id"] else "CAST(a.rowid AS VARCHAR)"
        td, ud = _event_date(tp), _event_date(up)
        if td and ud and td[1] != ud[1]:
            rules.append({
                "key": f"date:{t_key}.{td[0]}>={u_key}.{ud[0]}", "kind": "date_order",
                "table": t_key, "severity": "error",
                "description": (f"{t_key}.{td[0]} ({td[1]}) is on or after "
                                f"{u_key}.{ud[0]} ({ud[1]}) of the record it points at"),
                "sql": (f"SELECT {rec} AS record {join} WHERE"
                        f" CAST(a.{qi(td[0])} AS DATE) < CAST(b.{qi(ud[0])} AS DATE)")})
        for c, prop in tp.items():
            if not prop.endswith("_amount") or prop == "amount_unclassified":
                continue
            other = _col(up, prop)
            if not other:
                continue
            rules.append({
                "key": f"reconcile:{t_key}.{c}={u_key}.{other}", "kind": "reconcile",
                "table": t_key, "severity": "warning",
                "description": (f"{t_key}.{c} equals {u_key}.{other} ({prop}) for the "
                                f"same record, within 0.05%"),
                "sql": (f"SELECT {rec} AS record {join} WHERE abs(a.{qi(c)} - b.{qi(other)})"
                        f" > greatest(0.011, 0.0005 * abs(b.{qi(other)}))")})
    return rules


def _label(rule: dict, value: str) -> str:
    if rule.get("property") == "currency":
        return "withdrawn ISO code" if value.upper() in LEGACY_CURRENCIES \
            else "not an ISO code"
    return "not allowed"


def _check(graph, rule: dict) -> dict:
    count = int(graph.sql(f"SELECT count(*) FROM ({rule['sql']}) v")[0][0])
    rows = graph.sql(f"SELECT record FROM ({rule['sql']}) v ORDER BY 1"
                     f" LIMIT {MAX_VIOLATIONS_LISTED}") if count else []
    out = {**rule, "violations": count, "violating": [r[0] for r in rows]}
    if rule.get("offending_sql"):
        out["offending"] = [{"value": str(v), "count": int(n), "label": _label(rule, str(v))}
                            for v, n in graph.sql(rule["offending_sql"])] if count else []
    if rule.get("blank_sql"):
        out["blank"] = int(graph.sql(rule["blank_sql"])[0][0])
    return out


def _owner(onto, source: str) -> str:
    return next((s["owner_team"] for s in onto["sources"] if s["source_id"] == source), "")


def declare_actions(graph, ontology_id, onto, tables, checked) -> list[dict]:
    findings = [i["payload"] for i in reg.items(graph, ontology_id, kind="finding")
                if i["status"] != "rejected"]
    by_role = {s["role"]: s["owner_team"] for s in onto["sources"]}
    actions = []
    for name, spec in ACTION_TYPES.items():
        proposed = []
        if spec["from_finding"]:
            for f in findings:
                if f.get("type") != spec["from_finding"]:
                    continue
                if name == "merge_golden_records":
                    proposed.append({"survivor": f["survivor"], "duplicate": f["duplicate"]})
                elif name == "remap_report_column":
                    proposed.append({"column": f["column"], "from": f["built_from"],
                                     "to": f["should_be"]})
                elif name == "push_master_correction":
                    proposed.append({"concept": f["concept"], "property": f["property"],
                                     "count": f["count"]})
                elif name == "request_source_refresh":
                    proposed.append({"source": f["source"], "lag_days": f["lag_days"],
                                     "sla_days": f["sla_days"],
                                     "owner_team": _owner(onto, f["source"])})
        else:
            for r in checked:
                if r["violations"] and r["severity"] == "error":
                    proposed.append({"rule": r["key"], "records": r["violating"][:SAMPLE_STORED],
                                     "count": r["violations"],
                                     "owner_team": _owner(onto, tables[r["table"]]["source"])})
        role = spec["approver_role"]
        approver = by_role.get(role, "") if role in by_role else \
            "owner of the source" if role == "self" else "owner of the table's source"
        actions.append({"name": name, "description": spec["description"],
                        "parameters": spec["parameters"], "approver": approver,
                        "agents_may": "propose", "executes": "only after approval",
                        "proposed": proposed})
    return actions


def propose_rules(layer, ontology_id: str) -> dict:
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    tables = {t["key"]: t for t in _tables(layer, onto)}
    checked = [_check(graph, r) for r in
               derive_rules(graph, ontology_id, tables, _maps(graph, ontology_id))]
    for r in checked:
        payload = {k: v for k, v in r.items() if k != "violating"}
        payload["sample"] = r["violating"][:SAMPLE_STORED]
        reg.put(graph, ontology_id, "rule", r["key"], payload, confidence=0.9,
                evidence=[f"{r['violations']} violation(s) when checked"])
    reg.prune(graph, ontology_id, "rule", {r["key"] for r in checked})
    actions = declare_actions(graph, ontology_id, onto, tables, checked)
    for a in actions:
        reg.put(graph, ontology_id, "action", a["name"], a, confidence=0.9,
                evidence=[f"{len(a['proposed'])} proposed instance(s)"])
    return {"rules": checked, "actions": actions}


def validate_rules(layer, ontology_id: str) -> list[dict]:
    """Re-run every rule that is not rejected, against the data as it is now."""
    out = []
    for item in reg.items(layer.graph, ontology_id, kind="rule"):
        if item["status"] == "rejected":
            continue
        r = _check(layer.graph, item["payload"])
        out.append({"key": item["key"], "status": item["status"],
                    "description": r["description"], "violations": r["violations"],
                    "sample": r["violating"][:SAMPLE_STORED]})
    return out
