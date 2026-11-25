"""Global chat across ontology, knowledge graph, semantic, and context.

Answers are validated against live data before they are shown. Prefer a short,
structured, data-backed sentence over generative prose.
"""

from __future__ import annotations

import re

from ontology import ask as onto_ask


def _num(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return v


def _fmt_num(v) -> str:
    n = _num(v)
    if isinstance(n, bool) or n is None:
        return str(v)
    if isinstance(n, int):
        return f"{n:,}"
    if isinstance(n, float):
        return f"{n:,.2f}".rstrip("0").rstrip(".")
    return str(v)


def _nums_in(text: str) -> set[float]:
    out: set[float] = set()
    for raw in re.findall(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?", text or ""):
        whole, frac = raw if isinstance(raw, tuple) else (raw, "")
        try:
            s = whole.replace(",", "") + (("." + frac) if frac else "")
            f = float(s)
            out.add(f)
            if f.is_integer():
                out.add(float(int(f)))
        except ValueError:
            continue
    return out


def _table_nums(rows: list) -> set[float]:
    out: set[float] = set()
    for row in rows or []:
        for cell in row:
            n = _num(cell)
            if isinstance(n, (int, float)) and not isinstance(n, bool):
                out.add(float(n))
    return out


def _check(name: str, passed: bool, detail: str, severity: str = "info") -> dict:
    return {"name": name, "passed": passed, "detail": detail, "severity": severity}


def _answer_from_table(question: str, columns: list, rows: list, things: list,
                       metric: dict | None) -> str | None:
    """Write the answer from the result table — never from generative prose."""
    if not columns or not rows:
        return None
    if len(rows) == 1 and len(rows[0]) == 1:
        value = _fmt_num(rows[0][0])
        label = (columns[0] or "Result").replace("_", " ").strip()
        thing = (things[0] if things else "") or ""
        q = (question or "").lower()
        if metric and metric.get("title"):
            return f"{metric['title']}: {value}."
        if "how many" in q or "count" in label.lower() or label.lower() in (
                "v", "count", "n", "number of records", "number of customer records"):
            if thing:
                who = thing if thing.lower().endswith("s") else f"{thing} records"
                return f"There are {value} {who}."
            return f"There are {value} records."
        if label.lower().startswith("number of"):
            return f"There are {value} {label[10:].strip()}."
        return f"{label}: {value}."
    # Small result set: one short sentence naming the columns.
    if len(rows) <= 5 and len(columns) <= 3:
        bits = []
        for row in rows[:5]:
            parts = [f"{columns[i]} {_fmt_num(row[i])}" for i in range(min(len(columns), len(row)))]
            bits.append(", ".join(parts))
        return "; ".join(bits) + "."
    return f"Found {len(rows):,} rows across {len(columns)} fields."


def _clean_ai(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"\s*\[\d+\](?:\s*\[\d+\])*", "", t)
    t = re.sub(r"(?i)\baccording to strata'?s? own query\b", "from your data", t)
    t = re.sub(r"(?i)\breturned by strata'?s? query\b", "in your data", t)
    t = re.sub(r"(?i)\bbased on the number of\b", "", t)
    t = re.sub(r"\b(\d{4,})\b", lambda m: f"{int(m.group(1)):,}", t)
    t = re.sub(r"\s+", " ", t).strip(" :")
    if t and t[-1] not in ".!?":
        t += "."
    return t


def _clean_fact(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"\([^)]*not AI-written[^)]*\)", "", t, flags=re.I)
    t = re.sub(r"Computed by Strata'?s? own query\s*:?\s*", "", t, flags=re.I)
    t = re.sub(r"Strata'?s? own query over [A-Za-z ]+\s*:?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*computed from the data\.?\s*$", "", t, flags=re.I)
    t = re.sub(r"\b(\d{4,})\b", lambda m: f"{int(m.group(1)):,}", t)
    t = re.sub(r"\s+", " ", t).strip(" :.-")
    if t and t[-1] not in ".!?":
        t += "."
    return t


def _detail(things: list, metric: dict | None, sql: str | None, rows: list,
            status: str, checks: list) -> str:
    parts = []
    if metric and metric.get("title"):
        parts.append(f"Certified metric: {metric['title']}")
    elif things:
        parts.append("About " + ", ".join(things[:3]))
    if sql and rows:
        parts.append("checked against live query results")
    elif any(c["name"] == "catalogue" and c["passed"] for c in checks):
        parts.append("from the published ontology")
    if status == "unverified":
        parts.append("some numbers could not be verified")
    return " · ".join(parts)


def _from_context(layer, ontology_id: str, question: str, client=None,
                  max_rows: int = 50) -> dict:
    from context import engine as ctx

    out = ctx.build(layer, ontology_id, question[:1000], client=client)
    steps = out.get("steps") or {}
    understand = steps.get("understand") or {}
    facts = steps.get("facts") or {}
    answer = steps.get("answer") or {}
    follow = steps.get("follow") or {}

    table = facts.get("table") or None
    columns = list((table or {}).get("columns") or [])
    if columns == ["v"]:
        columns = ["Number of records"]
    rows = [list(r) for r in ((table or {}).get("rows") or [])][:max_rows]
    sql = facts.get("sql")
    metric = facts.get("metric")
    status = answer.get("status") or "not_enough"
    warning = (answer.get("warning") or "").strip()
    ai_text = _clean_ai((answer.get("text") or "").strip())
    unsupported = list(answer.get("unsupported_numbers") or [])

    things = [t.get("name") for t in (understand.get("things") or []) if t.get("name")]
    if not things:
        things = list(follow.get("in_scope") or [])

    checks: list[dict] = []
    allowed = _table_nums(rows)
    for f in facts.get("kept") or []:
        allowed |= _nums_in(f.get("text") or "")

    # 1) Prefer a sentence written from the result table.
    text = _answer_from_table(question, columns, rows, things, metric)
    source = "data"

    # 2) Otherwise use AI text only when every number is supported.
    if not text and ai_text and status in ("answered", "no_ai"):
        claimed = _nums_in(ai_text)
        bad = [n for n in claimed if allowed and all(abs(n - a) > 0.01 for a in allowed)]
        # Also respect the engine's own unsupported list.
        bad = bad or [float(n) for n in unsupported]
        if claimed and not allowed:
            checks.append(_check("numbers_supported", False,
                                 "Answer numbers could not be checked against results.", "warn"))
            text = None
            source = "none"
        elif bad:
            checks.append(_check("numbers_supported", False,
                                 "Rejected numbers not found in the data: "
                                 + ", ".join(_fmt_num(n) for n in bad[:5]) + ".", "warn"))
            text = None
            source = "none"
        else:
            text = ai_text
            source = "ai_checked"
            checks.append(_check("numbers_supported", True,
                                 "Every number in the answer appears in the evidence.", "info"))

    # 3) Fall back to cleaned facts, then a clear refusal.
    if not text:
        kept = facts.get("kept") or []
        cleaned = [_clean_fact(k.get("text") or "") for k in kept[:2] if k.get("text")]
        cleaned = [c for c in cleaned if c]
        if cleaned and status != "unverified":
            text = " ".join(cleaned)
            source = "facts"
        elif understand.get("records"):
            labels = [f"{r.get('thing')} {r.get('label') or r.get('key')}"
                      for r in understand["records"][:3]]
            text = "Matched records: " + "; ".join(labels) + "."
            source = "records"
        else:
            text = "Not enough proven data to answer that yet."
            source = "none"
            status = "not_enough"

    if rows:
        checks.append(_check("query_ran", True,
                             f"Query returned {len(rows):,} row{'s' if len(rows) != 1 else ''}.", "info"))
    if sql and source == "data":
        checks.append(_check("answer_from_data", True,
                             "Answer written from query results, not generative prose.", "info"))
    if metric:
        checks.append(_check("certified_metric", True,
                             f"Used certified metric {metric.get('title') or metric.get('name')}.", "info"))
    if status == "unverified" and source != "data":
        checks.append(_check("ai_verified", False, warning or "AI answer was not fully verified.", "warn"))
        # Never show unverified AI as the main answer when we have data.
        if rows:
            text = _answer_from_table(question, columns, rows, things, metric) or text
            source = "data"
            status = "answered"
            checks.append(_check("fallback_to_data", True,
                                 "Replaced unverified wording with the query result.", "info"))

    answerable = source != "none" and bool(text)
    if status in ("not_enough",) and not rows and not metric:
        answerable = False

    confidence = "high" if source == "data" or metric else (
        "medium" if source in ("ai_checked", "facts") else "low")

    records = []
    for r in understand.get("records") or []:
        if not r.get("set") or r.get("key") is None:
            continue
        records.append({
            "set": r["set"], "key": str(r["key"]),
            "thing": r.get("thing") or "", "label": r.get("label") or str(r["key"]),
        })

    fact_cards = []
    for f in (facts.get("kept") or [])[:6]:
        cleaned = _clean_fact(f.get("text") or "")
        if not cleaned or len(cleaned) < 8:
            continue
        if text and cleaned.rstrip(".")[:48].lower() in text.lower():
            continue
        fact_cards.append({
            "text": cleaned,
            "source": "from your data",
            "citation": f.get("citation") or "",
        })

    layers = [{"layer": "ontology", "what": "published terms and links"}]
    if records:
        layers.append({"layer": "knowledge graph", "what": "matched records and proven links"})
    if metric:
        layers.append({"layer": "semantic", "what": f"certified metric {metric.get('title') or metric.get('name')}"})
    if sql or rows or fact_cards:
        layers.append({"layer": "context", "what": "assembled and checked facts"})

    detail = _detail(things, metric, sql, rows, status, checks)

    return {
        "ontology": ontology_id,
        "version": (out.get("ontology") or {}).get("version"),
        "question": question,
        "coverage": float(understand.get("coverage") or 0),
        "things": things,
        "unknown_words": list(understand.get("unknown") or []),
        "sql": sql,
        "rows": [[_num(c) for c in row] for row in rows],
        "columns": columns,
        "row_count": len(rows),
        "truncated": bool(table and len((table.get("rows") or [])) > len(rows)),
        "fields_used": [],
        "repaired": False,
        "answerable": answerable,
        "explanation": text,
        "detail": detail,
        "confidence": confidence,
        "checks": checks,
        "mode": "query" if (sql or rows or metric) else "explain",
        "note": warning if status == "unverified" and source != "data" else "",
        "records": records[:12],
        "metric": metric,
        "facts": fact_cards,
        "layers_used": layers,
        "answer_status": "answered" if answerable and confidence != "low" else status,
        "answer_source": source,
    }


def _wants_metric_list(question: str) -> bool:
    q = f" {re.sub(r'[^a-z0-9]+', ' ', (question or '').lower())} "
    has_metric = any(w in q for w in (" metric ", " metrics ", " kpi ", " kpis ", " measure ", " measures "))
    listish = any(w in q for w in (
        " which ", " what ", " list ", " show ", " give ", " available ", " trust ",
        " certified ", " semantic ", " symentic ", " all ",
    ))
    # "which certified metrics", "give me semantic metrics", "list KPIs"
    return has_metric and listish and not any(w in q for w in (
        " how many ", " how much ", " total ", " average ", " by ",
    ))


def _answer_metric_list(layer, ontology_id: str) -> dict:
    """Catalogue of certified (and proposed) semantic metrics."""
    from semantic import model as sem

    overview = sem.overview(layer, ontology_id)
    cards = overview.get("metrics") or []
    certified = [c for c in cards if c.get("status") == "certified"]
    proposed = [c for c in cards if c.get("status") == "proposed"]

    if certified:
        lines = []
        for c in certified[:12]:
            value = c.get("value")
            bit = c.get("title") or c.get("name")
            if value is not None:
                bit += f" = {_fmt_num(value)}"
            if c.get("owner"):
                bit += f" (owner {c['owner']})"
            lines.append(bit)
        headline = (
            f"You can trust {len(certified)} certified metric"
            f"{'s' if len(certified) != 1 else ''}."
        )
        detail = "Certified on the semantic layer" + (
            f" · {len(proposed)} still proposed" if proposed else ""
        )
        facts = [{"text": line, "source": "semantic", "citation": f"metric:{c['name']}"}
                 for c, line in zip(certified[:12], lines)]
        columns = ["Metric", "Status", "Value", "Owner"]
        rows = [[c.get("title") or c.get("name"), "certified",
                 c.get("value"), c.get("owner")] for c in certified[:50]]
        text = headline + " " + "; ".join(lines[:8]) + ("." if len(lines) <= 8 else "…")
    elif proposed:
        text = (f"No certified metrics yet. There are {len(proposed)} proposed metric"
                f"{'s' if len(proposed) != 1 else ''} waiting for certification.")
        detail = "Open Semantic to certify a metric before Chat can trust its numbers"
        facts = [{"text": c.get("title") or c.get("name"), "source": "semantic",
                  "citation": f"metric:{c['name']}"} for c in proposed[:12]]
        columns = ["Metric", "Status"]
        rows = [[c.get("title") or c.get("name"), "proposed"] for c in proposed[:50]]
    else:
        text = "No semantic metrics are defined for this ontology yet."
        detail = "Add or propose metrics on the Semantic page"
        facts, columns, rows = [], [], []

    return {
        "ontology": ontology_id,
        "version": None,
        "question": "",
        "coverage": 1.0 if certified or proposed else 0.0,
        "things": [],
        "unknown_words": [],
        "sql": None,
        "rows": rows,
        "columns": columns,
        "row_count": len(rows),
        "truncated": False,
        "fields_used": [],
        "repaired": False,
        "answerable": bool(certified or proposed),
        "explanation": text,
        "detail": detail,
        "confidence": "high" if certified else ("medium" if proposed else "low"),
        "checks": [
            _check("semantic_catalogue", True,
                   f"{len(certified)} certified, {len(proposed)} proposed.", "info"),
        ],
        "mode": "explain",
        "note": "",
        "records": [],
        "metric": None,
        "facts": facts,
        "layers_used": [{"layer": "semantic", "what": "certified and proposed metrics"}],
        "answer_status": "answered" if (certified or proposed) else "not_enough",
        "answer_source": "semantic",
    }


def _answer_metric_value(layer, ontology_id: str, question: str, max_rows: int) -> dict | None:
    """A single certified metric the question is asking for."""
    from semantic import model as sem

    try:
        hit = sem.match(layer, ontology_id, question)
    except Exception:                              # noqa: BLE001
        hit = None
    if not hit:
        return None
    try:
        run = sem.value(layer, ontology_id, hit["metric"], by=hit.get("by"),
                        filters=hit.get("filters") or None, limit=max_rows)
    except Exception:                              # noqa: BLE001
        return None
    columns = list(run.get("columns") or [])
    rows = [list(r) for r in (run.get("rows") or [])][:max_rows]
    metric = {"name": hit["metric"], "title": hit["title"], "owner": hit.get("owner")}
    text = _answer_from_table(question, columns, rows, [], metric) or f"{hit['title']}."
    return {
        "ontology": ontology_id,
        "version": None,
        "question": question,
        "coverage": 1.0,
        "things": [],
        "unknown_words": [],
        "sql": run.get("sql"),
        "rows": [[_num(c) for c in row] for row in rows],
        "columns": columns,
        "row_count": len(rows),
        "truncated": False,
        "fields_used": [],
        "repaired": False,
        "answerable": True,
        "explanation": text,
        "detail": f"Certified metric: {hit['title']}"
                  + (f" · owner {hit['owner']}" if hit.get("owner") else ""),
        "confidence": "high",
        "checks": [
            _check("certified_metric", True, f"Served certified metric {hit['title']}.", "info"),
            _check("answer_from_data", True, "Value computed from the certified definition.", "info"),
        ],
        "mode": "query",
        "note": "",
        "records": [],
        "metric": metric,
        "facts": [],
        "layers_used": [{"layer": "semantic", "what": f"certified metric {hit['title']}"}],
        "answer_status": "answered",
        "answer_source": "data",
    }


def chat(layer, ontology_id: str, question: str, client=None, version: int | None = None,
         max_rows: int = 50) -> dict:
    """Pointed, validated chat answer."""
    question = str(question or "").strip()
    if not question:
        raise ValueError("ask a question")
    if len(question) > 2000:
        raise ValueError("keep the question under 2,000 characters")
    max_rows = max(1, min(int(max_rows or 50), 500))

    # Semantic catalogue: "which certified metrics", "give me semantic metrics".
    if _wants_metric_list(question):
        out = _answer_metric_list(layer, ontology_id)
        out["question"] = question
        return out

    # A named certified metric value, when the question is clearly about one.
    metric_out = _answer_metric_value(layer, ontology_id, question, max_rows)
    if metric_out is not None:
        return metric_out

    mode = onto_ask.intent(question)
    if mode in ("rules", "explain"):
        out = onto_ask.ask(layer, ontology_id, question, client=client,
                           version=version, max_rows=max_rows)
        out.setdefault("records", [])
        out.setdefault("metric", None)
        out.setdefault("facts", [])
        out.setdefault("detail", "From the published ontology catalogue")
        out.setdefault("confidence", "high" if out.get("answerable") else "low")
        out.setdefault("layers_used", [{"layer": "ontology", "what": "catalogue and business rules"}])
        out.setdefault("answer_status", "answered" if out.get("answerable") else "not_enough")
        out.setdefault("answer_source", "catalogue")
        checks = list(out.get("checks") or [])
        checks.append(_check("catalogue", True, "Answered from ontology terms and rules.", "info"))
        out["checks"] = checks
        return out

    try:
        out = _from_context(layer, ontology_id, question, client=client, max_rows=max_rows)
        # If context found nothing, still try a certified metric or the metric list.
        if not out.get("answerable") or out.get("answer_source") == "none":
            again = _answer_metric_value(layer, ontology_id, question, max_rows)
            if again is not None:
                return again
            if any(w in question.lower() for w in ("metric", "kpi", "semantic", "symentic")):
                listed = _answer_metric_list(layer, ontology_id)
                listed["question"] = question
                return listed
        return out
    except Exception:
        out = onto_ask.ask(layer, ontology_id, question, client=client,
                           version=version, max_rows=max_rows)
        out.setdefault("records", [])
        out.setdefault("metric", None)
        out.setdefault("facts", [])
        out.setdefault("detail", "From the ontology query path")
        out.setdefault("confidence", "medium" if out.get("answerable") else "low")
        out.setdefault("layers_used", [{"layer": "ontology", "what": "catalogue query"}])
        out.setdefault("answer_status", "answered" if out.get("answerable") else "not_enough")
        out.setdefault("answer_source", "catalogue")
        return out
