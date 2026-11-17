"""Run an ontology agent: one answer, from the four layers, by the agent's kind.

Every kind answers in the same shape, so the screen and MCP never need to know
which one spoke:

    answer      headline + text, in plain words
    answerable  yes / partial / no, with the reason (checked before answering)
    used        which layers were used, in plain words (the receipt)
    facts       what the answer rests on, each with where it comes from
    table       numbers, when there are any (columns + rows)
    proposal    the Data Steward's note, waiting for a person to apply it

An agent never leaves its scope: things and metrics outside it are refused,
named, not quietly used. Numbers come only from the data (a certified metric,
or a checked query labelled as such); the AI only words the answer.
"""

from __future__ import annotations

import re
import time

from ontology import ask
from ontology import simple


class OutOfScope(ValueError):
    pass


def _env(agent, question, headline, text, verdict="yes", reason="", nearest=None,
         used=None, facts=None, table=None, records=None, proposal=None, metric=None, sql=None,
         started=None) -> dict:
    return {"agent_id": agent["id"], "agent": agent["name"], "kind": agent["kind"],
            "question": question,
            "answer": {"headline": headline, "text": text,
                       "confidence": {"yes": "high", "partial": "medium"}.get(verdict, "low")},
            "answerable": {"verdict": verdict, "reason": reason, "nearest": nearest},
            "used": used or [], "facts": facts or [], "table": table, "records": records or [],
            "proposal": proposal, "metric": metric, "sql": sql,
            "latency_ms": round((time.perf_counter() - (started or time.perf_counter())) * 1000)}


def _no(agent, question, reason, started, nearest=None, used=None) -> dict:
    return _env(agent, question, "I cannot answer this.", reason, verdict="no", reason=reason,
                nearest=nearest, used=used, started=started)


def _fact(text, source, cite="") -> dict:
    return {"text": text, "source": source, "citation": cite}


def _in_scope_things(agent, view) -> list[dict]:
    want = set(agent["scope"].get("things") or [])
    return [t for t in view["things"] if not want or t["name"] in want]


# ------------------------------------------------------------------ guide
def _guide(layer, oid, agent, q, started):
    view = simple.view(layer.graph, oid)
    things = _in_scope_things(agent, view)
    picked = ask.pick({**view, "things": things}, q)
    by_name = {t["name"]: t for t in things}
    used = [{"layer": "ontology", "what": f"the ontology, version {view.get('version')}"}]
    chosen = [by_name[p["name"]] for p in picked["things"] if p["name"] in by_name and p["score"] >= 1]
    if not chosen:
        names = ", ".join(t["name"] for t in things)
        return _env(agent, q, f"This data has {len(things)} kinds of thing.",
                    f"The things here are: {names}. Ask about any of them, e.g. "
                    f"\"What is {things[0]['name']}?\"" if things else "There is nothing here yet.",
                    verdict="partial", reason="the question names no thing; here is the overview",
                    used=used, facts=[_fact(f"{t['name']}: {t['description']}", "ontology", t["key"])
                                      for t in things[:8]], started=started)
    facts = []
    hits = {k for p in picked["things"] for k in p.get("fields_hit") or []}
    for t in chosen[:2]:
        facts.append(_fact(f"{t['name']}: {t['description']}", "ontology", t["key"]))
        fields = [f for f in t["fields"] if f["key"] in hits] or t["fields"][:8]
        for f in fields[:8]:
            tag = f" (personal data: {f['personal']})" if f.get("personal") else ""
            check = {"verified": "checked in the data", "conflict": "the data disagrees",
                     "unchecked": "not checked"}.get(f.get("check"), "")
            facts.append(_fact(f"{f['label']}{tag}: {f['meaning']} [{f.get('role_label') or f['role']}; {check}]",
                               "ontology", f["key"]))
    names = {t["name"] for t in chosen}
    links = [x for x in view["links"] if {x["from_thing"], x["to_thing"]} & names]
    for x in links[:6]:
        facts.append(_fact(f"{x['label']} (join {x['from']} = {x['to']})", "ontology, proven in the data", x["key"]))
    main = chosen[0]
    text = f"{main['name']}: {main['description']}"
    if len(chosen) > 1:
        both = [x for x in links if {x["from_thing"], x["to_thing"]} == {chosen[0]["name"], chosen[1]["name"]}]
        text += (f" It links to {chosen[1]['name']}: {both[0]['label']}." if both
                 else f" {chosen[1]['name']} is not linked to it directly.")
    return _env(agent, q, f"{main['name']}, in plain words.", text, used=used, facts=facts, started=started)


