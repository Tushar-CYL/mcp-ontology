"""Impact analysis: what depends on this, across every layer, before a person
changes it.

    impact(layer, oid, "field",  "shop.orders.net_amount")
    impact(layer, oid, "metric", "total_net_amount")
    impact(layer, oid, "thing",  "Order")
    impact(layer, oid, "rule",   "<rule id>")

The answer is grouped by layer (ontology links, graph connections, metrics
and their verified questions, business rules, report checks and notes,
agents), with one plain sentence and the people to tell: the owners of the
certified metrics and active rules it touches. Read only.
"""

from __future__ import annotations

import re

KINDS = ("field", "metric", "thing", "rule")
LAYER_TITLES = {"ontology": "Ontology", "graph": "Knowledge graph", "semantic": "Metrics",
                "rules": "Business rules", "context": "Answers and reports", "agents": "Agents"}


def _item(text: str, detail: str = "", ref: str = "") -> dict:
    return {"text": text, "detail": detail, "ref": ref}


class _Out:
    def __init__(self):
        self.groups: dict[str, list[dict]] = {k: [] for k in LAYER_TITLES}
        self.seen: set = set()
        self.tell: list[str] = []

    def add(self, layer: str, item: dict) -> None:
        key = (layer, item["text"])
        if key not in self.seen:
            self.seen.add(key)
            self.groups[layer].append(item)

    def owner(self, who: str | None) -> None:
        if who and who not in self.tell:
            self.tell.append(who)


# ------------------------------------------------------------------ metrics
def _alias(base_sql: str, ref: str) -> str | None:
    m = re.search(re.escape(ref) + r"\s+(\w+)\b", base_sql or "")
    return m.group(1) if m else None


def _metric_uses(d: dict, ref: str, column: str) -> bool:
    """Does this metric read `column` of the table `ref` (to count, sum, slice or join)?"""
    alias = _alias(d["base_sql"], ref)
    if alias is None:
        return False
    col = f'"{column}"'
    if f"{alias}.{col}" in (d["base_sql"] or ""):
        return True
    if alias == "f" and (col in (d["value_expr"] or "") or column in (d.get("dimensions") or [])
                         or column == d.get("time_column")):
        return True
    return False


def _metrics(layer, oid: str) -> list[dict]:
    from semantic import definitions as defs
    from semantic import model as sem
    return [d for d in defs.list_definitions(layer.graph, sem.source_of(oid)) if d["status"] != "deprecated"]


def _add_metric(out: _Out, layer, oid: str, d: dict, why: str) -> None:
    from ontology import registry as reg
    status = "certified" if d["status"] == "approved" else "proposed"
    owner = d.get("owner") or None
    out.add("semantic", _item(f"Metric “{d['title']}” ({status}{', owner ' + owner if owner else ''})",
                              why, f"metric:{d['name']}"))
    if d["status"] == "approved":
        out.owner(owner)
    for v in reg.items(layer.graph, oid, kind="verified"):
        if v["payload"].get("metric") == d["name"]:
            out.add("semantic", _item(f"Verified question “{v['payload']['question']}”",
                                      f"re-checked against “{d['title']}”", f"verified:{v['key']}"))


def _add_metric_users(out: _Out, layer, oid: str, names: set[str], titles: set[str]) -> None:
    """Report checks whose last run used these metrics, and agents scoped to them."""
    from context import report_check as rc
    last = rc.last_run(layer.graph, oid)
    checks = {c["id"]: c for c in rc.checks(layer.graph, oid)}
    for r in (last or {}).get("results") or []:
        if any(a.get("metric") in titles for a in r.get("answers") or []):
            c = checks.get(r.get("id"), {})
            src = c.get("source") or r.get("source")
            out.add("context", _item(f"Report check “{r.get('question')}”" + (f" from “{src}”" if src else ""),
                                     "its last answer came from this metric", f"check:{r.get('id')}"))
    for c in checks.values():
        words = set(re.findall(r"[a-z]+", c["question"].lower()))
        for t in titles:
            tw = set(re.findall(r"[a-z]+", t.lower())) - {"total", "number", "of", "record", "records"}
            if tw and tw <= words:
                out.add("context", _item(f"Report check “{c['question']}”"
                                         + (f" from “{c['source']}”" if c.get("source") else ""),
                                         f"asks about {t}", f"check:{c['id']}"))
    _agents(out, layer, oid, metrics=names)


