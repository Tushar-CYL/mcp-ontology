"""Why a layer can be trusted, from two sides at once.

* proof  - how the layer was built and what the data itself checked. Each
  step is ok (the data settled it), warn (the data found a problem) or todo
  (nothing has checked it yet).
* people - the business knowledge the company's own people added: rules in
  plain words, definitions they set, approvals and rejections, owners of
  numbers, the reports they trust. Who did it and when, and what is still
  missing from them (each with where to add it).

Read from what the layers already hold: nothing is recomputed that the
screens do not already compute, nothing is invented, and the AI is never
called. A layer nobody has taught yet says so, instead of looking finished.
"""

from __future__ import annotations

LAYERS = ("ontology", "graph", "semantic", "context")
RECENT = 8


def _step(title: str, text: str, status: str) -> dict:
    return {"title": title, "text": text, "status": status}


def _n(x: int, word: str, plural: str | None = None) -> str:
    return f"{x:,} {word if x == 1 else plural or word + 's'}"


def _recent(items: list[dict]) -> list[dict]:
    """Newest first; the same thing said twice is shown once (its latest)."""
    seen, out = set(), []
    for i in sorted((i for i in items if i.get("at")), key=lambda i: i["at"], reverse=True):
        if i["text"] not in seen:
            seen.add(i["text"])
            out.append(i)
    return out[:RECENT]


def _people(counts: list[tuple[str, int]], recent: list[dict], missing: list[dict]) -> dict:
    total = sum(v for _, v in counts)
    headline = (f"{_n(total, 'piece')} of business knowledge from your people" if total
                else "Nothing from your people yet: everything here came from the data and the AI")
    return {"headline": headline, "counts": [{"label": k, "value": v} for k, v in counts],
            "recent": _recent(recent), "missing": missing}


