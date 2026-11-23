"""Business rules you can check.

A person writes a rule in plain words ("Net amount must be positive",
"Every order must belong to an existing customer", "Cancelled orders do not
count"). Strata reads it into one of six checks on a real field, runs it on
the data, and shows how many records follow it, with examples of the ones
that do not. A person then activates it with an owner, or retires it.

    required  the field must have a value
    range     a number must be above / below / between limits
    allowed   the field may only hold these values
    unique    no two records share the value
    exists    the reference must point to a record that exists
    excluded  records with these values do not count (a counting rule)

Rules are also suggested from the data (orphan links, negative amounts,
short lists of codes, missing values). Active rules reach the AI as facts
(context/engine.py), and a counting rule is compared with every metric on the
same table, so a metric that ignores it is named (`conflicts`).

AI proposes, data checks, person decides: nothing here edits the data or a
metric. Rules live in their own table, so they survive rebuilds.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from knowledge_graph.build import qi

TYPES = ("required", "range", "allowed", "unique", "exists", "excluded")
STATUSES = ("proposed", "active", "retired")
MAX_SUGGESTIONS = 8
EXAMPLES = 5
MAX_TEXT = 500
STATS_TTL_S = 600

_SCHEMA = """CREATE TABLE IF NOT EXISTS biz_rules (
    id VARCHAR PRIMARY KEY, ontology_id VARCHAR, text VARCHAR, spec VARCHAR,
    status VARCHAR, owner VARCHAR, by_user VARCHAR, decided_by VARCHAR,
    created_at VARCHAR, updated_at VARCHAR, result VARCHAR)"""


class RuleError(ValueError):
    """A rule Strata cannot turn into a check, said in plain words."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure(graph) -> None:
    if getattr(graph, "_biz_rules_ready", False):
        return
    with graph.lock:
        graph.con.execute(_SCHEMA)
    graph._biz_rules_ready = True


# ------------------------------------------------------------------ words
def _words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", str(text or "").lower()):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def _has(tokens: list[str], phrase: list[str]) -> bool:
    """`phrase` appears in `tokens` as consecutive words."""
    n = len(phrase)
    return n > 0 and any(tokens[i:i + n] == phrase for i in range(len(tokens) - n + 1))


