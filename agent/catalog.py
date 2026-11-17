"""Built-in agents, worked out from the data: ready to use, nothing to set up.

Six are always there, one per job a person brings to their data:

    Data Guide          what the data is and how it links      (ontology)
    <Thing> Investigator everything about one record            (knowledge graph)
    Metric Analyst      the certified number                   (semantic)
    Insight Analyst     any question, from checked facts       (context, all layers)
    Trust Checker       can I trust this number?               (health, drift, receipts)
    Data Steward        proposes notes for a person to apply   (ontology)

Up to four more are added only when the data supports them: a money analyst
(money fields), a status watcher (a status with cancelled / unavailable
values), a regional analyst (a place field), a trend analyst (a date and a
number) and a privacy checker (personal data). At most ten in all.

Every name and example question is made from THIS data - real things,
fields and values - never generic text. Built-ins are stored read-only;
anyone who wants a different agent copies one (agent/onto_agents.py).
"""

from __future__ import annotations

from ontology import simple
from ontology import suggest as sg

MAX_AGENTS = 10

# What each kind of agent may call over MCP (least privilege), and which
# layers it reads. The runner (agent/onto_runner.py) answers by kind.
KINDS = {
    "guide": {"title": "Explains the data", "layers": ["ontology"],
              "tools": ["get_ontology", "list_concepts", "get_concept", "map_column", "ontology_version"],
              "guardrails": ["Explains meaning and links only; never gives numbers or records",
                             "Personal-data fields are named as such, never shown"]},
    "investigator": {"title": "Looks up one record", "layers": ["graph", "ontology"],
                     "tools": ["find_entity", "get_entity", "how_connected", "get_ontology"],
                     "guardrails": ["Real records only, found by id or name; never guesses",
                                    "Personal data is masked", "At most two steps from the record"]},
    "metric": {"title": "Gives the certified number", "layers": ["semantic"],
               "tools": ["list_business_metrics", "get_business_metric", "get_ontology"],
               "guardrails": ["Certified metrics only; a proposal is never served as the answer",
                              "Refuses and names the nearest certified metric otherwise",
                              "Every number comes with its formula and owner"]},
    "insight": {"title": "Answers any question from checked facts",
                "layers": ["ontology", "graph", "semantic", "context"],
                "tools": ["context_for_question", "list_business_metrics", "get_business_metric",
                          "find_entity", "get_entity", "how_connected", "get_ontology", "ask_question"],
                "guardrails": ["A certified metric first; otherwise a checked query, labelled as such",
                               "Every number must be in the facts; others are rejected",
                               "Says when the facts do not answer the question"]},
    "trust": {"title": "Says whether a number can be trusted", "layers": ["semantic", "ontology", "graph"],
              "tools": ["list_business_metrics", "get_business_metric", "get_ontology"],
              "guardrails": ["Read-only; reports problems, never fixes them",
                             "Never computes a new number"]},
    "steward": {"title": "Proposes improvements for a person to apply", "layers": ["ontology"],
                "tools": ["get_ontology"],
                "guardrails": ["Proposes only: nothing changes until a person applies it",
                               "Every applied note is kept with who applied it"]},
    "privacy": {"title": "Finds personal data", "layers": ["ontology"],
                "tools": ["get_ontology"],
                "guardrails": ["Names where personal data is; never shows a value"]},
}


def _a(word: str) -> str:
    """'a Customer', 'an Order'."""
    return f"{'an' if str(word)[:1].lower() in 'aeiou' else 'a'} {word}"


def _title(text: str) -> str:
    """'Order status' -> 'Order Status' (agent names read as names)."""
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in str(text).split())


def _ex(text: str, why: str) -> dict:
    return {"text": text, "why": why}


def _agent(key, name, kind, job, why, examples, things=None, metrics=None, focus=None) -> dict:
    spec = KINDS[kind]
    return {"key": key, "name": name, "kind": kind, "kind_title": spec["title"], "job": job,
            "why": why, "layers": list(spec["layers"]), "tools": list(spec["tools"]),
            "guardrails": list(spec["guardrails"]),
            "scope": {"things": list(things or []), "metrics": list(metrics or [])},
            "focus": focus or {}, "examples": [e for e in examples if e and e.get("text")][:3]}


def _main_thing(facts) -> dict | None:
    """The thing most others hang on: most links, then most records."""
    degree: dict = {}
    for link in facts["view"]["links"]:
        for t in (link["from_thing"], link["to_thing"]):
            degree[t] = degree.get(t, 0) + 1
    things = [t for t in facts["things"] if any(f.get("role") == "identifier" for f in t["fields"])] \
        or facts["things"]
    if not things:
        return None
    return max(things, key=lambda t: (degree.get(t["name"], 0), t["records"]))


def _a_key(layer, oid: str, thing: str) -> str | None:
    """One real record key of a thing, for an example question."""
    try:
        from knowledge_graph import explore as kg
        m = kg.model(layer, oid)
        s = next((s for s in m["sets"].values() if s["thing"] == thing and s["key"]), None)
        if not s:
            return None
        row = layer.graph.sql(f"SELECT {kg._k(s)} FROM {s['ref']} WHERE {kg._k(s)} IS NOT NULL LIMIT 1")
        return str(row[0][0]) if row else None
    except Exception:                              # noqa: BLE001 - an example, not a feature
        return None


