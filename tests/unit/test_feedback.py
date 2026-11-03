"""Phase 6 (Learn): corrections become review proposals, never auto-changes.

"This answer was wrong" from a person or an agent is valuable, and also the
easiest way to poison a governed layer. So feedback lands in the human review
queue with everything a steward needs, and nothing is changed until they
decide.
"""

from __future__ import annotations

import pytest

from knowledge_graph.store import open_graph
from review import store as review
from semantic import feedback


@pytest.fixture
def graph(tmp_path):
    g = open_graph(str(tmp_path / "feedback.duckdb"))
    yield g
    g.close()


def _submit(graph, **overrides):
    payload = {"source": "shop", "question": "Why did revenue fall?",
               "answer": "Revenue fell 8%.", "correction": "Refunds were "
               "double counted in October.", "kind": "wrong_number",
               "metric": "revenue", "agent_id": "agent_1"}
    payload.update(overrides)
    return feedback.submit(graph, **payload)


def test_a_correction_becomes_a_pending_review_item(graph):
    item = _submit(graph)
    assert item["status"] == "proposed"
    pending = review.pending(graph, source="shop")
    assert [p["item_id"] for p in pending] == [item["id"]]


def test_metric_corrections_go_to_the_semantic_queue(graph):
    assert _submit(graph, kind="wrong_number")["review_kind"] == "semantic"
    assert _submit(graph, kind="wrong_definition",
                   question="q2")["review_kind"] == "semantic"
    assert _submit(graph, kind="missing_context",
                   question="q3")["review_kind"] == "context"


def test_the_item_carries_what_a_steward_needs(graph):
    item = _submit(graph)
    listed = feedback.list_feedback(graph, "shop")[0]
    assert listed["id"] == item["id"]
    for field in ("question", "answer", "correction", "kind", "metric",
                  "agent_id"):
        assert listed[field], field
    assert listed["status"] == "proposed"


@pytest.mark.parametrize("field, value, message", [
    ("correction", "  ", "correction"),
    ("question", "", "question"),
    ("kind", "rude", "kind"),
    ("source", "", "source"),
])
def test_bad_feedback_is_rejected(graph, field, value, message):
    with pytest.raises(ValueError, match=message):
        _submit(graph, **{field: value})


def test_the_same_correction_twice_is_one_item(graph):
    first = _submit(graph)
    second = _submit(graph)
    assert first["id"] == second["id"]
    assert len(feedback.list_feedback(graph, "shop")) == 1


def test_a_steward_decides_and_the_decision_is_audited(graph):
    item = _submit(graph)
    decided = feedback.decide(graph, item["id"], "approved",
                              note="Confirmed; fix refund join.")
    assert decided["status"] == "approved"
    assert feedback.list_feedback(graph, "shop", pending_only=True) == []
    trail = review.audit(graph, item["id"])
    assert trail and trail[-1]["decision"] == "approved"


def test_an_invalid_decision_is_rejected(graph):
    item = _submit(graph)
    with pytest.raises(ValueError):
        feedback.decide(graph, item["id"], "maybe")


def test_feedback_never_changes_the_metric(graph):
    from semantic import definitions as metric_defs
    before = metric_defs.get_definition(graph, "revenue", "shop")
    _submit(graph)
    assert metric_defs.get_definition(graph, "revenue", "shop") == before


# --------------------------------------------------------------- steward
@pytest.fixture
def metric_graph(graph):
    from semantic import definitions as metric_defs
    for name, title in (("revenue", "Revenue"), ("order_volume", "Order volume")):
        metric_defs.upsert_metric(graph, source="shop", name=name, title=title,
                                  base_sql="SELECT 1 AS x", value_expr="SUM(x)")
    return graph


@pytest.mark.parametrize("text, synonym, metric", [
    ('"sales" means revenue', "sales", "revenue"),
    ("turnover means Revenue", "turnover", "revenue"),
    ("add synonym orders count for order volume", "orders count", "order_volume"),
    ("Use 'net sales' as a synonym for revenue", "net sales", "revenue"),
])
def test_steward_parses_synonym_proposals(metric_graph, text, synonym, metric):
    item = feedback.propose(metric_graph, "shop", text, agent_id="steward_1")
    assert item["kind"] == "proposal"
    assert item["proposal"] == {"type": "synonym", "synonym": synonym,
                                "metric": metric}
    assert item["status"] == "proposed"


def test_a_free_text_proposal_is_kept_as_text(metric_graph):
    item = feedback.propose(metric_graph, "shop",
                            "Orders should link to warehouses.")
    assert item["proposal"] == {"type": "note",
                                "text": "Orders should link to warehouses."}


def test_a_synonym_for_an_unknown_metric_becomes_a_note(metric_graph):
    item = feedback.propose(metric_graph, "shop", '"margin" means profit')
    assert item["proposal"]["type"] == "note"


def test_proposing_never_changes_the_metric(metric_graph):
    from semantic import definitions as metric_defs
    feedback.propose(metric_graph, "shop", '"sales" means revenue')
    assert metric_defs.get_definition(metric_graph, "revenue", "shop")["synonyms"] == []


def test_approving_a_synonym_proposal_applies_it(metric_graph):
    from semantic import definitions as metric_defs
    item = feedback.propose(metric_graph, "shop", '"sales" means revenue')
    decided = feedback.decide(metric_graph, item["id"], "approved")
    assert decided["status"] == "approved"
    assert decided["applied"] == "synonym 'sales' added to revenue"
    assert metric_defs.get_definition(metric_graph, "revenue", "shop")["synonyms"] == ["sales"]


def test_rejecting_a_synonym_proposal_applies_nothing(metric_graph):
    from semantic import definitions as metric_defs
    item = feedback.propose(metric_graph, "shop", '"sales" means revenue')
    decided = feedback.decide(metric_graph, item["id"], "rejected")
    assert decided.get("applied") is None
    assert metric_defs.get_definition(metric_graph, "revenue", "shop")["synonyms"] == []


def test_approving_a_clashing_synonym_reports_why_it_was_not_applied(metric_graph):
    from semantic import definitions as metric_defs
    metric_defs.set_synonyms(metric_graph, "order_volume", "shop", ["sales"])
    item = feedback.propose(metric_graph, "shop", '"sales" means revenue')
    decided = feedback.decide(metric_graph, item["id"], "approved")
    assert decided["status"] == "approved"
    assert decided["applied"].startswith("not applied:")


def test_empty_proposal_is_refused(metric_graph):
    with pytest.raises(ValueError, match="proposal"):
        feedback.propose(metric_graph, "shop", "   ")