def _a(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


# ------------------------------------------------------------------ the data
def _model(layer, oid: str) -> dict:
    from knowledge_graph import explore as kg
    return kg.model(layer, oid)


def _fields(m: dict) -> dict:
    """field key -> {field, thing, set} for every readable field."""
    out = {}
    for s in m["sets"].values():
        for f in s["fields"]:
            out[f["key"]] = {"field": f, "thing": s["thing"], "set": s}
    return out


def _things(m: dict) -> list[str]:
    return sorted({s["thing"] for s in m["sets"].values()}, key=lambda t: -len(t))


def _things_in(tokens: list[str], m: dict) -> list[tuple[int, str]]:
    """Things named in the text, (position, name), longest names first so
    'Order Line' wins over 'Order' where both fit."""
    found, taken = [], set()
    for t in _things(m):
        w = _words(t)
        for i in range(len(tokens) - len(w) + 1):
            span = set(range(i, i + len(w)))
            if tokens[i:i + len(w)] == w and not span & taken:
                found.append((i, t))
                taken |= span
    return sorted(found)


def _pick_field(tokens: list[str], m: dict, things: list[str]) -> dict | None:
    best, score = None, 0
    for key, x in _fields(m).items():
        f = x["field"]
        label = _words(f["label"])
        column = _words(f["column"].replace("_", " "))
        hit = len(label) if _has(tokens, label) else len(column) if _has(tokens, column) else 0
        if not hit:
            continue
        s = hit * 10 + (5 if x["thing"] in things else 0)
        if s > score:
            best, score = key, s
    return best


def _values_of(layer, x: dict, limit: int = 60) -> list[str]:
    s, col = x["set"], qi(x["field"]["column"])
    rows = layer.graph.sql(f"SELECT CAST({col} AS VARCHAR) v, count(*) n FROM {s['ref']} WHERE {col} IS NOT NULL"
                           f" GROUP BY 1 ORDER BY n DESC, v LIMIT {limit + 1}")
    return [r[0] for r in rows] if len(rows) <= limit else []


def _number(text: str) -> float:
    return float(text.replace(",", ""))


# ------------------------------------------------------------------ read a rule
_EXCLUDED = re.compile(r"\b(do not|don't|does not|doesn't|never|should not|must not|shall not)\s+"
                       r"(be\s+)?(count|counted|included|include)\b|\bare excluded\b|^\s*exclude\b|"
                       r"\bleave out\b|\bnot counted\b", re.I)
_EXISTS = re.compile(r"\b(belong|belongs|point|points|refer|refers|link|links|linked)\s+(to\s+)?(an?\s+)?"
                     r"(existing|valid|real)\b|\bto an existing\b", re.I)
_UNIQUE = re.compile(r"\bunique\b|\bno (two|duplicate)", re.I)
_ALLOWED = re.compile(r"\b(?:one of|only be|must be in|either)\s+(?P<values>.+)$", re.I)
_REQUIRED = re.compile(r"\b(must|should|has to|have to|always)\s+(have|has)\b|\b(must not|cannot|can't|should not)"
                       r"\s+be\s+(empty|blank|missing)\b|\bis required\b|\bmandatory\b|\bmust be (filled|present)\b",
                       re.I)
_RANGE = re.compile(r"\b(positive|negative|greater than|more than|above|over|at least|less than|below|under|"
                    r"at most|between|zero or more)\b|[<>]=?\s*-?\d", re.I)


def _range(text: str) -> dict:
    t = text.lower()
    num = r"(-?\d[\d,]*(?:\.\d+)?)"
    out: dict = {}
    if m := re.search(rf"between\s+{num}\s+and\s+{num}", t):
        return {"min": _number(m.group(1)), "max": _number(m.group(2))}
    if re.search(r"\b(not|never)\s+(be\s+)?negative\b|\bzero or more\b", t):
        return {"min": 0.0}
    if re.search(r"\bpositive\b", t):
        return {"min": 0.0, "strict_min": True}
    if re.search(r"\bnegative\b", t):
        return {"max": 0.0, "strict_max": True}
    if m := re.search(rf"(?:greater than|more than|above|over|>)\s*{num}", t):
        out = {"min": _number(m.group(1)), "strict_min": True}
    elif m := re.search(rf"(?:at least|>=)\s*{num}", t):
        out = {"min": _number(m.group(1))}
    if m := re.search(rf"(?:less than|below|under|<)\s*{num}", t):
        out.update({"max": _number(m.group(1)), "strict_max": True})
    elif m := re.search(rf"(?:at most|<=)\s*{num}", t):
        out.update({"max": _number(m.group(1))})
    return out


def _try_fields(m: dict, limit: int = 4) -> str:
    order = {"amount": 0, "flag": 1, "category": 1, "text": 2, "reference": 3, "date": 4}
    fs = sorted(_fields(m).values(), key=lambda x: (order.get(x["field"]["role"], 9), x["field"]["label"]))
    return ", ".join(f"{x['field']['label']} ({x['thing']})" for x in fs[:limit])


def read(layer, oid: str, text: str, client=None) -> dict:
    """Plain words -> a check spec on a real field. Raises RuleError, naming
    real fields to try, when the words do not name one."""
    text = str(text or "").strip()
    if not text:
        raise RuleError("write the rule first")
    if len(text) > MAX_TEXT:
        raise RuleError(f"keep a rule under {MAX_TEXT} characters")
    m = _model(layer, oid)
    try:
        return _read(layer, m, text)
    except RuleError:
        if client is None:
            raise
        spec = _ai_read(client, m, text)
        if spec is None:
            raise
        return spec


def _read(layer, m: dict, text: str) -> dict:
    tokens = _words(text)
    things = _things_in(tokens, m)
    names = [t for _, t in things]
    fields = _fields(m)
    key = _pick_field(tokens, m, names)

    if _EXCLUDED.search(text):
        candidates = [k for k in ([key] if key else []) + list(fields)
                      if fields[k]["field"]["role"] in ("flag", "category", "text", "name")
                      and (not names or fields[k]["thing"] in names)]
        for k in dict.fromkeys(candidates):
            data = _values_of(layer, fields[k])
            low = {v.lower(): v for v in data}
            picked = [low[w] for w in _content(tokens, fields[k], names) if w in low]
            picked += [v for w in _content(tokens, fields[k], names) for v in data
                       if v not in picked and len(w) >= 4 and v.lower().startswith(w[:5])]
            if picked:
                return _spec("excluded", fields[k], values=list(dict.fromkeys(picked)))
        raise RuleError("I could not find the value to leave out in the data: name it as the data "
                        f"writes it, with its field. Fields to try: {_try_fields(m)}")

    if _EXISTS.search(text):
        if key and fields[key]["field"]["role"] == "reference" and _link_of(m, fields[key]):
            return _spec("exists", fields[key])
        target = next((t for i, t in things if "existing" in tokens[:i] or "valid" in tokens[:i]
                       or "real" in tokens[:i]), names[-1] if len(names) > 1 else None)
        subject = names[0] if names else None
        for link in m["links"]:
            if subject and target and link["from_thing"] == subject and link["to_thing"] == target:
                k = next((k for k, x in fields.items() if x["set"]["member"] == link["child"]
                          and x["field"]["column"] == link["child_col"]), None)
                if k:
                    return _spec("exists", fields[k])
        raise RuleError("I could not find a link between those things to check. "
                        f"Name the field that points to the other thing, e.g. {_try_fields(m)}")

    if key is None:
        raise RuleError(f"I could not find a field in this rule. Name one as Strata shows it, "
                        f"for example: {_try_fields(m)}")
    x = fields[key]
    if _UNIQUE.search(text):
        return _spec("unique", x)
    if am := _ALLOWED.search(text):
        given = [v.strip(" .'\"") for v in re.split(r",|\bor\b|\band\b|/", am.group("values")) if v.strip(" .'\"")]
        data = {v.lower(): v for v in _values_of(layer, x)}
        return _spec("allowed", x, values=[data.get(v.lower(), v) for v in given])
    if _RANGE.search(text):
        limits = _range(text)
        if limits:
            return _spec("range", x, **limits)
    if _REQUIRED.search(text):
        return _spec("required", x)
    raise RuleError(f"I found the field {x['field']['label']} ({x['thing']}) but not what must hold. "
                    "Say: must have a value, must be one of …, must be positive, must be unique, "
                    "must point to an existing …, or … do not count")


def _content(tokens: list[str], x: dict, things: list[str]) -> list[str]:
    """Words of the rule that are not the field, the thing or rule words: the values."""
    skip = set(_words(x["field"]["label"])) | {w for t in things for w in _words(t)} | {
        "do", "not", "don", "t", "doe", "never", "should", "must", "shall", "be", "count", "counted",
        "included", "include", "are", "is", "excluded", "exclude", "leave", "out", "the", "a", "an",
        "with", "in", "from", "of", "any", "all", "record", "row", "that", "which", "where", "status"}
    return [w for w in tokens if w not in skip]


def _spec(kind: str, x: dict, **extra) -> dict:
    return {"type": kind, "field": x["field"]["key"], "thing": x["thing"], "label": x["field"]["label"],
            "column": x["field"]["column"], **extra}


def _link_of(m: dict, x: dict) -> dict | None:
    return next((lk for lk in m["links"] if lk["child"] == x["set"]["member"]
                 and lk["child_col"] == x["field"]["column"]), None)


_AI_SYSTEM = (
    "Turn a business rule into ONE check on a field that exists. Types: required, range, "
    "allowed, unique, exists, excluded. Reply with one JSON object only: {\"type\": \"...\", "
    "\"field\": \"<exact field key>\", \"values\"?: [..], \"min\"?: n, \"max\"?: n, "
    "\"strict_min\"?: bool, \"strict_max\"?: bool}. If no field fits, reply {}.")


def _ai_read(client, m: dict, text: str) -> dict | None:
    from agent.llm import extract_json_object
    fields = _fields(m)
    small = [{"key": k, "label": x["field"]["label"], "thing": x["thing"], "role": x["field"]["role"]}
             for k, x in list(fields.items())[:400]]
    try:
        data = extract_json_object(client.complete(
            [{"role": "system", "content": _AI_SYSTEM},
             {"role": "user", "content": "FIELDS:\n" + json.dumps(small) + "\n\nRULE:\n" + text}],
            max_tokens=600))
    except Exception:                              # noqa: BLE001 - the offline reading already said why
        return None
    if data.get("type") not in TYPES or data.get("field") not in fields:
        return None
    x = fields[data["field"]]
    extra = {k: data[k] for k in ("values", "min", "max", "strict_min", "strict_max") if k in data}
    if data["type"] == "exists" and not _link_of(m, x):
        return None
    return _spec(data["type"], x, **extra)


# ------------------------------------------------------------------ check it
def _ok_sql(m: dict, x: dict, spec: dict) -> str:
    c = qi(x["field"]["column"])
    kind = spec["type"]
    if kind == "required":
        return f"({c} IS NOT NULL AND trim(CAST({c} AS VARCHAR)) <> '')"
    if kind == "range":
        parts = []
        if spec.get("min") is not None:
            parts.append(f"TRY_CAST({c} AS DOUBLE) {'>' if spec.get('strict_min') else '>='} {float(spec['min'])}")
        if spec.get("max") is not None:
            parts.append(f"TRY_CAST({c} AS DOUBLE) {'<' if spec.get('strict_max') else '<='} {float(spec['max'])}")
        return f"({c} IS NULL OR ({' AND '.join(parts) or 'TRUE'}))"
    if kind == "allowed":
        vals = ", ".join("'" + str(v).lower().replace("'", "''") + "'" for v in spec.get("values") or [])
        return f"({c} IS NULL OR lower(CAST({c} AS VARCHAR)) IN ({vals or 'NULL'}))"
    if kind == "unique":
        ref = x["set"]["ref"]
        return (f"({c} IS NULL OR {c} NOT IN (SELECT {c} FROM {ref} WHERE {c} IS NOT NULL"
                f" GROUP BY {c} HAVING count(*) > 1))")
    if kind == "exists":
        link = _link_of(m, x)
        if link is None:
            raise RuleError(f"{x['field']['label']} no longer points to another thing")
        parent = m["sets"][link["parent"]]
        pc = qi(link["parent_col"])
        return (f"({c} IS NULL OR CAST({c} AS VARCHAR) IN "
                f"(SELECT CAST({pc} AS VARCHAR) FROM {parent['ref']} WHERE {pc} IS NOT NULL))")
    if kind == "excluded":
        vals = ", ".join("'" + str(v).lower().replace("'", "''") + "'" for v in spec.get("values") or [])
        return f"NOT ({c} IS NOT NULL AND lower(CAST({c} AS VARCHAR)) IN ({vals or 'NULL'}))"
    raise RuleError(f"unknown rule type {kind!r}")


def run(layer, oid: str, spec: dict) -> dict:
    """What the data says about one rule, now."""
    from knowledge_graph import explore as kg
    m = _model(layer, oid)
    x = _fields(m).get(spec["field"])
    if x is None:
        return {"error": f"the field {spec.get('label') or spec['field']} is no longer in the data", "at": _now()}
    ok = f"coalesce({_ok_sql(m, x, spec)}, FALSE)"
    ref = x["set"]["ref"]
    g = layer.graph
    total, bad = g.sql(f"SELECT count(*), count(*) FILTER (WHERE NOT {ok}) FROM {ref}")[0]
    c = qi(x["field"]["column"])
    rec = kg._k(x["set"]) if x["set"]["key_cols"] else "NULL"
    examples = [{"record": r[0], "value": r[1]} for r in g.sql(
        f"SELECT {rec}, CAST({c} AS VARCHAR) FROM {ref} WHERE NOT {ok} ORDER BY 1 LIMIT {EXAMPLES}")]
    total, bad = int(total), int(bad)
    if spec["type"] == "excluded":
        return {"checked": total, "affected": bad, "share_pct": round(100 * bad / total, 1) if total else 0.0,
                "examples": examples, "at": _now()}
    return {"checked": total, "failed": bad,
            "passed_pct": round(100 * (total - bad) / total, 1) if total else 100.0,
            "examples": examples, "at": _now()}


# ------------------------------------------------------------------ store
_COLS = "id, ontology_id, text, spec, status, owner, by_user, decided_by, created_at, updated_at, result"


def _row(r) -> dict:
    (rid, oid, text, spec, status, owner, by, decided_by, created, updated, result) = r
    return {"id": rid, "ontology": oid, "text": text, "spec": json.loads(spec or "{}"), "status": status,
            "owner": owner or None, "by": by, "decided_by": decided_by or None,
            "created_at": created, "updated_at": updated, "result": json.loads(result or "{}")}


def get(graph, oid: str, rid: str) -> dict:
    ensure(graph)
    rows = graph.sql(f"SELECT {_COLS} FROM biz_rules WHERE ontology_id = ? AND id = ?", [oid, str(rid)])
    if not rows:
        raise KeyError(f"no rule {rid!r}")
    return _row(rows[0])


def all_rules(graph, oid: str) -> list[dict]:
    ensure(graph)
    order = {"active": 0, "proposed": 1, "retired": 2}
    out = [_row(r) for r in graph.sql(f"SELECT {_COLS} FROM biz_rules WHERE ontology_id = ?"
                                      " ORDER BY created_at DESC, id", [oid])]
    out.sort(key=lambda r: order.get(r["status"], 3))
    return out


def active(graph, oid: str) -> list[dict]:
    return [r for r in all_rules(graph, oid) if r["status"] == "active"]


def add(layer, oid: str, text: str, by: str = "you", client=None) -> dict:
    from ontology import registry as reg
    g = layer.graph
    reg.get(g, oid)
    spec = read(layer, oid, text, client=client)
    result = run(layer, oid, spec)
    ensure(g)
    rid = uuid.uuid4().hex[:12]
    now = _now()
    with g.lock:
        g.con.execute(f"INSERT INTO biz_rules ({_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      [rid, oid, str(text).strip(), json.dumps(spec), "proposed", None, by, None, now, now,
                       json.dumps(result)])
    _audit(g, oid, rid, "proposed", by, str(text).strip())
    return get(g, oid, rid)


