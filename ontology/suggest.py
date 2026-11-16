"""Suggestions taken from the data itself, for every layer.

    note    Ontology "Add context": what is worth telling the ontology about
            THIS data (a status that should not count, money with no currency,
            a code nobody explained, a field the data disagrees with).
    ask     questions worth asking (Ontology Ask, Context).
    metric  business metrics to define in words (Semantic).
    search  real values to look up (Knowledge graph).

Each suggestion is built from facts the data proved: real names, real values
and counts, never a generic placeholder. When an AI model is configured it
picks the most useful ones and completes them, using only names and values
from those facts; anything that names nothing in this data is dropped, and the
data's own suggestions fill the gaps. Results are cached until the ontology
changes (a new version or a new note).
"""

from __future__ import annotations

import json
import re
import threading

from ontology import meaning as mn
from ontology import registry as reg
from ontology import simple

KINDS = ("note", "ask", "metric", "search")
MAX = 5

# Values that usually mean "this row should not count".
EXCLUDE = re.compile(r"cancel|unavailable|return|refund|void|\btest|delet|reject|fail|draft|"
                     r"inactive|declin|\blost\b|fraud|chargeback|error|invalid|duplicate", re.I)
# Values that usually mean "this is the real, finished business", best first.
GOOD = ("paid", "delivered", "completed", "complete", "closed won", "won", "invoiced", "settled",
        "fulfilled", "approved", "confirmed", "booked", "success", "successful", "done", "active",
        "shipped")
TECHNICAL = re.compile(r"(translation|dataset|\btable\b|\btbl\b|lookup|xref|staging|\bstg\b|"
                       r"\bdim\b|\bfact\b|\bmap\b|_|\d)", re.I)
# Money most likely to be "the" business number first; side charges last.
MAIN_MONEY = re.compile(r"revenue|sales|gross|total|payment|price|net|value|amount", re.I)
SIDE_MONEY = re.compile(r"freight|tax|discount|fee|shipping|charge", re.I)

_cache: dict = {}
_lock = threading.Lock()


def forget() -> None:
    """Drop cached suggestions (tests; a rebuild changes the version anyway)."""
    with _lock:
        _cache.clear()


# ---------------------------------------------------------------- helpers
def _plural(name: str) -> str:
    if name.endswith("s"):
        return name
    if name.endswith("y") and name[-2:-1] not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def _short(label: str, thing: str) -> str:
    """'Order Status' on Order reads 'Status'."""
    head = thing.split()[-1].lower()
    words = label.split()
    return " ".join(words[1:]) if len(words) > 1 and words[0].lower() == head else label


def _norm_value(v: str) -> str:
    return re.sub(r"[_\-]+", " ", v.strip().lower())


def _good(values):
    """The most 'real business' value of a status: paid before shipped."""
    found = [(v, n) for v, n in values if _norm_value(v) in GOOD]
    found.sort(key=lambda x: GOOD.index(_norm_value(x[0])))
    return found[0] if found else None


def _bad(values):
    return next(((v, n) for v, n in values if EXCLUDE.search(v)), None)


def _cryptic(column: str) -> bool:
    """KUNNR, NETWR, cust_cd: a code, not a word. 'name' and 'country' are words."""
    if column.isupper() and len(column) <= 8:
        return True
    parts = [x for x in re.split(r"[_\W]+", column.lower()) if x]
    return any(len(x) >= 3 and not re.search(r"[aeiouy]", x) for x in parts)


def _s(text, why, score, subject, group) -> dict:
    return {"text": text, "why": why, "score": score, "subject": str(subject).lower(), "group": group}