# ----------------------------------------------------------- investigator
def _investigator(layer, oid, agent, q, started):
    from context import engine as ctx
    from knowledge_graph import explore as kg
    view = simple.view(layer.graph, oid)
    allowed = {t["name"] for t in _in_scope_things(agent, view)}
    linked = ctx.link(layer, oid, q, view)
    used = [{"layer": "knowledge graph", "what": "records and their proven links, read live"}]
    records = [r for r in linked["records"] if not allowed or r["thing"] in allowed]
    if linked["records"] and not records:
        return _no(agent, q, f"that record is a {linked['records'][0]['thing']}, outside this agent's scope "
                             f"({', '.join(sorted(allowed))})", started)
    if len(records) >= 2 and re.search(r"\b(connect|link|relat|between)", q, re.I):
        a, b = records[0], records[1]
        p = kg.path(layer, oid, (a["set"], a["key"]), (b["set"], b["key"]))
        steps = p.get("steps") or []
        hops = [f"{s['thing']} {s['label']}" + (f" ({s['via']})" if s.get("via") else "") for s in steps]
        text = (" -> ".join(hops) + f": {p['hops']} step(s)." if p.get("found")
                else p.get("text") or "No connection within reach.")
        return _env(agent, q, f"How {a['label']} and {b['label']} are connected.", text,
                    verdict="yes" if p.get("found") else "partial", used=used,
                    facts=[_fact(h, "knowledge graph, proven links") for h in hops], started=started)
    if records:
        r = records[0]
        e = kg.entity(layer, oid, r["set"], r["key"], sample=5)
        facts = [_fact(f"{f['label']}: {f['value']}" + (f" {f['unit']}" if f.get("unit") else ""),
                       "from the data", f"{r['set']}.{f['column']} [{r['key']}]")
                 for f in e["fields"] if f["value"] not in (None, "") and not f.get("personal")]
        links = []
        for c in e["connections"]:
            if c.get("broken"):
                links.append(_fact(f"points at {c['thing']} {c.get('value')}, which does not exist",
                                   "data check", c["link"]))
            elif c["direction"] == "in":
                names = ", ".join(str(i["label"]) for i in c["items"][:5])
                links.append(_fact(f"{c['count']} {c['thing'] or c['text']}: {names}"
                                   + (" ..." if c["count"] > 5 else ""), "from the data", c["link"]))
            elif c["items"]:
                links.append(_fact(f"{c['text']}: {c['items'][0]['label']}", "from the data", c["link"]))
        label = str(e["label"])
        head = label if label.lower().startswith(str(e["thing"]).lower()) else f"{e['thing']} {label}"
        # "Which Customer does Order X belong to?": that link first.
        asked = [t["name"] for t in view["things"] if t["name"] != e["thing"]
                 and re.search(rf"\b{re.escape(t['name'])}\b", q, re.I)]
        links.sort(key=lambda x: 0 if any(a.lower() in x["text"].lower() for a in asked) else 1)
        text = (f"{head}. " + ("; ".join(x["text"] for x in links[:2]) + ". " if asked and links else "")
                + "; ".join(x["text"] for x in facts[:4])
                + (". Linked: " + "; ".join(x["text"] for x in links[:3]) if links and not asked else ""))
        return _env(agent, q, head, text, used=used, facts=facts + links,
                    records=[{"set": r["set"], "key": r["key"], "thing": e["thing"], "label": e["label"]}],
                    started=started)
    if linked.get("values"):
        v = linked["values"][0]
        found = kg.search(layer, oid, v["value"], thing=v["thing"] if v["thing"] in (allowed or {v["thing"]}) else None,
                          limit=10)["results"]
        found = [h for h in found if not allowed or h["thing"] in allowed]
        return _env(agent, q, f"{v['records']:,} {v['thing']} records have {v['label']} = {v['value']}.",
                    "Some of them: " + ", ".join(str(h["label"]) for h in found[:10]) if found else "",
                    used=used, records=[{"set": h["set"], "key": h["key"], "thing": h["thing"], "label": h["label"]}
                                        for h in found[:10]],
                    facts=[_fact(f"{v['records']:,} records have {v['label']} = {v['value']}", "from the data",
                                 f"{v['set']}.{v['column']}")], started=started)
    example = next((t for t in view["things"] if t["name"] in (allowed or {t["name"]})), None)
    return _no(agent, q, "name a record by its id or name, e.g. \"Tell me about "
                         f"{example['name'] if example else 'Order'} <id>\"", started, used=used)


