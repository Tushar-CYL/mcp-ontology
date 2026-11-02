"""Per-layer certification before an agent is built on top of the data.

The checks are deliberately visible and boring: counts, keys, dangling edges,
an approved metric that actually evaluates, and a context pack that cites its
facts. A layer can warn (usable with caveats) or fail (an agent should not be
published on it).
"""

from __future__ import annotations

from datetime import datetime, timezone

from semantic import definitions as metric_defs


def _check(name: str, passed: bool, detail: str, severity: str = "error") -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail,
            "severity": severity if not passed else "ok"}


def certify_source(layer, source: str) -> dict:
    """Run the four layer checks against one loaded source."""
    bundles = [bundle for bundle in layer.bundles if bundle.source == source]
    if not bundles:
        raise KeyError(f"source {source!r} is not loaded")
    bundle = bundles[0]
    schema, onto = bundle.schema, bundle.onto
    graph = layer.graph
    layers: list[dict] = []

    # ---------------------------------------------------------- ontology
    classes = list(onto.classes.values())
    ontology_checks = [
        _check("Classes discovered", len(classes) > 0,
               f"{len(classes)} classes from {len(schema.tables)} tables"),
        _check("Every class has an identity", all(
            getattr(item, "key", None) for item in classes),
            "Every class must have a usable key or a documented synthetic key"),
        _check("Dates are available for time-aware answers",
               sum(1 for item in classes if getattr(item, "time_column", None)) > 0,
               f"{sum(1 for item in classes if getattr(item, 'time_column', None))}"
               " classes carry a time column", severity="warning"),
    ]
    relations = list(onto.relations.values())
    ontology_checks.append(_check(
        "Relationships are labelled",
        all(getattr(item, "provenance", None) for item in relations),
        f"{len(relations)} relationships; every one carries provenance"))
    layers.append(_layer("Ontology", ontology_checks))

    # ------------------------------------------------------------- graph
    nodes = graph.one("SELECT count(*) FROM nodes WHERE source_id = ?",
                      [source]) or 0
    edges = graph.one("SELECT count(*) FROM edges WHERE source_id = ?",
                       [source]) or 0
    dangling = graph.one(
        "SELECT count(*) FROM edges e LEFT JOIN nodes n ON n.id = e.src"
        " LEFT JOIN nodes m ON m.id = e.dst"
        " WHERE e.source_id = ? AND (n.id IS NULL OR m.id IS NULL)",
        [source]) or 0
    labelled = graph.one(
        "SELECT count(*) FROM nodes WHERE source_id = ? AND nkey IS NOT NULL"
        " AND nkey <> ''", [source]) or 0
    graph_checks = [
        _check("Nodes materialised", nodes > 0, f"{nodes:,} nodes"),
        _check("Edges materialised", edges > 0, f"{edges:,} edges"),
        _check("No dangling edges", dangling == 0,
               f"{dangling:,} dangling edges"),
        _check("Readable entity keys", labelled > 0,
               f"{labelled:,} nodes with a non-empty key", severity="warning"),
    ]
    layers.append(_layer("Knowledge graph", graph_checks))

    # --------------------------------------------------------- semantic
    definitions = metric_defs.list_definitions(graph, source)
    approved = [item for item in definitions if item.get("status") == "approved"]
    semantic_checks = [
        _check("Approved metric definitions", len(approved) > 0,
               f"{len(approved)} approved of {len(definitions)} definitions"),
        _check("Every metric has an owner", all(
            item.get("owner") for item in approved),
            "A metric without an owner cannot be governed", severity="warning"),
    ]
    evaluated = None
    if approved:
        try:
            evaluated = metric_defs.evaluate_definition(
                graph, approved[0]["name"], source, limit=5)
            semantic_checks.append(_check(
                "Metric evaluates with real SQL", bool(evaluated.get("rows")),
                f"{approved[0]['name']} returned "
                f"{len(evaluated.get('rows') or [])} row(s)"))
            semantic_checks.append(_check(
                "Metric keeps its SQL", bool(evaluated.get("sql")),
                "The evaluated statement is attached to the evidence"))
        except KeyError as exc:
            semantic_checks.append(_check(
                "Metric evaluates with real SQL", False, str(exc)))
    layers.append(_layer("Semantic layer", semantic_checks))

    # ----------------------------------------------------------- context
    context_checks = []
    try:
        row = graph.sql(
            "SELECT n.nkey, c.name FROM nodes n JOIN classes c"
            " ON c.code = n.class AND c.source_id = n.source_id"
            " WHERE n.source_id = ? LIMIT 1", [source])
        if not row:
            context_checks.append(_check(
                "A context pack can be built", False, "no entity to pack"))
        else:
            key, class_name = row[0][0], row[0][1]
            envelope = layer.context(
                entity=(source, str(class_name), str(key)), budget_chars=1200)
            facts = envelope.get("facts") or []
            cited = [fact for fact in facts
                     if isinstance(fact, dict) and fact.get("citation")]
            context_checks.extend([
                _check("A context pack can be built", bool(facts),
                       f"{len(facts)} facts packed for {class_name}:{key}"),
                _check("Facts carry citations", len(cited) == len(facts) and bool(facts),
                       f"{len(cited)} of {len(facts)} facts have a citation"),
                _check("Context budget is respected",
                       int(envelope.get("chars") or 0) <= 1200,
                       f"{envelope.get('chars')} characters used of 1200"),
            ])
    except (KeyError, ValueError) as exc:
        context_checks.append(_check(
            "A context pack can be built", False, str(exc)))
    layers.append(_layer("Context", context_checks))

    failed = any(item["status"] == "fail" for item in layers)
    warned = any(item["status"] == "warn" for item in layers)
    return {
        "source": source,
        "certified": not failed,
        "status": "fail" if failed else ("warn" if warned else "pass"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layers": layers,
        "metric_used": approved[0]["name"] if approved else None,
    }


def _layer(name: str, checks: list[dict]) -> dict:
    failed = [check for check in checks
              if not check["passed"] and check["severity"] == "error"]
    warned = [check for check in checks
              if not check["passed"] and check["severity"] == "warning"]
    status = "fail" if failed else ("warn" if warned else "pass")
    return {"layer": name, "status": status, "checks": checks,
            "passed": len(checks) - len(failed) - len(warned),
            "total": len(checks)}
