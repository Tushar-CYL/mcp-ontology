"""Step 10: drift watch and the maturity scorecard.

Drift (maturity level 5): when a source is reloaded it is compared with the
data contract frozen in the last published version - new, removed and
retyped columns, a new money column nobody has mapped, a source falling
behind its SLA - and each difference becomes a PROPOSAL. The published
ontology does not change until a person approves.

Usage (level 5): when an agent asks what an unmapped column means, the gap
is recorded as a proposal instead of being lost.

The scorecard computes the five Modern Data 101 levels from this ontology,
with the checks that pass and fail, so the pitch can say "you are at level 3;
this is what level 4 needs".
"""

from __future__ import annotations

import csv
import json

import pytest

from api import mcp_server
from ontology import drift as dr
from ontology import maturity as mt
from ontology import publish as pub
from ontology import registry as reg
from tests.integration.eo_fixtures import load_scenario, run_steps

KINDS = ("concept", "member", "property", "mapping", "relationship", "hierarchy",
         "identity", "survivorship", "rule", "action")


def _level(card):
    return card["level"]


@pytest.fixture(scope="module")
def journey(tmp_path_factory):
    layer, truth, root = load_scenario(tmp_path_factory.mktemp("dm"))
    run_steps(layer, upto="rules")
    cards = {"after_accelerator": mt.score(layer.graph, "sales")}
    pub.assign_owners(layer.graph, "sales")
    reg.grant(layer.graph, "sales", "ana", "approver")
    for kind in KINDS:
        reg.approve_all(layer.graph, "sales", kind=kind, by="ana")
    v1 = pub.publish_version(layer, "sales", by="ana", notes="v1")
    cards["after_publish"] = mt.score(layer.graph, "sales")

    # The ERP team changes its export: a new money column, BONUS dropped,
    # KWMENG now decimal.
    path = root / "erp" / "sales_orders.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for i, row in enumerate(rows):
        row.pop("BONUS")
        row["SKONTO"] = f"{float(row['NETWR']) * 0.02:.2f}"
        row["KWMENG"] = f"{int(row['KWMENG']) + 0.5}"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    layer.add_source(str(root / "erp"), source="bi_erp", rebuild=True)
    drift = dr.check_drift(layer, "sales")
    mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "map_column",
                                  "arguments": {"column": "bi_erp.sales_orders.SKONTO"}}},
                      layer)
    cards["after_drift"] = mt.score(layer.graph, "sales")
    yield layer, truth, v1, drift, cards
    layer.close()


def _of(drift, kind, column=None):
    return [d for d in drift["changes"] if d["type"] == kind
            and (column is None or d.get("column") == column)]


def test_a_new_money_column_is_proposed_for_mapping(journey):
    _, _, _, drift, _ = journey
    found = _of(drift, "new_amount_column", "SKONTO")
    assert found and found[0]["table"] == "bi_erp.sales_orders"
    assert "map" in found[0]["suggestion"]


def test_removed_and_retyped_columns_are_reported(journey):
    _, _, _, drift, _ = journey
    assert _of(drift, "removed_column", "BONUS")
    retyped = _of(drift, "retyped_column", "KWMENG")
    assert retyped and retyped[0]["was"] != retyped[0]["now"]


def test_stale_sources_are_part_of_drift(journey):
    _, _, _, drift, _ = journey
    assert {d["source"] for d in _of(drift, "freshness_breach")} == {"bi_mdm", "bi_mart"}


def test_drift_only_proposes_it_never_changes_the_published_ontology(journey):
    layer, _, v1, _, _ = journey
    assert reg.version(layer.graph, "sales")["version"] == v1["version"]
    contract = pub.get_contract(layer.graph, "sales", "bi_erp.sales_orders")
    assert "BONUS" in {c["name"] for c in contract["columns"]}
    proposals = reg.items(layer.graph, "sales", kind="drift", status="proposed")
    assert any("SKONTO" in p["key"] for p in proposals)


def test_an_agent_asking_about_an_unmapped_column_is_remembered(journey):
    layer, _, _, _, _ = journey
    gaps = [p for p in reg.items(layer.graph, "sales", kind="drift")
            if p["payload"].get("type") == "usage_gap"]
    assert gaps and gaps[0]["payload"]["column"] == "bi_erp.sales_orders.SKONTO"
    assert gaps[0]["payload"]["asked"] >= 1


def test_drift_check_with_nothing_published_explains_itself(tmp_path):
    from api.service import MiddleLayer
    layer = MiddleLayer(str(tmp_path / "x.duckdb"))
    reg.create(layer.graph, "empty", name="empty")
    with pytest.raises(ValueError, match="publish"):
        dr.check_drift(layer, "empty")
    layer.close()


# ----------------------------------------------------------- maturity
def test_the_accelerator_alone_reaches_level_one(journey):
    *_, cards = journey
    card = cards["after_accelerator"]
    assert _level(card) == 1
    l2 = next(lv for lv in card["levels"] if lv["level"] == 2)
    assert not l2["passed"]
    assert any(not c["passed"] and "owner" in c["name"].lower() for c in l2["checks"])


def test_governed_publishing_reaches_level_four(journey):
    *_, cards = journey
    assert _level(cards["after_publish"]) == 4


def test_drift_watch_and_usage_learning_reach_level_five(journey):
    *_, cards = journey
    assert _level(cards["after_drift"]) == 5


def test_every_level_has_named_checks_with_details(journey):
    *_, cards = journey
    card = cards["after_publish"]
    assert [lv["level"] for lv in card["levels"]] == [1, 2, 3, 4, 5]
    names = [lv["name"] for lv in card["levels"]]
    assert names == ["Infrastructure", "Ownership", "Standardisation", "Governed",
                     "Autonomous"]
    for lv in card["levels"]:
        assert len(lv["checks"]) >= 3
        for c in lv["checks"]:
            assert c["name"] and c["detail"]
    assert card["next_steps"]                               # what L5 needs
    json.dumps(card)                                        # serialisable for the UI
