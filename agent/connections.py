"""Agent connections: the API keys external agents use, and what they did.

An agent built anywhere (Claude Desktop, Cursor, Copilot Studio, a Databricks
app) connects to Strata with a key. The key:

* is shown once, when issued, and only its SHA-256 hash is stored;
* maps to exactly one registered agent, whose scope (sources, metrics) is
  enforced on every MCP call;
* can be revoked without touching the agent.

Every tool call made with a key is written to `agent_calls`, so a steward can
see exactly which context an agent consumed.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

KEY_PREFIX = "strata_"
SUMMARY_LIMIT = 300

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS agent_keys ("
    " id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, key_hash TEXT NOT NULL,"
    " prefix TEXT NOT NULL, label TEXT, created_at TEXT NOT NULL,"
    " last_used_at TEXT, revoked_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agent_calls ("
    " id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, tool TEXT NOT NULL,"
    " summary TEXT, ok BOOLEAN NOT NULL, error TEXT, latency_ms DOUBLE,"
    " created_at TEXT NOT NULL, seq BIGINT NOT NULL)",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def ensure_tables(graph) -> None:
    with graph.lock:
        for statement in _SCHEMA:
            graph.con.execute(statement)
        # Added after the first release: which governed metric a call used.
        graph.con.execute(
            "ALTER TABLE agent_calls ADD COLUMN IF NOT EXISTS metric TEXT")


# ------------------------------------------------------------------- keys
def issue_key(graph, agent_id: str, label: str = "") -> dict:
    """Create a key for an agent. The plain key is returned only here."""
    ensure_tables(graph)
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    key_id = "key_" + uuid.uuid4().hex[:12]
    created = _now()
    with graph.lock:
        graph.con.execute(
            "INSERT INTO agent_keys (id, agent_id, key_hash, prefix, label,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [key_id, agent_id, _hash(key), key[:12], label[:120], created])
    return {"id": key_id, "key": key, "prefix": key[:12], "label": label,
            "created_at": created}


def list_keys(graph, agent_id: str) -> list[dict]:
    ensure_tables(graph)
    rows = graph.sql(
        "SELECT id, prefix, label, created_at, last_used_at, revoked_at"
        " FROM agent_keys WHERE agent_id = ? ORDER BY created_at DESC",
        [agent_id])
    return [{"id": r[0], "prefix": r[1], "label": r[2] or "",
             "created_at": r[3], "last_used_at": r[4],
             "revoked": r[5] is not None, "revoked_at": r[5]} for r in rows]


def revoke_key(graph, agent_id: str, key_id: str) -> bool:
    """Revoke one of this agent's keys. Another agent's key is untouched."""
    ensure_tables(graph)
    found = graph.one(
        "SELECT count(*) FROM agent_keys WHERE id = ? AND agent_id = ?"
        " AND revoked_at IS NULL", [key_id, agent_id])
    if not found:
        return False
    with graph.lock:
        graph.con.execute(
            "UPDATE agent_keys SET revoked_at = ? WHERE id = ?",
            [_now(), key_id])
    return True


def verify_key(graph, key: str | None) -> str | None:
    """Return the agent id for a live key, or None. Records last use."""
    if not key or not isinstance(key, str) or not key.startswith(KEY_PREFIX):
        return None
    ensure_tables(graph)
    rows = graph.sql(
        "SELECT id, agent_id FROM agent_keys WHERE key_hash = ?"
        " AND revoked_at IS NULL", [_hash(key)])
    if not rows:
        return None
    key_id, agent_id = rows[0]
    with graph.lock:
        graph.con.execute(
            "UPDATE agent_keys SET last_used_at = ? WHERE id = ?",
            [_now(), key_id])
    return agent_id


def forget_agent(graph, agent_id: str) -> None:
    """Remove every key and logged call of one agent (used on delete)."""
    ensure_tables(graph)
    with graph.lock:
        graph.con.execute("DELETE FROM agent_keys WHERE agent_id = ?", [agent_id])
        graph.con.execute("DELETE FROM agent_calls WHERE agent_id = ?", [agent_id])


# ------------------------------------------------------------------ usage
def log_call(graph, agent_id: str, tool: str, summary: str = "",
             ok: bool = True, error: str | None = None,
             latency_ms: float | None = None,
             metric: str | None = None) -> None:
    ensure_tables(graph)
    with graph.lock:
        seq = graph.con.execute(
            "SELECT coalesce(max(seq), 0) + 1 FROM agent_calls").fetchone()[0]
        graph.con.execute(
            "INSERT INTO agent_calls (id, agent_id, tool, summary, ok, error,"
            " latency_ms, created_at, seq, metric)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["call_" + uuid.uuid4().hex[:12], agent_id, tool,
             str(summary or "")[:SUMMARY_LIMIT], bool(ok),
             (str(error)[:SUMMARY_LIMIT] if error else None),
             latency_ms, _now(), seq, metric or None])


def usage(graph, agent_id: str, limit: int = 50) -> list[dict]:
    ensure_tables(graph)
    rows = graph.sql(
        "SELECT id, tool, summary, ok, error, latency_ms, created_at"
        " FROM agent_calls WHERE agent_id = ? ORDER BY seq DESC LIMIT ?",
        [agent_id, int(limit)])
    return [{"id": r[0], "tool": r[1], "summary": r[2] or "",
             "ok": bool(r[3]), "error": r[4],
             "latency_ms": round(float(r[5]), 1) if r[5] is not None else None,
             "created_at": r[6]} for r in rows]


def metric_usage(graph, agent_ids: list[str] | None = None) -> list[dict]:
    """How often agents consumed each governed metric. Refused calls are
    not consumption and are not counted. Busiest metric first."""
    ensure_tables(graph)
    sql = ("SELECT metric, count(*), count(DISTINCT agent_id), max(created_at)"
           " FROM agent_calls WHERE ok AND metric IS NOT NULL")
    args: list = []
    if agent_ids is not None:
        if not agent_ids:
            return []
        sql += f" AND agent_id IN ({', '.join('?' for _ in agent_ids)})"
        args.extend(agent_ids)
    sql += " GROUP BY metric ORDER BY 2 DESC, metric"
    return [{"metric": r[0], "calls": int(r[1]), "agents": int(r[2]),
             "last_used_at": r[3]} for r in graph.sql(sql, args)]
