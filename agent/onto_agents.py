"""Agents of an ontology: the built-ins (from the data, read-only), copies of
them, and agents people create.

    builtin:<ontology>:<key>   made by agent/catalog.py, refreshed from the data,
                               never edited; one that the data no longer
                               supports is marked retired (its keys and usage stay)
    agent:<ontology>:<slug>    a copy or your own: edit, delete, version

Every agent has a kind (how it answers - see catalog.KINDS), a scope (the
things and metrics it may use; empty means all), instructions in plain words
and example questions. Keys, usage and MCP reuse agent/connections.py.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone

from agent import catalog

_SCHEMA = """
CREATE TABLE IF NOT EXISTS onto_agents (
    id           VARCHAR PRIMARY KEY,
    ontology_id  VARCHAR NOT NULL,
    name         VARCHAR NOT NULL,
    kind         VARCHAR NOT NULL,
    builtin      BOOLEAN NOT NULL DEFAULT FALSE,
    base         VARCHAR,
    status       VARCHAR NOT NULL DEFAULT 'active',
    version      INTEGER NOT NULL DEFAULT 1,
    config       JSON,
    created_at   VARCHAR,
    updated_at   VARCHAR
)"""
MAX_EXAMPLES = 5
MAX_TEXT = 2000
_cache: dict = {}
_lock = threading.Lock()


class AgentError(ValueError):
    """A request about an agent that cannot be done, in plain words."""


class ReadOnly(PermissionError):
    """Built-in agents are not edited: copy one instead."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "agent"


def ensure(graph) -> None:
    if getattr(graph, "_onto_agents_ready", False):
        return
    with graph.lock:
        graph.con.execute(_SCHEMA)
    graph._onto_agents_ready = True


def _row(r) -> dict:
    (aid, oid, name, kind, builtin, base, status, version, config, created, updated) = r
    cfg = json.loads(config or "{}")
    spec = catalog.KINDS.get(kind, {})
    return {"id": aid, "ontology": oid, "name": name, "kind": kind,
            "kind_title": spec.get("title", kind), "builtin": bool(builtin), "base": base,
            "status": status, "version": int(version), "created_at": created, "updated_at": updated,
            "job": cfg.get("job", ""), "why": cfg.get("why", ""),
            "layers": cfg.get("layers") or spec.get("layers", []),
            "tools": cfg.get("tools") or spec.get("tools", []),
            "guardrails": cfg.get("guardrails") or spec.get("guardrails", []),
            "scope": cfg.get("scope") or {"things": [], "metrics": []},
            "focus": cfg.get("focus") or {}, "examples": cfg.get("examples") or [],
            "instructions": cfg.get("instructions", "")}


_COLS = "id, ontology_id, name, kind, builtin, base, status, version, config, created_at, updated_at"


def get(graph, agent_id: str) -> dict:
    ensure(graph)
    rows = graph.sql(f"SELECT {_COLS} FROM onto_agents WHERE id = ?", [str(agent_id)])
    if not rows:
        raise KeyError(f"no agent {agent_id!r}")
    return _row(rows[0])


def exists(graph, agent_id: str) -> bool:
    ensure(graph)
    return bool(graph.sql("SELECT 1 FROM onto_agents WHERE id = ?", [str(agent_id)]))


# --------------------------------------------------------------- built-ins
def _fingerprint(layer, oid: str) -> tuple:
    from ontology import cache
    from semantic import definitions as defs
    from semantic import model as sem
    certified = tuple(sorted(d["name"] for d in defs.list_definitions(layer.graph, sem.source_of(oid))
                             if d["status"] == "approved"))
    return cache.stamp(layer.graph, oid) + (certified,)


