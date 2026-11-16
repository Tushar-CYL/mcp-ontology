"""Your data at a glance: the first thing the Context page shows.

Before anyone types a question, show what the data holds, as a few charts
chosen from the ontology's own fields. Each chart carries the question that
asks about it, so a person can click instead of type.

Everything here is plain SQL over the ontology's tables; no AI is involved.

* key numbers  - records per main thing, totals of the money fields;
* over time    - records per month, for a thing with a date field;
* breakdowns   - records per category (2-25 values), and a money total per
                 category where the same table has both;
* graph data   - entities per type, the busiest relations, the most
                 connected entities.
"""

from __future__ import annotations

from knowledge_graph import explore as kg
from knowledge_graph.build import qi
from ontology import simple

MAX_CHARTS = 6
TOP = 10
CATEGORY_MAX = 25


def _distinct(g, ref: str, col: str) -> int:
    return int(g.sql(f"SELECT approx_count_distinct({qi(col)}) FROM {ref}")[0][0] or 0)


def _is_text(f) -> bool:
    return "VARCHAR" in str(f.get("type") or "").upper() or "TEXT" in str(f.get("type") or "").upper()


def _is_time(f) -> bool:
    t = str(f.get("type") or "").upper()
    return f.get("role") == "date" and ("DATE" in t or "TIME" in t)


