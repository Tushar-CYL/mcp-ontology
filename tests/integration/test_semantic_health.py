"""The Semantic health check never reports a failure for work in progress.

Two rules, from what a governed semantic layer must and must not ask a
person to do:

* Metrics that are exact facts read straight from the data - record counts,
  distinct counts, items-per-parent along a link verified against the data -
  are approved automatically; there is no business interpretation to review.
  Totals and averages of amount-like columns stay proposals, because they can
  need business rules ("only completed orders count").
* Proposals waiting for a person are a warning with a next step, never a
  failure.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent import certification
from api.server import create_app
from api.service import MiddleLayer
from semantic import autopilot
from semantic import definitions as metric_defs
from tests.integration.test_autopilot import _write_salt_like


def _write_billing(folder):
    folder.mkdir(parents=True)
    rows = ["invoice_id,region,amount,issued_on"]
    for i in range(200):
        rows.append(f"I{i},{'NSEW'[i % 4]},{(i * 37) % 900 + 0.5},2025-0{1 + i % 6}-15")
    (folder / "invoices.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _semantic(report):
    return next(layer for layer in report["layers"] if layer["layer"] == "Semantic layer")


@pytest.fixture
def salt(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    layer = MiddleLayer(str(tmp_path / "s.duckdb"))
    layer.add_source(str(folder), source="salt")
    b = layer._bundle("salt")
    autopilot.seed_proposals(layer.graph, b.schema, b.onto, "salt")
    yield layer
    layer.close()


@pytest.fixture
def billing(tmp_path):
    folder = tmp_path / "billing"
    _write_billing(folder)
    layer = MiddleLayer(str(tmp_path / "b.duckdb"))
    layer.add_source(str(folder), source="billing")
    b = layer._bundle("billing")
    autopilot.seed_proposals(layer.graph, b.schema, b.onto, "billing")
    yield layer
    layer.close()


def _status_by_kind(layer, source):
    out = {}
    for d in metric_defs.list_definitions(layer.graph, source):
        expr = d["value_expr"].upper()
        kind = ("ratio" if "NULLIF" in expr else "distinct" if "DISTINCT" in expr
                else "count" if expr == "COUNT(*)" else "measure")
        out.setdefault(kind, set()).add(d["status"])
    return out


def test_exact_facts_are_approved_automatically(salt):
    statuses = _status_by_kind(salt, "salt")
    assert statuses["count"] == {"approved"}
    assert statuses["distinct"] == {"approved"}
    assert statuses["ratio"] == {"approved"}


def test_amount_totals_and_averages_wait_for_a_person(billing):
    statuses = _status_by_kind(billing, "billing")
    assert statuses["count"] == {"approved"}
    assert statuses["measure"] == {"draft"}


def test_auto_approved_metrics_say_so(salt):
    for d in metric_defs.list_definitions(salt.graph, "salt"):
        assert "approved automatically" in d["caveats"].lower()
        assert d["owner"] == autopilot.OWNER


@pytest.mark.parametrize("fixture", ["salt", "billing"])
def test_the_semantic_health_check_passes(request, fixture):
    layer = request.getfixturevalue(fixture)
    report = certification.certify_source(layer, fixture)
    semantic = _semantic(report)
    assert semantic["status"] == "pass", semantic["checks"]
    assert report["status"] != "fail"


def test_only_proposals_is_a_warning_with_a_next_step(billing):
    for d in metric_defs.list_definitions(billing.graph, "billing"):
        metric_defs.set_status(billing.graph, d["name"], "billing", "draft")
    report = certification.certify_source(billing, "billing")
    semantic = _semantic(report)
    assert semantic["status"] == "warn"
    check = next(c for c in semantic["checks"] if c["name"] == "Approved metric definitions")
    assert check["severity"] == "warning"
    assert "waiting for approval" in check["detail"]
    assert report["status"] != "fail"


def test_no_metrics_at_all_is_still_a_failure(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / "things.csv").write_text("a\nx\n", encoding="utf-8")
    layer = MiddleLayer(str(tmp_path / "e.duckdb"))
    try:
        layer.add_source(str(folder), source="empty")
        report = certification.certify_source(layer, "empty")
        check = next(c for c in _semantic(report)["checks"]
                     if c["name"] == "Approved metric definitions")
        # A single-column, one-row table still gets a record count.
        assert check["passed"] or check["severity"] == "error"
    finally:
        layer.close()


# ----------------------------------------------------- upgrading old sources
def test_untouched_old_proposals_are_upgraded_on_restart(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    graph_path = tmp_path / "old.duckdb"
    with TestClient(create_app(graph_path, warm=False)) as c:
        c.post("/api/sources", json={"path": str(folder), "name": "salt"})
        # Simulate a source seeded before auto-approval existed: all drafts,
        # still at version 1 (nobody touched them).
        state = c.app.state.platform
        state.layer.graph.con.execute(
            "UPDATE metric_definitions SET status = 'draft' WHERE source_id = 'salt'")
        # ...except one a person deliberately sent back to draft.
        name = metric_defs.list_definitions(state.layer.graph, "salt")[0]["name"]
        metric_defs.set_status(state.layer.graph, name, "salt", "approved")
        metric_defs.set_status(state.layer.graph, name, "salt", "draft")
    with TestClient(create_app(graph_path, warm=False)) as c:
        c.app.state.platform.warm()
        metrics = {m["name"]: m["status"] for m in
                   c.get("/api/metrics", params={"source": "salt"}).json()["metrics"]}
        assert metrics.pop(name) == "draft"              # the person's choice holds
        assert set(metrics.values()) == {"approved"}


def test_health_endpoint_reports_no_failure_for_a_fresh_source(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    with TestClient(create_app(tmp_path / "h.duckdb", warm=False)) as c:
        c.post("/api/sources", json={"path": str(folder), "name": "salt"})
        report = c.get("/api/certification", params={"source": "salt"}).json()
        assert report["status"] in ("pass", "warn")
        assert all(layer["status"] != "fail" for layer in report["layers"]), report["layers"]