def _agents(out: _Out, layer, oid: str, things: set[str] = frozenset(), metrics: set[str] = frozenset()) -> None:
    from agent import onto_agents as oa
    try:
        agents = oa.builtin_rows(layer.graph, oid) + oa.mine(layer.graph, oid)
    except Exception:                              # noqa: BLE001 - no agents table yet
        return
    whole = []
    for a in agents:
        scope = a.get("scope") or {}
        hit_t = set(scope.get("things") or []) & set(things)
        hit_m = set(scope.get("metrics") or []) & set(metrics)
        if hit_t or hit_m:
            out.add("agents", _item(f"Agent “{a['name']}”" + ("" if a["builtin"] else " (yours)"),
                                    "scoped to " + ", ".join(sorted(hit_t | hit_m)), f"agent:{a['id']}"))
        elif not scope.get("things") and not scope.get("metrics"):
            whole.append(a["name"])
    if whole and (things or metrics):
        out.add("agents", _item(f"{len(whole)} agents that read the whole ontology",
                                ", ".join(whole[:6]), "agents:whole"))


def _rules_on(out: _Out, layer, oid: str, pred) -> None:
    from ontology import business_rules as br
    for r in br.all_rules(layer.graph, oid):
        if r["status"] != "retired" and pred(r):
            out.add("rules", _item(f"Rule “{r['text']}” ({r['status']}"
                                   + (f", owner {r['owner']}" if r.get("owner") else "") + ")",
                                   "", f"rule:{r['id']}"))
            if r["status"] == "active":
                out.owner(r.get("owner"))


# ------------------------------------------------------------------ targets
def _field(layer, oid: str, key: str, out: _Out) -> str:
    from knowledge_graph import explore as kg
    from ontology import business_rules as br
    from ontology import simple
    m = kg.model(layer, oid)
    x = br._fields(m).get(key)
    if x is None:
        raise KeyError(f"no field {key!r} in ontology {oid!r}")
    f, s, thing = x["field"], x["set"], x["thing"]
    col_ref = f"{s['member']}.{f['column']}"
    conns = {c["key"]: c for c in kg.overview(layer, oid)["connections"]}
    for link in simple.view(layer.graph, oid)["links"]:
        if col_ref in (link.get("from"), link.get("to")):
            out.add("ontology", _item(f"Link “{link['label']}”", f"{link['from']} = {link['to']}",
                                      f"link:{link['key']}"))
            c = conns.get(link["key"])
            if c:
                out.add("graph", _item(f"{c['connections']:,} connections {link['from_thing']} → {link['to_thing']}",
                                       f"{c.get('orphans') or 0:,} point at nothing today", f"link:{link['key']}"))
    used = set()
    for d in _metrics(layer, oid):
        if _metric_uses(d, s["ref"], f["column"]):
            _add_metric(out, layer, oid, d, f"reads {thing} . {f['label']}")
            used.add(d["name"])
    _rules_on(out, layer, oid, lambda r: r["spec"].get("field") == key)
    words = {w.lower() for w in (f["column"], f["label"])}
    for n in simple.view(layer.graph, oid)["notes"]:
        if any(w in str(n.get("text") or "").lower() for w in words if len(w) > 2):
            out.add("context", _item(f"Note “{n['text']}”", "the AI reads it with this field", f"note:{n['key']}"))
    titles = {d["title"] for d in _metrics(layer, oid) if d["name"] in used}
    _add_metric_users(out, layer, oid, used, titles)
    _agents(out, layer, oid, things={thing})
    return f"{thing} . {f['label']}"


