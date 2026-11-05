"""Step 4: properties with meaning, and the amount-column solver.

The team lead's problem: a company has 10-12 "amount" columns and reports get
built on the wrong one. Every column is mapped to a canonical property with a
definition and a unit, from three kinds of evidence, strongest last:

* the name (including the SAP field dictionary: NETWR, MWSBK, BRTWR ...);
* value structure inside a table (net + tax = gross row by row; a column that
  is net times a per-currency rate is a currency conversion);
* reconciliation against another system (billing invoice_amount equals ERP
  BRTWR order by order; the data mart's revenue equals the monthly sum of
  BRTWR, not NETWR - so the mart is built on the wrong column).

Scored against ground_truth.json.
"""

from __future__ import annotations

import csv
import time

import pytest

from ontology import concepts as cn
from ontology import mapping as mp
from ontology import profile as prof
from ontology import registry as reg
from tests.integration.eo_fixtures import load_scenario

AMOUNTS = ["NETWR", "MWSBK", "BRTWR", "RABATT", "FRACHT", "LISTPR", "WAVWR",
           "BONUS", "NETWR_LC", "NETWR_USD"]


def _run(layer):
    prof.profile_ontology(layer, "sales")
    cn.propose_concepts(layer, "sales")
    started = time.perf_counter()
    result = mp.map_properties(layer, "sales")
    result["seconds"] = time.perf_counter() - started
    return result


@pytest.fixture(scope="module")
def mapped(tmp_path_factory):
    layer, truth, _ = load_scenario(tmp_path_factory.mktemp("map"))
    result = _run(layer)
    yield layer, truth, result
    layer.close()


def _meaning(result, column_key):
    return result["columns"][column_key]["property"]


def _accuracy(result, truth, prefix=""):
    keys = [k for k in truth["column_meanings"] if k.startswith(prefix)]
    right = [k for k in keys if _meaning(result, f"bi_{k}") == truth["column_meanings"][k]]
    return len(right) / len(keys), sorted(set(keys) - set(right))


def test_every_erp_amount_column_gets_its_true_meaning(mapped):
    _, truth, result = mapped
    score, wrong = _accuracy(result, truth, "erp.sales_orders.")
    assert score >= 0.9, wrong
    assert score == 1.0, wrong          # with SAP names + structure, all ten


def test_overall_column_meaning_accuracy(mapped):
    _, truth, result = mapped
    score, wrong = _accuracy(result, truth)
    assert score >= 0.9, wrong


def test_value_structure_confirms_net_tax_gross(mapped):
    _, _, result = mapped
    gross = result["columns"]["bi_erp.sales_orders.BRTWR"]
    assert any("NETWR + MWSBK" in e for e in gross["evidence"])
    assert gross["confidence"] >= 0.95
    lst = result["columns"]["bi_erp.sales_orders.LISTPR"]
    assert any("NETWR + RABATT" in e for e in lst["evidence"])


def test_currency_conversions_are_recognised_from_the_rates(mapped):
    _, _, result = mapped
    usd = result["columns"]["bi_erp.sales_orders.NETWR_USD"]
    assert usd["unit"] == "USD"
    assert any("rate" in e for e in usd["evidence"])
    local = result["columns"]["bi_erp.sales_orders.NETWR_LC"]
    assert local["unit"] == "EUR"                      # the company-code currency


def test_amounts_carry_their_currency_column(mapped):
    _, _, result = mapped
    assert result["columns"]["bi_erp.sales_orders.NETWR"]["unit"] == "currency in WAERK"


def test_billing_reconciles_to_erp_gross(mapped):
    _, _, result = mapped
    inv = result["columns"]["bi_billing.invoices.invoice_amount"]
    assert inv["property"] == "gross_amount"
    assert inv["method"] == "reconciliation"
    assert any("BRTWR" in e and "%" in e for e in inv["evidence"])


def test_the_data_mart_is_flagged_for_the_wrong_amount_column(mapped):
    layer, truth, result = mapped
    rev = result["columns"]["bi_mart.sales_monthly.revenue"]
    assert rev["property"] == "gross_amount"
    finding = next(f for f in result["findings"] if f["type"] == "wrong_amount_column")
    assert finding["column"] == "bi_mart.sales_monthly.revenue"
    assert finding["built_from"] == f"bi_erp.sales_orders.{truth['mart']['wrong_column']}"
    assert finding["should_be"] == f"bi_erp.sales_orders.{truth['mart']['right_column']}"
    assert 5 <= finding["overstatement_pct"] <= 25     # tax is 10-20%
    stored = reg.items(layer.graph, "sales", kind="finding")
    assert any(i["payload"]["type"] == "wrong_amount_column" for i in stored)


