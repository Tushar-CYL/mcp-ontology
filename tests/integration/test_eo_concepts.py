"""Step 3: shared concepts across sources.

CRM calls them accounts, ERP customers, billing accounts, and the MDM hub
golden customers - one business concept, four tables, four id schemes. The
accelerator groups them from evidence in the data (the hub's cross-reference
columns cover each system's keys one-to-one) plus business synonyms, and
never merges things that are merely related (an invoice is not an order).
"""

from __future__ import annotations

import pytest

from ontology import concepts as cn
from ontology import profile as prof
from ontology import registry as reg
from tests.integration.eo_fixtures import load_scenario


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    layer, truth, root = load_scenario(tmp_path_factory.mktemp("cn"))
    prof.profile_ontology(layer, "sales")
    result = cn.propose_concepts(layer, "sales")
    yield layer, truth, result
    layer.close()


def _members(result, name):
    concept = next(c for c in result["concepts"] if c["name"] == name)
    return set(concept["members"])


def _truth_members(truth, name):
    return {f"bi_{t}" for t in truth["concepts"][name]}


@pytest.mark.parametrize("name", ["Customer", "SalesOrder", "Invoice", "SalesMonthly"])
def test_concepts_match_the_ground_truth(built, name):
    _, truth, result = built
    assert _members(result, name) == _truth_members(truth, name)


def test_no_extra_concepts_are_invented(built):
    _, truth, result = built
    assert {c["name"] for c in result["concepts"]} == set(truth["concepts"])


def test_the_mdm_hub_is_recognised_as_the_master(built):
    _, _, result = built
    customer = next(c for c in result["concepts"] if c["name"] == "Customer")
    assert customer["master"] == "bi_mdm.golden_customers"


def test_crosswalk_evidence_is_cited(built):
    _, _, result = built
    customer = next(c for c in result["concepts"] if c["name"] == "Customer")
    joined = " ".join(customer["evidence"])
    assert "bi_mdm.golden_customers.erp_no" in joined
    assert "bi_erp.customers.KUNNR" in joined
    assert "%" in joined                                  # coverage is quantified


def test_related_but_different_things_are_not_merged(built):
    _, _, result = built
    assert _members(result, "Invoice") != _members(result, "SalesOrder")
    links = result["crosswalks"]
    assert any(l["from"] == "bi_billing.invoices.order_ref" and
               l["to"] == "bi_erp.sales_orders.VBELN" for l in links)


def test_concepts_and_members_are_registry_proposals(built):
    layer, _, _ = built
    concepts = reg.items(layer.graph, "sales", kind="concept")
    assert {c["key"] for c in concepts} == {"Customer", "SalesOrder", "Invoice",
                                             "SalesMonthly"}
    assert all(c["status"] == "proposed" for c in concepts)
    assert all(c["evidence"] for c in concepts)
    members = reg.items(layer.graph, "sales", kind="member")
    assert {m["key"] for m in members} >= {"Customer|bi_crm.accounts",
                                            "Customer|bi_mdm.golden_customers"}


def test_every_concept_has_a_plain_description(built):
    _, _, result = built
    for concept in result["concepts"]:
        assert len(concept["description"]) > 20


def test_rerunning_is_stable_and_keeps_decisions(built):
    layer, _, _ = built
    reg.decide(layer.graph, "sales", "concept", "Customer", "approved", by="steward")
    again = cn.propose_concepts(layer, "sales")
    assert {c["name"] for c in again["concepts"]} == {"Customer", "SalesOrder",
                                                      "Invoice", "SalesMonthly"}
    assert reg.get_item(layer.graph, "sales", "concept", "Customer")["status"] == "approved"
