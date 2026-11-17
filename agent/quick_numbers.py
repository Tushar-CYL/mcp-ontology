"""Common counting questions, answered by Strata's own query - no AI SQL.

    How many Orders have Order status canceled?        count, filter
    How many Orders per Order status?                  count by a category
    Which Customer state has the most Customers?       count by, top first
    Total Price by Customer state                      sum of money, by a parent's field
    How did the total Price change month by month?     sum by month

The query is built from the ontology the same way the Semantic layer builds a
metric: the thing's table plus its parents through proven many-to-one links
only (semantic.model._base), so a total is never inflated by a join. Every
field and value comes from the data; a question that does not fit one of these
shapes returns None and is left to the Context engine.
"""

from __future__ import annotations

import re

from knowledge_graph.build import qi
from ontology import ask

COUNT = re.compile(r"\b(how many|number of|count)\b", re.I)
SUM = re.compile(r"\b(total|sum)\b", re.I)
AVG = re.compile(r"\b(average|avg|mean)\b", re.I)
MONTH = re.compile(r"\b(per month|by month|each month|monthly|month by month|which month|over time)\b", re.I)
MOST = re.compile(r"\b(most|highest|largest|biggest|top)\b", re.I)
GROUP = re.compile(r"\b(?:by|per|each|which)\s+([a-z][a-z ]{1,40})", re.I)
NUMBER_ROLES = ("amount", "measure", "quantity")
MAX_ROWS = 50


def _best_field(view, words: set, allowed: set) -> tuple | None:
    best = None
    for t in view["things"]:
        if allowed and t["name"] not in allowed:
            continue
        for f in t["fields"]:
            if f.get("role") not in NUMBER_ROLES or f.get("check") == "conflict":
                continue
            lw = set(ask.words(f["label"]))
            score = len(lw & words) / max(1, len(lw)) if lw & words else 0
            if score >= 1 and (best is None or len(lw) > best[0]):
                best = (len(lw), f, t)
    return (best[1], best[2]) if best else None


def _thing(view, question: str, allowed: set) -> dict | None:
    """The thing being counted: the one the question names (plural ok)."""
    words = ask.words(question)
    best = None
    for t in view["things"]:
        if allowed and t["name"] not in allowed:
            continue
        tw = ask.words(t["name"])
        if tw and all(w in words for w in tw):
            # The counted thing comes after "how many" / "most": the later mention wins.
            pos = max(i for i, w in enumerate(words) if w == tw[-1])
            if best is None or (len(tw), pos) > (best[0], best[1]):
                best = (len(tw), pos, t)
    return best[2] if best else None


def _member(m: dict, thing: str) -> str | None:
    return next((k for k, s in m["sets"].items() if s["thing"] == thing and s["key"]), None)


