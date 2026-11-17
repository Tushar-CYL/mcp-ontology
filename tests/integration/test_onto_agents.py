"""Agents of an ontology: built-ins worked out from the data (6 to 10, ready
to use, read-only), copies you can change, agents you create - and how each
kind answers, inside its scope, with numbers only from the data."""

from __future__ import annotations

import sqlite3

import pytest

from agent import catalog, onto_agents, onto_runner
from api.service import MiddleLayer
from ontology import simple
from semantic import model as sem
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("agents")
    db = make_amounts(tmp / "amounts.db")
    s = sqlite3.connect(db)
    s.execute("alter table customer add column email text")
    s.execute("update customer set email = 'c' || id || '@example.com'")
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    sem.certify(layer, oid, "total_gross_amount", owner="Finance")
    onto_agents.forget()
    return layer, oid, db


def _sql(db, q):
    return sqlite3.connect(db).execute(q).fetchone()[0]


def _names(layer, oid):
    v = simple.view(layer.graph, oid)
    out = {t["name"].lower() for t in v["things"]}
    for t in v["things"]:
        out |= {f["label"].lower() for f in t["fields"]}
    return out


# ------------------------------------------------------------- built-ins
def test_built_ins_come_from_the_data(shop):
    layer, oid, _ = shop
    agents = catalog.builtins(layer, oid)
    assert 6 <= len(agents) <= catalog.MAX_AGENTS
    keys = [a["key"] for a in agents]
    assert keys[:6] == ["guide", "investigator", "metric", "insight", "trust", "steward"]
    assert len(set(a["name"] for a in agents)) == len(agents)          # no duplicates
    assert {"money", "status", "privacy"} <= set(keys)                 # this data supports them
    names = _names(layer, oid)
    for a in agents:
        assert a["examples"], a["name"]
        for e in a["examples"]:
            low = e["text"].lower()
            assert any(n in low for n in names if len(n) > 2) or "personal" in low, (a["name"], e["text"])
    inv = next(a for a in agents if a["key"] == "investigator")
    assert inv["name"] == "Order Investigator" and any(ch.isdigit() for ch in inv["examples"][0]["text"])
    assert "West" not in str(agents) and "October 2026" not in str(agents)   # no fixed text


def test_built_ins_are_stored_once_and_read_only(shop):
    layer, oid, _ = shop
    first = onto_agents.sync_builtins(layer, oid)
    again = onto_agents.sync_builtins(layer, oid)
    assert [a["id"] for a in first] == [a["id"] for a in again]
    assert all(a["version"] == 1 and a["builtin"] for a in again)
    guide = again[0]
    with pytest.raises(onto_agents.ReadOnly):
        onto_agents.update(layer, guide["id"], {"name": "Mine now"})
    with pytest.raises(onto_agents.ReadOnly):
        onto_agents.delete(layer, guide["id"])


def test_a_built_in_the_data_no_longer_supports_is_retired_not_deleted(shop, monkeypatch):
    layer, oid, _ = shop
    from agent import connections
    agents = onto_agents.sync_builtins(layer, oid)
    privacy = next(a for a in agents if a["id"].endswith(":privacy"))
    key = connections.issue_key(layer.graph, privacy["id"], "test")
    real = catalog.builtins
    monkeypatch.setattr(catalog, "builtins", lambda l, o: [a for a in real(l, o) if a["key"] != "privacy"])
    onto_agents.forget()
    left = onto_agents.sync_builtins(layer, oid)
    assert privacy["id"] not in {a["id"] for a in left}
    assert onto_agents.get(layer.graph, privacy["id"])["status"] == "retired"
    assert connections.list_keys(layer.graph, privacy["id"])                # keys kept
    assert key["key"]
    monkeypatch.setattr(catalog, "builtins", real)
    onto_agents.forget()
    assert privacy["id"] in {a["id"] for a in onto_agents.sync_builtins(layer, oid)}  # back when supported


# ------------------------------------------------------- copies and yours
def test_copy_a_built_in_and_change_the_copy(shop):
    layer, oid, _ = shop
    metric = next(a for a in onto_agents.sync_builtins(layer, oid) if a["kind"] == "metric")
    mine = onto_agents.copy(layer, metric["id"])
    assert not mine["builtin"] and mine["base"] == metric["id"] and mine["name"].endswith("(my copy)")
    changed = onto_agents.update(layer, mine["id"], {"name": "Finance numbers",
                                                     "scope": {"metrics": ["total_gross_amount"]},
                                                     "instructions": "Answer in one sentence."})
    assert changed["version"] == 2 and changed["scope"]["metrics"] == ["total_gross_amount"]
    assert onto_agents.get(layer.graph, metric["id"])["name"] == "Metric Analyst"   # original untouched
    second = onto_agents.copy(layer, metric["id"])
    assert second["name"] == "Metric Analyst (my copy)"                    # the first was renamed
    onto_agents.delete(layer, second["id"])
    with pytest.raises(KeyError):
        onto_agents.get(layer.graph, second["id"])


