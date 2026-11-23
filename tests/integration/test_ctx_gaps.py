"""Questions Strata could not answer: logged with the reason, grouped, ranked,
each with a fix a person can apply."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import ctx_routes
from api.server import create_app
from api.service import MiddleLayer
from context import engine as ctx
from context import gaps
from ontology import simple
from tests.integration.test_declared_links import make_shop


@pytest.fixture
def shop(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


def test_a_question_about_nothing_in_the_ontology_names_the_words(shop):
    layer, oid = shop
    why = gaps.classify(ctx.build(layer, oid, "What is the weather in Paris?"))
    assert why[0] == "unknown_words" and "weather" in why[1] and "Paris" in why[1]


def test_an_answered_question_is_not_a_gap(shop):
    layer, oid = shop
    assert gaps.classify(ctx.build(layer, oid, "How many orders?")) is None
    assert gaps.classify(ctx.build(layer, oid, "What did Customer 17 order?")) is None


def test_a_number_nothing_could_compute_is_a_gap(shop):
    layer, oid = shop
    # No certified metric, no AI to write a query, and not a shape Strata counts itself.
    built = ctx.build(layer, oid, "What is the average basket margin per customer?")
    assert gaps.classify(built)[0] in ("no_number", "unknown_words")


def test_ai_saying_not_enough_and_unverified_numbers_are_gaps():
    base = {"question": "Why did sales drop?", "steps": {
        "understand": {"things": [{"name": "Order", "why": "named in the question"}], "fields": [],
                       "records": [], "unknown": []},
        "facts": {"table": None, "quarantined": []}, "answer": {}}}
    base["steps"]["answer"] = {"status": "not_enough", "text": "no data on returns"}
    assert gaps.classify(base) == ("not_enough", "no data on returns")
    base["steps"]["answer"] = {"status": "unverified", "warning": "states 12"}
    assert gaps.classify(base) == ("unverified", "states 12")


def test_similar_questions_group_and_rank_by_count_with_a_fix(shop):
    layer, oid = shop
    for q in ["What is the weather in Paris?", "Weather Paris what is?", "What is the weather in Paris"]:
        gaps.record(layer.graph, oid, ctx.build(layer, oid, q))
    gaps.record(layer.graph, oid, ctx.build(layer, oid, "Show me the zorblax"))
    out = gaps.groups(layer.graph, oid)
    assert out["total"] == 4
    top = out["groups"][0]
    assert top["count"] == 3 and top["reason"] == "unknown_words" and top["sources"] == ["context"]
    assert top["fix"]["action"] == "note" and "means" in top["fix"]["note"]
    assert out["groups"][1]["count"] == 1
    left = gaps.dismiss(layer.graph, oid, top["key"])
    assert left["total"] == 1
    with pytest.raises(KeyError):
        gaps.dismiss(layer.graph, oid, top["key"])


def test_an_agent_that_cannot_answer_logs_a_gap_but_not_for_scope(shop):
    from agent import onto_agents, onto_runner
    layer, oid = shop
    agents = onto_agents.listing(layer, oid)["builtin"]
    metric = next(a for a in agents if a["kind"] == "metric")
    out = onto_runner.run(layer, metric, "What is the total weather of Paris?")
    assert out["answerable"]["verdict"] == "no"
    g = gaps.groups(layer.graph, oid)["groups"]
    assert g and g[0]["reason"] == "agent_refused" and g[0]["sources"] == [f"agent:{metric['name']}"]


def test_logging_never_stops_an_answer(shop, monkeypatch):
    layer, oid = shop
    monkeypatch.setattr(gaps, "ensure", lambda g: (_ for _ in ()).throw(RuntimeError("disk full")))
    gaps.log(layer.graph, oid, "x", "unknown_words")          # no exception


def test_gaps_through_the_api(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx_routes, "ai_client", lambda: None)
    app = create_app(tmp_path / "graphs" / "g.duckdb", warm=False)
    with TestClient(app) as c:
        layer = c.app.state.platform.layer
        layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
        oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        out = c.post(f"/api/ctx/{oid}/build", json={"question": "What is the weather in Paris?"}).json()
        assert out["gap"]["reason"] == "unknown_words"
        assert c.post(f"/api/ctx/{oid}/build", json={"question": "How many orders?"}).json()["gap"] is None
        listing = c.get(f"/api/ctx/{oid}/gaps").json()
        assert listing["total"] == 1
        key = listing["groups"][0]["key"]
        assert c.delete(f"/api/ctx/{oid}/gaps", params={"key": key}).json()["total"] == 0
        assert c.delete(f"/api/ctx/{oid}/gaps", params={"key": key}).status_code == 404
        assert c.get("/api/ctx/nope/gaps").status_code == 404