# ----------------------------------------------------------------- metric
def _metrics_in(layer, oid, agent, status=("approved",)):
    from semantic import definitions as defs
    from semantic import model as sem
    want = set(agent["scope"].get("metrics") or [])
    return [d for d in defs.list_definitions(layer.graph, sem.source_of(oid))
            if d["status"] in status and (not want or d["name"] in want)]


def _nearest(defs_, q):
    words = set(ask.words(q))
    scored = sorted(((len(set(ask.words(d["title"])) & words) + 2 * any(
        f" {s.lower()} " in f" {q.lower()} " for s in d.get("synonyms") or []), d) for d in defs_),
        key=lambda x: -x[0])
    return scored[0][1] if scored and scored[0][0] > 0 else None


def _metric_answer(layer, oid, agent, q, started, used_extra=None):
    from context import engine as ctx
    from semantic import model as sem
    certified = _metrics_in(layer, oid, agent)
    used = [{"layer": "semantic", "what": "certified metrics only"}] + (used_extra or [])
    linked = ctx.link(layer, oid, q)
    hit = sem.match(layer, oid, q, linked)
    scope = set(agent["scope"].get("metrics") or [])
    if hit and scope and hit["metric"] not in scope:
        hit = None                                  # certified, but outside this agent's scope
    if not hit:
        anyone = _nearest(_metrics_in(layer, oid, agent, status=("approved", "draft")), q)
        if anyone and anyone["status"] == "draft":
            return _no(agent, q, f"\"{anyone['title']}\" matches, but it is not certified yet. Certify it on "
                                 "the Semantic page and I will answer with it.", started,
                       nearest=anyone["title"], used=used)
        names = ", ".join(d["title"] for d in certified[:6])
        return _no(agent, q, "no certified metric in my scope matches this question"
                             + (f"; I can answer: {names}" if names else "; none is certified yet"),
                   started, nearest=certified[0]["title"] if certified else None, used=used)
    run = sem.value(layer, oid, hit["metric"], by=hit["by"], filters=hit["filters"] or None)
    rec = sem.receipt(layer, oid, hit["metric"])
    cols = run["columns"]
    rows = run["rows"]
    if hit["by"]:
        top = rows[0] if rows else None
        total = sum(r[-1] or 0 for r in rows)
        text = (f"{hit['title']} by {cols[0]}: {len(rows)} groups. The largest is {top[0]} with "
                f"{top[-1]:,.2f}" + (f" ({top[-1] / total:.0%} of {total:,.2f})." if total else ".")) if top else "No rows."
    else:
        val = rows[0][0] if rows else None
        text = f"{hit['title']} is {val:,.2f}." if isinstance(val, (int, float)) else f"{hit['title']}: {val}."
    if hit["filters"]:
        text += " Filtered to " + "; ".join(f"{k} = {v}" for k, v in hit["filters"].items()) + "."
    facts = [_fact(f"Formula: {rec.get('formula') or rec.get('words', '')}", "semantic", f"metric:{hit['metric']}")]
    if hit.get("owner"):
        facts.append(_fact(f"Certified, owner {hit['owner']}", "semantic", f"metric:{hit['metric']}"))
    for j in rec.get("joins") or []:
        facts.append(_fact(f"Join: {j}", "semantic, proven link"))
    return _env(agent, q, text.split(". ")[0] + ".", text, used=used, facts=facts,
                table={"columns": cols, "rows": [list(r) for r in rows[:50]]},
                metric={"name": hit["metric"], "title": hit["title"], "owner": hit.get("owner")},
                sql=run.get("sql"), started=started)