def sync_builtins(layer, oid: str) -> list[dict]:
    """Bring the built-ins in line with the data. Cheap when nothing changed."""
    g = layer.graph
    ensure(g)
    from ontology import registry as reg
    reg.get(g, oid)                                # unknown ontology: KeyError
    fp = _fingerprint(layer, oid)
    key = (getattr(g, "_cache_token", id(g)), oid)
    with _lock:
        if _cache.get(key) == fp:
            return builtin_rows(g, oid)
    specs = catalog.builtins(layer, oid)
    have = {a["id"]: a for a in builtin_rows(g, oid, include_retired=True)}
    now = _now()
    keep = set()
    for spec in specs:
        aid = f"builtin:{oid}:{spec['key']}"
        keep.add(aid)
        cfg = {k: spec[k] for k in ("job", "why", "layers", "tools", "guardrails", "scope", "focus", "examples")}
        old = have.get(aid)
        with g.lock:
            if old is None:
                g.con.execute(f"INSERT INTO onto_agents ({_COLS}) VALUES (?,?,?,?,TRUE,NULL,'active',1,?,?,?)",
                              [aid, oid, spec["name"], spec["kind"], json.dumps(cfg), now, now])
            else:
                same = (old["name"] == spec["name"] and old["kind"] == spec["kind"] and old["status"] == "active"
                        and all(old.get(k) == cfg[k] for k in cfg))
                if not same:
                    g.con.execute("UPDATE onto_agents SET name = ?, kind = ?, config = ?, status = 'active', "
                                  "version = version + 1, updated_at = ? WHERE id = ?",
                                  [spec["name"], spec["kind"], json.dumps(cfg), now, aid])
    for aid, old in have.items():
        if aid not in keep and old["status"] != "retired":
            with g.lock:
                g.con.execute("UPDATE onto_agents SET status = 'retired', updated_at = ? WHERE id = ?", [now, aid])
    with _lock:
        _cache[key] = fp
    return builtin_rows(g, oid)


def builtin_rows(graph, oid: str, include_retired: bool = False) -> list[dict]:
    ensure(graph)
    rows = [_row(r) for r in graph.sql(
        f"SELECT {_COLS} FROM onto_agents WHERE ontology_id = ? AND builtin ORDER BY created_at, id", [oid])]
    order = {k: i for i, k in enumerate(("guide", "investigator", "metric", "insight", "trust", "steward",
                                         "money", "status", "regional", "trend", "privacy"))}
    rows.sort(key=lambda a: order.get(a["id"].rsplit(":", 1)[-1], 99))
    return rows if include_retired else [a for a in rows if a["status"] == "active"]


def mine(graph, oid: str) -> list[dict]:
    ensure(graph)
    return [_row(r) for r in graph.sql(
        f"SELECT {_COLS} FROM onto_agents WHERE ontology_id = ? AND NOT builtin "
        "ORDER BY updated_at DESC, name", [oid])]


def listing(layer, oid: str) -> dict:
    """Everything the Agents page needs, including what an agent may be
    scoped to (names only: no metric is computed here)."""
    from semantic import definitions as defs
    from semantic import model as sem
    metrics = [{"name": d["name"], "title": d["title"],
                "certified": d["status"] == "approved"}
               for d in defs.list_definitions(layer.graph, sem.source_of(oid)) if d["status"] != "deprecated"]
    metrics.sort(key=lambda m: (not m["certified"], m["title"]))
    return {"ontology": oid, "builtin": sync_builtins(layer, oid), "mine": mine(layer.graph, oid),
            "kinds": catalog.describe_kinds(), "things": catalog.ontology_things(layer.graph, oid),
            "metrics": metrics}


# ------------------------------------------------------- copies and your own
def _clean(layer, oid: str, payload: dict, current: dict | None = None) -> dict:
    """Check a create / edit against the ontology; every problem is said."""
    from semantic import definitions as defs
    from semantic import model as sem
    p = dict(payload or {})
    cur = current or {}
    name = str(p.get("name", cur.get("name", "")) or "").strip()[:80]
    if not name:
        raise AgentError("give the agent a name")
    kind = str(p.get("kind", cur.get("kind", "insight")) or "").strip()
    if kind not in catalog.KINDS:
        raise AgentError(f"how it answers must be one of: {', '.join(catalog.KINDS)}")
    scope = p.get("scope", cur.get("scope")) or {}
    things = [str(t) for t in scope.get("things") or []]
    metrics = [str(m) for m in scope.get("metrics") or []]
    known_things = catalog.ontology_things(layer.graph, oid)
    unknown = [t for t in things if t not in known_things]
    if unknown:
        raise AgentError(f"no thing called {', '.join(unknown)} in this ontology; things: "
                         + ", ".join(known_things))
    known_metrics = {d["name"] for d in defs.list_definitions(layer.graph, sem.source_of(oid))
                     if d["status"] != "deprecated"}
    unknown = [m for m in metrics if m not in known_metrics]
    if unknown:
        raise AgentError(f"no metric called {', '.join(unknown)}; open the Semantic page to see them")
    examples = []
    for e in (p.get("examples", cur.get("examples")) or [])[:MAX_EXAMPLES]:
        text = str(e.get("text") if isinstance(e, dict) else e or "").strip()[:300]
        if text:
            examples.append({"text": text, "why": str(e.get("why", "") if isinstance(e, dict) else "")[:200]})
    spec = catalog.KINDS[kind]
    return {"name": name, "kind": kind, "config": {
        "job": str(p.get("job", cur.get("job", "")) or "")[:MAX_TEXT] or spec["title"],
        "why": str(cur.get("why", "") or ""),
        "instructions": str(p.get("instructions", cur.get("instructions", "")) or "")[:MAX_TEXT],
        "layers": list(spec["layers"]), "tools": list(spec["tools"]),
        "guardrails": list(spec["guardrails"]),
        "scope": {"things": things, "metrics": metrics},
        "focus": p.get("focus", cur.get("focus")) or {}, "examples": examples}}