def _set(graph, oid: str, rid: str, **changes) -> dict:
    get(graph, oid, rid)
    cols = ", ".join(f"{k} = ?" for k in changes)
    with graph.lock:
        graph.con.execute(f"UPDATE biz_rules SET {cols}, updated_at = ? WHERE ontology_id = ? AND id = ?",
                          [*changes.values(), _now(), oid, rid])
    return get(graph, oid, rid)


def _audit(graph, oid: str, rid: str, decision: str, by: str, note: str = "") -> None:
    from ontology import registry as reg
    reg._audit(graph, oid, "rule", rid, decision, by, note)


def check(layer, oid: str, rid: str) -> dict:
    r = get(layer.graph, oid, rid)
    return _set(layer.graph, oid, rid, result=json.dumps(run(layer, oid, r["spec"])))


def activate(layer, oid: str, rid: str, by: str = "you", owner: str = "") -> dict:
    r = get(layer.graph, oid, rid)
    out = _set(layer.graph, oid, rid, status="active", owner=(owner or r["owner"] or None),
               decided_by=by)
    _audit(layer.graph, oid, rid, "active", by, owner)
    return out


def retire(layer, oid: str, rid: str, by: str = "you") -> dict:
    out = _set(layer.graph, oid, rid, status="retired", decided_by=by)
    _audit(layer.graph, oid, rid, "retired", by)
    return out