# ------------------------------------------------------------------ facts
def _facts(graph, oid: str) -> dict:
    v = simple.view(graph, oid)
    tops: dict = {}
    for item in reg.items(graph, oid, kind="profile"):
        p = item["payload"]
        table = p.get("table_key") or item["key"]
        for c in p.get("columns") or []:
            vals = [(str(t["value"]), int(t.get("count") or 0)) for t in c.get("top_values") or []
                    if t.get("value") not in (None, "")]
            tops[(table, c["name"])] = vals
    things = []
    for t in v["things"]:
        fields = [{**f, "thing": t["name"],
                   "values": [] if f.get("personal") else tops.get((f["table"], f["column"]), [])}
                  for f in t["fields"]]
        things.append({"name": t["name"], "records": t["records"], "fields": fields})
    parents: dict = {}
    for link in v["links"]:
        a, b = link["from_thing"], link["to_thing"]
        if link.get("cardinality") == "one-to-many":
            a, b = b, a
        if a and b and a != b and b not in parents.setdefault(a, []):
            parents[a].append(b)
    return {"view": v, "things": things, "parents": parents,
            "notes": [str(n.get("text") or "") for n in v["notes"]],
            "fields": [f for t in things for f in t["fields"]]}


NOT_MONEY = re.compile(r"sequen|_seq\b|\bseq\b|_no\b|number|index|rank|position|count", re.I)


def _money(f) -> bool:
    from semantic.model import COUNT_WORDS, MONEY, MONEY_WORDS
    name = f"{f['column']} {f['label']}"
    if f.get("check") == "conflict" or NOT_MONEY.search(name):
        return False
    return (f.get("role") in ("amount", "measure", "quantity")
            and (f.get("role") in MONEY or bool(MONEY_WORDS.search(name)))
            and not COUNT_WORDS.search(name))


def _money_fields(facts) -> list[dict]:
    out = [f for f in facts["fields"] if _money(f)]
    out.sort(key=lambda f: (bool(SIDE_MONEY.search(f["column"])), not MAIN_MONEY.search(f["column"])))
    return out


def _categories(facts, thing: str) -> list[dict]:
    """Category fields of a thing and of its parents (reachable many-to-one)."""
    names = [thing, *facts["parents"].get(thing, [])]
    return [f for n in names for t in facts["things"] if t["name"] == n for f in t["fields"]
            if f.get("role") == "category" and f["values"] and not f.get("personal")]


def _noted(facts, *subjects) -> bool:
    text = " ".join(facts["notes"]).lower()
    return any(s and len(str(s)) > 2 and str(s).lower() in text for s in subjects)


# ------------------------------------------------------ data suggestions
def _notes(facts) -> list[dict]:
    out = []
    money_things = {f["thing"] for f in facts["fields"] if _money(f)}
    for f in facts["fields"]:
        label, thing = f["label"], f["thing"]
        if _noted(facts, label, f["column"]):
            continue
        if f.get("check") == "conflict":
            out.append(_s(f"{label} is ...",
                          f"The data disagrees with the AI here: {f.get('proof')}.", 100, label, "conflict"))
        bad = [(v, n) for v, n in f["values"] if EXCLUDE.search(v)]
        if f.get("role") == "category" and bad:
            near = thing in money_things or any(thing in facts["parents"].get(m, []) for m in money_things) \
                or any(m in facts["parents"].get(thing, []) for m in money_things)
            vals = " or ".join(v for v, _ in bad[:2])
            n = sum(c for _, c in bad[:2])
            out.append(_s(f"{_plural(thing)} with {_short(label, thing)} {vals} do not count"
                          + (" in revenue" if near else ""),
                          f"{n:,} {thing} records have {label} {vals}; say whether they count.",
                          95 if near else 70, label, "exclude"))
        restated = re.sub(r"[^a-z0-9]", "", label.lower()) == re.sub(r"[^a-z0-9]", "", f["column"].lower())
        if _cryptic(f["column"]) and restated and f.get("role") not in ("identifier", "reference", "date") \
                and not f.get("personal"):
            out.append(_s(f"{f['column']} means ...",
                          f"{f['column']} is a code and nobody has explained it yet.", 75, label, "code"))
        vals = [v for v, _ in f["values"][:4]]
        if f.get("role") == "category" and len(vals) >= 2 and all(len(v) <= 3 and v.isupper() for v in vals):
            out.append(_s(f'In {label}, "{vals[0]}" means ... and "{vals[1]}" means ...',
                          f"{label} holds short codes ({', '.join(vals)}).", 60, label, "value-codes"))
        elif f.get("role") == "category" and f["values"] and not EXCLUDE.search(f["values"][0][0]):
            v, n = f["values"][0]
            out.append(_s(f'{label} "{v}" means ...',
                          f"The most common {label} ({n:,} records); explain it in business words.",
                          30, label, "value-meaning"))
    for i, f in enumerate([f for f in _money_fields(facts) if not f.get("unit")
                           and not _noted(facts, f["label"], f["column"])][:2]):
        out.append(_s(f"{f['label']} is in ...",
                      f"{f['label']} is money with no currency, so every total of it shows no unit.",
                      85 - i * 10, f["label"], "currency"))
    for t in facts["things"]:
        if TECHNICAL.search(t["name"]) and not _noted(facts, t["name"]):
            out.append(_s(f"{t['name']} should be called ...",
                          f"'{t['name']}' comes from a technical table name.", 50, t["name"], "rename"))
    return out


