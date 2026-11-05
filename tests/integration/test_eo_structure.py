"""Step 5: relationships done properly - cardinality, optionality, hierarchies.

Cardinality is measured, not assumed: how many child rows share one parent
value, and what share of children find their parent. Hierarchies come from
functional dependencies in the data: every country sits in exactly one
region, so Region > Country is a drill path.
"""

from __future__ import annotations

import pytest

from ontology import registry as reg
from tests.integration.eo_fixtures import load_scenario, run_steps


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    layer, truth, _ = load_scenario(tmp_path_factory.mktemp("st"))
    out = run_steps(layer, upto="structure")
    yield layer, truth, out["structure"]
    layer.close()


def _rel(result, frm):
    return next(r for r in result["relationships"] if r["from"] == frm)


@pytest.mark.parametrize("index", range(4))
def test_cardinality_matches_the_truth(built, index):
    _, truth, result = built
    expected = truth["relationships"][index]
    got = _rel(result, f"bi_{expected['from']}")
    assert got["to"] == f"bi_{expected['to']}"
    assert got["cardinality"] == expected["cardinality"]
    assert got["required"] is expected["required"]


def test_cardinality_is_backed_by_numbers(built):
    _, _, result = built
    rel = _rel(result, "bi_erp.sales_orders.KUNNR")
    assert rel["max_children"] > 1
    assert rel["matched"] == 1.0
    assert rel["parents_used"] > 0.9
    joined = " ".join(rel["evidence"])
    assert "per parent" in joined and "%" in joined


def test_optional_side_is_measured(built):
    _, _, result = built
    rel = _rel(result, "bi_billing.invoices.order_ref")
    assert 0.8 < rel["parents_used"] < 1.0           # not every order is invoiced


def test_relationships_name_their_concepts(built):
    _, _, result = built
    rel = _rel(result, "bi_erp.sales_orders.KUNNR")
    assert (rel["from_concept"], rel["to_concept"]) == ("SalesOrder", "Customer")
    assert rel["name"]


def test_region_country_hierarchy_is_found(built):
    _, truth, result = built
    found = [h for h in result["hierarchies"] if h["concept"] == "Customer"
             and h["levels"] == ["region", "country"]]
    assert found, result["hierarchies"]
    h = found[0]
    assert h["parent_of"] == truth["hierarchies"][0]["parent_of"]
    assert h["evidence"]


def test_no_hierarchy_through_identifiers_or_names(built):
    _, _, result = built
    for h in result["hierarchies"]:
        assert not set(h["levels"]) & {"identifier", "customer_name", "tax_id"}


def test_structure_is_stored_in_the_registry(built):
    layer, _, _ = built
    rels = {i["key"]: i for i in reg.items(layer.graph, "sales", kind="relationship")}
    key = "bi_erp.sales_orders.KUNNR->bi_erp.customers.KUNNR"
    assert rels[key]["payload"]["cardinality"] == "many-to-one"
    hier = reg.items(layer.graph, "sales", kind="hierarchy")
    assert any(i["payload"]["levels"] == ["region", "country"] for i in hier)
