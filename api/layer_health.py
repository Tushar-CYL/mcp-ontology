"""Is each layer ready, for one ontology? One line per layer, in plain words.

Cheap on purpose (it is polled): it reads what the layers already know -
the ontology view, the graph's cached overview, metric statuses and drift -
and never recomputes a metric or calls the AI.
"""

from __future__ import annotations

from api import layers


def _row(layer: str, status: str, text: str, **extra) -> dict:
    return {"layer": layer, "on": layers.is_on(layer), "status": status, "text": text, **extra}


def report(layer, ontology_id: str | None = None) -> dict:
    from ontology import registry as reg
    from ontology import simple
    g = layer.graph
    ids = [o["id"] for o in reg.list_ontologies(g)]
    if ontology_id is None and len(ids) == 1:
        ontology_id = ids[0]
    if ontology_id is None:
        text = ("no ontology yet: build one from your data or import yours (Strata Model, Ossie, dbt)"
                if not ids else f"name one of: {', '.join(ids)}")
        rows = [_row("ontology", "not ready", text)]
        rows += [_row(x, "off" if not layers.is_on(x) else "not ready", "needs an ontology first")
                 for x in layers.LAYERS if x != "ontology"]
        return {"ontology": None, "layers": rows}
    v = simple.view(g, ontology_id)
    conflicts = v["summary"]["checks"].get("conflict", 0)
    rows = [_row("ontology", "ready" if v["things"] else "not ready",
                 f"{len(v['things'])} things, {v['summary']['fields']} fields, {len(v['links'])} links; "
                 f"{v['summary']['confirmed_pct']}% confirmed by the data"
                 + (f"; {conflicts} field(s) the data disagrees with" if conflicts else ""),
                 version=v.get("version"), mode=v.get("mode"))]
    # Knowledge graph
    if not layers.is_on("graph"):
        rows.append(_row("graph", "off", "switched off on this server"))
    else:
        try:
            from knowledge_graph import explore as kg
            o = kg.overview(layer, ontology_id)
            broken = o["summary"]["broken_links"]
            unreadable = [h["text"] for h in o["health"] if h["kind"] == "unreadable"]
            status = "not ready" if unreadable else "needs attention" if broken else "ready"
            rows.append(_row("graph", status,
                             unreadable[0] if unreadable else
                             f"{o['summary']['entities']:,} records, {o['summary']['connections']:,} "
                             f"connections, {o['summary']['connected_pct']}% connected"
                             + (f"; {broken:,} broken" if broken else "")))
        except Exception as exc:                   # noqa: BLE001 - said, not hidden
            rows.append(_row("graph", "not ready", str(exc)[:200]))
    # Semantic
    if not layers.is_on("semantic"):
        rows.append(_row("semantic", "off", "switched off on this server"))
    else:
        from semantic import definitions as defs
        from semantic import model as sem
        ds = defs.list_definitions(g, sem.source_of(ontology_id))
        certified = [d for d in ds if d["status"] == "approved"]
        drifting = []
        for d in certified:
            try:
                if sem.drift(layer, ontology_id, d["name"]):
                    drifting.append(d["title"])
            except Exception:                      # noqa: BLE001 - a check, not the metric
                continue
        proposed = sum(d["status"] == "draft" for d in ds)
        if not ds:
            rows.append(_row("semantic", "not ready", "no metrics yet: open the Semantic page to propose them"))
        else:
            rows.append(_row("semantic", "needs attention" if drifting or not certified else "ready",
                             f"{len(certified)} certified, {proposed} proposed"
                             + (f"; data changed under: {', '.join(drifting[:3])}" if drifting else "")
                             + ("" if certified else "; certify the ones you trust")))
    # Context
    if not layers.is_on("context"):
        rows.append(_row("context", "off", "switched off on this server"))
    else:
        from ontology import meaning as mn
        ai = mn.ai_enabled() and _ai_configured()
        rows.append(_row("context", "ready" if v["things"] else "not ready",
                         ("answers are written by the AI from checked facts" if ai else
                          "facts and packs are ready; no AI configured, so answers are not written")))
    # Agents
    if not layers.is_on("agents"):
        rows.append(_row("agents", "off", "the Agents page is switched off; MCP still works with a key"))
    else:
        try:
            n = int(g.sql("SELECT count(*) FROM agents")[0][0])
        except Exception:                          # noqa: BLE001
            n = 0
        rows.append(_row("agents", "ready", f"{n} agent(s); MCP at /mcp with an agent key"))
    return {"ontology": {"id": v["id"], "name": v["name"], "version": v.get("version")},
            "layers": rows}


def _ai_configured() -> bool:
    import os
    return bool(os.environ.get("EYQ_INCUBATOR_ENDPOINT") and os.environ.get("EYQ_INCUBATOR_KEY"))
