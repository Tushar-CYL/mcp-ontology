"""Which layers this server offers.

A team that wants only the Semantic layer runs Strata with
``STRATA_LAYERS=semantic`` (or ``run_server.py --layers semantic``): the web
app shows only that page, the other layers' API routes answer "switched off",
and agents over MCP see only that layer's tools. The ontology is always on -
every other layer is built from one (Strata's own, or yours imported as a
Strata Model) - and the others still use each other inside: Context reads
the graph and the certified metrics even when their pages are off.
"""

from __future__ import annotations

import os

LAYERS = ("ontology", "graph", "semantic", "context", "agents")
ALIASES = {"kg": "graph", "knowledge_graph": "graph", "knowledge-graph": "graph",
           "metrics": "semantic", "sem": "semantic", "ctx": "context", "agent": "agents",
           "onto": "ontology", "all": "all"}
# Which API prefixes and MCP tool groups belong to which layer.
# The agents' API stays on with the page off: agent keys for MCP live there.
ROUTES = {"graph": ("/api/kg/",), "semantic": ("/api/sem/",), "context": ("/api/ctx/",)}
TOOL_GROUPS = {"Ontology": "ontology", "Steward": "ontology", "General": "ontology",
               "Graph": "graph", "Semantic": "semantic", "Context": "context"}


def parse(text: str | None) -> tuple[str, ...]:
    """'semantic, context' -> ('ontology', 'semantic', 'context'). Empty means all."""
    words = [w.strip().lower() for w in str(text or "").replace(";", ",").split(",") if w.strip()]
    if not words:
        return LAYERS
    out = {"ontology"}
    for w in words:
        w = ALIASES.get(w, w)
        if w == "all":
            return LAYERS
        if w not in LAYERS:
            raise ValueError(f"unknown layer {w!r}: choose from {', '.join(LAYERS)}")
        out.add(w)
    return tuple(x for x in LAYERS if x in out)


def enabled() -> tuple[str, ...]:
    return parse(os.environ.get("STRATA_LAYERS"))


def is_on(layer: str) -> bool:
    return layer in enabled()


def route_layer(path: str) -> str | None:
    """The layer an API path belongs to (None: shared, always on)."""
    for layer, prefixes in ROUTES.items():
        if any(path.startswith(p) for p in prefixes):
            return layer
    return None


def tool_layer(tool: dict) -> str:
    """'[Semantic] ...' -> 'semantic'."""
    desc = str(tool.get("description") or "")
    group = desc[1:desc.index("]")] if desc.startswith("[") and "]" in desc else "General"
    return TOOL_GROUPS.get(group, "ontology")
