"""Layer 4: make the answer fit, and never lose where a fact came from.

An AI can only read so much. Given everything, it does worse than given a
small correct bundle - so something must be dropped, and WHICH something
is the whole design.

Two rules, in order:
  a measurement outranks an inference of the same weight
  a fact that does not fit is dropped whole, never truncated

The second matters more than it looks. Half a sentence of evidence still
reads as complete, and a reader cannot tell it was cut.
"""

from __future__ import annotations

from dataclasses import dataclass

# Measured beats derived beats external, at equal weight. When room runs
# out, the thing we are least sure of goes first.
RANK = {"measured": 0, "derived": 1, "external": 2}


@dataclass
class Fact:
    text: str
    provenance: str = "measured"
    weight: float = 1.0
    when: str | None = None
    # Where the fact came from: `table:column:key`, a node id, a metric name.
    # A citation is not the same thing as a provenance label: one tells you
    # which row, the other tells you whether we measured or guessed.
    citation: str | None = None


def pack(facts: list[Fact], max_chars: int) -> tuple[list[Fact], list[Fact]]:
    """Return (kept, dropped).

    A measurement outranks a guess of equal weight. A fact that does not fit is
    dropped whole, never truncated. `dropped` is returned, not discarded: the
    answer must be able to say what it left out and why.
    """
    if not facts:
        return [], []
    ordered = sorted(
        enumerate(facts),
        key=lambda p: (-p[1].weight, RANK.get(p[1].provenance, 9), p[0]))

    kept, dropped, used = [], [], 0
    for idx, fact in ordered:
        size = len(fact.text)
        if used + size > max_chars:
            dropped.append((idx, fact))
            continue          # skip it, keep looking: a later fact may fit
        kept.append((idx, fact))
        used += size
    # Back into the order the caller gave them, which is the order that
    # reads as an argument rather than a ranked list.
    kept_facts = [f for _, f in sorted(kept, key=lambda p: p[0])]
    dropped_facts = [f for _, f in sorted(dropped, key=lambda p: p[0])]
    return kept_facts, dropped_facts


def fit(facts: list[Fact], max_chars: int) -> list[Fact]:
    """The most valuable facts that fit, in their original order."""
    kept, _ = pack(facts, max_chars)
    return kept


def render(facts: list[Fact]) -> str:
    """Plain text, with the provenance of every line visible.

    A reader must be able to tell a measurement from an inference without
    asking. That is the difference between an answer someone can act on and
    one they have to go and check.
    """
    lines = []
    for f in facts:
        tag = {"measured": "measured", "derived": "derived (a guess)",
               "external": "external"}.get(f.provenance, f.provenance)
        when = f"  as at {f.when}" if f.when else ""
        cite = f"  cite: {f.citation}" if f.citation else ""
        lines.append(f"- {f.text}\n      [{tag}]{when}{cite}")
    return "\n".join(lines)
