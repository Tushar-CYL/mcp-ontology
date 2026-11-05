"""Step 6: identity across sources - the MDM problem.

CRM says AC-1000, ERP says 100000, billing says B-5000, the hub says M000000:
one company. Identity is resolved from the hub's cross-reference columns and,
where no hub vouches, from attributes (tax id, normalised name + country).
Scored as pairwise precision and recall against ground_truth.json. Nothing is
merged in the sources: the crosswalk is a separate, reviewable table.
"""

from __future__ import annotations

from itertools import combinations

import pytest

from ontology import identity as idn
from ontology import registry as reg
from tests.integration.eo_fixtures import INTAKE, load_scenario, run_steps

HUB = "bi_mdm.golden_customers"


def _truth_pairs(truth, with_hub=True):
    clusters = {}
    for e in truth["identity"]:
        recs = {("bi_erp.customers", e["erp_no"]),
                ("bi_billing.accounts", e["billing_ref"])}
        if e["crm_id"]:
            recs.add(("bi_crm.accounts", e["crm_id"]))
        if with_hub:
            recs.add((HUB, e["mdm_id"]))
        clusters[e["mdm_id"]] = recs
    if with_hub:
        for dup, original in truth["duplicates"].items():
            clusters[original].add((HUB, dup))
    return {frozenset(p) for recs in clusters.values() for p in combinations(sorted(recs), 2)}


def _found_pairs(result, concept="Customer"):
    by_entity = {}
    for row in result["concepts"][concept]["crosswalk"]:
        by_entity.setdefault(row["entity_id"], set()).add((row["table"], row["record"]))
    return {frozenset(p) for recs in by_entity.values()
            for p in combinations(sorted(recs), 2)}


def _scores(found, truth):
    tp = len(found & truth)
    return tp / len(found) if found else 0.0, tp / len(truth)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    layer, truth, _ = load_scenario(tmp_path_factory.mktemp("id"))
    out = run_steps(layer, upto="identity")
    reg.create(layer.graph, "nohub", **INTAKE, sources=[
        {"source_id": s, "role": "source_system", "owner_team": "IT", "cadence_days": 1}
        for s in ("bi_crm", "bi_erp", "bi_billing")])
    nohub = run_steps(layer, "nohub", upto="identity")
    yield layer, truth, out["identity"], nohub
    layer.close()


def test_identity_with_the_hub_meets_the_bar(built):
    _, truth, result, _ = built
    precision, recall = _scores(_found_pairs(result), _truth_pairs(truth))
    assert precision >= 0.95 and recall >= 0.90, (precision, recall)


def test_every_hub_duplicate_is_found_with_the_right_survivor(built):
    _, truth, result, _ = built
    dups = {f["duplicate"]: f["survivor"] for f in result["findings"]
            if f["type"] == "duplicate_golden_record"}
    assert dups == {f"{HUB}.{d}": f"{HUB}.{o}" for d, o in truth["duplicates"].items()}


def test_entities_are_named_after_the_surviving_golden_record(built):
    _, truth, result, _ = built
    first = truth["identity"][0]
    rows = [r for r in result["concepts"]["Customer"]["crosswalk"]
            if r["record"] == first["erp_no"]]
    assert rows and rows[0]["entity_id"] == first["mdm_id"]


def test_crosswalk_rows_carry_method_and_score(built):
    _, _, result, _ = built
    rows = result["concepts"]["Customer"]["crosswalk"]
    methods = {r["method"] for r in rows}
    assert "mdm_xref" in methods
    assert all(0 < r["score"] <= 1 for r in rows)


def test_without_a_hub_concepts_unify_on_attribute_evidence(built):
    layer, _, _, nohub = built
    concepts = {c["key"]: c["payload"] for c in reg.items(layer.graph, "nohub", kind="concept")}
    assert "Customer" in concepts
    assert set(concepts["Customer"]["members"]) == {
        "bi_crm.accounts", "bi_erp.customers", "bi_billing.accounts"}


def test_without_a_hub_attributes_still_rebuild_the_crosswalk(built):
    _, truth, _, nohub = built
    found = _found_pairs(nohub["identity"])
    precision, recall = _scores(found, _truth_pairs(truth, with_hub=False))
    assert precision >= 0.95 and recall >= 0.90, (precision, recall)
    methods = {r["method"] for r in nohub["identity"]["concepts"]["Customer"]["crosswalk"]}
    assert methods & {"tax_id", "name+country"}


def test_two_records_of_one_source_are_never_merged_on_attributes(built):
    _, _, _, nohub = built
    seen = {}
    for r in nohub["identity"]["concepts"]["Customer"]["crosswalk"]:
        seen.setdefault((r["entity_id"], r["table"]), []).append(r["record"])
    assert all(len(v) == 1 for v in seen.values())


def test_resolve_entity_answers_from_any_id(built):
    layer, truth, _, _ = built
    e = truth["identity"][5]
    for value in (e["erp_no"], e["billing_ref"], e["mdm_id"]):
        got = idn.resolve_entity(layer.graph, "sales", value)
        assert got["entity_id"] == e["mdm_id"]
        assert {"bi_erp.customers", "bi_billing.accounts", HUB} <= set(got["records"])
    assert idn.resolve_entity(layer.graph, "sales", "no-such-id") is None


def test_identity_summary_is_stored(built):
    layer, _, result, _ = built
    item = reg.get_item(layer.graph, "sales", "identity", "Customer")
    assert item["payload"]["entities"] == result["concepts"]["Customer"]["entities"]
    assert item["payload"]["methods"]["mdm_xref"] > 0
    findings = reg.items(layer.graph, "sales", kind="finding")
    assert sum(1 for f in findings if f["payload"]["type"] == "duplicate_golden_record") >= 3
