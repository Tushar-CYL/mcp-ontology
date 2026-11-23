"""Impact analysis: before a person changes a field, a metric, a thing or a
rule, Strata lists everything across the layers that depends on it - links
and connections, metrics and their verified questions, business rules, report
checks, agents - and who to tell (the owners). Read only: nothing changes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent import onto_agents as oa
from api.server import create_app
from api.service import MiddleLayer
from context import report_check as rc
from ontology import business_rules as br
from ontology import impact
from ontology import simple
from semantic import model as sem
from tests.integration.test_business_rules import _shop_with_problems


@pytest.fixture
def shop(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(_shop_with_problems(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    sem.certify(layer, oid, "total_net_amount", by="cfo", owner="Finance")
    sem.add_verified(layer, oid, "What is our net amount?", "total_net_amount")
    return layer, oid


def _group(out, layer_name):
    return next((g for g in out["groups"] if g["layer"] == layer_name), {"items": []})


def _texts(out, layer_name):
    return [i["text"] for i in _group(out, layer_name)["items"]]


def test_a_metric_field_lists_its_metrics_questions_rules_and_owner(shop):
    layer, oid = shop
    br.add(layer, oid, "Net amount must be positive", by="ravi")
    out = impact.impact(layer, oid, "field", "shop.orders.net_amount")
    assert out["target"]["title"] == "Order . Net amount"
    sem_texts = " ".join(_texts(out, "semantic"))
    assert "Total Net Amount" in sem_texts or "total_net_amount" in sem_texts.lower().replace(" ", "_")
    assert "What is our net amount?" in sem_texts                       # the verified question
    assert any("must be positive" in t for t in _texts(out, "rules"))
    assert "Finance" in out["tell"]
    assert out["total"] == sum(len(g["items"]) for g in out["groups"])
    assert out["summary"].startswith("Changing Order . Net amount affects")


def test_a_reference_field_lists_its_link_and_connections(shop):
    layer, oid = shop
    out = impact.impact(layer, oid, "field", "shop.orders.customer_id")
    assert any("Customer" in t for t in _texts(out, "ontology"))         # the link Order -> Customer
    graph = " ".join(_texts(out, "graph"))
    assert "990" in graph                                                # real connections that ride on it
    # Every metric that joins orders to customers depends on the key too.
    assert any("Net Amount" in t or "net amount" in t.lower() for t in _texts(out, "semantic"))


def test_a_field_nothing_uses_says_so(shop):
    layer, oid = shop
    out = impact.impact(layer, oid, "field", "shop.customer.email")
    assert out["total"] == 0 or all(g["layer"] in ("agents",) for g in out["groups"])
    assert "nothing" in out["summary"].lower() or out["total"] > 0


def test_a_metric_lists_questions_report_checks_conflicting_rules_and_agents(shop):
    layer, oid = shop
    rule = br.add(layer, oid, "Cancelled orders do not count")
    rc.add(layer.graph, oid, [{"question": "What is the total net amount?", "expected": "1", "source": "Q3 pack"}])
    oa.sync_builtins(layer, oid)
    out = impact.impact(layer, oid, "metric", "total_net_amount")
    assert "What is our net amount?" in " ".join(_texts(out, "semantic"))
    assert any(rule["text"] in t for t in _texts(out, "rules"))          # the rule it ignores
    assert any("Q3 pack" in t for t in _texts(out, "context"))
    assert _texts(out, "agents")                                        # built-in agents use certified metrics
    assert "Finance" in out["tell"]


def test_a_thing_and_a_rule(shop):
    layer, oid = shop
    rule = br.add(layer, oid, "Cancelled orders do not count")
    thing = impact.impact(layer, oid, "thing", "Order")
    assert thing["total"] > 0 and _texts(thing, "ontology") and _texts(thing, "semantic")
    r = impact.impact(layer, oid, "rule", rule["id"])
    assert any("Total Net Amount" in t or "net amount" in t.lower() for t in _texts(r, "semantic"))


def test_unknown_targets_are_refused(shop):
    layer, oid = shop
    with pytest.raises(KeyError):
        impact.impact(layer, oid, "field", "shop.nope.x")
    with pytest.raises(ValueError):
        impact.impact(layer, oid, "planet", "x")


def test_impact_api(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setenv("STRATA_DATA_ROOTS", "")
    app = create_app(tmp_path / "g.duckdb", warm=False)
    with TestClient(app) as c:
        layer = app.state.platform.layer
        layer.add_source(str(_shop_with_problems(tmp_path / "shop.db")), source="shop")
        oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        r = c.get(f"/api/impact/{oid}", params={"kind": "field", "key": "shop.orders.customer_id"})
        assert r.status_code == 200 and r.json()["groups"]
        assert c.get(f"/api/impact/{oid}", params={"kind": "field", "key": "nope"}).status_code == 404
        assert c.get(f"/api/impact/{oid}", params={"kind": "planet", "key": "x"}).status_code == 400