def _num(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def insights(layer, ontology_id: str) -> dict:
    view = simple.view(layer.graph, ontology_id)
    m = kg.model(layer, ontology_id)
    g = layer.graph
    kpis, charts = [], []

    rows_of = {s["member"]: int(g.sql(f"SELECT count(*) FROM {s['ref']}")[0][0])
               for s in m["sets"].values()}
    degree: dict = {}
    for link in m["links"]:
        for end in (link["child"], link["parent"]):
            degree[end] = degree.get(end, 0) + 1
    # The most connected things first (orders, customers), not the biggest
    # table: a million-row lookup table that links to nothing says little.
    sets = sorted(m["sets"].values(), key=lambda s: (-degree.get(s["member"], 0), -rows_of[s["member"]]))
    for s in sets[:4]:
        kpis.append({"label": f"{s['thing']} records", "value": rows_of[s["member"]],
                     "question": f"How many {s['thing']} records are there?"})

    # Money totals (fields the data confirmed are amounts).
    for s in sets:
        for f in s["fields"]:
            if f.get("role") == "amount" and f.get("check") == "verified" and len(kpis) < 6:
                total = g.sql(f"SELECT sum(TRY_CAST({qi(f['column'])} AS DOUBLE)) FROM {s['ref']}")[0][0]
                if total is not None:
                    kpis.append({"label": f"Total {f['label']}", "value": _num(float(total)),
                                 "unit": f.get("unit"),
                                 "question": f"What is the total {f['label']}?"})

    # Over time: records per month for the biggest thing with a date.
    for s in sets:
        date = next((f for f in s["fields"] if _is_time(f)), None)
        if not date:
            continue
        rows = g.sql(f"""
            SELECT strftime(date_trunc('month', TRY_CAST({qi(date['column'])} AS TIMESTAMP)), '%Y-%m') AS m,
                   count(*) FROM {s['ref']} WHERE {qi(date['column'])} IS NOT NULL
            GROUP BY 1 HAVING m IS NOT NULL ORDER BY 1""")
        # A last month with almost nothing in it is a month the data has
        # not finished, not a collapse: leave it out rather than draw a cliff.
        peak = max((int(r[1]) for r in rows), default=0)
        while len(rows) > 3 and int(rows[-1][1]) < 0.05 * peak:
            rows = rows[:-1]
        if len(rows) >= 3:
            charts.append({"id": f"time:{s['member']}", "kind": "line",
                           "title": f"{s['thing']} records per month",
                           "subtitle": f"by {date['label']}",
                           "x": [r[0] for r in rows], "y": [int(r[1]) for r in rows],
                           "y_label": "records",
                           "question": f"How many {s['thing']} records per month?"})
            break

    # Breakdowns: per category, and money per category.
    for s in sets:
        if len(charts) >= MAX_CHARTS:
            break
        cats = [f for f in s["fields"] if _is_text(f) and not f.get("personal")
                and f.get("role") not in ("identifier", "reference", "name", "text")
                and f["column"] != s.get("label")]
        cat = next((f for f in cats if 2 <= _distinct(g, s["ref"], f["column"]) <= CATEGORY_MAX), None)
        if not cat:
            continue
        rows = g.sql(f"""SELECT CAST({qi(cat['column'])} AS VARCHAR), count(*) FROM {s['ref']}
                        WHERE {qi(cat['column'])} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT {TOP}""")
        charts.append({"id": f"cat:{s['member']}.{cat['column']}", "kind": "bar",
                       "title": f"{s['thing']} records by {cat['label']}",
                       "x": [str(r[0]) for r in rows], "y": [int(r[1]) for r in rows],
                       "y_label": "records",
                       "question": f"How many {s['thing']} records per {cat['label']}?"})
        money = next((f for f in s["fields"] if f.get("role") == "amount"
                      and f.get("check") == "verified"), None)
        if money and len(charts) < MAX_CHARTS:
            rows = g.sql(f"""SELECT CAST({qi(cat['column'])} AS VARCHAR),
                                    sum(TRY_CAST({qi(money['column'])} AS DOUBLE)) FROM {s['ref']}
                            WHERE {qi(cat['column'])} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT {TOP}""")
            charts.append({"id": f"sum:{s['member']}.{money['column']}.{cat['column']}", "kind": "bar",
                           "title": f"Total {money['label']} by {cat['label']}",
                           "x": [str(r[0]) for r in rows], "y": [_num(float(r[1] or 0)) for r in rows],
                           "y_label": money.get("unit") or money["label"],
                           "question": f"What is the total {money['label']} per {cat['label']}?"})

    # Knowledge-graph sources: ONE set of charts across all of them. The
    # ontology's types and relations already span every source, so doing
    # this per source drew the same charts once per source (seen live with
    # three CSKG folders in one ontology).
    if m["graphs"]:
        sources = list(m["graphs"])
        things = sorted(((t["name"], t["records"]) for t in view["things"]
                         if any("#" in x for x in t["tables"])), key=lambda x: -x[1])
        types_chart = rel_chart = None
        if things:
            kpis.append({"label": "Entities", "value": sum(n for _, n in things),
                         "question": "How many entities are there?"})
            types_chart = {"id": "graph:types", "kind": "bar", "title": "Entities by type",
                           "x": [n for n, _ in things[:TOP]], "y": [c for _, c in things[:TOP]],
                           "y_label": "entities", "question": ""}
            charts.append(types_chart)
        rels = sorted((link for link in view["links"] if link.get("triples")),
                      key=lambda x: -x["triples"])[:TOP]
        if rels:
            kpis.append({"label": "Connections", "value": sum(int(link["triples"]) for link in view["links"]
                                                              if link.get("triples")),
                         "question": "Which relations are most common?"})
            rel_chart = {"id": "graph:rels", "kind": "bar", "title": "Most common relations",
                         "x": [link["label"] for link in rels], "y": [int(link["triples"]) for link in rels],
                         "y_label": "connections", "horizontal": True, "question": ""}
            charts.append(rel_chart)
        # The most connected entities across every source: degrees add up
        # when the same entity appears in several sources.
        per_source = " UNION ALL ".join(f"""
            SELECT coalesce(e.label, deg.id) AS name, deg.d AS d FROM (
              SELECT x AS id, count(*) d FROM (SELECT h AS x FROM ({q['triples']})
                UNION ALL SELECT t FROM ({q['triples']})) GROUP BY 1) deg
            LEFT JOIN (SELECT id, any_value(label) AS label FROM ({q['entities']}) GROUP BY id) e
              ON e.id = deg.id""" for q in m["graphs"].values())
        hubs = g.sql(f"SELECT name, sum(d) FROM ({per_source}) GROUP BY name ORDER BY 2 DESC, 1 LIMIT {TOP}")
        if hubs:
            names = [str(h[0]).replace("_", " ") for h in hubs]
            charts.append({"id": "graph:hubs", "kind": "bar", "title": "Most connected entities",
                           "subtitle": f"across {len(sources)} sources" if len(sources) > 1 else None,
                           "x": [str(h[0]) for h in hubs], "y": [int(h[1]) for h in hubs],
                           "y_label": "connections", "horizontal": True,
                           "question": f"What is {names[0]} connected to?"})
            # Totals cannot be computed over a graph, so graph charts offer
            # questions about entities, which the graph answers.
            verb = (rels[0].get("verb") or "use") if rels else "use"
            first, _, rest = verb.partition(" ")
            if first.endswith("s") and not first.endswith("ss"):      # "uses" -> "use"
                first = first[:-1]
            verb = f"{first} {rest}".strip()
            if types_chart:
                types_chart["question"] = f"What does {names[1 % len(names)]} {verb}?"
            if rel_chart:
                rel_chart["question"] = f"What does {names[2 % len(names)]} {verb}?"

    # Never the same chart or number twice.
    seen: set = set()
    charts = [c for c in charts if not (c["title"] in seen or seen.add(c["title"]))]
    seen = set()
    kpis = [k for k in kpis if not (k["label"] in seen or seen.add(k["label"]))]
    charts = charts[:MAX_CHARTS]
    questions = list(dict.fromkeys(c["question"] for c in charts if c["question"]))[:5]
    return {"ontology": {"id": view["id"], "name": view["name"]},
            "kpis": kpis[:6], "charts": charts, "questions": questions}
