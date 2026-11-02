"""Human-in-the-loop: what a machine proposes, a person decides.

The product rule (from the manager conversation and the plan):

* ontology and knowledge graph may publish automatically — they are structure
  with confidence attached, and every guess is visible;
* **semantic definitions and the context answer policy wait for a reviewer** —
  a wrong metric definition or an unapproved answer rule is the kind of silent
  failure this product exists to prevent.

This module is deliberately storage-only: it does not know what a metric is.
It records proposals, decisions and publish state, and answers "may this
artifact be served yet?". The UI/API layer renders the queue; the planner seeds
proposals.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

KINDS = ("rename", "relation", "semantic", "context", "entity")
DECISIONS = ("approved", "rejected", "edited")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value) -> str:
    return json.dumps(value or {}, sort_keys=True, default=str)


def item_id(kind: str, source: str, subject: str) -> str:
    """Stable id, so re-running a planner does not duplicate the queue."""
    raw = f"{kind}|{source}|{subject}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def propose(graph, kind: str, subject: str = "", source: str = "",
            payload: dict | None = None, confidence: float | None = None,
            proposed_by: str = "system") -> str:
    """Record a proposal. Idempotent for the same (kind, source, subject)."""
    if kind not in KINDS:
        raise ValueError(f"unknown review kind {kind!r}; expected {KINDS}")
    iid = item_id(kind, source, subject)
    graph.con.execute(
        "INSERT INTO review_items(item_id, kind, source_id, subject, payload,"
        " confidence, status, created_at, proposed_by)"
        " VALUES (?,?,?,?,?,?,'proposed',?,?)"
        " ON CONFLICT DO NOTHING",
        [iid, kind, source, subject, _json(payload), confidence,
         _now(), proposed_by])
    return iid


def propose_many(graph, kind: str, source: str, proposals: list[dict],
                 proposed_by: str = "system") -> list[str]:
    """Propose a batch. Each item needs a `subject`; the rest is payload."""
    ids = []
    for proposal in proposals:
        item = dict(proposal)
        subject = str(item.pop("subject"))
        confidence = item.pop("confidence", None)
        ids.append(propose(graph, kind, subject, source, payload=item,
                           confidence=confidence, proposed_by=proposed_by))
    return ids


def get(graph, iid: str) -> dict | None:
    rows = graph.sql(
        "SELECT item_id, kind, source_id, subject, payload, confidence,"
        " status, created_at, proposed_by FROM review_items WHERE item_id = ?",
        [iid])
    if not rows:
        return None
    keys = ("item_id", "kind", "source", "subject", "payload", "confidence",
            "status", "created_at", "proposed_by")
    item = dict(zip(keys, rows[0]))
    item["payload"] = json.loads(item["payload"]) if item["payload"] else {}
    return item


def pending(graph, kind: str | None = None,
            source: str | None = None) -> list[dict]:
    sql = ("SELECT item_id, kind, source_id, subject, payload, confidence,"
           " status, created_at, proposed_by FROM review_items"
           " WHERE status = 'proposed'")
    args: list = []
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    if source is not None:
        sql += " AND source_id = ?"
        args.append(source)
    sql += " ORDER BY kind, confidence DESC, subject"
    keys = ("item_id", "kind", "source", "subject", "payload", "confidence",
            "status", "created_at", "proposed_by")
    out = []
    for row in graph.sql(sql, args):
        item = dict(zip(keys, row))
        item["payload"] = json.loads(item["payload"]) if item["payload"] else {}
        out.append(item)
    return out


def decide(graph, iid: str, decision: str, reviewer: str = "human",
           rationale: str = "") -> dict:
    """Approve, reject or edit one proposal. Every decision is audited."""
    decision = decision.lower()
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    item = get(graph, iid)
    if item is None:
        raise KeyError(f"no review item {iid!r}")
    graph.con.execute("UPDATE review_items SET status = ? WHERE item_id = ?",
                      [decision, iid])
    graph.con.execute(
        "INSERT INTO review_decisions(item_id, decision, reviewer, rationale,"
        " decided_at) VALUES (?,?,?,?,?)",
        [iid, decision, reviewer, rationale, _now()])
    return get(graph, iid)


def approve(graph, iid: str, reviewer: str = "human",
            rationale: str = "") -> dict:
    return decide(graph, iid, "approved", reviewer, rationale)


def reject(graph, iid: str, reviewer: str = "human",
           rationale: str = "") -> dict:
    return decide(graph, iid, "rejected", reviewer, rationale)


def audit(graph, iid: str) -> list[dict]:
    rows = graph.sql(
        "SELECT decision, reviewer, rationale, decided_at FROM review_decisions"
        " WHERE item_id = ? ORDER BY decided_at, decision", [iid])
    return [dict(zip(("decision", "reviewer", "rationale", "decided_at"), r))
            for r in rows]


def publish_state(graph, artifact: str, source: str = "") -> str | None:
    return graph.one(
        "SELECT state FROM publish_state WHERE artifact = ? AND source_id = ?",
        [artifact, source])


def publish(graph, artifact: str, source: str = "",
            reviewer: str = "human", signature: str | None = None) -> dict:
    """Publish an approved artifact.

    Refuses while the queue still holds proposals of that kind. A rejected
    proposal is a decision, so it does not block; a pending one does.
    """
    waiting = pending(graph, kind=artifact, source=source)
    if waiting:
        ids = ", ".join(item["item_id"] for item in waiting[:5])
        raise KeyError(
            f"{len(waiting)} {artifact} proposal(s) still need a decision: {ids}")
    graph.con.execute(
        "INSERT INTO publish_state(artifact, source_id, state, signature,"
        " published_at) VALUES (?,?,'approved',?,?)"
        " ON CONFLICT (artifact, source_id) DO UPDATE SET"
        " state = 'approved', signature = excluded.signature,"
        " published_at = excluded.published_at",
        [artifact, source, signature, _now()])
    graph.con.execute(
        "INSERT INTO review_decisions(item_id, decision, reviewer, rationale,"
        " decided_at) VALUES (?,?,?,?,?)",
        [f"publish:{artifact}:{source}", "approved", reviewer,
         "artifact published", _now()])
    return {"artifact": artifact, "source": source, "state": "approved"}


def can_serve(graph, artifact: str, source: str = "") -> bool:
    """The gate the API and the context builder ask before serving."""
    if pending(graph, kind=artifact, source=source):
        return False
    return publish_state(graph, artifact, source) == "approved"


def seed_from_relations(graph, source: str) -> list[str]:
    """Propose every inferred (non-measured) relation for review. These are
    the links a person is most likely to correct."""
    rows = graph.sql(
        "SELECT name, confidence, domain, range FROM relations"
        " WHERE source_id = ? AND provenance <> 'measured'"
        " ORDER BY name", [source])
    return propose_many(
        graph, "relation", source,
        [{"subject": name,
          "domain": domain, "range": range_, "confidence": confidence}
         for name, confidence, domain, range_ in rows])
