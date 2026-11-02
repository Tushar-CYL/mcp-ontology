"""Safe, user-defined analysis skills over the approved tool surface.

A custom skill is a reusable recipe, not code: choose a kind of analysis, an
approved metric and an optional declared dimension. The runtime turns it into
real tool calls, so every output still has a citation and the same guardrails
as a built-in skill.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from semantic import definitions as metric_defs

BUILTIN_SKILLS = [
    {"id": "explain_metric", "label": "Explain a metric",
     "description": "Definition, SQL and current value from the semantic layer.",
     "builtin": True},
    {"id": "compare_periods", "label": "Compare periods",
     "description": "Current versus prior period, with the change and inputs.",
     "builtin": True},
    {"id": "breakdown_by", "label": "Break down a metric",
     "description": "Which dimension values moved the metric, and by how much.",
     "builtin": True},
    {"id": "graph_context", "label": "Graph context",
     "description": "Entities and relationships around the question.",
     "builtin": True},
    {"id": "evidence_search", "label": "Evidence search",
     "description": "The cited facts, source rows and caveats.",
     "builtin": True},
]

KINDS = ("metric_focus", "comparison", "breakdown")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(source: str, name: str) -> str:
    digest = hashlib.sha1(f"{source}|{name}|custom".encode()).hexdigest()
    return f"skill_{digest[:12]}"


def _row(row) -> dict:
    keys = ("id", "name", "description", "source", "kind", "metric",
            "dimension", "owner", "status", "created_at")
    item = dict(zip(keys, row))
    item["builtin"] = False
    return item


def list_custom_skills(graph, source: str | None = None) -> list[dict]:
    if source:
        rows = graph.sql(
            "SELECT id, name, description, source_id, kind, metric, dimension,"
            " owner, status, created_at FROM skill_definitions"
            " WHERE source_id = ? AND status = 'active' ORDER BY name",
            [source])
    else:
        rows = graph.sql(
            "SELECT id, name, description, source_id, kind, metric, dimension,"
            " owner, status, created_at FROM skill_definitions"
            " WHERE status = 'active' ORDER BY source_id, name")
    return [_row(row) for row in rows]


def get_custom_skill(graph, skill_id: str) -> dict | None:
    rows = graph.sql(
        "SELECT id, name, description, source_id, kind, metric, dimension,"
        " owner, status, created_at FROM skill_definitions WHERE id = ?",
        [str(skill_id or "")])
    return _row(rows[0]) if rows else None


def list_all_skills(graph, source: str | None = None) -> list[dict]:
    return [dict(skill) for skill in BUILTIN_SKILLS] + list_custom_skills(graph, source)


def create_custom_skill(graph, payload: dict) -> dict:
    """Validate and persist a custom recipe. Raises ValueError on bad input."""
    source = str(payload.get("source_id") or "").strip()
    if not source:
        raise ValueError("a custom skill needs a source")
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 120:
        raise ValueError("a custom skill needs a name of 1-120 characters")
    kind = str(payload.get("kind") or "metric_focus").strip()
    if kind not in KINDS:
        raise ValueError(f"unknown skill kind {kind!r}; choose one of "
                         f"{', '.join(KINDS)}")
    metric = str(payload.get("metric") or "").strip()
    definition = metric_defs.get_definition(graph, metric, source) if metric else None
    if definition is None or definition.get("status") != "approved":
        raise ValueError(f"metric {metric!r} is not approved for source {source!r}")
    dimension = str(payload.get("dimension") or "").strip()
    if dimension and dimension not in set(definition.get("dimensions") or []):
        raise ValueError(
            f"metric {metric!r} has no declared dimension {dimension!r}")
    if kind in ("comparison", "breakdown") and not dimension:
        raise ValueError(f"a {kind} skill needs a declared dimension")
    skill_id = _id(source, name)
    description = str(payload.get("description") or "").strip()[:1000]
    owner = str(payload.get("owner") or "workspace").strip()[:120]
    if get_custom_skill(graph, skill_id) is not None:
        raise ValueError(f"a custom skill named {name!r} already exists")
    with graph.lock:
        graph.con.execute(
            "INSERT INTO skill_definitions(id, name, description, source_id,"
            " kind, metric, dimension, owner, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,'active',?)",
            [skill_id, name, description, source, kind, metric, dimension,
             owner, _now()])
    return get_custom_skill(graph, skill_id) or {}


def delete_custom_skill(graph, skill_id: str) -> None:
    with graph.lock:
        graph.con.execute(
            "DELETE FROM skill_definitions WHERE id = ?", [str(skill_id or "")])