def _metric(layer, oid, agent, q, started):
    return _metric_answer(layer, oid, agent, q, started)


# ---------------------------------------------------------------- insight
def _insight(layer, oid, agent, q, started, client):
    from agent import quick_numbers
    from context import engine as ctx
    from semantic import model as sem
    allowed = set(agent["scope"].get("things") or [])
    view = simple.view(layer.graph, oid)
    linked = ctx.link(layer, oid, q, view)
    # A certified metric answers first (one definition everywhere); then a
    # counting question Strata can write itself; only then the AI's query.
    if not sem.match(layer, oid, q, linked):
        own = quick_numbers.compute(layer, oid, q, linked, view, allowed)
        if own is not None:
            support = ctx.build(layer, oid, q, client=None)["steps"]["facts"]["kept"][:4]
            facts = [_fact(f"Computed: {own['text']}", own["how"], "sql:strata")]
            facts += [_fact(x["text"], x["source"], x["citation"]) for x in support]
            return _env(agent, q, own["text"].split(": ")[0] + ".", own["text"],
                        reason="computed from the data by Strata's own query",
                        used=[{"layer": "ontology", "what": own["how"]},
                              {"layer": "context", "what": "supporting facts"}],
                        facts=facts, table={"columns": own["columns"], "rows": own["rows"]},
                        sql=own["sql"], started=started)
    out = ctx.build(layer, oid, q, client=client, instructions=agent.get("instructions") or "")
    under = out["steps"]["understand"]
    named = [t["name"] for t in under.get("things") or [] if t.get("why") != "joins the others"]
    if allowed and named and not set(named) & allowed:
        return _no(agent, q, f"this question is about {', '.join(named)}; this agent covers "
                             f"{', '.join(sorted(allowed))}", started)
    f = out["steps"]["facts"]
    metric_scope = set(agent["scope"].get("metrics") or [])
    if metric_scope and f.get("metric") and f["metric"]["name"] not in metric_scope:
        return _no(agent, q, f"the number comes from {f['metric']['title']}, outside this agent's metrics",
                   started)
    said = out["steps"]["answer"]
    used = [{"layer": "context", "what": f"{len(f['kept'])} checked facts within the budget"}]
    if f.get("metric"):
        used.insert(0, {"layer": "semantic", "what": f"certified metric {f['metric']['title']}"})
    elif f.get("sql"):
        used.insert(0, {"layer": "ontology", "what": "a checked query (not a certified metric)"})
    if out["steps"]["follow"].get("walks"):
        used.append({"layer": "knowledge graph", "what": "linked records, followed through proven links"})
    facts = [_fact(x["text"], x["source"], x["citation"]) for x in f["kept"]]
    if said["status"] == "answered":
        text, verdict = re.sub(r"\[\d+\]", "", said["text"]).strip(), "yes"
    elif said["status"] == "not_enough":
        return _no(agent, q, said["text"], started, used=used)
    elif said["status"] == "unverified":
        return _no(agent, q, said.get("warning") or "the answer stated numbers that are not in the facts",
                   started, used=used)
    else:
        # No AI: the facts themselves are the answer, plainly listed.
        if not facts:
            return _no(agent, q, "there are no facts in scope for this question", started, used=used)
        # Numbers first (a certified metric's rows), then what the fields mean.
        numbers = [x["text"] for x in f["kept"] if x.get("kind") == "number"]
        text = " ".join(numbers[:3]) if numbers else " ".join(x["text"] for x in facts[:3])
        verdict = "yes" if numbers or f.get("table") else "partial"
    return _env(agent, q, text.split(". ")[0].rstrip(".") + ".", text, verdict=verdict,
                reason="answered from checked facts" if verdict == "yes" else "facts only (no AI to word an answer)",
                used=used, facts=facts, table=f.get("table"), metric=f.get("metric"), sql=f.get("sql"),
                started=started)