def remove(layer, oid: str, rid: str, by: str = "you") -> None:
    g = layer.graph
    get(g, oid, rid)
    with g.lock:
        g.con.execute("DELETE FROM biz_rules WHERE ontology_id = ? AND id = ?", [oid, rid])
    _audit(g, oid, rid, "removed", by)


# ------------------------------------------------------------------ conflicts
_FROM = re.compile(r"\bFROM\s+(\"[^\"]+\"|[\w.]+)\s+f\b", re.I)


def conflicts(layer, oid: str) -> list[dict]:
    """Metrics that count records a counting rule leaves out."""
    from semantic import definitions as defs
    from semantic import model as sem
    m = _model(layer, oid)
    fields = _fields(m)
    ds = [d for d in defs.list_definitions(layer.graph, sem.source_of(oid)) if d["status"] != "deprecated"]
    out = []
    for r in all_rules(layer.graph, oid):
        spec = r["spec"]
        if spec.get("type") != "excluded" or r["status"] == "retired" or spec["field"] not in fields:
            continue
        ref = fields[spec["field"]]["set"]["ref"]
        values = [str(v).lower() for v in spec.get("values") or []]
        for d in ds:
            fm = _FROM.search(d["base_sql"] or "")
            if not fm or fm.group(1) != ref:
                continue
            sql = f"{d['base_sql']} {d['value_expr']}".lower()
            if any(f"'{v}'" in sql for v in values):
                continue                               # the metric already leaves them out
            affected = (r["result"] or {}).get("affected")
            out.append({"rule": r["id"], "rule_text": r["text"], "metric": d["name"], "title": d["title"],
                        "certified": d["status"] == "approved",
                        "text": f"{d['title']} counts {spec['thing']} records your rule leaves out "
                                f"({', '.join(spec.get('values') or [])})"
                                + (f": {affected:,} records" if affected else "")})
    return out


