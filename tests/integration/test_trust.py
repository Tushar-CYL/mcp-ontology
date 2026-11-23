"""Why each layer can be trusted, from two sides at once:

* technical proof - how the layer was built and what the data itself checked;
* business knowledge - what the company's own people added (rules,
  definitions, approvals, owners, trusted reports), who, and when; and what
  is still missing from them.

Everything is read from what the layers already hold: nothing is invented,
and a layer with nothing from people says so instead of looking finished."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import trust
from api.server import create_app
from api.service import MiddleLayer
from context import gaps
from context import report_check as rc
from ontology import review as rv
from ontology import simple
from semantic import model as sem
from tests.integration.simple_fixtures import FakeAI, load
from tests.integration.test_declared_links import make_shop

LIES = {"model": "reference", "status_code": "reference"}


@pytest.fixture
def iot(tmp_path):
    layer = load(tmp_path, ["iot"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI(lies=LIES))["ontology"]
    return layer, oid


@pytest.fixture
def shop(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


def _step(side, word):
    return next(s for s in side["steps"] if word in s["title"].lower())


def _count(side, word):
    return next(c["value"] for c in side["counts"] if word in c["label"].lower())


# ---------------------------------------------------------------- ontology
def test_ontology_proof_is_the_data_checks(iot):
    layer, oid = iot
    v = simple.view(layer.graph, oid)
    t = trust.layer_trust(layer, oid, "ontology")
    proof = t["proof"]
    assert f"{v['summary']['confirmed_pct']}%" in proof["headline"]
    checked = _step(proof, "check")
    assert str(v["summary"]["checks"]["verified"]) in checked["text"]
    assert checked["status"] in ("ok", "warn")
    assert all(s["status"] in ("ok", "warn", "todo") for s in proof["steps"])


def test_ontology_with_nothing_from_people_says_so_and_what_is_missing(iot):
    layer, oid = iot
    people = trust.layer_trust(layer, oid, "ontology")["people"]
    assert _count(people, "set by") == 0 and _count(people, "rule") == 0
    assert people["recent"] == []
    review = next(m for m in people["missing"] if m["where"] == "review")
    assert review["text"].startswith("2 ")                  # the two claims only a person can settle
    assert any(m["where"] == "notes" for m in people["missing"])
    assert any(m["where"] == "rules" for m in people["missing"])


def test_ontology_counts_active_business_rules_on_both_sides(shop):
    from ontology import business_rules as br
    layer, oid = shop
    r = br.add(layer, oid, "Every Order Customer id must point to an existing Customer", by="ops")
    br.activate(layer, oid, r["id"], by="meera", owner="Sales Ops")
    t = trust.layer_trust(layer, oid, "ontology")
    step = _step(t["proof"], "business rules")
    assert step["status"] == "warn" and "1 broken" in step["text"]     # 10 orders point at nothing
    assert _count(t["people"], "checked business rules") == 1
    assert any("Sales Ops" in x["text"] and x["by"] == "meera" for x in t["people"]["recent"])
    assert not any(m["where"] == "rules" for m in t["people"]["missing"])


def test_ontology_people_counts_and_recent_name_who_did_what(iot):
    layer, oid = iot
    v = simple.view(layer.graph, oid)
    field = next(f for t in v["things"] for f in t["fields"] if f["review"] == "confirmed")
    simple.edit_field(layer, oid, field["key"], by="asha", label="Reading time")
    simple.add_context(layer, oid, "Readings below zero are sensor faults.", by="ravi")
    simple.add_context(layer, oid, "Readings below zero are sensor faults.", by="ravi")   # said twice
    open_ = rv.queue(layer.graph, oid)["cards"]
    rv.decide(layer, oid, [open_[0]["target"]], "approved", by="meera")
    people = trust.layer_trust(layer, oid, "ontology")["people"]
    assert _count(people, "set by") == 1
    assert _count(people, "rule") == 2
    assert _count(people, "approved") == 1
    who = {r["by"] for r in people["recent"]}
    assert {"asha", "ravi", "meera"} <= who
    assert sum("sensor faults" in r["text"] for r in people["recent"]) == 1   # shown once
    approved = next(r for r in people["recent"] if r["by"] == "meera")
    assert open_[0]["title"].replace(" . ", " . ") in approved["text"]        # named as on screen, not a raw key
    assert "column:" not in approved["text"] and "link:" not in approved["text"]
    assert not any(m["where"] == "notes" for m in people["missing"])


# ---------------------------------------------------------------- graph
def test_graph_proof_names_broken_links_and_people_removed_links(shop):
    layer, oid = shop
    t = trust.layer_trust(layer, oid, "graph")
    broken = _step(t["proof"], "line")
    assert broken["status"] == "warn" and broken["text"].startswith("10 ")
    assert _count(t["people"], "removed") == 0
    link = simple.view(layer.graph, oid)["links"][0]
    rv.decide(layer, oid, [rv.link_target(link)], "rejected", by="ops")
    t = trust.layer_trust(layer, oid, "graph")
    assert _count(t["people"], "removed") == 1
    assert any(r["by"] == "ops" for r in t["people"]["recent"])


# ---------------------------------------------------------------- semantic
def test_semantic_proof_and_people_follow_certify_and_verified_questions(shop):
    layer, oid = shop
    sem.propose(layer, oid)
    t = trust.layer_trust(layer, oid, "semantic")
    assert _count(t["people"], "certified") == 0
    assert any(m["where"] == "semantic" for m in t["people"]["missing"])
    assert _step(t["proof"], "verified")["status"] == "todo"

    sem.certify(layer, oid, "total_net_amount", by="cfo", owner="Finance")
    missing = [m["text"] for m in trust.layer_trust(layer, oid, "semantic")["people"]["missing"]]
    assert any("nobody has certified" in m for m in missing)        # the rest still wait for a person
    assert any("No verified question" in m for m in missing)
    sem.add_verified(layer, oid, "What is our net amount?", "total_net_amount")
    t = trust.layer_trust(layer, oid, "semantic")
    assert _count(t["people"], "certified") == 1
    assert any("Finance" in r["text"] and r["by"] == "cfo" for r in t["people"]["recent"])
    verified = _step(t["proof"], "verified")
    assert verified["status"] == "ok" and verified["text"].startswith("1 of 1")


# ---------------------------------------------------------------- context
def test_context_trust_reads_report_checks_and_unanswered_questions(shop):
    layer, oid = shop
    t = trust.layer_trust(layer, oid, "context")
    assert any(m["where"] == "report_check" for m in t["people"]["missing"])
    assert _step(t["proof"], "report")["status"] == "todo"

    rc.add(layer.graph, oid, [{"question": "How many orders?", "expected": "1000", "source": "Q3 sales pack"}])
    gaps.log(layer.graph, oid, "What is the carbon footprint?", "not_enough")
    t = trust.layer_trust(layer, oid, "context")
    assert _count(t["people"], "report") == 1
    assert any("Q3 sales pack" in r["text"] for r in t["people"]["recent"])
    assert not any(m["where"] == "report_check" for m in t["people"]["missing"])
    assert _step(t["proof"], "unanswered")["text"].startswith("1 ")


def test_unknown_layer_is_refused(shop):
    layer, oid = shop
    with pytest.raises(ValueError):
        trust.layer_trust(layer, oid, "nope")


def test_trust_route(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setenv("STRATA_DATA_ROOTS", "")
    app = create_app(tmp_path / "g.duckdb", warm=False)
    with TestClient(app) as c:
        layer = app.state.platform.layer if hasattr(app.state, "platform") else None
        if layer is None:
            pytest.skip("no platform handle on this app")
        layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
        oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        r = c.get(f"/api/trust/{oid}/ontology")
        assert r.status_code == 200 and r.json()["proof"]["steps"] and "people" in r.json()
        assert c.get(f"/api/trust/{oid}/nope").status_code in (400, 422)