# ------------------------------------------------------------------ trust
def _trust(layer, oid, agent, q, started):
    from knowledge_graph import explore as kg
    from semantic import model as sem
    view = simple.view(layer.graph, oid)
    used = [{"layer": "semantic", "what": "certification, drift and verified questions"},
            {"layer": "ontology", "what": "field checks against the data"}]
    checks = []
    if re.search(r"disagree|conflict|wrong field", q, re.I):
        bad = [(t["name"], f) for t in view["things"] for f in t["fields"] if f.get("check") == "conflict"]
        text = (f"The data disagrees with {len(bad)} field(s): "
                + "; ".join(f"{t}.{f['label']} ({f['proof']})" for t, f in bad[:8]) + "."
                if bad else "The data confirms every field it could check.")
        return _env(agent, q, f"{len(bad)} field(s) the data disagrees with.", text, used=used,
                    facts=[_fact(f"{t}.{f['label']}: {f['proof']}", "data check", f["key"]) for t, f in bad],
                    verdict="yes", started=started)
    complete = re.search(r"complete|missing|empty|fresh|gaps?\b|broken", q, re.I)
    target = None if complete else _nearest(_metrics_in(layer, oid, agent, status=("approved", "draft")), q)
    if target is None:
        picked = ask.pick(view, q)
        thing = next((t for t in view["things"] if picked["things"] and t["name"] == picked["things"][0]["name"]), None)
        if thing is None:
            return _no(agent, q, "name a metric or a thing to check, e.g. \"Can I trust "
                                 f"{view['things'][0]['name']}?\"" if view["things"] else "nothing to check",
                       started, used=used)
        conflicts = [f for f in thing["fields"] if f.get("check") == "conflict"]
        health = [h for h in kg.overview(layer, oid)["health"] if thing["name"] in h["text"]]
        from ontology import registry as reg
        empty = {}
        for item in reg.items(layer.graph, oid, kind="profile"):
            if item["key"] in thing["tables"]:
                for c in item["payload"].get("columns") or []:
                    empty[c["name"]] = float(c.get("null_ratio") or 0)
        gaps = [(f, empty[f["column"]]) for f in thing["fields"] if empty.get(f["column"], 0) >= 0.05]
        checks += [{"check": f"{f['label']} filled in", "passed": False, "why": f"{r:.0%} empty"} for f, r in gaps]
        if empty and not gaps:
            checks.append({"check": "fields filled in", "passed": True, "why": "every field is at least 95% filled"})
        checks += [{"check": f"{f['label']} matches its meaning", "passed": False, "why": f["proof"]} for f in conflicts]
        checks += [{"check": "links", "passed": h["severity"] != "warning", "why": h["text"]} for h in health]
        if not conflicts:
            checks.append({"check": "every field matches its meaning", "passed": True, "why": "checked in the data"})
        ok = all(c["passed"] for c in checks)
        return _env(agent, q, f"{thing['name']}: " + ("looks sound." if ok else "check before trusting."),
                    "; ".join(f"{'OK' if c['passed'] else 'NO'} - {c['check']}: {c['why']}" for c in checks),
                    verdict="yes", used=used + [{"layer": "knowledge graph", "what": "link health"}],
                    facts=[_fact(f"{c['check']}: {c['why']}", "data check") for c in checks], started=started)
    name = target["name"]
    certified = target["status"] == "approved"
    checks.append({"check": "certified by a person", "passed": certified,
                   "why": f"owner {target.get('owner')}" if certified and target.get("owner") else
                   ("certified" if certified else "still a proposal")})
    drift = sem.drift(layer, oid, name) if certified else []
    checks.append({"check": "data unchanged since certification", "passed": not drift,
                   "why": "; ".join(drift) if drift else ("no drift" if certified else "not certified, so not watched")})
    verified = sem.check_verified(layer, oid, name)
    if verified:
        failed = [v for v in verified if not v["passed"]]
        checks.append({"check": "verified questions still give the same answer", "passed": not failed,
                       "why": f"{len(verified) - len(failed)} of {len(verified)} pass"})
    meta = sem._meta(layer.graph, oid, name)
    field_key = meta.get("field")
    field = next((f for t in view["things"] for f in t["fields"] if f["key"] == field_key), None)
    if field:
        checks.append({"check": f"{field['label']} is what it claims to be", "passed": field.get("check") == "verified",
                       "why": field.get("proof") or field.get("check")})
    ok = all(c["passed"] for c in checks)
    verdict_text = "Yes, it can be trusted." if ok else ("Not yet." if not certified else "Check it first.")
    return _env(agent, q, f"{target['title']}: {verdict_text}",
                "; ".join(f"{'OK' if c['passed'] else 'NO'} - {c['check']}: {c['why']}" for c in checks),
                verdict="yes", used=used, facts=[_fact(f"{c['check']}: {c['why']}", "check") for c in checks],
                metric={"name": name, "title": target["title"], "owner": target.get("owner")}, started=started)


