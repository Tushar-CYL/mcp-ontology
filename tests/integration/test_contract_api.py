"""The open ontology format and the three build modes over HTTP and MCP."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from api import onto_routes
from api.server import create_app
from tests.integration.simple_fixtures import FakeAI, make_iot


def _wait(client, job_id, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} did not finish")


def _build(api, body):
    r = api.post("/api/onto/build", json=body)
    assert r.status_code == 202, r.text
    job = _wait(api, r.json()["job_id"])
    assert job["status"] == "done", job
    return job["result"]["ontology"]


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("contract")
    fake = FakeAI()
    original = onto_routes.ai_client
    onto_routes.ai_client = lambda: fake
    app = create_app(root / "graphs" / "g.duckdb", warm=False)
    with TestClient(app) as c:
        c.fake, c.root = fake, root
        c.iot = make_iot(root / "data")
        yield c
    onto_routes.ai_client = original


@pytest.fixture(scope="module")
def first(api):
    return _build(api, {"name": "Sensors", "paths": [{"path": str(api.iot), "name": "iot"}]})


def test_download_the_ontology_as_an_open_document(api, first):
    r = api.get(f"/api/onto/{first}/contract")
    assert r.status_code == 200
    assert "strata-model.json" in r.headers["content-disposition"]
    doc = r.json()
    assert doc["spec"] == "strata.model/v1" and doc["things"] and doc["links"]
    assert api.get("/api/onto/nope/contract").status_code == 404


def test_use_the_downloaded_document_exactly(api, first):
    doc = api.get(f"/api/onto/{first}/contract").json()
    doc["things"][0]["name"] = "Renamed By Us"
    path = api.root / "mine.strata-model.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    calls = api.fake.calls if hasattr(api.fake, "calls") else None
    oid = _build(api, {"name": "Mine", "sources": ["iot"], "metadata": [str(path)], "mode": "model"})
    view = api.get(f"/api/onto/{oid}").json()
    assert view["mode"] == "model"
    assert "Renamed By Us" in [t["name"] for t in view["things"]]
    # CSV files declare no keys: the links the engine found are in the file,
    # and an exact build keeps every one of them (live on Olist it lost all 7).
    original = api.get(f"/api/onto/{first}").json()
    assert len(view["links"]) == len(original["links"]) > 0
    assert view["summary"]["confirmed_pct"] == original["summary"]["confirmed_pct"]
    assert view["built"]["ai"]["used"] is False
    if calls is not None:
        assert api.fake.calls == calls                     # the AI was not asked


def test_model_mode_needs_a_file(api):
    r = api.post("/api/onto/build", json={"name": "x", "sources": ["iot"], "mode": "model"})
    assert r.status_code == 400 and "file" in r.json()["error"]["message"]
    r = api.post("/api/onto/build", json={"name": "x", "sources": ["iot"], "mode": "magic"})
    assert r.status_code == 422


def test_keys_only_never_asks_the_ai_even_on_rebuild(api):
    oid = _build(api, {"name": "Keys", "sources": ["iot"], "mode": "keys"})
    view = api.get(f"/api/onto/{oid}").json()
    assert view["mode"] == "keys" and view["built"]["ai"]["used"] is False
    r = api.post(f"/api/onto/{oid}/rebuild")
    job = _wait(api, r.json()["job_id"])
    assert job["status"] == "done"
    assert api.get(f"/api/onto/{oid}").json()["built"]["ai"]["used"] is False


def test_a_broken_document_is_refused_with_its_problems(api):
    path = api.root / "broken.json"
    path.write_text(json.dumps({"spec": "strata.model/v1", "name": "b",
                                "things": [{"name": "A", "tables": []}]}), encoding="utf-8")
    r = api.post("/api/onto/build", json={"name": "b", "sources": ["iot"],
                                          "metadata": [str(path)], "mode": "model"})
    assert r.status_code == 400
    assert "tables must be a non-empty list" in r.json()["error"]["message"]


def test_an_agent_gets_the_same_document_over_mcp(api, first):
    from api import mcp_server
    layer = api.app.state.platform.layer
    body = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "get_ontology",
                                         "arguments": {"ontology": first, "format": "contract"}}},
                             layer)
    doc = json.loads(body["result"]["content"][0]["text"])
    assert doc["spec"] == "strata.model/v1"
    assert doc["things"] == api.get(f"/api/onto/{first}/contract").json()["things"]
