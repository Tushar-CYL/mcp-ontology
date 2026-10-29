"""Layer 4: pack an answer that fits, and that says where every fact came from."""

from __future__ import annotations

from context.budget import Fact, fit


def f(text, prov="measured", weight=1.0):
    return Fact(text=text, provenance=prov, weight=weight)


class TestBudget:
    def test_everything_fits_when_there_is_room(self):
        facts = [f("a"), f("b")]
        assert len(fit(facts, max_chars=1000)) == 2

    def test_the_least_important_is_dropped_first(self):
        # Room for exactly one of them, so a choice is actually forced.
        kept = fit([f("keep", weight=10), f("drop", weight=0.1)], max_chars=5)
        assert [x.text for x in kept] == ["keep"]

    def test_nothing_exceeds_the_budget(self):
        facts = [f("x" * 50, weight=i) for i in range(20)]
        kept = fit(facts, max_chars=120)
        assert sum(len(x.text) for x in kept) <= 120

    def test_a_measured_fact_outranks_a_guess_of_equal_weight(self):
        """When something must go, drop the inference, not the measurement."""
        kept = fit([f("guess", "derived"), f("fact", "measured")], max_chars=5)
        assert [x.text for x in kept] == ["fact"]

    def test_an_empty_bundle_is_allowed(self):
        assert fit([], max_chars=100) == []

    def test_a_single_fact_too_large_is_dropped_not_truncated(self):
        """A half-sentence of evidence is worse than none: it reads as
        complete and is not."""
        assert fit([f("x" * 500)], max_chars=100) == []

    def test_order_is_stable_for_equal_facts(self):
        facts = [f("a"), f("b"), f("c")]
        assert [x.text for x in fit(facts, 1000)] == ["a", "b", "c"]


class TestProvenanceSurvives:
    def test_every_kept_fact_still_says_where_it_came_from(self):
        kept = fit([f("a", "measured"), f("b", "derived")], max_chars=1000)
        assert {x.provenance for x in kept} == {"measured", "derived"}

    def test_rendering_labels_a_guess(self):
        from context.budget import render
        out = render([f("teams own services", "derived")])
        assert "derived" in out.lower() or "guess" in out.lower()