# ---------------------------------------------------------------- ontology
def _ontology(layer, oid: str) -> dict:
    from ontology import registry as reg
    from ontology import review as rv
    from ontology import simple
    g = layer.graph
    v = simple.view(g, oid)
    s = v["summary"]
    checks = s["checks"]
    review = s["review"]
    tables = sum(len(t["tables"]) for t in v["things"])
    records = sum(t["records"] for t in v["things"])
    verified_links = sum(lk["check"] == "verified" for lk in v["links"])
    stats = rv.stats(g, oid)
    conflict = checks.get("conflict", 0)
    unchecked = checks.get("unchecked", 0)
    steps = [
        _step("Read the data", f"{_n(tables, 'table')}, {_n(s['fields'], 'column')}, "
              f"{records:,} records, read in place (nothing copied)", "ok" if tables else "todo"),
        _step("The AI proposed a model", f"{_n(s['things'], 'thing')}, {_n(s['fields'], 'field meaning')}, "
              f"{_n(s['links'], 'link')}", "ok" if s["things"] else "todo"),
        _step("The data checked every claim",
              f"{_n(checks.get('verified', 0), 'claim')} confirmed by the data, "
              f"{conflict:,} the data disagrees with, {unchecked:,} the data cannot settle",
              "warn" if conflict else "ok"),
        _step("Links tested on real values",
              f"{verified_links:,} of {_n(len(v['links']), 'link')}: the values match in the data",
              "ok" if v["links"] and verified_links == len(v["links"]) else "warn" if v["links"] else "todo"),
        _step("Spot checks of the checks",
              f"{stats['spot_checked']:,} spot-checked by a person; the checks were wrong "
              f"{stats['checks_wrong_pct']}% of the time" if stats["spot_checked"]
              else f"{_n(review.get('spot_checks', 0), 'confirmed item')} waiting for a person to spot-check",
              "ok" if stats["spot_checked"] else "todo"),
    ]
    from ontology import business_rules as br
    biz = [r for r in br.all_rules(g, oid) if r["status"] != "retired"]
    live = [r for r in biz if r["status"] == "active"]
    broken = [r for r in live if (r["result"] or {}).get("failed")]
    steps.append(_step("Business rules checked on the data",
                       f"{_n(len(live), 'active rule')}; {len(broken):,} broken by some records" if live
                       else "No business rule is active yet", "warn" if broken else "ok" if live else "todo"))
    proof = {"headline": f"{s['confirmed_pct']}% of what the AI said was confirmed by the data itself",
             "steps": steps}

    meanings = {i["key"]: i["payload"] for i in reg.items(g, oid, kind="meaning")}
    recent = []
    set_by_people = 0
    for key, m in meanings.items():
        if key.startswith("column:") and m.get("by") == "you":
            set_by_people += 1
            recent.append({"text": f"Set {m.get('column')} as “{m.get('label')}”"
                           + (f": {m['meaning']}" if m.get("meaning") else ""),
                           "by": m.get("editor") or "you", "at": m.get("edited")})
    # Name each decided item as it reads on screen ("Device . Device model"),
    # not by its raw key ("iot.devices.model").
    titled = {f["key"]: f"{t['name']} . {f['label']}" for t in v["things"] for f in t["fields"]}
    titled.update({lk["key"]: lk.get("label") or f"{lk['from_thing']} . {lk['to_thing']}"
                   for lk in v["links"]})
    for key, d in rv.decisions(meanings).items():
        raw = key.split(":", 1)[-1]
        recent.append({"text": f"{d['decision'].capitalize()} {titled.get(raw, raw)}",
                       "by": d.get("by"), "at": d.get("at")})
    notes = v["notes"]
    for n in notes:
        recent.append({"text": f"Wrote a rule: “{n.get('text')}”", "by": n.get("by"), "at": n.get("at")})
    from_model = sum(f.get("by") == "metadata" for t in v["things"] for f in t["fields"])
    for r in biz:
        recent.append({"text": f"{'Activated' if r['status'] == 'active' else 'Wrote'} the rule “{r['text']}”"
                       + (f", owner {r['owner']}" if r.get("owner") else ""),
                       "by": r.get("decided_by") or r.get("by"), "at": r.get("updated_at")})
    counts = [("Fields set by people", set_by_people), ("Business rules in plain words", len(notes)),
              ("Checked business rules active", len(live)),
              ("Claims approved", review.get("approved", 0)), ("Claims rejected", review.get("rejected", 0))]
    if from_model:
        counts.append(("Meanings from your own model file", from_model))
    missing = []
    if review.get("needs_you"):
        missing.append({"text": f"{_n(review['needs_you'], 'claim')} only a person can confirm: "
                                "the data cannot prove or disprove them", "where": "review"})
    if not live:
        missing.append({"text": "No business rule is checked on the data yet: which values are allowed, "
                                "which records must exist, which do not count", "where": "rules"})
    if not notes:
        missing.append({"text": "No business rules written yet: which records count, what a word "
                                "means here, what to leave out", "where": "notes"})
    return {"proof": proof, "people": _people(counts, recent, missing)}


