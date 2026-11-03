"""The layer receipt: which of the four layers an answer used, in plain words.

Example::

    Used: Ontology (Order) · Semantic (Revenue, approved) · Graph (Customer c1)
    · Context (5 cited facts, 3 dropped).

Vendors expose provenance as retrieval citations and builder-facing traces; a
layer-level receipt for non-experts is not a documented feature elsewhere
(docs/research/2026/REPORT.md). Every Strata answer carries one.
"""

from __future__ import annotations

LAYERS = ("ontology", "graph", "semantic", "context")
TITLES = {"ontology": "Ontology", "graph": "Graph", "semantic": "Semantic",
          "context": "Context"}

# Which layer a context-pack fact comes from.
_FACT_LAYER = {
    "definition": "semantic", "lineage": "semantic", "caveat": "semantic",
    "metric": "semantic", "change": "semantic", "contribution": "semantic",
    "trend": "semantic", "volume": "semantic", "quality": "semantic",
    "relationship": "ontology", "class": "ontology",
    "source_row": "graph", "entity": "graph", "neighbour": "graph",
}


def build_receipt(steps: list[dict]) -> dict:
    """Steps are ``{"layer": ..., "detail": ...}``; unknown layers are ignored."""
    details: dict[str, list[str]] = {layer: [] for layer in LAYERS}
    used: set[str] = set()
    for step in steps or []:
        layer = step.get("layer")
        if layer not in details:
            continue
        used.add(layer)
        detail = str(step.get("detail") or "").strip()
        if detail and detail not in details[layer]:
            details[layer].append(detail)
    layers = []
    parts = []
    for layer in LAYERS:
        if layer in used:
            summary = "; ".join(details[layer]) or "used"
            parts.append(f"{TITLES[layer]} ({summary})")
        else:
            summary = "not needed"
        layers.append({"layer": layer, "used": layer in used,
                       "summary": summary})
    text = "Used: " + (" · ".join(parts) if parts else "no layers") + "."
    return {"layers": layers, "text": text}


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def receipt_from_facts(kept: list[dict], dropped: list[dict],
                       metric_title: str | None = None,
                       metric_status: str | None = None) -> dict:
    """A receipt for a context pack, from the kinds of facts it kept."""
    counts = {"relationship": 0, "source_row": 0}
    semantic = False
    for fact in kept or []:
        kind = fact.get("kind")
        layer = _FACT_LAYER.get(kind)
        if layer == "semantic":
            semantic = True
        if kind in counts:
            counts[kind] += 1
    steps = []
    if semantic and metric_title:
        status = f" ({metric_status})" if metric_status else ""
        steps.append({"layer": "semantic", "detail": f"{metric_title}{status}"})
    elif semantic:
        steps.append({"layer": "semantic", "detail": "metric evidence"})
    if counts["relationship"]:
        steps.append({"layer": "ontology",
                      "detail": _plural(counts["relationship"], "relationship")})
    if counts["source_row"]:
        steps.append({"layer": "graph",
                      "detail": _plural(counts["source_row"], "source row")})
    pack = f"{len(kept or [])} cited facts"
    if dropped:
        pack += f", {len(dropped)} dropped"
    steps.append({"layer": "context", "detail": pack})
    return build_receipt(steps)
