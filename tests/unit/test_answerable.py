"""The answerable verdict: yes / partial / no, with a reason.

Research (docs/research/2026/04_context.md): with insufficient context,
models guess instead of declining; one model's wrong answers rose from 10.2%
to 66.1%. The data.world ontology check turned errors into "I don't know".
So every pack and every agent answer carries an explicit verdict, and a "no"
names the nearest metric the user could ask about instead.
"""

from __future__ import annotations

import pytest

from context.question import answerable_verdict, nearest_metric

DEFS = [
    {"name": "revenue", "title": "Revenue", "status": "approved",
     "synonyms": ["sales"], "description": "Net revenue from completed orders."},
    {"name": "order_volume", "title": "Order volume", "status": "approved",
     "synonyms": [], "description": "Number of completed orders."},
    {"name": "refund_rate", "title": "Refund rate", "status": "draft",
     "synonyms": [], "description": "Refunded revenue over gross revenue."},
]


def test_yes_when_metric_measured_and_coverage_high():
    v = answerable_verdict(chosen=DEFS[0], coverage=100.0, missing=[],
                           has_current=True, has_prior=True)
    assert v["verdict"] == "yes"
    assert "revenue" in v["reason"]
    assert v["nearest_metric"] is None


def test_no_when_no_metric_matches_and_nearest_is_suggested():
    v = answerable_verdict(chosen=None, coverage=0.0, missing=[],
                           has_current=False, has_prior=False,
                           question="How many orders did we get?",
                           candidates=DEFS)
    assert v["verdict"] == "no"
    assert v["nearest_metric"] == "order_volume"
    assert "order_volume" in v["reason"]


def test_no_when_metric_is_not_approved():
    v = answerable_verdict(chosen=DEFS[2], coverage=90.0, missing=[],
                           has_current=True, has_prior=True)
    assert v["verdict"] == "no"
    assert "draft" in v["reason"]


def test_no_when_nothing_was_measured():
    v = answerable_verdict(chosen=DEFS[0], coverage=40.0, missing=["metric"],
                           has_current=False, has_prior=False)
    assert v["verdict"] == "no"
    assert "measured" in v["reason"]


def test_partial_when_there_is_no_prior_period():
    v = answerable_verdict(chosen=DEFS[0], coverage=100.0, missing=[],
                           has_current=True, has_prior=False)
    assert v["verdict"] == "partial"
    assert "prior" in v["reason"]


@pytest.mark.parametrize("coverage", [0.0, 50.0, 74.9])
def test_partial_when_coverage_is_low(coverage):
    v = answerable_verdict(chosen=DEFS[0], coverage=coverage,
                           missing=["source_row", "relationship"],
                           has_current=True, has_prior=True)
    assert v["verdict"] == "partial"
    assert "source_row" in v["reason"]


def test_outside_scope_is_no_even_if_measurable():
    v = answerable_verdict(chosen=DEFS[0], coverage=100.0, missing=[],
                           has_current=True, has_prior=True,
                           allowed=["order_volume"])
    assert v["verdict"] == "no"
    assert "scope" in v["reason"]


@pytest.mark.parametrize("question, expected", [
    ("total sales last month", "revenue"),            # synonym
    ("how many orders were placed", "order_volume"),  # description/title word
    ("net revenue trend", "revenue"),
    ("weather in Paris", None),                       # nothing related
])
def test_nearest_metric(question, expected):
    assert nearest_metric(question, DEFS) == expected


def test_nearest_metric_ignores_unapproved_metrics():
    assert nearest_metric("refund rate", DEFS) is None


def test_nearest_metric_handles_empty_input():
    assert nearest_metric("", DEFS) is None
    assert nearest_metric("revenue", []) is None