def compute(layer, oid: str, question: str, linked: dict, view: dict, allowed: set | None = None) -> dict | None:
    """{columns, rows, sql, how, text} or None when the question is not one of the shapes."""
    from knowledge_graph import explore as kg
    from semantic import model as sem
    allowed = set(allowed or [])
    q = question
    words = set(ask.words(q))
    if not (COUNT.search(q) or SUM.search(q) or AVG.search(q) or MOST.search(q) or MONTH.search(q)):
        return None
    m = kg.model(layer, oid)
    g = layer.graph
    field = thing = None
    if SUM.search(q) or AVG.search(q):
        hit = _best_field(view, words, allowed)
        if hit:
            field, thing = hit
    if field is None:
        if not (COUNT.search(q) or MOST.search(q) or MONTH.search(q)):
            return None
        thing = _thing(view, q, allowed)
        if thing is None:
            return None
    member = field["table"] if field else _member(m, thing["name"])
    if not member or member not in m["sets"]:
        return None
    base = sem._base(m, g, member)
    dims = base["dims"]
    own = {f["column"]: f for f in m["sets"][member]["fields"]}

    # Filters: values the question names, on the fact table or a safe parent.
    where, shown, used_dims = [], [], set()
    for v in linked.get("values") or []:
        alias = f"{sem._slug(v['thing'])}_{sem._slug(v['column'])}"
        col = v["column"] if (v["column"] in own and v["thing"] == m["sets"][member]["thing"]) else \
            alias if any(d["name"] == alias for d in dims) else None
        if col is None:
            continue
        where.append(f"CAST({qi(col)} AS VARCHAR) = {sem._lit(v['value'])}")
        shown.append(f"{v['label']} = {v['value']}")
        used_dims.add(col)
    # A value can also be a word the ontology knows ("delivered" is in a date
    # field's name too), so look at the real values of the fields we can
    # filter on: the thing's own categories and its safe parents'.
    from ontology import suggest as sg
    facts = sg._facts(g, oid)
    fact_thing = m["sets"][member]["thing"]
    for f in sg._categories(facts, fact_thing):
        alias = f"{sem._slug(f['thing'])}_{sem._slug(f['column'])}"
        col = f["column"] if f["thing"] == fact_thing and f["column"] in own else \
            alias if any(d["name"] == alias for d in dims) else None
        if col is None or col in used_dims:
            continue
        for value, _n_ in f["values"]:
            if len(str(value)) >= 3 and re.search(rf"(?<![\w-]){re.escape(str(value))}(?![\w-])", q, re.I):
                where.append(f"CAST({qi(col)} AS VARCHAR) = {sem._lit(value)}")
                shown.append(f"{f['label']} = {value}")
                used_dims.add(col)
                break

    # Group: month, or the dimension the question names after by / per / which.
    by_sql = by_label = None
    if MONTH.search(q) and base["time"]:
        by_sql = f"strftime(date_trunc('month', TRY_CAST({qi(base['time'])} AS TIMESTAMP)), '%Y-%m')"
        by_label = "Month"
    else:
        tail = " ".join(m_.group(1) for m_ in GROUP.finditer(q))
        tail_words = set(ask.words(tail)) or words
        scored = []
        for d in dims:
            if d["name"] in used_dims:
                continue
            lw = set(ask.words(d["label"]))
            if lw and lw <= words and lw & tail_words:
                scored.append((len(lw), d))
        if scored:
            d = max(scored, key=lambda x: x[0])[1]
            by_sql, by_label = qi(d["name"]), d["label"]
    if by_sql is None and not where and not field and not COUNT.search(q):
        return None

    agg_label = (f"{'Average' if AVG.search(q) and not SUM.search(q) else 'Total'} {field['label']}"
                 if field else f"Number of {thing['name'] if thing else m['sets'][member]['thing']} records")
    agg = (f"{'avg' if AVG.search(q) and not SUM.search(q) else 'sum'}({qi(field['column'])})"
           if field else "count(*)")
    sql = f"SELECT {by_sql + ' AS g, ' if by_sql else ''}{agg} AS v FROM ({base['sql']}) b"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if by_sql:
        sql += f" GROUP BY 1 HAVING g IS NOT NULL ORDER BY {'1' if by_label == 'Month' else '2 DESC'} LIMIT {MAX_ROWS}"
    rows = [list(r) for r in g.sql(sql)]
    cols = ([by_label] if by_sql else []) + [agg_label]
    thing_name = m["sets"][member]["thing"]
    how = f"Strata's own query over {thing_name}" + (" and its linked records" if base["joins"] else "") + \
        (f", filtered to {'; '.join(shown)}" if shown else "") + " (not AI-written, not a certified metric)"
    what = agg_label + (f" with {'; '.join(shown)}" if shown else "")
    if not rows:
        text = "No records match."
    elif by_sql:
        if by_label == "Month":
            peak = max(rows, key=lambda r: r[1] or 0)
            text = (f"{what}, per month, {rows[0][0]} to {rows[-1][0]}: highest in {peak[0]} "
                    f"({_n(peak[1])}); latest {rows[-1][0]}: {_n(rows[-1][1])}.")
        else:
            total = sum(r[1] or 0 for r in rows)
            top = rows[0]
            text = (f"{what}, by {by_label}: {top[0]} is the largest with {_n(top[1])}"
                    + (f" ({top[1] / total:.0%} of {_n(total)})" if total else "") + f"; {len(rows)} groups.")
    else:
        text = f"{what}: {_n(rows[0][0])}."
    return {"columns": cols, "rows": rows, "sql": sql, "how": how, "text": text}


def _n(v) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)
