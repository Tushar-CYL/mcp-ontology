"""Cross-source identity: propose that two source rows are the same thing.

The manager's question was concrete: the same product exists in three systems,
so which one should an agent believe? This module answers the *first* half —
find the candidates and explain them. It deliberately does **not** merge nodes.

Why not merge:

* an answer must be able to say which source a fact came from;
* a false merge is silent and poisons every later answer;
* the human review gate (see `review/`) is where a merge becomes real.

So the graph keeps per-source nodes and records `entity_links` rows with a
method and a confidence. High-confidence candidates can be used by the context
builder to mention the other sources; low-confidence ones go to the review
queue. Nothing is hidden either way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Class names that name the vendor/export rather than the thing. Only used to
# compare candidates; a class called `ErpProduct` and one called `PimProduct`
# are both about Product.
_VENDOR_WORDS = {
    "erp", "pim", "crm", "legacy", "stg", "stage", "staging", "raw", "src",
    "core", "mdm", "oltp", "dw", "dwh", "lake", "odoo", "sap", "netsuite",
    "shopify", "marketplace", "web", "app", "b2b", "b2c",
}


@dataclass
class Candidate:
    a_source: str
    a_class: str
    a_key: str
    b_source: str
    b_class: str
    b_key: str
    method: str
    confidence: float
    overlap: int
    a_total: int
    b_total: int


def _tokens(name: str) -> list[str]:
    # CamelCase, snake_case and digits all become lowercase words.
    parts = re.findall(r"[A-Z]?[a-z]+|\d+", str(name))
    if not parts:
        parts = re.split(r"[^A-Za-z0-9]+", str(name))
    return [p.lower() for p in parts if p]


def class_stem(name: str) -> str:
    """The meaningful tail of a class name, for cross-source comparison.

    `ErpProduct` -> `product`, `PimProduct` -> `product`, `Customer` ->
    `customer`. A leading vendor/export word is ignored; the rest of the words
    are kept so `OrderItem` does not collapse into `Order`.
    """
    words = [w for w in _tokens(name) if w not in _VENDOR_WORDS]
    return "_".join(words) if words else "_".join(_tokens(name))


def name_similarity(a: str, b: str) -> float:
    """How likely two class names are the same concept, before seeing data."""
    low_a, low_b = a.lower(), b.lower()
    if low_a == low_b:
        return 0.95
    if class_stem(a) == class_stem(b):
        return 0.70
    return 0.0


def _keys(graph, source: str, cls: str, limit: int = 5000) -> set[str]:
    code = graph.class_code(cls, source)
    if code is None:
        return set()
    return {r[0] for r in graph.sql(
        "SELECT nkey FROM nodes WHERE source_id = ? AND class = ? LIMIT ?",
        [source, code, limit])}


def _upsert(graph, candidate: Candidate) -> None:
    graph.con.execute(
        "INSERT INTO entity_links(a_source, a_class, a_key, b_source, b_class,"
        " b_key, method, confidence, status) VALUES (?,?,?,?,?,?,?,?,'proposed')"
        " ON CONFLICT DO NOTHING",
        [candidate.a_source, candidate.a_class, candidate.a_key,
         candidate.b_source, candidate.b_class, candidate.b_key,
         candidate.method, candidate.confidence])


def resolve(graph, min_confidence: float = 0.5,
            max_candidates: int = 2000,
            min_overlap_ratio: float = 0.2) -> list[Candidate]:
    """Find and store cross-source identity candidates.

    Two classes are compared when their names match exactly (0.95) or share the
    same meaningful stem (0.70). The confidence is lowered when the shared keys
    are only a small part of either class, because a handful of overlapping
    ids is a coincidence more often than an identity.

    Returns the candidates that were stored (or already present). No node is
    merged; `entity_links` is a proposal table.
    """
    classes = [(r[0], r[1]) for r in graph.sql(
        "SELECT source_id, name FROM classes ORDER BY source_id, name")]
    found: list[Candidate] = []
    for i in range(len(classes)):
        a_source, a_class = classes[i]
        for j in range(i + 1, len(classes)):
            b_source, b_class = classes[j]
            if a_source == b_source:
                continue                       # same source is not cross-source
            base = name_similarity(a_class, b_class)
            if base <= 0:
                continue
            a_keys = _keys(graph, a_source, a_class)
            b_keys = _keys(graph, b_source, b_class)
            if not a_keys or not b_keys:
                continue
            shared = a_keys & b_keys
            if not shared:
                continue
            ratio = len(shared) / min(len(a_keys), len(b_keys))
            if ratio < min_overlap_ratio:
                continue
            confidence = round(base * (0.5 + 0.5 * ratio), 4)
            if confidence < min_confidence:
                continue
            # Deterministic output and order-independent table identity.
            if (b_source, b_class) < (a_source, a_class):
                a_source, a_class, b_source, b_class = (
                    b_source, b_class, a_source, a_class)
                a_keys, b_keys, shared = b_keys, a_keys, shared
            for key in sorted(shared):
                candidate = Candidate(
                    a_source, a_class, key, b_source, b_class, key,
                    "same_key+name_similarity", confidence,
                    len(shared), len(a_keys), len(b_keys))
                _upsert(graph, candidate)
                found.append(candidate)
                if len(found) >= max_candidates:
                    return found
    return found


def candidates(graph, status: str | None = "proposed",
               min_confidence: float = 0.0) -> list[dict]:
    """Stored candidates, newest table order is not meaningful; sorted for a
    stable UI."""
    sql = ("SELECT a_source, a_class, a_key, b_source, b_class, b_key,"
           " method, confidence, status FROM entity_links")
    where, args = [], []
    if status:
        where.append("status = ?")
        args.append(status)
    if min_confidence:
        where.append("confidence >= ?")
        args.append(min_confidence)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a_source, a_class, a_key, b_source, b_class, b_key"
    keys = ("a_source", "a_class", "a_key", "b_source", "b_class", "b_key",
            "method", "confidence", "status")
    return [dict(zip(keys, row)) for row in graph.sql(sql, args)]


def explain(graph, source: str, cls: str, key: str) -> dict:
    """What else in the graph claims to be the same thing?

    Returns both directions so a caller does not have to know which side of the
    link its entity was stored on.
    """
    rows = graph.sql(
        "SELECT a_source, a_class, a_key, b_source, b_class, b_key, method,"
        " confidence, status FROM entity_links"
        " WHERE (a_source = ? AND a_class = ? AND a_key = ?)"
        "    OR (b_source = ? AND b_class = ? AND b_key = ?)"
        " ORDER BY confidence DESC",
        [source, cls, key, source, cls, key])
    keys = ("a_source", "a_class", "a_key", "b_source", "b_class", "b_key",
            "method", "confidence", "status")
    matches = []
    for row in rows:
        item = dict(zip(keys, row))
        mine = (item["a_source"] == source and item["a_class"] == cls
                and item["a_key"] == key)
        other = {}
        if mine:
            other["source"] = item["b_source"]
            other["class"] = item["b_class"]
            other["key"] = item["b_key"]
        else:
            other["source"] = item["a_source"]
            other["class"] = item["a_class"]
            other["key"] = item["a_key"]
        matches.append({"other": other, "method": item["method"],
                        "confidence": item["confidence"],
                        "status": item["status"]})
    return {"source": source, "class": cls, "key": key, "matches": matches}


def approve(graph, source: str, cls: str, key: str,
            other_source: str, other_class: str, other_key: str) -> int:
    """Mark one candidate approved (the review gate calls this after a human
    decision). The nodes still stay separate; only the link becomes trusted."""
    return graph.sql(
        "UPDATE entity_links SET status = 'approved'"
        " WHERE ((a_source = ? AND a_class = ? AND a_key = ? AND b_source = ?"
        "         AND b_class = ? AND b_key = ?)"
        "     OR (a_source = ? AND a_class = ? AND a_key = ? AND b_source = ?"
        "         AND b_class = ? AND b_key = ?))",
        [source, cls, key, other_source, other_class, other_key,
         other_source, other_class, other_key, source, cls, key]) or 0