def _certified_questions(layer, oid) -> list[dict]:
    out = []
    try:
        from semantic import definitions as defs
        from semantic.model import _meta, source_of
        for d in defs.list_definitions(layer.graph, source_of(oid)):
            dims = _meta(layer.graph, oid, d["name"]).get("dims") or [] if d["status"] == "approved" else []
            if dims:
                out.append(_s(f"What is {d['title']} by {dims[0]['label']}?",
                              "A certified metric: the same answer every time.", 100, d["title"], "certified"))
    except Exception:                                  # noqa: BLE001 - suggestions only
        pass
    return out


def _questions(facts, layer, oid) -> list[dict]:
    out = _certified_questions(layer, oid)
    for f in _money_fields(facts)[:3]:
        for c in _categories(facts, f["thing"])[:2]:
            good = _good(c["values"])
            if good:
                out.append(_s(f"What is the total {f['label']} of {_plural(c['thing'])} with "
                              f"{_short(c['label'], c['thing'])} {good[0]}?",
                              f"{good[1]:,} {c['thing']} records have {c['label']} {good[0]}.", 90,
                              f["label"] + " good", "money-good"))
            out.append(_s(f"What is the total {f['label']} per {c['label']}?",
                          f"{c['label']} has {len(c['values'])} values to compare.", 80,
                          f["label"] + " by " + c["label"], "money-by"))
    for f in facts["fields"]:
        bad = _bad(f["values"])
        if f.get("role") == "category" and bad:
            out.append(_s(f"How many {_plural(f['thing'])} have {_short(f['label'], f['thing'])} {bad[0]}?",
                          f"{bad[1]:,} records have {f['label']} {bad[0]}.", 85,
                          f["label"] + " " + bad[0], "excluded"))
    for child, ps in facts["parents"].items():
        for p in ps[:1]:
            out.append(_s(f"Which {p} has the most {_plural(child)}?",
                          f"Every {child} links to one {p}.", 70, p + " " + child, "top-parent"))
    for t in facts["things"]:
        if any(f.get("role") == "date" for f in t["fields"]):
            out.append(_s(f"How many {_plural(t['name'])} per month?",
                          f"{t['name']} has a date to count by.", 60, t["name"] + " month", "per-month"))
    return out