# ---------------------------------------------------------------- graph
def _graph(layer, oid: str) -> dict:
    from knowledge_graph import explore as kg
    from ontology import registry as reg
    from ontology import review as rv
    from ontology import simple
    g = layer.graph
    o = kg.overview(layer, oid)
    v = simple.view(g, oid)
    s = o["summary"]
    broken = s["broken_links"]
    steps = [
        _step("Built from the checked ontology",
              f"{_n(s['things'], 'kind')} of things and {_n(s['link_types'], 'kind')} of link, "
              "each tested on the data first", "ok" if s["things"] else "todo"),
        _step("Every record is a point",
              f"{s['entities']:,} records, {s['connections']:,} connections, straight from the live tables",
              "ok" if s["entities"] else "todo"),
        _step("Every line joins two real records",
              f"{_n(broken, 'line')} point at a record that does not exist" if broken
              else "No line points at a missing record", "warn" if broken else "ok"),
        _step("How connected it is", f"{s['connected_pct']}% of records are linked to another record",
              "ok" if s["connected_pct"] >= 50 else "warn"),
    ]
    proof = {"headline": f"{s['entities']:,} real records and {s['connections']:,} real connections; "
                         + (f"{broken:,} broken" if broken else "none broken"),
             "steps": steps}
    meanings = {i["key"]: i["payload"] for i in reg.items(g, oid, kind="meaning")}
    decided = {k: d for k, d in rv.decisions(meanings).items() if k.startswith("link:")}
    rejected = v.get("rejected_links") or []
    label = {rv.link_target(lk): lk["label"] for lk in v["links"] + rejected}
    recent = [{"text": f"{'Removed' if d['decision'] == 'rejected' else 'Approved'} the link "
                       f"“{label.get(k, k.split(':', 1)[-1])}”", "by": d.get("by"), "at": d.get("at")}
              for k, d in decided.items()]
    approved = sum(d["decision"] == "approved" for d in decided.values())
    counts = [("Links approved by people", approved), ("Links removed by people", len(rejected))]
    open_links = sum(lk["review"] == "needs_you" for lk in v["links"])
    missing = []
    if open_links:
        missing.append({"text": f"{_n(open_links, 'link')} the data could not prove: a person should "
                                "say if it is a real business relationship", "where": "review"})
    if broken:
        missing.append({"text": f"{_n(broken, 'record')} point at nothing: ask the data owner whether "
                                "they are old records or a load problem", "where": "graph"})
    return {"proof": proof, "people": _people(counts, recent, missing)}


# ---------------------------------------------------------------- semantic
def _semantic(layer, oid: str) -> dict:
    from semantic import definitions as defs
    from semantic import model as sem
    g = layer.graph
    ds = [d for d in defs.list_definitions(g, sem.source_of(oid)) if d["status"] != "deprecated"]
    certified = [d for d in ds if d["status"] == "approved"]
    drifting = []
    for d in certified:
        try:
            if sem.drift(layer, oid, d["name"]):
                drifting.append(d["title"])
        except Exception:                          # noqa: BLE001 - a check, not the metric
            continue
    verified = sem.check_verified(layer, oid)
    passed = sum(c["passed"] for c in verified)
    steps = [
        _step("Metrics proposed from the data", f"{_n(len(ds), 'metric')}, each a query on real columns",
              "ok" if ds else "todo"),
        _step("Every certified number has a receipt",
              f"{_n(len(certified), 'certified metric')}: formula, SQL, owner and date on each"
              if certified else "No metric certified yet", "ok" if certified else "todo"),
        _step("Verified questions re-run",
              f"{passed} of {_n(len(verified), 'verified question')} still give the same number"
              if verified else "No verified question yet: nothing re-checks the numbers over time",
              "todo" if not verified else "ok" if passed == len(verified) else "warn"),
        _step("Watching for data changes",
              f"The data changed under {', '.join(drifting[:3])}" if drifting
              else "No certified number has moved under its definition",
              "warn" if drifting else "ok" if certified else "todo"),
    ]
    proof = {"headline": (f"{len(certified)} of {_n(len(ds), 'metric')} certified, each with a receipt"
                          if ds else "No metrics yet"), "steps": steps}
    recent = []
    synonyms = 0
    for d in ds:
        synonyms += len(d.get("synonyms") or [])
        if d["status"] == "approved":
            meta = sem._meta(g, oid, d["name"])
            recent.append({"text": f"Certified {d['title']}"
                           + (f", owner {d['owner']}" if d.get("owner") else ""),
                           "by": meta.get("certified_by"), "at": meta.get("certified_at")})
    from ontology import registry as reg
    for item in reg.items(g, oid, kind="verified"):
        p = item["payload"]
        recent.append({"text": f"Verified “{p['question']}”", "by": p.get("by_person"), "at": p.get("at")})
    counts = [("Metrics certified by people", len(certified)),
              ("Owners named", sum(bool(d.get("owner")) for d in certified)),
              ("Business words taught (synonyms)", synonyms),
              ("Verified questions", len(verified))]
    missing = []
    if not certified:
        missing.append({"text": "No number is certified: ask the business owner which metrics they "
                                "stand behind", "where": "semantic"})
    no_owner = [d["title"] for d in certified if not d.get("owner")]
    if no_owner:
        missing.append({"text": f"{_n(len(no_owner), 'certified metric')} without an owner: "
                                f"{', '.join(no_owner[:3])}", "where": "semantic"})
    proposed = [d["title"] for d in ds if d["status"] != "approved"]
    if certified and proposed:
        missing.append({"text": f"{_n(len(proposed), 'proposed metric')} nobody has certified yet: "
                                f"{', '.join(proposed[:3])}", "where": "semantic"})
    if certified and not verified:
        missing.append({"text": "No verified question: ask the owner for one question and its right "
                                "answer per certified metric, so a change is caught", "where": "semantic"})
    for dec in sem.decisions(layer, oid):
        missing.append({"text": dec["question"], "where": "semantic"})
    return {"proof": proof, "people": _people(counts, recent, missing)}


