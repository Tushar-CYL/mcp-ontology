"""Suggested questions, generated from the connected dataset itself.

The Context page used to start every source with the same revenue question.
A question only helps if this dataset can answer it, so suggestions are built
from what Strata found in THIS source: its metrics (approved first), their
dimensions, the latest month that has data, and real entity keys. Each
suggestion names the agent type best suited to it.
"""

from __future__ import annotations

from context import question as qctx
from semantic import definitions as metric_defs
from semantic.autopilot import _human


def _pick_metrics(definitions: list[dict]) -> list[dict]:
    """Dated metrics with dimensions first, then any dated, then the rest."""
    def rank(d):
        return (not d.get("time_column"), not d.get("dimensions"),
                d.get("format") != "integer", d["name"])
    return sorted(definitions, key=rank)


def suggest_questions(graph, layer, source: str, limit: int = 7) -> dict:
    definitions = metric_defs.list_definitions(graph, source)
    approved = [d for d in definitions if d.get("status") == "approved"]
    pool = approved or [d for d in definitions if d.get("status") == "draft"]
    note = "" if approved else (
        "These questions use proposed metrics. Approve them in 3 Semantic so "
        "agents can answer; until then the answer will say they are not "
        "approved." if pool else
        "No metrics yet for this source. Approve or define metrics in 3 Semantic.")
    questions: list[dict] = []

    def add(text: str, preset: str, layer_name: str) -> None:
        if text not in {q["text"] for q in questions}:
            questions.append({"text": text, "preset": preset, "layer": layer_name})

    metrics = _pick_metrics(pool)
    if metrics:
        main = metrics[0]
        title = main["title"].lower() if main["title"][:1].isupper() and \
            main["title"].split()[0].lower() == "number" else main["title"]
        month = ""
        try:
            _, _, _, label = qctx._latest_window(graph, main)
            month = qctx.month_label(label) if label else ""
        except Exception:                          # noqa: BLE001 - undated data
            month = ""
        when = f" in {month}" if month else ""
        add(f"How did the {title} change{when}?", "insight", "context")
        dims = main.get("dimensions") or []
        if dims:
            # Plain words for the person; the agent maps them back to the column.
            label = _human(dims[0])
            add(f"Which {label} drove the change in the {title}{when}?",
                "insight", "context")
            add(f"{main['title']} by {dims[0].lower()}{when}", "metric", "semantic")
        for other in metrics[1:3]:
            add(f"What was the {other['title'][:1].lower() + other['title'][1:]}{when}?",
                "metric", "semantic")
        add(f"Can I trust the {title}?", "trust", "semantic")

    # One real entity, so "tell me about ..." points at a record that exists.
    for bundle in layer.bundles:
        if bundle.source != source:
            continue
        for klass in sorted(bundle.onto.classes.values(),
                            key=lambda c: -graph.count_class(c.name, source)):
            if klass.key_is_synthetic:
                continue
            keys = sorted(graph.keys_of(klass.name, limit=1, source=source))
            if keys:
                add(f"Tell me about {klass.name} {keys[0]}", "entity", "graph")
                add(f"What is a {klass.name}?", "data_guide", "ontology")
                break
    return {"source": source, "questions": questions[:limit], "note": note}
