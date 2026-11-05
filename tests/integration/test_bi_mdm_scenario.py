"""The BI/MDM demo scenario: the team's real problem, with a known answer key.

From the call notes (data.txt): source systems feed an MDM hub that feeds a
data mart; there are three sources of truth, the hub runs 2-3 weeks behind,
corrected values disagree with the source, and a company has 10-12 "amount"
columns so reports get built on the wrong one. The generator plants exactly
those problems and writes ground_truth.json, so every later ontology step is
measured against the truth instead of eyeballed.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date

import pytest

from datasets.generate_bi_mdm import AMOUNT_COLUMNS, generate
from ontology.connect import connect

SOURCES = ("crm", "erp", "billing", "mdm", "mart")


@pytest.fixture(scope="module")
def scenario(tmp_path_factory):
    out = tmp_path_factory.mktemp("bi")
    root = generate(out, seed=7, customers=300)
    truth = json.loads((root / "ground_truth.json").read_text(encoding="utf-8"))
    return root, truth


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_five_source_systems_are_written(scenario):
    root, _ = scenario
    for name in SOURCES:
        assert (root / name).is_dir(), name
        assert list((root / name).glob("*.csv")), name


def test_the_generator_is_deterministic(tmp_path):
    def digest(folder):
        h = hashlib.sha256()
        for path in sorted(folder.rglob("*.csv")):
            h.update(path.read_bytes())
        return h.hexdigest()
    a = generate(tmp_path / "a", seed=7, customers=120)
    b = generate(tmp_path / "b", seed=7, customers=120)
    assert digest(a) == digest(b)
    c = generate(tmp_path / "c", seed=8, customers=120)
    assert digest(a) != digest(c)


def test_erp_orders_carry_ten_amount_columns_with_known_meanings(scenario):
    root, truth = scenario
    header = _rows(root / "erp" / "sales_orders.csv")[0].keys()
    amounts = [c for c in header if c in AMOUNT_COLUMNS]
    assert len(amounts) == 10
    meanings = truth["column_meanings"]
    assert {meanings[f"erp.sales_orders.{c}"] for c in amounts} == {
        "net_amount", "tax_amount", "gross_amount", "discount_amount",
        "freight_amount", "list_amount", "cost_amount", "rebate_amount",
        "net_amount_local", "net_amount_usd"}


def test_amounts_reconcile_except_the_planted_violations(scenario):
    root, truth = scenario
    planted = set(truth["rule_violations"]["gross_not_net_plus_tax"])
    bad = []
    for row in _rows(root / "erp" / "sales_orders.csv"):
        net, tax, gross = float(row["NETWR"]), float(row["MWSBK"]), float(row["BRTWR"])
        if abs(net + tax - gross) > 0.011:
            bad.append(row["VBELN"])
    assert set(bad) == planted and len(planted) >= 3


def test_billing_reconciles_with_erp_gross(scenario):
    root, truth = scenario
    gross = {r["VBELN"]: float(r["BRTWR"]) for r in _rows(root / "erp" / "sales_orders.csv")}
    planted = set(truth["rule_violations"]["gross_not_net_plus_tax"])
    for inv in _rows(root / "billing" / "invoices.csv"):
        if inv["order_ref"] in planted:
            continue
        assert abs(float(inv["invoice_amount"]) - gross[inv["order_ref"]]) < 0.011


def test_invoice_date_violations_are_exactly_the_planted_ones(scenario):
    root, truth = scenario
    order_date = {r["VBELN"]: r["ERDAT"] for r in _rows(root / "erp" / "sales_orders.csv")}
    early = [i["inv_id"] for i in _rows(root / "billing" / "invoices.csv")
             if i["invoice_date"] < order_date[i["order_ref"]]]
    assert set(early) == set(truth["rule_violations"]["invoice_before_order"])
    assert len(early) >= 3


def test_identity_crosswalk_matches_the_mdm_hub(scenario):
    root, truth = scenario
    hub = _rows(root / "mdm" / "golden_customers.csv")
    true_links = {c["mdm_id"]: c for c in truth["identity"]}
    for row in hub:
        if row["mdm_id"] in truth["duplicates"]:
            continue
        link = true_links[row["mdm_id"]]
        assert row["erp_no"] == link["erp_no"]
        assert row["crm_id"] == (link["crm_id"] or "")


def test_ids_differ_across_systems(scenario):
    _, truth = scenario
    one = truth["identity"][0]
    assert len({one["crm_id"], one["erp_no"], one["billing_ref"], one["mdm_id"]}) == 4


def test_the_hub_has_planted_duplicates_and_corrections(scenario):
    root, truth = scenario
    hub = {r["mdm_id"]: r for r in _rows(root / "mdm" / "golden_customers.csv")}
    assert len(truth["duplicates"]) >= 3
    for dup, original in truth["duplicates"].items():
        assert hub[dup]["erp_no"] == hub[original]["erp_no"]
    erp = {r["KUNNR"]: r for r in _rows(root / "erp" / "customers.csv")}
    for fix in truth["conflicts"]["name_corrected_in_mdm"]:
        assert hub[fix["mdm_id"]]["legal_name"] != erp[fix["erp_no"]]["NAME1"]


def test_the_hub_is_two_to_three_weeks_behind(scenario):
    root, truth = scenario
    lag = truth["staleness"]["mdm_lag_days"]
    assert 14 <= lag <= 21
    synced = max(r["last_synced"] for r in _rows(root / "mdm" / "golden_customers.csv"))
    latest = max(r["ERDAT"] for r in _rows(root / "erp" / "sales_orders.csv"))
    assert (date.fromisoformat(latest) - date.fromisoformat(synced[:10])).days == lag


def test_the_mart_is_built_from_the_wrong_amount_column(scenario):
    root, truth = scenario
    assert truth["mart"]["wrong_column"] == "BRTWR"
    assert truth["mart"]["right_column"] == "NETWR"
    orders = _rows(root / "erp" / "sales_orders.csv")
    hub = {r["erp_no"]: r["mdm_id"] for r in _rows(root / "mdm" / "golden_customers.csv")
           if r["mdm_id"] not in truth["duplicates"]}
    snapshot = truth["mart"]["snapshot_date"]
    expected: dict = {}
    for o in orders:
        if o["ERDAT"] > snapshot:
            continue
        key = (hub[o["KUNNR"]], o["ERDAT"][:7])
        expected[key] = expected.get(key, 0.0) + float(o["BRTWR"])
    mart = {(r["mdm_id"], r["month"]): float(r["revenue"])
            for r in _rows(root / "mart" / "sales_monthly.csv")}
    assert mart.keys() == expected.keys()
    assert all(abs(mart[k] - expected[k]) < 0.05 for k in mart)


@pytest.mark.parametrize("name", SOURCES)
def test_strata_can_read_every_source(scenario, name):
    root, _ = scenario
    schema = connect(str(root / name))
    assert schema.tables
    assert all(t.row_count for t in schema.tables)
