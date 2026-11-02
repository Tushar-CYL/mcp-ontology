"""Layer 4, the real thing: build the evidence pack an agent can cite.

The existing `context/budget.py` knows how to choose facts under a size limit.
This module decides *which* facts exist for a question: the entity, its
properties, its direct and indirect links, cross-source matches, data-quality
findings and review state — each with a provenance label and a citation.

It is deterministic on purpose. An LLM may phrase the final sentence, but the
facts must not move: if the answer changes between runs, no one can audit it.

The output envelope:

    {
      "focus":  {"source", "class", "key"},
      "answer": one deterministic sentence,
      "facts":  [{"text", "provenance", "weight", "citation", "as_of"}],
      "dropped":[{"text", "provenance", "weight"}],
      "sources": [...],
      "review_pending": N,
      "budget_chars": N, "chars": N,
      "as_of": ..., "latency_ms": ...
    }
"""

from __future__ import annotations

import re
import time

from context.budget import Fact, pack, render
from knowledge_graph.build import row_for
from knowledge_graph.resolve import explain
from review import store as review


def _bundles(bundles):
    """Accept (source, schema, onto) tuples or dicts with those keys."""
    out = []
    for item in bundles:
        if isinstance(item, dict):
            out.append((item["source"], item["schema"], item["onto"]))
        else:
            out.append(tuple(item))
    return out


def _bundle_for(bundles, source: str):
    for src, schema, onto in bundles:
        if src == source:
            return schema, onto
    raise KeyError(f"unknown source {source!r}")


def _find_entity(graph, bundles, task: str):
    """Find the one thing the question is about.

    Deterministic and explainable: prefer `<Class> <key>` in the text, then a
    bare key that is unique across the graph. Never invent an entity.
    """
    tokens = [t for t in re.findall(r"[A-Za-z0-9_.\-]+", task)
              if len(t) > 0]
    # 1) a class name followed by one of its keys
    for source, schema, onto in bundles:
        for cls in onto.classes.values():
            if cls.name.lower() not in task.lower():
                continue
            for token in tokens:
                if graph.node_id(cls.name, token, source) is not None:
                    return source, cls.name, token
    # 2) any token that is a key of exactly one class across all sources
    hits = []
    for token in tokens:
        rows = graph.sql(
            "SELECT n.source_id, c.name, n.nkey FROM nodes n"
            " JOIN classes c ON c.code = n.class AND c.source_id = n.source_id"
            " WHERE n.nkey = ? LIMIT 5", [token])
        hits.extend(rows)
    if hit_parent := _unique(hits):
        return hit_parent
    raise ValueError(
        "could not find the thing this question is about; pass "
        "entity=(class, key, source) explicitly. "
        f"Tried tokens: {', '.join(tokens[:8]) or '(none)'}")


def _unique(hits):
    if not hits:
        return None
    if len(hits) == 1:
        return tuple(hits[0])
    return tuple(hits[0])       # deterministic; caller sees the focus


def build_context(graph, bundles, task: str = "",
                  entity: tuple[str, str, str] | None = None,
                  budget_chars: int = 1200,
                  as_of: str | None = None) -> dict:
    """Assemble a cited, budgeted evidence pack for one entity."""
    started = time.perf_counter()
    bundles = _bundles(bundles)
    if entity is not None:
        source, cls_name, key = entity
        source = str(source)
        key = str(key)
        if graph.node_id(cls_name, key, source) is None:
            raise ValueError(
                f"no {cls_name} {key!r} in source {source!r}")
    else:
        source, cls_name, key = _find_entity(graph, bundles, task)

    schema, onto = _bundle_for(bundles, source)
    cls = onto.classes[cls_name]
    facts: list[Fact] = []

    def add(text, provenance, weight, citation=None, when=None):
        facts.append(Fact(text, provenance, weight, when, citation))

    add(f"{cls_name} {key} exists in source {source}.",
        "measured", 10, citation=f"{cls.table}:{cls.key}")

    props = row_for(graph, schema, onto, cls_name, key, source=source)
    for name, value in list(props.items())[:8]:
        if value not in (None, ""):
            add(f"Its {name} is {value}.", "measured", 5,
                citation=f"{cls.table}.{name}")

    count = graph.count_class(cls_name, source)
    add(f"There are {count:,} {cls_name} records in this source.",
        "measured", 3, citation=f"nodes:{source}:{cls_name}")

    # Direct links, with the edge's own provenance. This is where a guessed
    # relationship must show up as a guess.
    direct: list[str] = []
    for rel in onto.relations.values():
        if rel.domain != cls_name:
            continue
        neighbours = graph.neighbours(cls_name, key, rel.name, source=source)
        for other_key, valid_from in list(neighbours.items())[:3]:
            direct.append(f"{rel.range}:{other_key}")
            when = None
            if valid_from is not None:
                when = str(valid_from)
            add(f"It links to {rel.range} {other_key} via '{rel.name}'.",
                rel.provenance, 4,
                citation=f"edge:{rel.name}:{other_key}", when=when)

    # Indirect neighbours are useful but weaker: derived, not measured.
    reached = graph.reach(cls_name, key, None, depth=2, source=source)
    for item in sorted(reached - set(direct))[:5]:
        kind, which = item.split(":", 1)
        add(f"It is connected to {kind} {which} (indirect).",
            "derived", 2, citation=f"reach:{item}")

    # Cross-source identity: useful only if it says how sure it is.
    match_info = explain(graph, source, cls_name, key)
    sources = {source}
    for match in match_info["matches"][:4]:
        other = match["other"]
        sources.add(other["source"])
        state = match["status"]
        add(f"Same {other['class']} {other['key']} appears in "
            f"{other['source']} (confidence {match['confidence']:.0%}, "
            f"{state}).",
            "measured" if state == "approved" else "derived", 4,
            citation=f"entity_links:{other['source']}:{other['class']}:"
                     f"{other['key']}")

    findings = graph.one(
        "SELECT count(*) FROM findings WHERE source_id = ?", [source]) or 0
    if findings:
        add(f"The source has {findings:,} recorded data-quality finding(s).",
            "derived", 2, citation=f"findings:{source}")

    waiting = review.pending(graph, kind="semantic", source=source)
    waiting += review.pending(graph, kind="context", source=source)
    if waiting:
        add(f"{len(waiting)} semantic/context proposal(s) still await review; "
            f"treat definitions in this answer accordingly.",
            "derived", 1, citation="review:pending")

    kept, dropped = pack(facts, budget_chars)
    text = render(kept)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "focus": {"source": source, "class": cls_name, "key": key},
        "answer": (f"{cls_name} {key} from {source}: "
                   f"{len(kept)} facts kept, {len(dropped)} dropped."),
        "facts": [
            {"text": f.text, "provenance": f.provenance,
             "weight": f.weight, "citation": f.citation,
             "as_of": f.when}
            for f in kept
        ],
        "dropped": [
            {"text": f.text, "provenance": f.provenance,
             "weight": f.weight}
            for f in dropped
        ],
        "sources": sorted(sources),
        "review_pending": len(waiting),
        "budget_chars": budget_chars,
        # The budget applies to fact text, the same unit `pack` uses; the
        # rendered string adds provenance tags, so it is reported separately.
        "chars": sum(len(f.text) for f in kept),
        "rendered_chars": len(text),
        "as_of": as_of,
        "latency_ms": latency_ms,
        "rendered": text,
    }