def _free_id(graph, oid: str, name: str) -> str:
    base = f"agent:{oid}:{_slug(name)}"
    aid, n = base, 2
    while exists(graph, aid):
        aid, n = f"{base}-{n}", n + 1
    return aid


def create(layer, oid: str, payload: dict, base: str | None = None) -> dict:
    g = layer.graph
    ensure(g)
    from ontology import registry as reg
    reg.get(g, oid)
    clean = _clean(layer, oid, payload)
    taken = {a["name"].lower() for a in mine(g, oid)}
    if clean["name"].lower() in taken:
        raise AgentError(f"you already have an agent called {clean['name']!r}; pick another name")
    aid = _free_id(g, oid, clean["name"])
    now = _now()
    with g.lock:
        g.con.execute(f"INSERT INTO onto_agents ({_COLS}) VALUES (?,?,?,?,FALSE,?,'active',1,?,?,?)",
                      [aid, oid, clean["name"], clean["kind"], base, json.dumps(clean["config"]), now, now])
    return get(g, aid)


def copy(layer, agent_id: str, name: str | None = None) -> dict:
    """A copy you can change. The original stays exactly as it is."""
    src = get(layer.graph, agent_id)
    taken = {a["name"].lower() for a in mine(layer.graph, src["ontology"])}
    new = name or f"{src['name']} (my copy)"
    n = 2
    while new.lower() in taken and not name:
        new, n = f"{src['name']} (my copy {n})", n + 1
    payload = {k: src[k] for k in ("kind", "job", "scope", "focus", "examples", "instructions")}
    payload["name"] = new
    return create(layer, src["ontology"], payload, base=src["id"])


def update(layer, agent_id: str, payload: dict) -> dict:
    g = layer.graph
    cur = get(g, agent_id)
    if cur["builtin"]:
        raise ReadOnly("built-in agents are not changed: make a copy and change the copy")
    clean = _clean(layer, cur["ontology"], payload, current=cur)
    if clean["name"].lower() != cur["name"].lower() and \
            clean["name"].lower() in {a["name"].lower() for a in mine(g, cur["ontology"])}:
        raise AgentError(f"you already have an agent called {clean['name']!r}")
    with g.lock:
        g.con.execute("UPDATE onto_agents SET name = ?, kind = ?, config = ?, version = version + 1, "
                      "updated_at = ? WHERE id = ?",
                      [clean["name"], clean["kind"], json.dumps(clean["config"]), _now(), agent_id])
    return get(g, agent_id)


def delete(layer, agent_id: str) -> None:
    g = layer.graph
    cur = get(g, agent_id)
    if cur["builtin"]:
        raise ReadOnly("built-in agents cannot be deleted; they come from your data")
    from agent import connections
    connections.forget_agent(g, agent_id)
    with g.lock:
        g.con.execute("DELETE FROM onto_agents WHERE id = ?", [agent_id])


# --------------------------------------------------------------------- MCP
def mcp_scope(graph, agent: dict) -> dict:
    """What a key of this agent may do over MCP: its tools, its ontology, and
    (when it has one) its scope of things and metrics."""
    from ontology import registry as reg
    onto = reg.get(graph, agent["ontology"])
    return {"agent_id": agent["id"], "ontology": agent["ontology"],
            "sources": [s["source_id"] for s in onto["sources"]],
            "tools": list(agent["tools"]), "metrics": [],
            "onto_metrics": list(agent["scope"].get("metrics") or []) or None,
            "things": list(agent["scope"].get("things") or []) or None}


def forget() -> None:
    with _lock:
        _cache.clear()