def _metric(layer, oid: str, name: str, out: _Out) -> str:
    from ontology import business_rules as br
    d = next((d for d in _metrics(layer, oid) if d["name"] == name), None)
    if d is None:
        raise KeyError(f"no metric {name!r} in ontology {oid!r}")
    _add_metric(out, layer, oid, d, "this metric")
    out.groups["semantic"] = [i for i in out.groups["semantic"] if i["ref"] != f"metric:{name}"]
    for c in br.conflicts(layer, oid):
        if c["metric"] == name:
            out.add("rules", _item(f"Rule “{c['rule_text']}”", c["text"], f"rule:{c['rule']}"))
    _add_metric_users(out, layer, oid, {name}, {d["title"]})
    if d["status"] == "approved":
        out.owner(d.get("owner"))
    return f"Metric “{d['title']}”"


def _thing(layer, oid: str, name: str, out: _Out) -> str:
    from knowledge_graph import explore as kg
    from ontology import simple
    m = kg.model(layer, oid)
    sets = [s for s in m["sets"].values() if s["thing"].lower() == str(name).lower()]
    if not sets:
        raise KeyError(f"no thing {name!r} in ontology {oid!r}")
    thing = sets[0]["thing"]
    conns = {c["key"]: c for c in kg.overview(layer, oid)["connections"]}
    for link in simple.view(layer.graph, oid)["links"]:
        if thing in (link["from_thing"], link["to_thing"]):
            out.add("ontology", _item(f"Link “{link['label']}”", "", f"link:{link['key']}"))
            c = conns.get(link["key"])
            if c:
                out.add("graph", _item(f"{c['connections']:,} connections {link['from_thing']} → {link['to_thing']}",
                                       "", f"link:{link['key']}"))
    refs = {s["ref"] for s in sets}
    used = set()
    for d in _metrics(layer, oid):
        if any(_alias(d["base_sql"], r) for r in refs):
            _add_metric(out, layer, oid, d, f"reads {thing}")
            used.add(d["name"])
    _rules_on(out, layer, oid, lambda r: r["spec"].get("thing") == thing)
    titles = {d["title"] for d in _metrics(layer, oid) if d["name"] in used}
    _add_metric_users(out, layer, oid, used, titles)
    _agents(out, layer, oid, things={thing})
    return thing


def _rule(layer, oid: str, rid: str, out: _Out) -> str:
    from ontology import business_rules as br
    r = br.get(layer.graph, oid, rid)
    for c in br.conflicts(layer, oid):
        if c["rule"] == rid:
            d = next((d for d in _metrics(layer, oid) if d["name"] == c["metric"]), None)
            if d:
                _add_metric(out, layer, oid, d, c["text"])
    if r["status"] == "active":
        out.add("context", _item(f"Answers about {r['spec'].get('thing')}",
                                 "the AI is given this rule as a fact", f"rule:{rid}"))
        out.owner(r.get("owner"))
    _agents(out, layer, oid, things={r["spec"].get("thing")} - {None})
    return f"Rule “{r['text']}”"


_TARGETS = {"field": _field, "metric": _metric, "thing": _thing, "rule": _rule}


def impact(layer, oid: str, kind: str, key: str) -> dict:
    from ontology import registry as reg
    if kind not in _TARGETS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    reg.get(layer.graph, oid)
    out = _Out()
    title = _TARGETS[kind](layer, oid, str(key), out)
    groups = [{"layer": k, "title": LAYER_TITLES[k], "items": v} for k, v in out.groups.items() if v]
    total = sum(len(g["items"]) for g in groups)
    if total:
        parts = [f"{len(g['items'])} in {g['title'].lower()}" for g in groups]
        summary = f"Changing {title} affects {total} item{'s' if total != 1 else ''}: {', '.join(parts)}"
        if out.tell:
            summary += f". Tell: {', '.join(out.tell)}"
    else:
        summary = f"Nothing else uses {title}: it is safe to change"
    return {"ontology": oid, "target": {"kind": kind, "key": key, "title": title}, "summary": summary,
            "total": total, "tell": out.tell, "groups": groups}
