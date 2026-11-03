"""Run an agent by its preset: one orchestrator, six agent types.

Every run returns the same envelope shape so the UI and the API never need to
know which preset answered:

* ``answer``: headline and summary in plain language;
* ``answerable``: yes / partial / no, with a reason (and the nearest metric
  when the answer is no) - checked BEFORE anything is computed;
* ``receipt``: which of the four layers were used, in plain words;
* ``evidence`` and ``trace``: what was looked at, step by step.

The Insight Analyst delegates to the existing runtime (`AgentRuntime`), after
making sure the metric the question names is the one it answers about.
"""

from __future__ import annotations

import re
import time
from datetime import date

from agent.presets import get_preset
from agent.receipt import build_receipt
from context import question as qctx
from semantic import definitions as metric_defs

MAX_LINKS_PER_RELATION = 25
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


# ----------------------------------------------------------------- helpers
def _envelope(agent: dict, preset: str, question: str, summary: str,
              verdict: dict, steps: list[dict], evidence: dict,
              started: float, confidence: str = "high") -> dict:
    headline = summary.split(". ")[0].rstrip(".") + "." if summary else ""
    return {
        "agent_id": agent["id"], "preset": preset, "question": question,
        "answer": {"headline": headline, "summary": summary,
                   "confidence": confidence if verdict["verdict"] == "yes"
                   else ("medium" if verdict["verdict"] == "partial" else "low")},
        "answerable": verdict,
        "receipt": build_receipt(steps),
        "evidence": {"facts": [], "trace": steps, **evidence},
        "trace": steps,
        "guardrails": {"passed": verdict["verdict"] != "no",
                       "notes": [] if verdict["verdict"] != "no"
                       else [verdict["reason"]]},
        "sources": [str(agent.get("source_id") or "")],
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _refuse(agent, preset, question, reason, started, nearest=None,
            steps=None, evidence=None) -> dict:
    verdict = {"verdict": "no", "reason": reason, "nearest_metric": nearest}
    summary = f"I cannot answer this: {reason}."
    if nearest:
        summary += f" Try asking about {nearest}."
    return _envelope(agent, preset, question, summary, verdict, steps or [],
                     evidence or {}, started)


def _yes(reason: str) -> dict:
    return {"verdict": "yes", "reason": reason, "nearest_metric": None}


def _word_in(text: str, word: str) -> bool:
    word = word.lower()
    variants = {word, word + "s", word + "es"}
    if word.endswith("y"):
        variants.add(word[:-1] + "ies")
    return any(re.search(r"(?<![a-z0-9])" + re.escape(v) + r"(?![a-z0-9])", text)
               for v in variants)


def _find_class(onto, question: str):
    text = question.lower()
    # Longest names first so "OrderLine" is preferred over "Order" when named.
    for klass in sorted(onto.classes.values(), key=lambda c: -len(c.name)):
        spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", klass.name).lower()
        if _word_in(text, klass.name.lower()) or _word_in(text, spaced) \
                or _word_in(text, klass.table.lower().rstrip("s")):
            return klass
    return None


def _scope_defs(graph, agent, source):
    definitions = metric_defs.list_definitions(graph, source)
    allowed = [str(m) for m in agent.get("metrics") or []]
    return definitions, allowed


def _check_metric(definitions, allowed, question):
    """(definition, verdict-or-None). A verdict means: refuse."""
    found = qctx.detect_metric(definitions, question)
    approved_in_scope = [d for d in definitions
                         if d.get("status") == "approved" and d["name"] in allowed]
    if found is None:
        return None, qctx.answerable_verdict(
            chosen=None, coverage=0, missing=[], has_current=False,
            has_prior=False, question=question, candidates=approved_in_scope)
    if found.get("status") != "approved" or found["name"] not in allowed:
        return found, qctx.answerable_verdict(
            chosen=found, coverage=0, missing=[], has_current=False,
            has_prior=False, allowed=allowed)
    return found, None


def _window(graph, definition, question):
    """(time_from, time_to, label): the month the question names, else the
    latest full month in the data. Shared with the context pack."""
    _, current_from, current_to, label = qctx.question_window(
        graph, definition, question)
    return current_from or None, current_to or None, label


def _explicit_dimension(definition, question):
    text = question.lower()
    for dim in definition.get("dimensions") or []:
        if re.search(r"\b(?:by|per|across)\s+" + re.escape(dim.lower()) + r"s?\b", text):
            return dim
    return None


# ----------------------------------------------------------------- presets
def _data_guide(layer, agent, question, started):
    source = agent["source_id"]
    bundle = layer._bundle(source)
    onto = layer.ontology(source)
    klass = _find_class(bundle.onto, question)
    steps = []
    if klass is None:
        entities = ", ".join(f"{c['name']} ({c['table']})" for c in onto["classes"])
        summary = (f"This source has {len(onto['classes'])} kinds of thing: "
                   f"{entities}, connected by {len(onto['relations'])} links. "
                   "Ask about any of them, for example 'What is an "
                   f"{onto['classes'][0]['name']}?'")
        steps.append({"layer": "ontology", "tool": "list_entities",
                      "detail": f"{len(onto['classes'])} kinds of thing, "
                                f"{len(onto['relations'])} links"})
        return _envelope(agent, "data_guide", question, summary,
                         _yes("the ontology describes this source"), steps,
                         {"entities": onto["classes"],
                          "links": onto["relations"]}, started)
    from api.mcp_server import call_tool
    table = call_tool(layer, "describe_table",
                      {"table": klass.table, "source": source})
    links = [r for r in onto["relations"]
             if klass.name in (r["domain"], r["range"])]
    allowed = set(agent.get("metrics") or [])
    metrics = [m for m in table["metrics"] if not allowed or m in allowed] \
        or table["metrics"]
    parts = [f"An {klass.name} is a kind of thing stored in table "
             f"{klass.table}, identified by {klass.key}"]
    count = layer.graph.count_class(klass.name, source)
    parts.append(f"There are {count:,} of them"
                 + (f", dated by {klass.time_column}" if klass.time_column else ""))
    if links:
        parts.append("It links to " + "; ".join(
            f"{r['range'] if r['domain'] == klass.name else r['domain']} "
            f"via {r['name']} ({r['provenance']})" for r in links))
    if metrics:
        parts.append("Approved metrics built on it: " + ", ".join(metrics))
    pii = [c["name"] for c in table["columns"] if c["pii"]]
    if pii:
        parts.append("Personal-data columns (hidden from agents): " + ", ".join(pii))
    steps.append({"layer": "ontology", "tool": "describe_table",
                  "detail": f"{klass.name} ({klass.table})"})
    if metrics:
        steps.append({"layer": "semantic", "tool": "list_metrics",
                      "detail": f"{len(metrics)} metric(s) on {klass.table}"})
    return _envelope(agent, "data_guide", question, ". ".join(parts) + ".",
                     _yes(f"the ontology describes {klass.name}"), steps,
                     {"entity": klass.name, "table": table,
                      "links": links, "metrics": metrics}, started)


def _metric(layer, agent, question, started):
    graph, source = layer.graph, agent["source_id"]
    definitions, allowed = _scope_defs(graph, agent, source)
    definition, refusal = _check_metric(definitions, allowed, question)
    if refusal:
        return _refuse(agent, "metric", question, refusal["reason"], started,
                       refusal.get("nearest_metric"))
    filters = qctx.detect_filters(graph, definition, question)
    time_from, time_to, label = _window(graph, definition, question)
    result = metric_defs.evaluate_definition(
        graph, definition["name"], source, filters=filters,
        time_from=time_from, time_to=time_to, compare_previous=True)
    current = result["rows"][0][0] if result.get("rows") else None
    prior, change, pct = (result.get("prior"), result.get("change"),
                          result.get("change_pct"))
    fmt = lambda v: qctx._fmt(v, definition)            # noqa: E731
    steps = [{"layer": "semantic", "tool": "evaluate_metric",
              "detail": f"{definition['title']} ({definition['status']})"}]
    if current is None:
        return _refuse(agent, "metric", question,
                       f"{definition['name']!r} has no data for {label}",
                       started, steps=steps)
    where = (" for " + ", ".join(f"{k} = {v}" for k, v in filters.items())
             if filters else "")
    summary = f"{definition['title']} for {label}{where} was {fmt(current)}"
    if prior is not None:
        summary += (f", against {fmt(prior)} the period before (change "
                    f"{fmt(change)}" + (f", {pct:+.2f}%" if pct is not None else "")
                    + ")")
        steps.append({"layer": "semantic", "tool": "evaluate_metric",
                      "detail": "compared with the previous period"})
    breakdown = []
    dimension = _explicit_dimension(definition, question)
    if dimension:
        grouped = metric_defs.evaluate_definition(
            graph, definition["name"], source, filters=filters,
            group_by=dimension, time_from=time_from, time_to=time_to)
        breakdown = [{"key": str(r[0]), "value": r[1]} for r in grouped["rows"]]
        summary += ". By " + dimension + ": " + ", ".join(
            f"{b['key']} {fmt(b['value'])}" for b in breakdown)
        steps.append({"layer": "semantic", "tool": "evaluate_metric",
                      "detail": f"split by {dimension}"})
    verdict = (_yes(f"approved metric {definition['name']!r} measured and compared")
               if prior is not None else
               {"verdict": "partial", "nearest_metric": None,
                "reason": "measured, but there is no prior period to compare"})
    return _envelope(agent, "metric", question, summary + ".", verdict, steps,
                     {"metric": {"name": definition["name"],
                                 "title": definition["title"],
                                 "current": current, "prior": prior,
                                 "change": change, "change_pct": pct,
                                 "filters": filters, "period": label},
                      "sql": result.get("sql", ""), "breakdown": breakdown},
                     started)


def _entity(layer, agent, question, started):
    graph, source = layer.graph, agent["source_id"]
    bundle = layer._bundle(source)
    kinds = ", ".join(sorted(bundle.onto.classes))
    klass = _find_class(bundle.onto, question)
    if klass is None:
        return _refuse(agent, "entity", question,
                       f"name the kind of thing and its id, e.g. "
                       f"'{sorted(bundle.onto.classes)[0]} 1'; kinds here: {kinds}",
                       started)
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", klass.name)
    names = "|".join(re.escape(n) for n in {klass.name, spaced, klass.table})
    match = re.search(r"(?:" + names + r")s?\s+['\"#]?([\w\-]+)", question, re.I)
    if not match:
        return _refuse(agent, "entity", question,
                       f"which {klass.name}? give its id, e.g. "
                       f"'{klass.name} 1'", started)
    key = match.group(1)
    if graph.node_id(klass.name, key, source) is None:
        return _refuse(agent, "entity", question,
                       f"there is no {klass.name} {key!r} in source {source!r}",
                       started)
    neighbours, groups = [], []
    for rel in bundle.onto.relations.values():
        if rel.domain == klass.name:
            found = graph.neighbours(klass.name, key, rel.name, source=source)
            total, other = len(found), rel.range
        elif rel.range == klass.name:
            found = graph.inbound(klass.name, key, rel.name, source=source,
                                  limit=MAX_LINKS_PER_RELATION)
            total = graph.inbound_count(klass.name, key, rel.name, source=source)
            other = rel.domain
        else:
            continue
        keys = sorted(found)[:MAX_LINKS_PER_RELATION]
        for target in keys:
            neighbours.append({"relation": rel.name, "target_class": other,
                               "target_key": target,
                               "provenance": rel.provenance})
        if total:
            more = f" and {total - len(keys)} more" if total > len(keys) else ""
            groups.append(f"{total} {other}(s) via {rel.name} "
                          f"({', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}{more})")
    pack = layer.context(entity=(source, klass.name, key), budget_chars=1200)
    facts = pack.get("facts") or []
    summary = f"{klass.name} {key}: " + (
        "linked to " + "; ".join(groups) if groups else "no links recorded")
    if facts:
        summary += ". " + " ".join(f["text"] for f in facts[:3])
    steps = [{"layer": "ontology", "tool": "describe_table", "detail": klass.name},
             {"layer": "graph", "tool": "graph_neighbours",
              "detail": f"{klass.name} {key}, {len(neighbours)} links"},
             {"layer": "context", "tool": "get_entity_context",
              "detail": f"{len(facts)} cited facts"}]
    return _envelope(agent, "entity", question, summary,
                     _yes(f"{klass.name} {key} exists in the graph"), steps,
                     {"entity": {"class": klass.name, "key": key},
                      "neighbours": neighbours, "facts": facts}, started)


def _trust(layer, agent, question, started):
    graph, source = layer.graph, agent["source_id"]
    definitions, allowed = _scope_defs(graph, agent, source)
    definition, refusal = _check_metric(definitions, allowed, question)
    if refusal:
        return _refuse(agent, "trust", question, refusal["reason"], started,
                       refusal.get("nearest_metric"))
    checks = []

    def check(name, passed, detail, critical=False):
        checks.append({"name": name, "passed": bool(passed), "detail": detail,
                       "critical": critical})

    check("Metric approved", definition["status"] == "approved",
          f"status {definition['status']}, owner {definition.get('owner') or 'none'}",
          critical=True)
    health = metric_defs.metric_health(graph, definition["name"], source)
    check("Metric health", health["score"] >= 90,
          f"{health['score']}/100: " + "; ".join(
              c["name"] for c in health["checks"] if not c["passed"]) if
          health["score"] < 100 else f"{health['score']}/100, every check passed",
          critical=True)
    try:
        cert = layer.readiness(source)
        check("Source certification", cert["status"] != "fail",
              f"{cert['status']}" + (" (cached)" if cert.get("cached") else ""))
    except Exception as exc:                       # noqa: BLE001 - reported
        check("Source certification", False, f"could not run: {exc}")
    check("Caveats", True, definition.get("caveats") or "none recorded")
    pack = qctx.build_question_context(
        graph, [(b.source, b.schema, b.onto) for b in layer.bundles
                if b.source == source],
        definition["title"], source=source, metric=definition["name"])
    coverage = pack.get("coverage", {}).get("score", 0)
    check("Evidence coverage", coverage >= qctx.PARTIAL_COVERAGE,
          f"{coverage:.0f}% of a full evidence pack")
    failed = [c for c in checks if not c["passed"]]
    passed = len(checks) - len(failed)
    if not failed:
        lead = "Yes"
    elif any(c["critical"] for c in failed):
        lead = "No"
    else:
        lead = "Mostly"
    summary = (f"{lead}: {definition['title']} passes {passed} of {len(checks)} "
               "trust checks" + ("" if not failed else "; failed: " + ", ".join(
                   f"{c['name']} ({c['detail']})" for c in failed)))
    if definition.get("caveats"):
        summary += f". Caveat: {definition['caveats']}"
    steps = [{"layer": "semantic", "tool": "get_metric",
              "detail": f"{definition['title']} health {health['score']}/100"},
             {"layer": "ontology", "tool": "check_readiness",
              "detail": "source certification"},
             {"layer": "context", "tool": "check_answerable",
              "detail": f"coverage {coverage:.0f}%"}]
    return _envelope(agent, "trust", question, summary + ".",
                     _yes(f"trust checks ran for {definition['name']!r}"), steps,
                     {"metric": definition["name"], "checks": checks}, started)


def _steward(layer, agent, question, started):
    from semantic import feedback
    try:
        item = feedback.propose(layer.graph, agent["source_id"], question,
                                agent_id=agent["id"],
                                submitted_by=f"agent:{agent['id']}")
    except ValueError as exc:
        return _refuse(agent, "steward", question, str(exc), started)
    proposal = item["proposal"]
    if proposal["type"] == "synonym":
        what = (f"synonym {proposal['synonym']!r} for metric "
                f"{proposal['metric']}")
        step = {"layer": "semantic", "tool": "propose_change",
                "detail": f"proposed {what}"}
    else:
        what = f"note: {proposal['text']}"
        step = {"layer": "ontology", "tool": "propose_change",
                "detail": "proposed a change for review"}
    summary = (f"Filed for approval: {what}. Nothing changes until a person "
               "approves it.")
    return _envelope(agent, "steward", question, summary,
                     _yes("the proposal was filed for review"), [step],
                     {"proposal": item}, started)


def _insight(layer, runtime, agent, question, persist, started):
    graph, source = layer.graph, agent["source_id"]
    definitions, allowed = _scope_defs(graph, agent, source)
    found = qctx.detect_metric(definitions, question)
    verdict = None
    if found is not None and (found.get("status") != "approved"
                              or found["name"] not in allowed):
        reason = qctx.answerable_verdict(
            chosen=found, coverage=0, missing=[], has_current=False,
            has_prior=False, allowed=allowed)["reason"]
        envelope = runtime._refusal(agent, question, reason, [], started)
        envelope.update({"preset": "insight",
                         "answerable": {"verdict": "no", "reason": reason,
                                        "nearest_metric": None},
                         "receipt": build_receipt([])})
        if persist:
            runtime._persist(agent, question, envelope, status="refused")
        return envelope
    run_agent = dict(agent)
    if found is not None:
        # Answer about the metric the question names, not the first attached.
        run_agent["metrics"] = [found["name"]] + [m for m in allowed
                                                  if m != found["name"]]
    else:
        assumed = allowed[0] if allowed else None
        verdict = {"verdict": "partial", "nearest_metric": None,
                   "reason": "the question names no metric"
                             + (f"; assumed {assumed!r}" if assumed else "")}
    envelope = runtime._safe_run(run_agent, question, persist=persist)
    evidence = envelope.get("evidence") or {}
    refused = not envelope.get("guardrails", {}).get("passed", True) and \
        "cannot answer" in str((envelope.get("answer") or {}).get("headline", ""))
    if refused:
        verdict = {"verdict": "no", "nearest_metric": None,
                   "reason": str((envelope.get("answer") or {}).get("cause", ""))}
    elif verdict is None:
        verdict = _yes("approved metric measured with cited evidence")
    facts = evidence.get("facts") or []
    steps = []
    metric_name = run_agent["metrics"][0] if run_agent.get("metrics") else None
    if metric_name and not refused:
        steps.append({"layer": "semantic", "tool": "evaluate_metric",
                      "detail": f"{metric_name} (approved)"})
    if evidence.get("relationships"):
        steps.append({"layer": "ontology", "tool": "describe_table",
                      "detail": f"{len(evidence['relationships'])} relationship(s)"})
    if evidence.get("source_records"):
        steps.append({"layer": "graph", "tool": "source_rows",
                      "detail": f"{len(evidence['source_records'])} source record(s)"})
    if facts:
        steps.append({"layer": "context", "tool": "get_context",
                      "detail": f"{len(facts)} cited facts"})
    envelope.update({"preset": "insight", "answerable": verdict,
                     "receipt": build_receipt(steps)})
    return envelope


# -------------------------------------------------------------------- run
_SIMPLE = {"data_guide": _data_guide, "metric": _metric, "entity": _entity,
           "trust": _trust, "steward": _steward}


def run(layer, runtime, agent: dict, question: str,
        persist: bool = False) -> dict:
    started = time.perf_counter()
    preset = get_preset(agent.get("preset"))["id"]
    question = str(question or "").strip()
    if preset == "insight":
        return _insight(layer, runtime, agent, question, persist, started)
    if not question:
        return _refuse(agent, preset, question, "the question is empty", started)
    envelope = _SIMPLE[preset](layer, agent, question, started)
    if persist:
        status = "completed" if envelope["answerable"]["verdict"] != "no" else "refused"
        runtime._persist(agent, question, envelope, status=status)
    return envelope