# ---------------------------------------------------------------- steward
def _steward(layer, oid, agent, q, started, client):
    from ontology import meaning as mn
    if "..." in q or "…" in q:
        return _no(agent, q, "fill in the \"...\" first, then I will propose it", started)
    catalog_ = simple._catalog(layer.graph, oid)
    edits, method = [], "rules"
    if client is not None and not getattr(client, "mock", True) and mn.ai_enabled():
        try:
            edits, _ = simple.ai_note(client, q, catalog_)
            method = "ai"
        except Exception:                          # noqa: BLE001 - rules below
            edits = []
    if not edits:
        edits = simple.parse_note(q, catalog_)
    things = {t["key"]: t["name"] for t in catalog_["things"]}
    fields = {f["key"]: f["label"] for f in catalog_["fields"]}
    shown = []
    for e in edits:
        what = things.get(e.get("key")) or fields.get(e.get("key"))
        if not what:
            continue
        change = ", ".join(f"{k} = {e[k]}" for k in ("name", "label", "meaning", "role", "unit", "description")
                           if e.get(k))
        shown.append({"target": e.get("target"), "key": e["key"], "what": what, "change": change})
    text = (f"I propose {len(shown)} change(s): " + "; ".join(f"{s['what']}: {s['change']}" for s in shown)
            if shown else "I propose saving this as a note on the ontology; it guides the next rebuild "
                          "and every agent reads it.")
    return _env(agent, q, "A proposal, waiting for you to apply it.", text + " Nothing has changed yet.",
                verdict="yes", used=[{"layer": "ontology", "what": f"notes ({method}); applied only by a person"}],
                proposal={"text": q, "changes": shown, "apply": f"/api/onto/{oid}/context"}, started=started)


# ---------------------------------------------------------------- privacy
def _privacy(layer, oid, agent, q, started):
    view = simple.view(layer.graph, oid)
    picked = {p["name"] for p in ask.pick(view, q)["things"] if p["score"] >= 3}
    found = [(t["name"], f) for t in view["things"] for f in t["fields"] if f.get("personal")
             and (not picked or t["name"] in picked)]
    text = ("Personal data is in: " + "; ".join(f"{t}.{f['label']} ({f['personal']})" for t, f in found) +
            ". Its values are masked in every answer and export." if found else
            "No personal data was found" + (" in " + ", ".join(sorted(picked)) if picked else "") + ".")
    return _env(agent, q, f"{len(found)} personal-data field(s).", text, verdict="yes",
                used=[{"layer": "ontology", "what": "fields flagged as personal data"}],
                facts=[_fact(f"{t}.{f['label']}: {f['personal']}", "ontology", f["key"]) for t, f in found],
                started=started)


def run(layer, agent: dict, question: str, client=None) -> dict:
    """Answer one question as this agent."""
    started = time.perf_counter()
    q = str(question or "").strip()
    if not q:
        raise ValueError("type a question first")
    if len(q) > 1000:
        raise ValueError("keep the question under 1,000 characters")
    if agent.get("status") == "retired":
        raise ValueError("this agent is retired: the data no longer supports it")
    oid, kind = agent["ontology"], agent["kind"]
    if kind == "guide":
        return _guide(layer, oid, agent, q, started)
    if kind == "investigator":
        return _investigator(layer, oid, agent, q, started)
    if kind == "metric":
        return _metric(layer, oid, agent, q, started)
    if kind == "insight":
        return _insight(layer, oid, agent, q, started, client)
    if kind == "trust":
        return _trust(layer, oid, agent, q, started)
    if kind == "steward":
        return _steward(layer, oid, agent, q, started, client)
    if kind == "privacy":
        return _privacy(layer, oid, agent, q, started)
    raise ValueError(f"unknown kind {kind!r}")
