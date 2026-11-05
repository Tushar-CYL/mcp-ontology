"""Step 8: rules (constraints) and action types.

Rules are derived from what the earlier steps learned, then checked live:
the value structure gives gross = net + tax, the relationships give
invoice date >= order date, the currency mapping gives "an ISO code". The
violating records must be exactly the planted ones.

Action types are what an agent may PROPOSE (merge two golden records, re-map
a report column, request a refresh); none executes without an approver.
"""

from __future__ import annotations

import pytest

from ontology import registry as reg
from ontology import rules as rl
from tests.integration.eo_fixtures import load_scenario, run_steps


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    layer, truth, _ = load_scenario(tmp_path_factory.mktemp("rl"))
    out = run_steps(layer, upto="rules")
    yield layer, truth, out["rules"]
    layer.close()


def _rule(result, kind, table=None):
    return next(r for r in result["rules"] if r["kind"] == kind
                and (table is None or r["table"] == table))


def test_gross_equals_net_plus_tax_finds_exactly_the_planted_rows(built):
    _, truth, result = built
    r = next(r for r in result["rules"] if r["kind"] == "sum"
             and r["target"] == "gross_amount" and r["table"] == "bi_erp.sales_orders")
    assert set(r["violating"]) == set(truth["rule_violations"]["gross_not_net_plus_tax"])
    assert r["violations"] == len(truth["rule_violations"]["gross_not_net_plus_tax"])
    assert "NETWR + MWSBK" in r["description"]


def test_list_equals_net_plus_discount_holds(built):
    _, _, result = built
    r = next(r for r in result["rules"] if r["kind"] == "sum" and r["target"] == "list_amount")
    assert r["violations"] == 0


def test_invoice_before_order_is_caught_across_systems(built):
    _, truth, result = built
    r = _rule(result, "date_order")
    assert set(r["violating"]) == set(truth["rule_violations"]["invoice_before_order"])
    assert "invoice_date" in r["description"] and "order_date" in r["description"]


def test_invalid_currency_codes_are_caught(built):
    _, truth, result = built
    r = _rule(result, "allowed_values", "bi_erp.sales_orders")
    assert set(r["violating"]) == set(truth["rule_violations"]["invalid_currency"])
    billing = _rule(result, "allowed_values", "bi_billing.invoices")
    assert billing["violations"] == 0


def test_keys_are_unique_and_present(built):
    _, _, result = built
    keys = [r for r in result["rules"] if r["kind"] == "key"]
    assert {r["table"] for r in keys} >= {"bi_erp.sales_orders", "bi_erp.customers",
                                           "bi_mdm.golden_customers"}
    assert all(r["violations"] == 0 for r in keys)


def test_cross_system_amounts_must_agree(built):
    _, truth, result = built
    r = _rule(result, "reconcile")
    assert "invoice_amount" in r["description"] and "BRTWR" in r["description"]
    assert r["violations"] <= len(truth["rule_violations"]["gross_not_net_plus_tax"])


def test_every_rule_carries_sql_a_person_can_run(built):
    layer, _, result = built
    for r in result["rules"]:
        assert r["sql"].lstrip().upper().startswith("SELECT")
        count = layer.graph.sql(f"SELECT count(*) FROM ({r['sql']}) v")[0][0]
        assert count == r["violations"], r["key"]


def test_validate_rechecks_live(built):
    layer, _, result = built
    again = rl.validate_rules(layer, "sales")
    assert {r["key"]: r["violations"] for r in again} == \
        {r["key"]: r["violations"] for r in result["rules"]}


def test_action_types_are_declared_and_never_execute(built):
    layer, truth, result = built
    actions = {a["name"]: a for a in result["actions"]}
    assert {"merge_golden_records", "remap_report_column", "request_source_refresh",
            "correct_records"} <= set(actions)
    merge = actions["merge_golden_records"]
    assert len(merge["proposed"]) == len(truth["duplicates"])
    assert merge["agents_may"] == "propose"
    assert merge["approver"] == "Data Governance"
    remap = actions["remap_report_column"]
    assert remap["proposed"][0]["to"].endswith("NETWR")
    stored = reg.items(layer.graph, "sales", kind="action")
    assert {i["key"] for i in stored} >= {"merge_golden_records", "remap_report_column"}


def test_rules_are_registry_proposals(built):
    layer, _, _ = built
    stored = reg.items(layer.graph, "sales", kind="rule")
    assert stored and all(i["status"] == "proposed" for i in stored)
    assert all(i["payload"]["sql"] for i in stored)