def _certified(layer, oid: str) -> list[dict]:
    from semantic import definitions as defs
    from semantic import model as sem
    return [d for d in defs.list_definitions(layer.graph, sem.source_of(oid)) if d["status"] == "approved"]


def _data_texts(layer, oid: str, kind: str) -> list[dict]:
    """The data's own suggestions (no AI: instant and stable)."""
    try:
        return sg.suggest(layer, oid, kind, client=None)["suggestions"]
    except Exception:                              # noqa: BLE001
        return []


def builtins(layer, oid: str) -> list[dict]:
    """6 to 10 ready-made agents for this ontology, each with examples from its data."""
    facts = sg._facts(layer.graph, oid)
    v = facts["view"]
    things = facts["things"]
    certified = _certified(layer, oid)
    money = sg._money_fields(facts)
    main = _main_thing(facts)
    out = []

    # 1. Data Guide
    ex = []
    if main:
        ex.append(_ex(f"What is {_a(main['name'])}?", f"{main['records']:,} {main['name']} records"))
    if v["links"]:
        link = v["links"][0]
        ex.append(_ex(f"How does {link['from_thing']} link to {link['to_thing']}?", link["label"]))
    if money:
        ex.append(_ex(f"What does {money[0]['label']} mean?", f"a money field of {money[0]['thing']}"))
    elif len(things) > 1:
        ex.append(_ex("What data do we have?", f"{len(things)} things, {v['summary']['fields']} fields"))
    out.append(_agent("guide", "Data Guide", "guide",
                      "Explains what the data is, what every field means and how things link.",
                      f"{len(things)} things and {len(v['links'])} links to explain", ex))

    # 2. <Main thing> Investigator
    if main:
        key = _a_key(layer, oid, main["name"])
        parent = (facts["parents"].get(main["name"]) or [None])[0]
        ex = []
        if key:
            ex.append(_ex(f"Tell me about {main['name']} {key}", "a real record"))
            if parent:
                ex.append(_ex(f"Which {parent} does {main['name']} {key} belong to?", f"every {main['name']} links to one {parent}"))
        place = next((f for t in things for f in t["fields"] if f.get("role") in ("location", "category")
                      and f["values"] and not f.get("personal")), None)
        if place:
            ex.append(_ex(f"Find records with {place['label']} {place['values'][0][0]}",
                          f"{place['values'][0][1]:,} records have it"))
        out.append(_agent("investigator", f"{main['name']} Investigator", "investigator",
                          f"Finds any {main['name']} (or any other record) by id or name and shows everything it is linked to.",
                          f"{main['records']:,} {main['name']} records to look up", ex))

    # 3. Metric Analyst
    ex = []
    for d in certified[:2]:
        ex.append(_ex(f"What is the {d['title']}?", "certified metric"))
    if certified and certified[0].get("dimensions"):
        from semantic import model as sem
        dims = sem._meta(layer.graph, oid, certified[0]["name"]).get("dims") or []
        if dims:
            ex.append(_ex(f"{certified[0]['title']} by {dims[0]['label']}", "a certified breakdown"))
    if not ex and money:
        ex.append(_ex(f"What is the total {money[0]['label']}?",
                      "certify it on the Semantic page first; until then I say so"))
    out.append(_agent("metric", "Metric Analyst", "metric",
                      "Gives the governed number: only certified metrics, each with its formula, owner and breakdown.",
                      f"{len(certified)} certified metric(s)" if certified else
                      "no metric certified yet: it refuses until one is", ex))

    # 4. Insight Analyst
    asks = _data_texts(layer, oid, "ask")
    out.append(_agent("insight", "Insight Analyst", "insight",
                      "Answers any question about this data from checked, cited facts, using all four layers.",
                      "questions this data can answer", [_ex(s["text"], s["why"]) for s in asks[:3]]))

    # 5. Trust Checker
    conflicts = [f for f in facts["fields"] if f.get("check") == "conflict"]
    ex = []
    if certified:
        ex.append(_ex(f"Can I trust the {certified[0]['title']}?", "certified: drift and checks"))
    elif money:
        ex.append(_ex(f"Can I trust the total {money[0]['label']}?", "not certified yet"))
    if conflicts:
        ex.append(_ex("Which fields does the data disagree with?", f"{len(conflicts)} field(s)"))
    if main:
        ex.append(_ex(f"Is the {main['name']} data complete?", "empty shares and broken links"))
    out.append(_agent("trust", "Trust Checker", "trust",
                      "Says whether a number or a field can be trusted: certification, drift, data checks and broken links.",
                      f"{v['summary']['confirmed_pct']}% of fields confirmed by the data", ex))

    # 6. Data Steward
    notes = _data_texts(layer, oid, "note")
    # Complete notes first: one with "..." needs a person to fill it in.
    notes = sorted(notes, key=lambda n: "..." in n["text"])
    out.append(_agent("steward", "Data Steward", "steward",
                      "Turns what you know into notes on the ontology, and proposes the ones the data needs. You apply them.",
                      "notes this data still needs", [_ex(s["text"], s["why"]) for s in notes[:3]]))

    # ---- added only when the data supports them --------------------------
    extra = []
    if money:
        f = money[0]
        cats = sg._categories(facts, f["thing"])
        name = "Revenue Analyst" if sg.MAIN_MONEY.search(f["column"]) else f"{f['label']} Analyst"
        ex = [_ex(f"What is the total {f['label']}?", f"money field of {f['thing']}")]
        if cats:
            ex.append(_ex(f"Total {f['label']} by {cats[0]['label']}", f"{len(cats[0]['values'])} values to compare"))
            good = sg._good(cats[0]["values"])
            if good:
                ex.append(_ex(f"Total {f['label']} of {sg._plural(cats[0]['thing'])} with {cats[0]['label']} {good[0]}",
                              f"{good[1]:,} records"))
        metrics = [f"total_{x['column'].lower()}" for x in money]
        extra.append(_agent("money", name, "insight",
                            f"Everything about {f['label']} and the other money fields: totals, splits and what counts.",
                            f"{len(money)} money field(s)", ex, things=[f["thing"]], metrics=metrics,
                            focus={"field": f["label"]}))
    status = next((f for f in facts["fields"] if f.get("role") == "category" and sg._bad(f["values"])), None)
    if status:
        bad = sg._bad(status["values"])
        short = sg._short(status["label"], status["thing"])
        title = status["label"] if status["thing"].split()[-1].lower() in status["label"].lower() \
            else f"{status['thing']} {short}"
        extra.append(_agent("status", f"{_title(title)} Watcher", "insight",
                            f"Watches {status['label']}: how many {sg._plural(status['thing'])} are in each state, "
                            f"and the ones that should not count ({bad[0]}).",
                            f"{bad[1]:,} records have {status['label']} {bad[0]}",
                            [_ex(f"How many {sg._plural(status['thing'])} have {short} {bad[0]}?", f"{bad[1]:,} records"),
                             _ex(f"How many {sg._plural(status['thing'])} per {status['label']}?",
                                 f"{len(status['values'])} values"),
                             _ex(f"How many {sg._plural(status['thing'])} with {short} {bad[0]} per month?",
                                 "is it getting better?")],
                            things=[status["thing"]], focus={"field": status["label"]}))
    place = next((f for f in facts["fields"] if f.get("role") == "location" and f["values"]
                  and not f.get("personal")), None)
    if place:
        ex = [_ex(f"Which {place['label']} has the most {sg._plural(place['thing'])}?",
                  "places to compare")]
        if money:
            ex.append(_ex(f"Total {money[0]['label']} by {place['label']}", "money by place"))
        ex.append(_ex(f"How many {sg._plural(place['thing'])} are in {place['values'][0][0]}?",
                      f"{place['values'][0][1]:,} records"))
        extra.append(_agent("regional", f"Regional Analyst ({_title(place['label'])})", "insight",
                            f"Compares places by {place['label']}: where the records and the money are.",
                            f"{place['label']} to compare", ex,
                            focus={"field": place["label"]}))
    dated = next((t for t in things if any(f.get("role") == "date" and f.get("check") == "verified"
                                            for f in t["fields"])), None)
    if dated:
        ex = [_ex(f"How many {sg._plural(dated['name'])} per month?", "a verified date to count by")]
        if money:
            ex.append(_ex(f"How did the total {money[0]['label']} change month by month?", "a money trend"))
        ex.append(_ex(f"Which month had the most {sg._plural(dated['name'])}?", "the peak"))
        extra.append(_agent("trend", "Trend Analyst", "insight",
                            "Shows how things change over time: per month, peaks and drops.",
                            f"{dated['name']} has a verified date", ex, focus={"time": True}))
    personal = [f for f in facts["fields"] if f.get("personal")]
    if personal:
        kinds = sorted({f["personal"] for f in personal})
        extra.append(_agent("privacy", "Privacy Checker", "privacy",
                            "Finds where personal data is (emails, phones, ids...) so it can be protected. Never shows a value.",
                            f"{len(personal)} personal field(s): {', '.join(kinds)}",
                            [_ex("Where is personal data?", f"{len(personal)} field(s)"),
                             _ex(f"Which fields of {personal[0]['thing']} are personal?", personal[0]["personal"]),
                             _ex("Is personal data shared with agents?", "masked in every answer")]))
    # When the data supports more than fit, privacy comes before the views.
    order = {"money": 0, "status": 1, "privacy": 2, "regional": 3, "trend": 4}
    extra.sort(key=lambda x: order.get(x["key"], 9))
    return (out + extra)[:MAX_AGENTS]


def describe_kinds() -> list[dict]:
    """The kinds an agent can be, for the form (with what each one may use)."""
    return [{"kind": k, "title": v["title"], "layers": v["layers"], "guardrails": v["guardrails"]}
            for k, v in KINDS.items()]


def ontology_things(graph, oid: str) -> list[str]:
    return [t["name"] for t in simple.view(graph, oid)["things"]]
