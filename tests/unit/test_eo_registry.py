"""The enterprise ontology registry: where the cross-source ontology lives.

Every item (concept, property, mapping, relationship, rule, action) carries a
status, an owner, a confidence and its evidence, so governance is uniform.
Re-running the accelerator refreshes proposals but never overrides a person's
decision; publishing freezes the approved items as a numbered version.
"""

from __future__ import annotations

import pytest

from knowledge_graph.store import open_graph
from ontology import registry as reg

INTAKE = {
    "name": "Sales reporting",
    "problem": "Reports are late; three sources disagree on amounts.",
    "domain": "Sales / order-to-cash",
    "questions": ["What is net revenue by region per month?"],
    "sources": [
        {"source_id": "bi_erp", "role": "source_system", "owner_team": "Finance IT",
         "cadence_days": 1},
        {"source_id": "bi_mdm", "role": "mdm_hub", "owner_team": "Data Governance",
         "cadence_days": 7},
    ],
}


@pytest.fixture
def graph(tmp_path):
    g = open_graph(str(tmp_path / "eo.duckdb"))
    yield g
    g.close()


@pytest.fixture
def onto(graph):
    return reg.create(graph, "sales", **INTAKE)


def test_create_records_the_intake(graph, onto):
    got = reg.get(graph, "sales")
    assert got["problem"].startswith("Reports are late")
    assert [s["source_id"] for s in got["sources"]] == ["bi_erp", "bi_mdm"]
    assert got["sources"][1]["role"] == "mdm_hub"
    assert got["sources"][1]["cadence_days"] == 7
    assert [o["id"] for o in reg.list_ontologies(graph)] == ["sales"]


@pytest.mark.parametrize("bad", [
    {"role": "warehouse_of_doom"}, {"cadence_days": 0}, {"source_id": ""},
])
def test_bad_intake_is_rejected(graph, bad):
    sources = [{**INTAKE["sources"][0], **bad}]
    with pytest.raises(ValueError):
        reg.create(graph, "x", **{**INTAKE, "sources": sources})


def test_duplicate_ontology_id_is_rejected(graph, onto):
    with pytest.raises(ValueError, match="exists"):
        reg.create(graph, "sales", **INTAKE)


def test_unknown_ontology_is_a_key_error(graph):
    with pytest.raises(KeyError):
        reg.get(graph, "nope")


def test_put_and_read_items_with_evidence(graph, onto):
    reg.put(graph, "sales", "concept", "Customer", {"description": "A buyer."},
            confidence=0.9, evidence=["erp.customers", "crm.accounts"])
    item = reg.get_item(graph, "sales", "concept", "Customer")
    assert item["status"] == "proposed"
    assert item["payload"]["description"] == "A buyer."
    assert item["evidence"] == ["erp.customers", "crm.accounts"]
    assert item["confidence"] == 0.9
    assert [i["key"] for i in reg.items(graph, "sales", kind="concept")] == ["Customer"]


def test_unknown_kind_is_rejected(graph, onto):
    with pytest.raises(ValueError, match="kind"):
        reg.put(graph, "sales", "spaceship", "x", {})


def test_rerun_refreshes_proposals_but_never_a_decision(graph, onto):
    reg.put(graph, "sales", "concept", "Customer", {"description": "v1"})
    reg.decide(graph, "sales", "concept", "Customer", "approved", by="steward")
    reg.put(graph, "sales", "concept", "Customer", {"description": "v2"})
    item = reg.get_item(graph, "sales", "concept", "Customer")
    assert item["status"] == "approved"
    assert item["payload"]["description"] == "v1"
    reg.put(graph, "sales", "concept", "Order", {"description": "v1"})
    reg.put(graph, "sales", "concept", "Order", {"description": "v2"})
    assert reg.get_item(graph, "sales", "concept", "Order")["payload"]["description"] == "v2"


def test_decide_edits_and_audits(graph, onto):
    reg.put(graph, "sales", "property", "net_amount", {"definition": "old"})
    reg.decide(graph, "sales", "property", "net_amount", "edited", by="ana",
               payload={"definition": "Value after discount, before tax."},
               note="clearer")
    item = reg.get_item(graph, "sales", "property", "net_amount")
    assert item["status"] == "approved"
    assert item["payload"]["definition"].startswith("Value after discount")
    trail = reg.audit(graph, "sales")
    assert trail[-1]["decision"] == "edited" and trail[-1]["by"] == "ana"
    assert trail[-1]["note"] == "clearer"