def _metrics(facts, layer, oid) -> list[dict]:
    from semantic.model import _slug
    try:
        from semantic import definitions as defs
        from semantic.model import source_of
        have = {d["name"] for d in defs.list_definitions(layer.graph, source_of(oid))}
    except Exception:                                  # noqa: BLE001
        have = set()
    out = []
    for f in _money_fields(facts)[:4]:
        for c in _categories(facts, f["thing"])[:2]:
            good = _good(c["values"])
            if good:
                v, n = good
                title = f"{v.title()} {f['label']}"
                if _slug(title) not in have:
                    out.append(_s(f"{title} is the total {f['label']} of {_plural(c['thing'])} with "
                                  f"{_short(c['label'], c['thing'])} {v}",
                                  f"{n:,} {c['thing']} records have {c['label']} {v}.", 90,
                                  f["label"] + " good", "money-good"))
                break
    for f in facts["fields"]:
        bad = _bad(f["values"])
        if f.get("role") == "category" and bad:
            title = f"{bad[0].title()} {_plural(f['thing'])}"
            if _slug(title) not in have:
                out.append(_s(f"{title} is the number of {f['thing']} records with "
                              f"{_short(f['label'], f['thing'])} {bad[0]}",
                              f"{bad[1]:,} records have {f['label']} {bad[0]}.", 80,
                              f["label"] + " " + bad[0], "excluded-count"))
    for f in _money_fields(facts)[:2]:
        title = f"Average {f['label']}"
        if _slug(title) not in have:
            out.append(_s(f"{title} is the average {f['label']} per {f['thing']} record",
                          f"{f['label']} is money on {f['thing']}.", 60, f["label"] + " avg", "average"))
    return out


def _search(facts) -> list[dict]:
    out, seen = [], set()
    cats = [f for f in facts["fields"] if f.get("role") in ("category", "location")
            and not f.get("personal") and f["values"]]
    # A fair share per field: the most common value of each field first.
    for rank in range(3):
        for f in cats:
            if rank < len(f["values"]):
                v, n = f["values"][rank]
                if v.lower() not in seen:
                    seen.add(v.lower())
                    out.append(_s(v, f"{f['label']} ({n:,} records)", 50 - rank, v, "value"))
    return out


# ------------------------------------------------------------------- AI
AI_SYSTEM = {
    "note": ("You help a business person improve an ontology of their data. From the FACTS "
             "(things, fields, real values) and the DRAFTS, return the most useful notes they "
             "could add: what a code means, the currency of money, which statuses must not count, "
             "better names. Complete a draft's '...' only when the facts give a strong hint "
             "(e.g. country codes suggest a currency), otherwise keep '...'. Use ONLY names and "
             "values from the facts; never invent fields."),
    "ask": ("Suggest the questions a business person would most want answered from this data. "
            "Each must be answerable from the FACTS, end with '?', be under 15 words, and use the "
            "business labels (e.g. 'Payment Amount'), never column names (e.g. 'payment_value'). "
            "At most one real value per question; never list values in brackets."),
    "metric": ("Suggest business metrics to define in words over this data, written exactly "
               "like: '<Name> is the total|number|average <field label> of <Thing> records with "
               "<field label> <value>' (the filter part is optional). Use business labels, never "
               "column names. The name must describe the filter: a metric filtered on credit_card "
               "must not be called 'Delivered ...'. Use ONLY fields and values from the FACTS; "
               "sums only of money."),
}


def _ai(client, kind, facts, drafts) -> list[dict]:
    from agent.llm import extract_json_object
    small = [{"thing": t["name"], "records": t["records"],
              "fields": [{"label": f["label"], "column": f["column"], "role": f.get("role"),
                          "unit": f.get("unit"), "check": f.get("check"),
                          "values": [v for v, _ in f["values"][:5]]}
                         for f in t["fields"] if not f.get("personal")][:40]}
             for t in facts["things"]][:30]
    system = AI_SYSTEM[kind] + (f" Return at most {MAX}, most useful first, each a different idea. "
                                "Reply with one JSON object only: {\"suggestions\": [{\"text\": "
                                "\"...\", \"why\": \"one short line, citing the data\"}]}")
    user = json.dumps({"facts": small, "links": facts["parents"], "notes": facts["notes"][-10:],
                       "drafts": [d["text"] for d in drafts[:10]]})
    reply = client.complete([{"role": "system", "content": system},
                             {"role": "user", "content": user}], max_tokens=900)
    return [s for s in extract_json_object(reply).get("suggestions") or [] if isinstance(s, dict)]