def test_create_checks_against_the_ontology(shop):
    layer, oid, _ = shop
    with pytest.raises(onto_agents.AgentError, match="no thing called Invoices"):
        onto_agents.create(layer, oid, {"name": "X", "kind": "insight", "scope": {"things": ["Invoices"]}})
    with pytest.raises(onto_agents.AgentError, match="no metric called"):
        onto_agents.create(layer, oid, {"name": "X", "kind": "metric", "scope": {"metrics": ["nope"]}})
    with pytest.raises(onto_agents.AgentError, match="must be one of"):
        onto_agents.create(layer, oid, {"name": "X", "kind": "oracle"})
    with pytest.raises(onto_agents.AgentError, match="name"):
        onto_agents.create(layer, oid, {"kind": "insight"})
    a = onto_agents.create(layer, oid, {"name": "Order watcher", "kind": "insight",
                                        "scope": {"things": ["Order"]},
                                        "examples": ["How many Orders have Status cancelled?"]})
    assert a["id"].startswith(f"agent:{oid}:") and a["examples"][0]["text"].startswith("How many")
    with pytest.raises(onto_agents.AgentError, match="already have"):
        onto_agents.create(layer, oid, {"name": "order watcher", "kind": "guide"})


# ------------------------------------------------------------- answering
def _agent(layer, oid, kind):
    return next(a for a in onto_agents.sync_builtins(layer, oid) if a["kind"] == kind)


def test_metric_agent_gives_the_certified_number_only(shop):
    layer, oid, db = shop
    a = _agent(layer, oid, "metric")
    r = onto_runner.run(layer, a, "What is the Total Gross Amount?")
    assert r["answerable"]["verdict"] == "yes" and r["metric"]["owner"] == "Finance"
    assert abs(r["table"]["rows"][0][0] - _sql(db, "select sum(gross_amount) from orders")) < 0.01
    r = onto_runner.run(layer, a, "What is the Total Net Amount?")        # proposed, not certified
    assert r["answerable"]["verdict"] == "no" and "not certified" in r["answer"]["text"]


def test_investigator_finds_a_record_and_masks_personal_data(shop):
    layer, oid, _ = shop
    a = _agent(layer, oid, "investigator")
    r = onto_runner.run(layer, a, "Tell me about customer 7")
    assert r["answerable"]["verdict"] == "yes" and r["records"]
    assert "@example.com" not in str(r)
    r = onto_runner.run(layer, a, "Tell me about something")
    assert r["answerable"]["verdict"] == "no" and "name a record" in r["answer"]["text"]


def test_guide_explains_without_numbers_from_the_data(shop):
    layer, oid, _ = shop
    r = onto_runner.run(layer, _agent(layer, oid, "guide"), "What is an Order?")
    assert r["answerable"]["verdict"] == "yes" and r["answer"]["text"].startswith("Order")
    assert not r["table"]


def test_counting_questions_are_answered_by_strata_not_the_ai(shop):
    layer, oid, db = shop
    a = _agent(layer, oid, "insight")
    r = onto_runner.run(layer, a, "How many Orders have Status cancelled?")
    assert r["table"]["rows"][0][0] == _sql(db, "select count(*) from orders where status='cancelled'")
    assert "not AI-written" in r["used"][0]["what"]
    r = onto_runner.run(layer, a, "Total Gross Amount by Customer Country")
    by = {row[0]: row[1] for row in r["table"]["rows"]}
    want = _sql(db, "select sum(o.gross_amount) from orders o join customer c on c.id=o.customer_id "
                    "where c.country='IN'")
    assert abs(by["IN"] - want) < 0.01
    r = onto_runner.run(layer, a, "How many Orders per month?")
    assert r["table"]["columns"][0] == "Month" and sum(x[1] for x in r["table"]["rows"]) == 400


def test_an_agent_stays_in_its_scope(shop):
    layer, oid, _ = shop
    a = onto_agents.create(layer, oid, {"name": "Lines only", "kind": "insight",
                                        "scope": {"things": ["Order Line"]}})
    r = onto_runner.run(layer, a, "How many Customers have Segment SMB?")
    assert r["answerable"]["verdict"] == "no" and "Order Line" in r["answer"]["text"]
    narrow = onto_agents.create(layer, oid, {"name": "Net only", "kind": "metric",
                                             "scope": {"metrics": ["total_net_amount"]}})
    r = onto_runner.run(layer, narrow, "What is the Total Gross Amount?")
    assert r["answerable"]["verdict"] == "no"


def test_trust_checker_reports_without_computing(shop):
    layer, oid, _ = shop
    r = onto_runner.run(layer, _agent(layer, oid, "trust"), "Can I trust the Total Gross Amount?")
    assert "certified by a person" in r["answer"]["text"] and "OK" in r["answer"]["text"]
    assert not r["table"]
    r = onto_runner.run(layer, _agent(layer, oid, "trust"), "Is the Order data complete?")
    assert r["answerable"]["verdict"] == "yes" and "filled in" in r["answer"]["text"]


def test_steward_proposes_and_changes_nothing(shop):
    layer, oid, _ = shop
    before = simple.view(layer.graph, oid)
    r = onto_runner.run(layer, _agent(layer, oid, "steward"), "net_amount = Net value before tax")
    assert r["proposal"]["changes"] and "Nothing has changed yet" in r["answer"]["text"]
    assert simple.view(layer.graph, oid)["notes"] == before["notes"]
    r = onto_runner.run(layer, _agent(layer, oid, "steward"), "Gross Amount is in ...")
    assert r["answerable"]["verdict"] == "no" and "fill in" in r["answer"]["text"]


def test_privacy_checker_names_fields_never_values(shop):
    layer, oid, _ = shop
    r = onto_runner.run(layer, _agent(layer, oid, "privacy"), "Where is personal data?")
    assert "Email" in r["answer"]["text"] and "@example.com" not in str(r)