# ------------------------------------------------------------------ suggestions
def _stats(layer, oid: str, m: dict) -> dict:
    from ontology import cache
    return cache.remember(layer.graph, "rules.stats", oid, (), lambda: _measure(layer, m), ttl=STATS_TTL_S)


def _measure(layer, m: dict) -> dict:
    """Per field: rows, missing values, distinct values, negatives (one query per table)."""
    out = {}
    for s in m["sets"].values():
        fs = [f for f in s["fields"] if f["role"] in ("amount", "flag", "category", "reference", "identifier",
                                                       "text", "date")][:40]
        if not fs:
            continue
        parts = ["count(*)"]
        for f in fs:
            c = qi(f["column"])
            parts += [f"count({c})", f"approx_count_distinct({c})",
                      f"count(*) FILTER (WHERE TRY_CAST({c} AS DOUBLE) < 0)" if f["role"] == "amount" else "0"]
        try:
            row = layer.graph.sql(f"SELECT {', '.join(parts)} FROM {s['ref']}")[0]
        except Exception:                          # noqa: BLE001 - a table we cannot read suggests nothing
            continue
        total = int(row[0])
        for i, f in enumerate(fs):
            nonnull, distinct, neg = row[1 + 3 * i: 4 + 3 * i]
            out[f["key"]] = {"rows": total, "missing": total - int(nonnull), "distinct": int(distinct),
                             "negative": int(neg or 0)}
    return out