def test_decide_rejects_bad_decisions_and_unknown_items(graph, onto):
    reg.put(graph, "sales", "concept", "Customer", {})
    with pytest.raises(ValueError):
        reg.decide(graph, "sales", "concept", "Customer", "maybe", by="x")
    with pytest.raises(KeyError):
        reg.decide(graph, "sales", "concept", "Ghost", "approved", by="x")


def test_bulk_approve_by_confidence(graph, onto):
    reg.put(graph, "sales", "mapping", "a", {}, confidence=0.95)
    reg.put(graph, "sales", "mapping", "b", {}, confidence=0.6)
    done = reg.approve_all(graph, "sales", kind="mapping", min_confidence=0.9, by="ana")
    assert done == ["a"]
    assert reg.get_item(graph, "sales", "mapping", "b")["status"] == "proposed"


def test_publish_freezes_approved_items_as_versions(graph, onto):
    reg.put(graph, "sales", "concept", "Customer", {"d": 1})
    reg.put(graph, "sales", "concept", "Order", {"d": 1})
    reg.decide(graph, "sales", "concept", "Customer", "approved", by="ana")
    v1 = reg.publish(graph, "sales", by="ana", notes="first")
    assert v1["version"] == 1
    assert [i["key"] for i in v1["items"]] == ["Customer"]    # approved only
    reg.decide(graph, "sales", "concept", "Order", "approved", by="ana")
    reg.decide(graph, "sales", "concept", "Customer", "edited", by="ana",
               payload={"d": 2})
    v2 = reg.publish(graph, "sales", by="ana")
    assert v2["version"] == 2
    assert [v["version"] for v in reg.versions(graph, "sales")] == [1, 2]
    diff = reg.diff(graph, "sales", 1, 2)
    assert diff["added"] == [{"kind": "concept", "key": "Order"}]
    assert diff["changed"] == [{"kind": "concept", "key": "Customer"}]
    assert diff["removed"] == []
    assert reg.version(graph, "sales", 1)["items"][0]["payload"] == {"d": 1}


def test_publishing_nothing_approved_is_refused(graph, onto):
    with pytest.raises(ValueError, match="approved"):
        reg.publish(graph, "sales", by="ana")


def test_ontologies_are_isolated(graph, onto):
    reg.create(graph, "hr", **{**INTAKE, "name": "HR"})
    reg.put(graph, "hr", "concept", "Employee", {})
    assert reg.items(graph, "sales", kind="concept") == []


def test_prune_drops_stale_proposals_but_keeps_decisions(graph, onto):
    for key in ("a", "b", "c"):
        reg.put(graph, "sales", "concept", key, {})
    reg.decide(graph, "sales", "concept", "b", "approved", by="ana")
    gone = reg.prune(graph, "sales", "concept", keep={"c"})
    assert gone == ["a"]
    assert {i["key"] for i in reg.items(graph, "sales", kind="concept")} == {"b", "c"}


def test_prune_can_be_limited_to_the_keys_a_step_owns(graph, onto):
    reg.put(graph, "sales", "finding", "dup|x", {})
    reg.put(graph, "sales", "finding", "wrong|y", {})
    assert reg.prune(graph, "sales", "finding", keep=set(), prefixes=("dup|",)) == ["dup|x"]
    assert [i["key"] for i in reg.items(graph, "sales", kind="finding")] == ["wrong|y"]


def test_facts_are_refreshed_even_though_they_are_approved(graph, onto):
    reg.put(graph, "sales", "profile", "t", {"rows": 1}, fact=True)
    reg.put(graph, "sales", "profile", "t", {"rows": 2}, fact=True)
    item = reg.get_item(graph, "sales", "profile", "t")
    assert item["status"] == "approved" and item["payload"] == {"rows": 2}


def test_annotate_labels_a_decided_item_without_changing_its_status(graph, onto):
    reg.put(graph, "sales", "concept", "Customer", {"description": "x"})
    reg.decide(graph, "sales", "concept", "Customer", "approved", by="ana")
    item = reg.annotate(graph, "sales", "concept", "Customer", owner="Gov", tier="core")
    assert item["status"] == "approved" and item["owner"] == "Gov"
    assert item["payload"] == {"description": "x", "tier": "core"}