def test_mappings_and_properties_are_registry_proposals(mapped):
    layer, _, _ = mapped
    maps = {i["key"]: i for i in reg.items(layer.graph, "sales", kind="mapping")}
    net = maps["bi_erp.sales_orders.NETWR"]
    assert net["status"] == "proposed" and net["evidence"]
    assert net["payload"]["property"] == "net_amount"
    assert net["payload"]["concept"] == "SalesOrder"
    props = {i["key"]: i for i in reg.items(layer.graph, "sales", kind="property")}
    assert "Value after discounts" in props["net_amount"]["payload"]["definition"]
    assert "bi_erp.sales_orders.NETWR" in props["net_amount"]["payload"]["columns"]


def test_identifier_columns_are_not_called_amounts(mapped):
    _, _, result = mapped
    for key in ("bi_erp.sales_orders.VBELN", "bi_erp.customers.KUNNR"):
        assert result["columns"][key]["property"] == "identifier"


def test_mapping_is_fast(mapped):
    _, _, result = mapped
    assert result["seconds"] < 20


def test_rerun_keeps_a_stewards_correction(mapped):
    layer, _, _ = mapped
    reg.decide(layer.graph, "sales", "mapping", "bi_erp.sales_orders.FRACHT", "edited",
               by="steward", payload={"property": "shipping_fee", "column": "FRACHT"})
    again = mp.map_properties(layer, "sales")
    assert again["columns"]["bi_erp.sales_orders.FRACHT"]["property"] == "shipping_fee"
    assert again["columns"]["bi_erp.sales_orders.FRACHT"]["method"] == "steward"


# ------------------------------------------------------------- no names
def _strip_names(root, truth):
    """Rename the ten amount columns AMT_01..AMT_10 in a scrambled order."""
    path = root / "erp" / "sales_orders.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    order = [7, 2, 9, 4, 0, 6, 1, 8, 3, 5]           # scramble
    rename = {AMOUNTS[i]: f"AMT_{n + 1:02d}" for n, i in enumerate(order)}
    rows[0] = [rename.get(c, c) for c in rows[0]]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    meanings = truth["column_meanings"]
    for old, new in rename.items():
        meanings[f"erp.sales_orders.{new}"] = meanings.pop(f"erp.sales_orders.{old}")
    truth["renamed"] = rename
    return truth


@pytest.fixture(scope="module")
def nameless(tmp_path_factory):
    layer, truth, _ = load_scenario(tmp_path_factory.mktemp("nameless"),
                                    mutate=_strip_names)
    result = _run(layer)
    yield layer, truth, result
    layer.close()


STRUCTURAL = ["net_amount", "tax_amount", "gross_amount", "discount_amount",
              "list_amount", "net_amount_local", "net_amount_usd"]


def test_without_names_the_data_still_reveals_the_structure(nameless):
    _, truth, result = nameless
    for old, new in truth["renamed"].items():
        meaning = truth["column_meanings"][f"erp.sales_orders.{new}"]
        if meaning in STRUCTURAL:
            got = result["columns"][f"bi_erp.sales_orders.{new}"]
            assert got["property"] == meaning, (old, new, got)
            assert got["method"] in ("values", "reconciliation")


def test_without_names_unknowns_are_admitted_not_guessed(nameless):
    _, truth, result = nameless
    for old, new in truth["renamed"].items():
        meaning = truth["column_meanings"][f"erp.sales_orders.{new}"]
        got = result["columns"][f"bi_erp.sales_orders.{new}"]
        if meaning not in STRUCTURAL:
            assert got["property"] in ("amount_unclassified", meaning), (old, new, got)
            if got["property"] == "amount_unclassified":
                assert got["confidence"] < 0.6


def test_without_names_the_mart_is_still_caught(nameless):
    _, truth, result = nameless
    finding = next(f for f in result["findings"] if f["type"] == "wrong_amount_column")
    wrong = truth["renamed"][truth["mart"]["wrong_column"]]
    right = truth["renamed"][truth["mart"]["right_column"]]
    assert finding["built_from"] == f"bi_erp.sales_orders.{wrong}"
    assert finding["should_be"] == f"bi_erp.sales_orders.{right}"
