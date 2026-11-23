"""Questions Strata could not answer, kept so the gaps get fixed.

Every time the Context page or an agent cannot answer - no business thing
matches the words, no metric or query can compute the number asked for, the
AI says the facts are not enough, or it states a number the facts do not
hold - the question is logged with the reason. Similar questions are grouped
(the same words in any order), ranked by how often they were asked, and each
group gets a suggested fix a person can apply (a note, a metric to certify).
Logging never stops an answer.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ontology import ask

_SCHEMA = """CREATE TABLE IF NOT EXISTS ctx_gaps (
    id VARCHAR PRIMARY KEY, ontology_id VARCHAR NOT NULL, question VARCHAR NOT NULL,
    norm VARCHAR NOT NULL, reason VARCHAR NOT NULL, detail VARCHAR, things JSON,
    source VARCHAR, asked_at VARCHAR)"""
MAX_PER_ONTOLOGY = 5000
REASONS = {
    "unknown_words": "No business thing or field matches the words",
    "ambiguous": "The words fit more than one thing",
    "no_number": "No certified metric or Strata query could compute the number",
    "not_enough": "The facts found were not enough",
    "unverified": "The answer stated a number the facts do not hold",
    "agent_refused": "An agent could not answer",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure(graph) -> None:
    if getattr(graph, "_ctx_gaps_ready", False):
        return
    with graph.lock:
        graph.con.execute(_SCHEMA)
    graph._ctx_gaps_ready = True


def norm(question: str) -> str:
    """The same question in other word order or plural is the same gap."""
    return " ".join(sorted(set(ask.words(question)))) or str(question).strip().lower()[:200]


def classify(built: dict) -> tuple[str, str] | None:
    """Why a Context build did not answer, or None when it did."""
    from context.engine import AGGREGATE
    steps = built["steps"]
    under, facts, said = steps["understand"], steps["facts"], steps["answer"]
    named = [t for t in under.get("things") or [] if t.get("why") != "joins the others"]
    # The words as the person typed them ("Paris"), not their stems ("pari").
    stems = {w for w in under.get("unknown") or [] if len(w) > 2}
    unknown = []
    for token in re.findall(r"[\w'-]+", built["question"]):
        if set(ask.words(token)) & stems and token not in unknown:
            unknown.append(token)
    if not named and not under.get("records") and not under.get("fields"):
        words = ", ".join(unknown[:6]) or "the question's words"
        return "unknown_words", f"Nothing in the ontology matches: {words}"
    if under.get("ambiguous") and not facts.get("table"):
        a = under["ambiguous"][0]
        return "ambiguous", f"\"{a['phrase']}\" could be {', '.join(a['things'])}"
    if AGGREGATE.search(built["question"]) and not facts.get("table"):
        held = "; ".join(q["why"] for q in facts.get("quarantined") or [] if q.get("why"))
        return "no_number", held or "the question asks for a number and nothing computed it"
    if said.get("status") == "not_enough":
        return "not_enough", said.get("text") or ""
    if said.get("status") == "unverified":
        return "unverified", said.get("warning") or ""
    return None


def log(graph, ontology_id: str, question: str, reason: str, detail: str = "",
        things: list | None = None, source: str = "context") -> None:
    try:
        ensure(graph)
        with graph.lock:
            n = graph.con.execute("SELECT count(*) FROM ctx_gaps WHERE ontology_id = ?",
                                  [ontology_id]).fetchone()[0]
            if n >= MAX_PER_ONTOLOGY:              # keep the newest
                graph.con.execute(
                    "DELETE FROM ctx_gaps WHERE id IN (SELECT id FROM ctx_gaps WHERE ontology_id = ?"
                    " ORDER BY asked_at LIMIT ?)", [ontology_id, n - MAX_PER_ONTOLOGY + 1])
            graph.con.execute("INSERT INTO ctx_gaps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              ["gap_" + uuid.uuid4().hex[:10], ontology_id, question[:1000],
                               norm(question), reason, str(detail or "")[:500],
                               json.dumps(list(things or [])[:10]), source[:120], _now()])
    except Exception:                              # noqa: BLE001 - logging never stops an answer
        pass


def record(graph, ontology_id: str, built: dict, source: str = "context") -> dict | None:
    """Log a Context build when it did not answer. Returns the gap, if any."""
    why = classify(built)
    if why is None:
        return None
    things = [t["name"] for t in built["steps"]["understand"].get("things") or []]
    log(graph, ontology_id, built["question"], why[0], why[1], things, source)
    return {"reason": why[0], "label": REASONS[why[0]], "detail": why[1]}


def _fix(reason: str, group: dict, ontology_name: str) -> dict:
    """What a person can do about it, in one line, plus a ready-made note."""
    words = group["unknown"]
    if reason == "unknown_words":
        word = words[0] if words else "this term"
        return {"action": "note", "text": f"Tell Strata what \"{word}\" means in {ontology_name}",
                "note": f"\"{word}\" means "}
    if reason == "ambiguous":
        return {"action": "note", "text": "Say which thing these words mean",
                "note": f"When people say \"{group['question']}\" they mean "}
    if reason == "no_number":
        thing = group["things"][0] if group["things"] else "this"
        return {"action": "metric", "text": f"Define and certify a metric for {thing} on the Semantic page",
                "note": f"For \"{group['question']}\", count or add up "}
    if reason == "unverified":
        return {"action": "metric", "text": "Certify the metric this question needs, so the number has a receipt",
                "note": ""}
    return {"action": "note", "text": "Add the missing fact as context",
            "note": f"About \"{group['question']}\": "}


def groups(graph, ontology_id: str, limit: int = 30) -> dict:
    """The gaps, grouped and ranked by how often they were asked."""
    from ontology import registry as reg
    onto = reg.get(graph, ontology_id)
    ensure(graph)
    rows = graph.sql("SELECT question, norm, reason, detail, things, source, asked_at FROM ctx_gaps"
                     " WHERE ontology_id = ? ORDER BY asked_at", [ontology_id])
    by: dict = {}
    for question, nm, reason, detail, things, source, at in rows:
        g = by.setdefault(nm, {"key": nm, "question": question, "count": 0, "reasons": {},
                               "detail": "", "things": [], "sources": set(), "first": at,
                               "last": at, "unknown": []})
        g["count"] += 1
        g["reasons"][reason] = g["reasons"].get(reason, 0) + 1
        g["question"], g["detail"], g["last"] = question, detail or g["detail"], at
        for t in json.loads(things or "[]"):
            if t not in g["things"]:
                g["things"].append(t)
        g["sources"].add(source)
        if reason == "unknown_words" and detail and ":" in detail:
            g["unknown"] = [w.strip() for w in detail.split(":", 1)[1].split(",") if w.strip()]
    out = []
    for g in by.values():
        reason = max(g["reasons"], key=g["reasons"].get)
        out.append({**g, "reason": reason, "label": REASONS.get(reason, reason),
                    "sources": sorted(g["sources"]), "fix": _fix(reason, g, onto["name"])})
    out.sort(key=lambda g: (g["count"], g["last"]), reverse=True)
    return {"ontology": ontology_id, "total": len(rows), "groups": out[:limit],
            "reasons": REASONS}


def dismiss(graph, ontology_id: str, key: str) -> dict:
    """A gap that was fixed (or does not matter) leaves the list."""
    ensure(graph)
    with graph.lock:
        n = graph.con.execute("SELECT count(*) FROM ctx_gaps WHERE ontology_id = ? AND norm = ?",
                              [ontology_id, key]).fetchone()[0]
        if not n:
            raise KeyError(f"no gap {key!r}")
        graph.con.execute("DELETE FROM ctx_gaps WHERE ontology_id = ? AND norm = ?", [ontology_id, key])
    return groups(graph, ontology_id)
