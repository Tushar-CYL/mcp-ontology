"""Corrections from people and agents, routed to the human review queue.

Feedback is the learning loop (NVIDIA auto-ontology calls it "Learn"): the
places an answer was wrong are exactly where the governed layer needs work.
It is also the easiest way to poison that layer, so nothing here changes a
definition. A correction becomes a review proposal with everything a steward
needs; the steward approves or rejects it, and the decision is audited.
"""

from __future__ import annotations

import hashlib
import json
import re

from review import store as review

KINDS = ("wrong_number", "wrong_definition", "missing_context", "other",
         "proposal")
# A wrong number or definition is a semantic-layer problem; the rest is
# about what the context pack included.
_REVIEW_KIND = {"wrong_number": "semantic", "wrong_definition": "semantic",
                "missing_context": "context", "other": "context",
                "proposal": "semantic"}
_PREFIX = "feedback:"


def _required(name: str, value) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"feedback needs a {name}")
    return text


def submit(graph, source: str, question: str, correction: str,
           kind: str = "other", answer: str = "", metric: str | None = None,
           agent_id: str | None = None, submitted_by: str = "person") -> dict:
    source = _required("source", source)
    question = _required("question", question)
    correction = _required("correction", correction)
    if kind not in KINDS:
        raise ValueError(f"unknown feedback kind {kind!r}; use one of "
                         + ", ".join(KINDS))
    digest = hashlib.sha1(f"{question}|{correction}".encode()).hexdigest()[:12]
    iid = review.propose(
        graph, _REVIEW_KIND[kind], subject=_PREFIX + digest, source=source,
        payload={"question": question, "answer": str(answer or "")[:4000],
                 "correction": correction[:4000], "kind": kind,
                 "metric": metric or None, "agent_id": agent_id or None},
        proposed_by=submitted_by)
    return _view(review.get(graph, iid))


def _view(item: dict) -> dict:
    payload = item.get("payload") or {}
    return {"id": item["item_id"], "status": item["status"],
            "review_kind": item["kind"], "source": item["source"],
            "question": payload.get("question", ""),
            "answer": payload.get("answer", ""),
            "correction": payload.get("correction", ""),
            "kind": payload.get("kind", "other"),
            "metric": payload.get("metric"),
            "agent_id": payload.get("agent_id"),
            "proposal": payload.get("proposal"),
            "submitted_by": item.get("proposed_by"),
            "created_at": str(item.get("created_at") or "")}


def list_feedback(graph, source: str, pending_only: bool = False) -> list[dict]:
    sql = ("SELECT item_id, kind, source_id, subject, payload, confidence,"
           " status, created_at, proposed_by FROM review_items"
           " WHERE source_id = ? AND subject LIKE ?")
    args: list = [source, _PREFIX + "%"]
    if pending_only:
        sql += " AND status = 'proposed'"
    sql += " ORDER BY created_at DESC, item_id"
    keys = ("item_id", "kind", "source", "subject", "payload", "confidence",
            "status", "created_at", "proposed_by")
    out = []
    for row in graph.sql(sql, args):
        item = dict(zip(keys, row))
        item["payload"] = json.loads(item["payload"]) if item["payload"] else {}
        out.append(_view(item))
    return out


def decide(graph, item_id: str, decision: str, note: str = "",
           reviewer: str = "steward") -> dict:
    """Record a person's decision. Only an APPROVED synonym proposal changes
    anything, and it is applied here, after the decision, never before."""
    item = review.get(graph, item_id)
    if item is None or not str(item["subject"]).startswith(_PREFIX):
        raise KeyError(f"no feedback item {item_id!r}")
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")
    applied = None
    proposal = (item.get("payload") or {}).get("proposal") or {}
    if decision == "approved" and proposal.get("type") == "synonym":
        from semantic import definitions as metric_defs
        try:
            metric_defs.add_synonym(graph, proposal["metric"], item["source"],
                                    proposal["synonym"])
            applied = (f"synonym {proposal['synonym']!r} added to "
                       f"{proposal['metric']}")
        except (KeyError, ValueError) as exc:
            applied = f"not applied: {str(exc).strip(chr(39))}"
    rationale = note if not applied else f"{note} [{applied}]".strip()
    view = _view(review.decide(graph, item_id, decision, reviewer=reviewer,
                               rationale=rationale))
    view["applied"] = applied
    return view


# ---------------------------------------------------------------- steward
_SYNONYM_PATTERNS = (
    re.compile(r"^\s*add\s+(?:a\s+)?synonym\s+[\"'“]?(?P<syn>.+?)[\"'”]?\s+"
               r"(?:for|to)\s+[\"'“]?(?P<metric>.+?)[\"'”]?\s*\.?\s*$", re.I),
    re.compile(r"^\s*use\s+[\"'“]?(?P<syn>.+?)[\"'”]?\s+as\s+(?:a\s+)?synonym\s+"
               r"(?:for|of)\s+[\"'“]?(?P<metric>.+?)[\"'”]?\s*\.?\s*$", re.I),
    re.compile(r"^\s*[\"'“]?(?P<syn>[^\"'“”]+?)[\"'”]?\s+(?:means|=)\s+"
               r"[\"'“]?(?P<metric>[^\"'“”]+?)[\"'”]?\s*\.?\s*$", re.I),
)


def _resolve_metric(graph, source: str, text: str) -> str | None:
    from semantic import definitions as metric_defs
    wanted = " ".join(text.replace("_", " ").lower().split())
    for definition in metric_defs.list_definitions(graph, source):
        if wanted in (definition["name"].replace("_", " ").lower(),
                      (definition.get("title") or "").lower()):
            return definition["name"]
    return None


def parse_proposal(graph, source: str, text: str) -> dict:
    for pattern in _SYNONYM_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        metric = _resolve_metric(graph, source, match.group("metric"))
        synonym = " ".join(match.group("syn").split())
        if metric and synonym:
            return {"type": "synonym", "synonym": synonym, "metric": metric}
    return {"type": "note", "text": text}


def propose(graph, source: str, text: str, agent_id: str | None = None,
            submitted_by: str = "steward") -> dict:
    """File a Steward proposal. Nothing changes until a person approves it."""
    source = _required("source", source)
    text = " ".join(str(text or "").split())
    if not text:
        raise ValueError("a proposal needs some text")
    proposal = parse_proposal(graph, source, text)
    digest = hashlib.sha1(f"proposal|{text}".encode()).hexdigest()[:12]
    iid = review.propose(
        graph, "semantic", subject=_PREFIX + digest, source=source,
        payload={"question": text, "correction": text, "answer": "",
                 "kind": "proposal", "metric": proposal.get("metric"),
                 "agent_id": agent_id or None, "proposal": proposal},
        proposed_by=submitted_by)
    return _view(review.get(graph, iid))