def suggestions(layer, oid: str, existing: list[dict] | None = None) -> list[dict]:
    """Rules worth writing, from what the data shows; the ones already
    broken by some records first (they matter most)."""
    from knowledge_graph import explore as kg
    m = _model(layer, oid)
    fields = _fields(m)
    stats = _stats(layer, oid, m)
    have = {(r["spec"].get("type"), r["spec"].get("field")) for r in (existing or [])}
    have_text = {r["text"].strip().lower() for r in (existing or [])}
    orphans = {c["key"]: c.get("orphans") or 0 for c in kg.overview(layer, oid)["connections"]}
    out = []

    def add(kind, x, text, why, broken):
        if (kind, x["field"]["key"]) in have or text.strip().lower() in have_text:
            return
        out.append({"text": text, "spec": {"type": kind, "field": x["field"]["key"]}, "why": why,
                    "broken": broken})

    for key, x in fields.items():
        f, thing = x["field"], x["thing"]
        st = stats.get(key)
        if f["role"] == "reference":
            link = _link_of(m, x)
            if link:
                n = orphans.get(link["key"], 0)
                add("exists", x, f"Every {thing} {f['label']} must point to an existing {link['to_thing']}",
                    f"{n:,} {thing} records point at a {link['to_thing']} that does not exist" if n
                    else f"Guards the link from {thing} to {link['to_thing']}", n)
        if not st or not st["rows"]:
            continue
        if f["role"] == "amount" and st["negative"] <= st["rows"] * 0.05:
            add("range", x, f"{thing} {f['label']} must not be negative",
                f"{st['negative']:,} records are below zero" if st["negative"]
                else "No record is below zero today", st["negative"])
        if f["role"] in ("flag", "category") and 2 <= st["distinct"] <= 12:
            values = _values_of(layer, x, limit=12)
            if values and all(re.fullmatch(r"[\w .\-/]{1,30}", v) and "," not in v for v in values):
                add("allowed", x, f"{thing} {f['label']} must be one of {', '.join(values)}",
                    f"The data holds {len(values)} values; a new one would show up here", 0)
        if f["role"] in ("reference", "identifier", "text", "date") and 0 < st["missing"] <= st["rows"] * 0.2:
            add("required", x, f"Every {thing} must have {_a(f['label'])} {f['label']}",
                f"{st['missing']:,} records have no {f['label']}", st["missing"])
        if f["role"] == "identifier" and st["missing"] == 0 and st["distinct"] >= st["rows"] * 0.98 \
                and len(x["set"]["key_cols"]) == 1 and x["set"]["key_cols"][0] == f["column"]:
            add("unique", x, f"{thing} {f['label']} must be unique", "Each record has its own value today", 0)
    weight = {"exists": 0, "range": 1, "required": 2, "allowed": 3, "unique": 4}
    out.sort(key=lambda s: (-(s["broken"] > 0), weight[s["spec"]["type"]], -s["broken"], s["text"]))
    picked, per_kind = [], {}
    for s in out:                                  # a mix of kinds, not eight of one
        k = s["spec"]["type"]
        if per_kind.get(k, 0) < 3:
            picked.append(s)
            per_kind[k] = per_kind.get(k, 0) + 1
    return picked[:MAX_SUGGESTIONS]


# ------------------------------------------------------------------ the page
def listing(layer, oid: str) -> dict:
    from ontology import registry as reg
    g = layer.graph
    reg.get(g, oid)
    rs = all_rules(g, oid)
    failing = [r for r in rs if r["status"] != "retired" and (r["result"] or {}).get("failed")]
    return {"ontology": oid, "rules": rs, "suggestions": suggestions(layer, oid, rs),
            "conflicts": conflicts(layer, oid),
            "summary": {"active": sum(r["status"] == "active" for r in rs),
                        "proposed": sum(r["status"] == "proposed" for r in rs),
                        "failing": len(failing)}}


def as_fact(r: dict) -> str:
    """How an active rule reads to the AI: the rule, its owner, and what the data found."""
    res = r["result"] or {}
    owner = f" (owner: {r['owner']})" if r.get("owner") else ""
    if r["spec"].get("type") == "excluded":
        found = (f" On the data: {res.get('affected', 0):,} of {res.get('checked', 0):,} records are left out."
                 if "checked" in res else "")
    else:
        found = (f" On the data: {res.get('failed', 0):,} of {res.get('checked', 0):,} records break it."
                 if "checked" in res else "")
    return f"Business rule{owner}: {r['text'].rstrip('.')}.{found}"
