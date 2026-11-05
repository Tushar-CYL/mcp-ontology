"""The Ontology Accelerator through the real HTTP API, end to end.

Load the demo in the background, read the journey state, review and approve,
grant roles, publish, diff, export (Turtle, SHACL, a Git zip), resolve an
entity, ask what a column means, check drift and maturity - and the error
paths a UI will hit (unknown ontology, unloaded source, non-approver).
"""

from __future__ import annotations

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from api.server import create_app

KINDS = ("concept", "member", "property", "mapping", "relationship", "hierarchy",
         "identity", "survivorship", "rule", "action")


def _wait(client, job_id, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.3)
    raise AssertionError(f"job {job_id} did not finish")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    app = create_app(tmp_path_factory.mktemp("eoapi") / "graphs" / "eo.duckdb", warm=False)
    with TestClient(app) as c:
        started = c.post("/api/eo/demo", json={"customers": 120})
        assert started.status_code == 202
        job = _wait(c, started.json()["job_id"])
        assert job["status"] == "done", job
        c.demo_job = job
        yield c


def test_demo_job_reports_every_step(client):
    texts = " ".join(s["text"] for s in client.demo_job["steps"])
    for word in ("generating", "loading mdm", "Shared concepts", "Rules and actions"):
        assert word in texts
    assert client.demo_job["result"]["run"]["seconds"] < 60


def test_listing_and_state(client):
    listed = client.get("/api/eo/ontologies").json()["ontologies"]
    assert [o["id"] for o in listed] == ["sales"]
    state = client.get("/api/eo/sales").json()
    assert [s["id"] for s in state["steps"]][:3] == ["intake", "profile", "concepts"]
    concepts = next(s for s in state["steps"] if s["id"] == "concepts")
    assert concepts["status"] == "review" and concepts["pending"] > 0
    assert any(f["type"] == "wrong_amount_column" for f in state["findings"])
    assert state["maturity"]["level"] == 1


def test_steps_catalogue(client):
    steps = client.get("/api/eo/steps").json()["steps"]
    assert len(steps) == 11 and all(s["what"] for s in steps)


def test_knowledge_map(client):
    m = client.get("/api/eo/sales/map").json()
    types = {n["type"] for n in m["nodes"]}
    assert {"concept", "table", "hierarchy"} <= types
    assert any(e["type"] == "relationship" for e in m["edges"])


def test_review_edit_and_audit(client):
    items = client.get("/api/eo/sales/items", params={"kind": "mapping"}).json()["items"]
    target = next(i for i in items if i["key"] == "bi_erp.sales_orders.WAVWR")
    edited = client.post("/api/eo/sales/decide", json={
        "kind": "mapping", "key": target["key"], "decision": "edited", "by": "ana",
        "payload": {**target["payload"], "definition": "Standard cost of goods."},
        "note": "finance wording"}).json()
    assert edited["status"] == "approved"
    audit = client.get("/api/eo/sales/audit").json()["audit"]
    assert audit[-1]["note"] == "finance wording"


def test_governance_publish_diff_and_exports(client):
    assert client.post("/api/eo/sales/owners").json()["owners"]["Customer"]
    client.post("/api/eo/sales/roles", json={"user": "ana", "role": "approver"})
    client.post("/api/eo/sales/roles", json={"user": "bob", "role": "viewer"})
    denied = client.post("/api/eo/sales/approve-all", json={"kind": "concept", "by": "bob"})
    assert denied.status_code == 403
    for kind in KINDS:
        assert client.post("/api/eo/sales/approve-all",
                           json={"kind": kind, "by": "ana"}).status_code == 200
    v1 = client.post("/api/eo/sales/publish", json={"by": "ana", "notes": "v1"}).json()
    assert v1["version"] == 1 and v1["counts"]["contract"] >= 7
    concepts = client.get("/api/eo/sales/items", params={"kind": "concept"}).json()["items"]
    invoice = next(i for i in concepts if i["key"] == "Invoice")
    client.post("/api/eo/sales/decide", json={
        "kind": "concept", "key": "Invoice", "decision": "edited", "by": "ana",
        "payload": {**invoice["payload"], "description": "A bill sent to a customer."}})
    v2 = client.post("/api/eo/sales/publish", json={"by": "ana", "notes": "v2"}).json()
    assert v2["version"] == 2
    diff = client.get("/api/eo/sales/diff", params={"a": 1, "b": 2}).json()
    assert diff["changed"]
    ttl = client.get("/api/eo/sales/export/turtle")
    assert ttl.status_code == 200 and "owl:Class" in ttl.text
    assert "sh:NodeShape" in client.get("/api/eo/sales/export/shacl").text
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/eo/sales/export/zip").content))
    names = z.namelist()
    assert "sales/ontology.ttl" in names and "sales/CHANGELOG.md" in names


def test_column_entity_drift_and_maturity(client):
    col = client.get("/api/eo/sales/column",
                     params={"column": "bi_mart.sales_monthly.revenue"}).json()
    assert col["property"] == "gross_amount" and col["findings"]
    customers = client.get("/api/eo/sales/items", params={"kind": "identity"}).json()
    assert customers["items"]
    entity = client.get("/api/eo/sales/resolve", params={"value": "M000001"}).json()
    assert entity["entity_id"] == "M000001" and entity["golden"]
    drift = client.post("/api/eo/sales/drift").json()
    assert {c["type"] for c in drift["changes"]} == {"freshness_breach"}
    card = client.get("/api/eo/sales/maturity").json()
    assert card["level"] == 4                       # no usage learning recorded yet
    assert card["next_steps"]


@pytest.mark.parametrize("method, url, body, status", [
    ("get", "/api/eo/nope", None, 404),
    ("get", "/api/eo/sales/resolve?value=zzz", None, 404),
    ("get", "/api/eo/sales/column?column=bi_erp.nope.x", None, 404),
    ("get", "/api/eo/sales/diff?a=1&b=99", None, 404),
    ("post", "/api/eo/ontologies", {"id": "x", "name": "x", "sources": [
        {"source_id": "not_loaded"}]}, 400),
    ("post", "/api/eo/ontologies", {"id": "sales", "name": "dup", "sources": []}, 400),
    ("post", "/api/eo/sales/decide", {"kind": "concept", "key": "Customer",
                                      "decision": "maybe", "by": "ana"}, 400),
    ("post", "/api/eo/sales/roles", {"user": "x", "role": "emperor"}, 400),
])
def test_error_paths_use_the_envelope(client, method, url, body, status):
    response = getattr(client, method)(url, json=body) if body is not None \
        else getattr(client, method)(url)
    assert response.status_code == status, response.text
    assert set(response.json()["error"]) == {"type", "message"}
