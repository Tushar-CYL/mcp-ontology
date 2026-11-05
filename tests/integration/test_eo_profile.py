"""Step 2 of the journey: connect and profile every source.

The profile is the evidence base for every later proposal (concepts, column
meanings, identity, conflicts), so it records what a data engineer would look
at first: type, nulls, distinct values, ranges, top values, and how fresh
each table is.
"""

from __future__ import annotations

import pytest

from ontology import profile as prof
from ontology import registry as reg
from tests.integration.eo_fixtures import load_scenario


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    layer, truth, root = load_scenario(tmp_path_factory.mktemp("prof"))
    profiles = prof.profile_ontology(layer, "sales")
    yield layer, truth, profiles
    layer.close()


def _table(profiles, key):
    return next(p for p in profiles if p["table_key"] == key)


def _col(table, name):
    return next(c for c in table["columns"] if c["name"] == name)


def test_every_table_of_every_source_is_profiled(loaded):
    _, _, profiles = loaded
    keys = {p["table_key"] for p in profiles}
    assert {"bi_crm.accounts", "bi_erp.customers", "bi_erp.sales_orders",
            "bi_billing.accounts", "bi_billing.invoices",
            "bi_mdm.golden_customers", "bi_mart.sales_monthly"} <= keys


def test_row_counts_and_column_types(loaded):
    _, truth, profiles = loaded
    orders = _table(profiles, "bi_erp.sales_orders")
    assert orders["rows"] == truth["customers"] * 10
    assert len(orders["columns"]) == 15
    assert _col(orders, "NETWR")["family"] == "numeric"
    assert _col(orders, "ERDAT")["family"] == "temporal"
    assert _col(orders, "WAERK")["family"] == "text"


def test_numeric_ranges_and_nulls(loaded):
    _, _, profiles = loaded
    net = _col(_table(profiles, "bi_erp.sales_orders"), "NETWR")
    assert 200 <= net["min"] <= net["max"] <= 20000
    assert net["null_ratio"] == 0
    crm = _table(profiles, "bi_mdm.golden_customers")
    assert _col(crm, "crm_id")["null_ratio"] > 0          # ~8% have no CRM account


def test_top_values_for_low_cardinality_columns(loaded):
    _, _, profiles = loaded
    currency = _col(_table(profiles, "bi_erp.sales_orders"), "WAERK")
    values = {v["value"] for v in currency["top_values"]}
    assert {"EUR", "USD"} <= values
    assert "XXX" in values                                 # the planted bad currency


def test_freshness_is_the_latest_date_in_each_table(loaded):
    _, truth, profiles = loaded
    assert _table(profiles, "bi_erp.sales_orders")["freshness"] == \
        truth["staleness"]["latest_source_date"]
    assert _table(profiles, "bi_mdm.golden_customers")["freshness"] == \
        truth["staleness"]["mdm_synced"]


def test_profiles_are_stored_as_evidence_in_the_registry(loaded):
    layer, _, _ = loaded
    stored = reg.items(layer.graph, "sales", kind="profile")
    assert {i["key"] for i in stored} >= {"bi_erp.sales_orders", "bi_crm.accounts"}
    assert stored[0]["status"] == "approved"           # facts, not proposals


def test_profiling_only_covers_the_ontologys_sources(loaded):
    _, _, profiles = loaded
    assert all(p["source"].startswith("bi_") for p in profiles)
