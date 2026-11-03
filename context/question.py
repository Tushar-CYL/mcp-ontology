"""Question-first context: the evidence pack for a business question.

The entity pack in `context.assemble` answers “tell me about this row”. This
module answers “why did this metric move, and can I trust it?”. It combines the
governed metric definition, the measured change, segment contributions, trend,
volume, source rows and schema relationships, then packs the highest-value
facts under the budget.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from context.budget import Fact, pack, render
from knowledge_graph.build import qi, source_rows
from semantic import definitions as metric_defs

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bundle_for(bundles, source: str):
    for item in bundles:
        if isinstance(item, dict):
            src, schema, onto = item["source"], item["schema"], item["onto"]
        else:
            src, schema, onto = item
        if src == source:
            return schema, onto
    raise KeyError(f"unknown source {source!r}")


def _mentions(text: str, token: str) -> bool:
    token = str(token or "").lower().strip()
    return bool(token) and re.search(
        r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", text) is not None


def _detect_metric(definitions: list[dict], question: str) -> dict | None:
    """The metric a question names: its name or title first, then a synonym.

    Names win over synonyms so a loosely chosen synonym can never hijack a
    question that names another metric outright.
    """
    text = f" {question.lower()} "
    for definition in definitions:
        if _mentions(text, definition["name"]) or                 _mentions(text, definition["name"].replace("_", " ")) or                 _mentions(text, definition["title"]):
            return definition
    for definition in definitions:
        if any(_mentions(text, s) for s in definition.get("synonyms") or []):
            return definition
    return None


_STOP = {"the", "a", "an", "of", "in", "on", "for", "and", "or", "to", "by",
         "what", "why", "how", "did", "does", "do", "is", "was", "were", "we",
         "our", "last", "this", "month", "week", "year", "many", "much",
         "total", "get", "got", "show", "me", "trend", "can", "i", "it"}


def _words(text: str) -> set[str]:
    out = set()
    for word in re.findall(r"[a-z0-9]+", str(text or "").lower()):
        if word in _STOP or len(word) < 3:
            continue
        out.add(word[:-1] if word.endswith("s") and len(word) > 4 else word)
    return out


def nearest_metric(question: str, definitions: list[dict]) -> str | None:
    """The approved metric whose words overlap the question most, or None.

    Used to make a refusal useful: "I can't answer that; the nearest approved
    metric is order_volume." Synonyms and titles weigh more than descriptions.
    """
    asked = _words(question)
    if not asked:
        return None
    best, best_score = None, 0.0
    for definition in definitions:
        if definition.get("status") != "approved":
            continue
        strong = _words(" ".join([definition["name"].replace("_", " "),
                                  definition.get("title") or "",
                                  *(definition.get("synonyms") or [])]))
        weak = _words(definition.get("description") or "")
        score = 2 * len(asked & strong) + 0.5 * len(asked & weak)
        if score > best_score:
            best, best_score = definition["name"], score
    return best if best_score >= 1 else None


PARTIAL_COVERAGE = 75.0


def answerable_verdict(chosen: dict | None, coverage: float, missing: list,
                       has_current: bool, has_prior: bool,
                       question: str = "", candidates: list | None = None,
                       allowed: list | None = None) -> dict:
    """yes / partial / no, with a reason a person can act on."""
    if chosen is None:
        near = nearest_metric(question, candidates or [])
        reason = "no approved metric is named in the question"
        if near:
            reason += f"; the nearest approved metric is {near!r}"
        return {"verdict": "no", "reason": reason, "nearest_metric": near}
    name = chosen["name"]
    if chosen.get("status") != "approved":
        return {"verdict": "no", "nearest_metric": None,
                "reason": f"metric {name!r} is {chosen.get('status')!r}, not "
                          "approved, so it cannot be used as evidence"}
    if allowed is not None and name not in allowed:
        return {"verdict": "no", "nearest_metric": None,
                "reason": f"metric {name!r} is outside this agent's scope"}
    if not has_current:
        return {"verdict": "no", "nearest_metric": None,
                "reason": f"{name!r} could not be measured for the period"}
    if not has_prior:
        return {"verdict": "partial", "nearest_metric": None,
                "reason": f"{name!r} was measured but there is no prior period "
                          "to compare with"}
    if coverage < PARTIAL_COVERAGE:
        return {"verdict": "partial", "nearest_metric": None,
                "reason": f"evidence covers {coverage:.0f}% of what a full "
                          f"answer needs; missing: {', '.join(missing) or 'none'}"}
    return {"verdict": "yes", "nearest_metric": None,
            "reason": f"approved metric {name!r} was measured and compared; "
                      f"evidence coverage {coverage:.0f}%"}


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def question_window(graph, definition: dict,
                    question: str) -> tuple[str, str, str, str]:
    """(prior_from, current_from, current_to, label) for the month a question
    names ("in March 2024"), else the latest month in the data."""
    match = re.search(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})\b",
                      question.lower())
    if not match or not definition.get("time_column"):
        return _latest_window(graph, definition)
    month, year = _MONTHS[match.group(1)], int(match.group(2))
    current_from = date(year, month, 1)
    current_to = date(year + (month == 12), month % 12 + 1, 1)
    prior_from = date(year - (month == 1), (month - 2) % 12 + 1, 1)
    return (prior_from.isoformat(), current_from.isoformat(),
            current_to.isoformat(), f"{year}-{month:02d}")


def month_label(label: str) -> str:
    """'2024-04' -> 'April 2024'."""
    try:
        year, month = label.split("-")[:2]
        return f"{list(_MONTHS)[int(month) - 1].capitalize()} {int(year)}"
    except (ValueError, IndexError):
        return label


def _latest_window(graph, definition: dict) -> tuple[str, str, str, str]:
    time_column = definition.get("time_column")
    if not time_column:
        return "", "", "", ""
    row = graph.sql(
        f"SELECT max({qi(time_column)}) FROM ({definition['base_sql']}) AS fact")[0]
    latest = row[0]
    if latest is None:
        return "", "", "", ""
    if isinstance(latest, datetime):
        latest = latest.date()
    elif isinstance(latest, str):
        try:
            latest = date.fromisoformat(latest[:10])
        except ValueError:
            return "", "", "", ""
    if not isinstance(latest, date):
        return "", "", "", ""
    current_from = latest.replace(day=1)
    if current_from.month == 12:
        current_to = date(current_from.year + 1, 1, 1)
        prior_from = date(current_from.year, 11, 1)
    else:
        current_to = date(current_from.year, current_from.month + 1, 1)
        prior_from = date(current_from.year, current_from.month - 1, 1) \
            if current_from.month > 1 else date(current_from.year - 1, 12, 1)
    return (prior_from.isoformat(), current_from.isoformat(),
            current_to.isoformat(), f"{current_from.year}-{current_from.month:02d}")


def _detect_filters(graph, definition: dict,
                    question: str) -> dict[str, str]:
    text = " " + re.sub(r"[^a-z0-9]+", " ", question.lower()) + " "
    filters: dict[str, str] = {}
    for dimension in (definition.get("dimensions") or [])[:6]:
        if len(filters) >= 2:
            break
        try:
            rows = graph.sql(
                f"SELECT DISTINCT {qi(dimension)} FROM"
                f" ({definition['base_sql']}) AS fact"
                f" WHERE {qi(dimension)} IS NOT NULL LIMIT 60")
        except Exception:                          # noqa: BLE001
            continue
        for row in rows:
            value = str(row[0]).strip()
            if len(value) < 2 or value.lower() in ("true", "false"):
                continue
            pattern = r"(?<![a-z0-9])" + re.escape(value.lower()) + r"(?![a-z0-9])"
            if re.search(pattern, text):
                filters[dimension] = value
                break
    return filters


def _pick_dimension(definition: dict, question: str) -> str | None:
    dimensions = list(definition.get("dimensions") or [])
    text = question.lower()
    for dimension in dimensions:
        if re.search(r"(?<![a-z0-9])" + re.escape(dimension.lower()) +
                     r"s?(?![a-z0-9])", text):
            return dimension
    for preferred in ("segment", "region", "category", "channel"):
        if preferred in dimensions:
            return preferred
    return dimensions[0] if dimensions else None


def _fmt(value, definition: dict) -> str:
    if value is None:
        return "—"
    precision = int(definition.get("precision") or 2)
    kind = definition.get("format") or "number"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if kind == "currency":
        return f"${number:,.{precision}f}"
    if kind == "percent":
        return f"{number * 100:,.{precision}f}%"
    if kind == "integer":
        return f"{number:,.0f}"
    return f"{number:,.{precision}f}"


def build_question_context(graph, bundles, question: str,
                           source: str | None = None,
                           metric: str | None = None,
                           budget_chars: int = 1800) -> dict:
    bundles = list(bundles)
    sources = []
    for item in bundles:
        sources.append(item["source"] if isinstance(item, dict) else item[0])
    source = source or (sources[0] if len(sources) == 1 else "")
    if not source:
        raise ValueError("a source is required for question context")
    definitions = metric_defs.list_definitions(graph, source)
    chosen = (metric_defs.get_definition(graph, metric, source)
              if metric else _detect_metric(definitions, question))
    if chosen is None:
        # No governed metric in this question: fall back to the entity pack,
        # and say plainly that no approved metric answers it.
        from agent.receipt import receipt_from_facts
        from context.assemble import build_context
        verdict = answerable_verdict(
            chosen=None, coverage=0.0, missing=[], has_current=False,
            has_prior=False, question=question,
            candidates=[d for d in definitions if d.get("status") == "approved"])
        try:
            result = build_context(graph, bundles, task=question,
                                   budget_chars=budget_chars)
        except ValueError as exc:
            # Neither a metric nor an entity matches: that is a refusal with
            # a reason, not an error. An agent must be able to say "no".
            result = {"focus": {"type": "question", "source": source,
                                "question": question},
                      "facts": [], "dropped": [], "sources": [source],
                      "budget_chars": budget_chars, "chars": 0,
                      "rendered": "", "review_pending": 0,
                      "coverage": {"score": 0.0, "present": [], "missing": []},
                      "as_of": _now(), "latency_ms": 0.0}
            verdict = {**verdict,
                       "reason": verdict["reason"] + "; no entity matches either ("
                                 + str(exc).split(";")[0] + ")"}
        result["answerable"] = verdict
        result["receipt"] = receipt_from_facts(
            result.get("facts") or [], result.get("dropped") or [])
        return result
    schema, onto = _bundle_for(bundles, source)
    prior_from, current_from, current_to, period_label = question_window(
        graph, chosen, question)
    chart_trend: list[dict] = []
    chart_breakdown: dict = {"dimension": None, "rows": []}
    filters = _detect_filters(graph, chosen, question)
    dimension = _pick_dimension(chosen, question)
    facts: list[Fact] = []

    def add(text: str, provenance: str, weight: float, citation: str,
            relevance: float = 1.0, confidence: float = 1.0,
            kind: str = "evidence", when: str | None = None) -> None:
        facts.append(Fact(text, provenance, weight, when, citation,
                          relevance, confidence, kind))

    title = chosen["title"]
    add(f"{title} is an approved metric: {chosen['description']} "
        f"Unit: {chosen['unit'] or 'not stated'}.",
        "measured", 10, f"metric_definition:{chosen['name']}",
        relevance=10, confidence=1, kind="definition")
    add(f"The approved calculation is {chosen['value_expr']} over the "
        f"governed base query.",
        "measured", 7, f"metric_sql:{chosen['name']}",
        relevance=8, confidence=1, kind="lineage")
    if chosen.get("caveats"):
        add(f"Caveat: {chosen['caveats']}", "derived", 6,
            f"metric_caveat:{chosen['name']}", relevance=8, confidence=0.9,
            kind="caveat")

    comparison = None
    if current_from and current_to:
        try:
            comparison = metric_defs.evaluate_definition(
                graph, chosen["name"], source, filters=filters,
                time_from=current_from, time_to=current_to,
                compare_previous=True)
        except Exception:                          # noqa: BLE001
            comparison = None
    if comparison and comparison.get("rows"):
        current = comparison["rows"][0][0]
        prior = comparison.get("prior")
        add(f"{title} was {_fmt(current, chosen)} for {period_label}"
            + (f" with filters {filters}" if filters else "") + ".",
            "measured", 10, f"metric:{chosen['name']}:current",
            relevance=10, confidence=1, kind="metric")
        if prior is not None:
            add(f"The prior period was {_fmt(prior, chosen)}.",
                "measured", 9, f"metric:{chosen['name']}:prior",
                relevance=9, confidence=1, kind="metric")
            change = comparison.get("change")
            pct = comparison.get("change_pct")
            add(f"The change was {_fmt(change, chosen)}"
                + (f" ({pct:+.2f}%)" if pct is not None else "") + ".",
                "derived", 10, f"metric:{chosen['name']}:change",
                relevance=10, confidence=0.95, kind="change")
        # Segment contributions, if the metric declares a useful dimension.
        if dimension:
            try:
                grouped = metric_defs.evaluate_definition(
                    graph, chosen["name"], source, filters=filters,
                    group_by=dimension, time_from=current_from,
                    time_to=current_to, compare_previous=True)
                prior_map = {str(row[0]): row[1]
                             for row in grouped.get("prior_rows") or []}
                change_total = comparison.get("change")
                rows = []
                for row in grouped["rows"]:
                    key, value = str(row[0]), row[1]
                    old = prior_map.get(key)
                    delta = (value - old if value is not None and old is not None
                             else None)
                    rows.append((key, value, old, delta))
                rows.sort(key=lambda item: (item[3] is None, item[3] or 0))
                chart_breakdown = {"dimension": dimension, "rows": [
                    {"key": key, "current": value, "prior": old, "change": delta}
                    for key, value, old, delta in rows[:12]]}
                for key, value, old, delta in rows[:4]:
                    if delta is None:
                        continue
                    share = (delta / change_total * 100
                             if change_total not in (None, 0) else None)
                    add(f"{dimension} {key}: {_fmt(old, chosen)} → "
                        f"{_fmt(value, chosen)}, change {_fmt(delta, chosen)}"
                        + (f" ({share:+.1f}% of the total change)"
                           if share is not None else "") + ".",
                        "measured", 8, f"metric:{chosen['name']}:{dimension}:{key}",
                        relevance=9, confidence=0.95, kind="contribution",
                        when=current_to)
            except Exception:                      # noqa: BLE001
                pass

    # Trend, limited to the recent points that fit the context budget.
    if current_from and current_to and chosen.get("time_column"):
        try:
            trend = metric_defs.metric_insights(
                graph, chosen["name"], source, filters=filters,
                time_from=prior_from or current_from, time_to=current_to,
                group_by=None, grain="month")
            chart_trend = [{"period": str(point["period"]), "value": point.get("value")}
                           for point in trend.get("trend") or []]
            for point in (trend.get("trend") or [])[-6:]:
                if point.get("value") is None:
                    continue
                add(f"{title} in {point['period'][:7]}: "
                    f"{_fmt(point['value'], chosen)}.",
                    "measured", 4, f"metric:{chosen['name']}:trend:{point['period']}",
                    relevance=5, confidence=0.9, kind="trend")
        except Exception:                          # noqa: BLE001
            pass

    # Volume is a different governed metric, not a row-count guess.
    volume = metric_defs.get_definition(graph, "order_volume", source)
    if volume and current_from and current_to:
        try:
            vol = metric_defs.evaluate_definition(
                graph, "order_volume", source, filters=filters,
                time_from=current_from, time_to=current_to,
                compare_previous=True)
            if vol.get("rows"):
                add(f"Order volume was {_fmt(vol['rows'][0][0], volume)}"
                    + (f", prior {_fmt(vol.get('prior'), volume)}"
                       if vol.get("prior") is not None else "")
                    + (f" ({vol.get('change_pct'):+.1f}%)"
                       if vol.get("change_pct") is not None else "") + ".",
                    "measured", 8, "metric:order_volume:current",
                    relevance=8, confidence=0.95, kind="volume")
        except Exception:                          # noqa: BLE001
            pass

    # Schema relationships behind the metric.
    try:
        relations = graph.sql(
            "SELECT r.name, r.domain, r.range, r.provenance, count(e.src)"
            " FROM relations r LEFT JOIN edges e ON e.rel = r.code"
            " AND e.source_id = r.source_id"
            " WHERE r.source_id = ? GROUP BY r.name, r.domain, r.range,"
            " r.provenance ORDER BY 5 DESC LIMIT 3", [source])
        for name, domain, target, provenance, count in relations:
            add(f"{domain} → {target} via {name} ({provenance}); "
                f"{int(count or 0):,} links in the source.",
                "derived", 4, f"relationship:{name}",
                relevance=5, confidence=0.9, kind="relationship")
    except Exception:                              # noqa: BLE001
        pass

    # A small source-row sample keeps the pack auditable.
    try:
        table = "orders" if any(t.name == "orders" for t in schema.tables) \
            else (schema.tables[0].name if schema.tables else "")
        if table:
            columns, sample = source_rows(graph, schema, table, limit=1,
                                          source=source)
            if sample:
                first = sample[0]
                shown = ", ".join(
                    f"{column}={value}"
                    for column, value in list(zip(columns, first))[:6])
                add(f"Sample source row from {table}: {shown}.",
                    "measured", 9, f"row:{table}:1",
                    relevance=9, confidence=1, kind="source_row")
    except Exception as exc:                       # noqa: BLE001
        log.warning("question context: source row sample failed: %s", exc)

    # Health and remaining review work are part of trust, not decoration.
    try:
        health = metric_defs.metric_health(graph, chosen["name"], source)
        add(f"Metric health is {health['score']}/100: "
            + "; ".join(check["name"] for check in health["checks"] if check["passed"])
            + ".", "derived", 3, f"metric_health:{chosen['name']}",
            relevance=3, confidence=0.95, kind="quality")
    except Exception:                              # noqa: BLE001
        pass
    try:
        from review import store as review_store
        pending = (review_store.pending(graph, kind="semantic", source=source) +
                   review_store.pending(graph, kind="context", source=source))
        if pending:
            add(f"{len(pending)} semantic/context proposal(s) remain in review.",
                "derived", 2, "review:pending", relevance=2,
                confidence=1, kind="review")
    except Exception:                              # noqa: BLE001
        pass

    kept, dropped = pack(facts, budget_chars)
    rendered = render(kept)
    available = {"definition", "metric", "change", "contribution", "volume",
                 "relationship", "source_row", "quality"}
    present = {fact.kind for fact in kept}
    coverage = round(100 * len(available & present) / len(available), 1)
    missing = sorted(available - present)
    top = [fact for fact in kept if fact.kind == "contribution"][:1]
    current_row = next((row for row in
                        (comparison["rows"] if comparison else [])), None)
    answer = (f"{title}: {_fmt(current_row[0], chosen) if current_row else 'not measured'}."
              if current_row else f"{title}: no comparable period was measured.")
    if comparison and comparison.get("change") is not None:
        answer += (f" Change {_fmt(comparison['change'], chosen)}"
                   f" ({comparison.get('change_pct'):+.2f}%)."
                   if comparison.get("change_pct") is not None else ".")
    if top:
        answer += f" {top[0].text}"
    return {
        "focus": {"type": "question", "source": source,
                  "question": question, "metric": chosen["name"],
                  "period": period_label, "filters": filters,
                  "dimension": dimension},
        "answer": answer,
        "facts": [{"text": fact.text, "provenance": fact.provenance,
                   "weight": fact.weight, "citation": fact.citation,
                   "as_of": fact.when, "relevance": fact.relevance,
                   "confidence": fact.confidence, "kind": fact.kind}
                  for fact in kept],
        "dropped": [{"text": fact.text, "provenance": fact.provenance,
                     "weight": fact.weight, "reason": fact.reason,
                     "kind": fact.kind} for fact in dropped],
        "sources": [source],
        "review_pending": sum(1 for fact in kept if fact.kind == "review"),
        "budget_chars": budget_chars,
        "chars": sum(len(fact.text) for fact in kept),
        "rendered": rendered,
        "metric": chosen,
        "filters": filters,
        "period": {"label": period_label, "from": current_from,
                   "to": current_to, "prior_from": prior_from},
        "coverage": {"score": coverage, "present": sorted(present),
                     "missing": missing},
        "answerable": answerable_verdict(
            chosen=chosen, coverage=coverage, missing=missing,
            has_current=bool(current_row),
            has_prior=bool(comparison and comparison.get("prior") is not None),
            question=question,
            candidates=[d for d in definitions if d.get("status") == "approved"]),
        "receipt": _receipt(kept, dropped, chosen),
        "charts": {"trend": chart_trend, "breakdown": chart_breakdown},
        "as_of": _now(),
        "latency_ms": 0.0,
    }


def _receipt(kept, dropped, chosen) -> dict:
    from agent.receipt import receipt_from_facts
    return receipt_from_facts(
        [{"kind": f.kind, "citation": f.citation} for f in kept],
        [{"kind": f.kind} for f in dropped],
        metric_title=chosen.get("title") or chosen.get("name"),
        metric_status=chosen.get("status"))


# Public names for the MCP layer (check_answerable reuses the same detection
# the context pack uses, so "answerable" and "packed" can never disagree).
detect_metric = _detect_metric
detect_filters = _detect_filters