# ---------------------------------------------------------------- context
def _context(layer, oid: str) -> dict:
    from context import gaps
    from context import report_check as rc
    from ontology import simple
    g = layer.graph
    checks = rc.checks(g, oid)
    last = rc.last_run(g, oid)
    open_gaps = gaps.groups(g, oid)
    s = (last or {}).get("summary") or {}
    if last:
        silent = s.get("silent_wrong", 0)
        report = _step("Tested against your reports",
                       f"{s.get('passed', 0)} of {_n(s.get('checks', 0), 'check')} match the report"
                       + (f"; {_n(silent, 'wrong number')} shown as an answer" if silent else ""),
                       "warn" if silent or s.get("passed", 0) < s.get("checks", 0) else "ok")
    else:
        report = _step("Tested against your reports", "Not yet: no report check has run", "todo")
    asked = open_gaps.get("total", 0)
    steps = [
        _step("Answers only from checked facts",
              "The AI gets a pack of facts for each question; a number not in the facts is rejected", "ok"),
        report,
        _step("Questions it left unanswered",
              f"{_n(asked, 'question')} logged instead of guessed" if asked
              else "None logged yet", "warn" if asked else "ok"),
    ]
    acc = s.get("accuracy_pct")
    proof = {"headline": (f"{acc}% of numbers matched your own reports" if acc is not None
                          else "Not yet tested against your own reports"), "steps": steps}
    sources = sorted({c["source"] for c in checks if c.get("source")})
    recent = [{"text": f"Added a check from “{c['source']}”: {c['question']}" if c.get("source")
               else f"Added a check: {c['question']}", "by": None, "at": c.get("created_at")}
              for c in checks]
    notes = simple.view(g, oid)["notes"]
    counts = [("Report checks", len(checks)), ("Reports named", len(sources)),
              ("Business rules the AI reads", len(notes))]
    missing = []
    if not checks:
        missing.append({"text": "No numbers from a report your people trust: add a few, so every "
                                "answer is compared with them", "where": "report_check"})
    if asked:
        missing.append({"text": f"{_n(asked, 'question')} people asked that Strata could not answer: "
                                "each needs a rule, a definition or a metric", "where": "gaps"})
    return {"proof": proof, "people": _people(counts, recent, missing)}


_BUILD = {"ontology": _ontology, "graph": _graph, "semantic": _semantic, "context": _context}


def layer_trust(layer, ontology_id: str, which: str) -> dict:
    if which not in _BUILD:
        raise ValueError(f"layer must be one of {', '.join(LAYERS)}")
    from ontology import registry as reg
    reg.get(layer.graph, ontology_id)
    return {"ontology": ontology_id, "layer": which, **_BUILD[which](layer, ontology_id)}
