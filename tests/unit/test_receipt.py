"""The layer receipt: which of the four layers an answer used, in plain words.

No vendor reviewed in the research gives end users a layer-level receipt
(docs/research/2026/REPORT.md, "Trust comes from refusal..."). Every Strata
answer gets one, always in the same order, naming what each layer contributed
and saying plainly when a layer was not needed.
"""

from __future__ import annotations

from agent.receipt import LAYERS, build_receipt, receipt_from_facts


def test_layers_are_always_the_four_in_order():
    assert LAYERS == ("ontology", "graph", "semantic", "context")
    receipt = build_receipt([])
    assert [item["layer"] for item in receipt["layers"]] == list(LAYERS)
    assert all(item["used"] is False for item in receipt["layers"])
    assert receipt["text"] == "Used: no layers."


def test_steps_are_summarised_per_layer():
    receipt = build_receipt([
        {"layer": "ontology", "detail": "Order"},
        {"layer": "semantic", "detail": "Revenue (approved)"},
        {"layer": "semantic", "detail": "compared with September"},
        {"layer": "context", "detail": "5 cited facts, 3 dropped"},
    ])
    by_layer = {item["layer"]: item for item in receipt["layers"]}
    assert by_layer["ontology"]["summary"] == "Order"
    assert by_layer["semantic"]["summary"] == "Revenue (approved); compared with September"
    assert by_layer["graph"]["used"] is False
    assert by_layer["graph"]["summary"] == "not needed"
    assert receipt["text"] == ("Used: Ontology (Order) · Semantic (Revenue (approved); "
                               "compared with September) · Context (5 cited facts, 3 dropped).")


def test_duplicate_details_are_collapsed_and_unknown_layers_ignored():
    receipt = build_receipt([
        {"layer": "graph", "detail": "Customer c1"},
        {"layer": "graph", "detail": "Customer c1"},
        {"layer": "warehouse", "detail": "ignored"},
        {"layer": "ontology", "detail": ""},
    ])
    by_layer = {item["layer"]: item for item in receipt["layers"]}
    assert by_layer["graph"]["summary"] == "Customer c1"
    assert by_layer["ontology"]["used"] is True
    assert by_layer["ontology"]["summary"] == "used"
    assert "warehouse" not in receipt["text"]


def test_receipt_from_context_pack_facts():
    kept = [
        {"kind": "definition", "citation": "metric_definition:revenue"},
        {"kind": "metric", "citation": "metric:revenue:current"},
        {"kind": "contribution", "citation": "metric:revenue:segment:A"},
        {"kind": "relationship", "citation": "relationship:placed_by"},
        {"kind": "source_row", "citation": "row:orders:1"},
    ]
    dropped = [{"kind": "trend"}, {"kind": "trend"}]
    receipt = receipt_from_facts(kept, dropped, metric_title="Revenue",
                                 metric_status="approved")
    by_layer = {item["layer"]: item for item in receipt["layers"]}
    assert by_layer["semantic"]["summary"] == "Revenue (approved)"
    assert by_layer["ontology"]["summary"] == "1 relationship"
    assert by_layer["graph"]["summary"] == "1 source row"
    assert by_layer["context"]["summary"] == "5 cited facts, 2 dropped"


def test_receipt_from_an_empty_pack():
    receipt = receipt_from_facts([], [], metric_title=None)
    by_layer = {item["layer"]: item for item in receipt["layers"]}
    assert by_layer["context"]["summary"] == "0 cited facts"
    assert by_layer["semantic"]["used"] is False