def _real_names(facts) -> set[str]:
    names = set()
    for t in facts["things"]:
        names |= {t["name"].lower(), t["name"].split()[-1].lower()}
        for f in t["fields"]:
            names |= {f["label"].lower(), f["column"].lower()}
    return {n for n in names if len(n) > 2}


def _values(facts) -> set[str]:
    return {v.lower() for f in facts["fields"] if f.get("role") == "category"
            for v, _ in f["values"] if len(v) > 2}


def _valid(kind, text: str, names, facts) -> bool:
    if not text or len(text) > 220 or (kind == "ask" and (not text.endswith("?") or len(text) > 140)):
        return False
    low = text.lower()
    # '"SP" means SP' says nothing.
    for value, meaning in re.findall(r'"([^"]+)"\s+means\s+([\w\- ]+?)(?=\s+and\b|[.,;]|$)', text):
        if re.sub(r"\W", "", value.lower()) == re.sub(r"\W", "", meaning.lower()):
            return False
    if kind in ("ask", "metric") and ("(" in text or re.search(r"\b[a-z]+_[a-z_]+\b", text)
                                      and not any(v in low for v in _values(facts) if "_" in v)):
        return False                                   # column names or value lists: not for people
    if kind == "metric" and " is " in low:
        title, body = low.split(" is ", 1)
        vals = _values(facts)
        in_title = {v for v in vals if re.search(rf"\b{re.escape(v)}\b", title)}
        in_body = {v for v in vals if re.search(rf"\b{re.escape(v)}\b", body)}
        if in_title and not in_title & in_body:
            return False                               # "Delivered ..." filtered on credit_card
    return any(n in low for n in names)


# ------------------------------------------------------------------ main
def suggest(layer, oid: str, kind: str, client=None) -> dict:
    """{"suggestions": [{"text", "why"}], "method": "ai" | "data"}."""
    if kind not in KINDS:
        raise ValueError(f"unknown suggestion kind {kind!r}; use one of {', '.join(KINDS)}")
    graph = layer.graph
    facts = _facts(graph, oid)
    use_ai = (kind != "search" and client is not None and not getattr(client, "mock", True)
              and mn.ai_enabled())
    key = (id(graph), oid, kind, facts["view"]["version"], len(facts["notes"]), use_ai)
    with _lock:
        if key in _cache:
            return _cache[key]
    drafts = {"note": lambda: _notes(facts), "ask": lambda: _questions(facts, layer, oid),
              "metric": lambda: _metrics(facts, layer, oid), "search": lambda: _search(facts)}[kind]()
    drafts.sort(key=lambda s: -s["score"])
    picked, method = [], "data"
    if use_ai and drafts:
        try:
            names = _real_names(facts)
            for s in _ai(client, kind, facts, drafts):
                text = str(s.get("text") or "").strip()
                if _valid(kind, text, names, facts) and not _noted(facts, text) \
                        and text.lower() not in {p["text"].lower() for p in picked}:
                    picked.append({"text": text, "why": mn._clean(s.get("why"), 200) or "from your data"})
            method = "ai" if picked else "data"
        except Exception:                              # noqa: BLE001 - the data's suggestions stand
            picked = []
    picked = picked[:MAX]
    # Top up from the data: one of each kind of idea first, then the rest.
    seen = {p["text"].lower() for p in picked}
    subjects, groups = set(), set()
    for one_per_group in (True, False):
        for s in drafts:
            if len(picked) >= MAX:
                break
            if s["text"].lower() in seen or s["subject"] in subjects:
                continue
            if one_per_group and s["group"] in groups:
                continue
            # The AI already said something about this subject.
            if method == "ai" and kind != "search" and s["subject"] in " ".join(seen):
                continue
            subjects.add(s["subject"])
            groups.add(s["group"])
            seen.add(s["text"].lower())
            picked.append({"text": s["text"], "why": s["why"]})
    out = {"suggestions": picked, "method": method}
    with _lock:
        _cache[key] = out
    return out
