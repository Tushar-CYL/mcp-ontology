"""Step 7: conflicts, freshness and survivorship.

"Three sources of truth, the hub runs 2-3 weeks behind, old records keep
getting corrected." This step measures exactly that: how far behind each
source is against its own refresh SLA, where systems disagree about the same
entity (and whether it is the hub overriding all sources - a steward's
correction - or the sources disagreeing among themselves), and which source
should win each property.
"""

from __future__ import annotations

import pytest

from ontology import registry as reg
from ontology import survivorship as sv
from tests.integration.eo_fixtures import load_scenario, run_steps


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    layer, truth, _ = load_scenario(tmp_path_factory.mktemp("sv"))
    out = run_steps(layer, upto="survivorship")
    yield layer, truth, out["survivorship"]
    layer.close()


def _fresh(result, source):
    return next(f for f in result["freshness"] if f["source"] == source)


def test_hub_and_mart_lag_matches_the_truth_and_breaches_sla(built):
    _, truth, result = built
    lag = truth["staleness"]["mdm_lag_days"]
    for source in ("bi_mdm", "bi_mart"):
        f = _fresh(result, source)
        assert f["lag_days"] == lag
        assert f["sla_days"] == 7
        assert f["breach"] is True


def test_source_systems_are_current(built):
    _, _, result = built
    for source in ("bi_erp", "bi_crm", "bi_billing"):
        f = _fresh(result, source)
        assert f["lag_days"] <= f["sla_days"], f
        assert f["breach"] is False


def test_freshness_ignores_future_looking_dates(built):
    _, truth, result = built
    assert result["as_of"] == truth["staleness"]["latest_source_date"]   # not a due date


def test_every_planted_correction_is_found_as_a_hub_override(built):
    _, truth, result = built
    name = next(c for c in result["conflicts"]
                if c["concept"] == "Customer" and c["property"] == "customer_name")
    overrides = {e["entity_id"] for e in name["examples_all"] if e["kind"] == "hub_override"}
    planted = {fix["mdm_id"] for fix in truth["conflicts"]["name_corrected_in_mdm"]}
    assert overrides == planted


def test_cosmetic_differences_are_not_conflicts(built):
    _, _, result = built
    country = [c for c in result["conflicts"] if c["property"] == "country"]
    assert all(c["entities_in_conflict"] == 0 for c in country)
    # CRM writes "G.m.b.H.", billing lower-cases names: not conflicts.
    name = next(c for c in result["conflicts"] if c["property"] == "customer_name")
    assert name["by_kind"].get("source_disagreement", 0) == 0


def test_survivorship_rules_are_proposed_with_reasons(built):
    layer, _, result = built
    rules = {(r["concept"], r["property"]): r for r in result["survivorship"]}
    name = rules[("Customer", "customer_name")]
    assert name["rule"] == "master_wins" and name["winner"] == "bi_mdm"
    assert "correct" in name["reason"]
    assert "behind" in name["caveat"]                 # the hub is stale
    net = rules[("SalesOrder", "net_amount")]
    assert net["rule"] == "system_of_record" and net["winner"] == "bi_erp"
    stored = reg.items(layer.graph, "sales", kind="survivorship")
    assert any(i["key"] == "Customer.customer_name" for i in stored)


def test_golden_record_applies_the_rules(built):
    layer, truth, _ = built
    fix = truth["conflicts"]["name_corrected_in_mdm"][0]
    golden = sv.golden_record(layer, "sales", "Customer", fix["mdm_id"])
    assert golden["customer_name"]["value"] == fix["mdm_value"]
    assert golden["customer_name"]["source"] == "bi_mdm.golden_customers"
    assert golden["country"]["value"]


def test_stale_sources_become_findings(built):
    layer, _, _ = built
    findings = {i["key"]: i["payload"] for i in reg.items(layer.graph, "sales", kind="finding")}
    assert "stale_source|bi_mdm" in findings
    assert "days behind" in findings["stale_source|bi_mdm"]["detail"]
    assert "stale_source|bi_erp" not in findings
