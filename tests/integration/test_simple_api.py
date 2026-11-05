"""The simple ontology flow through the real HTTP API and MCP: connect a
folder, build, read, add context, edit, export for Nexus/Excel, serve to an
agent, delete - plus the error paths the screens will hit."""

from __future__ import annotations

import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from api import onto_routes
from api.server import create_app
from tests.integration.simple_fixtures import FakeAI, make_clinic, make_iot


def _wait(client, job_id, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} did not finish")


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("onto")
    fake = FakeAI()
    original = onto_routes.ai_client
    onto_routes.ai_client = lambda: fake
    app = create_app(root / "graphs" / "g.duckdb", warm=False)
    with TestClient(app) as c:
        c.fake = fake
        c.iot = make_iot(root / "data")
        c.clinic = make_clinic(root / "data")
        yield c
    onto_routes.ai_client = original


@pytest.fixture(scope="module")
def built(api):
    started = api.post("/api/onto/build", json={
        "name": "Factory Sensors", "paths": [{"path": str(api.iot), "name": "iot"}],
        "domain": "Manufacturing IoT"})
    assert started.status_code == 202
    job = _wait(api, started.json()["job_id"])
    assert job["status"] == "done", job
    assert any("Published version 1" in s["text"] for s in job["steps"])
    return job["result"]["ontology"]


def test_build_from_a_folder_path(api, built):
    assert built == "factory-sensors"
    listing = api.get("/api/onto").json()
    assert listing["ai"]["configured"] is True and listing["ai"]["model"] == "fake-model"
    assert "identifier" in listing["roles"]
    row = next(o for o in listing["ontologies"] if o["id"] == built)
    assert row["sources"] == ["iot"] and row["version"] == 1
    assert row["summary"]["things"] == 3


def test_view_has_things_fields_links_in_plain_words(api, built):
    v = api.get(f"/api/onto/{built}").json()
    assert {t["name"] for t in v["things"]} == {"Site", "Device", "Sensor Reading"}
    reading = next(t for t in v["things"] if t["name"] == "Sensor Reading")
    temp = next(f for f in reading["fields"] if f["column"] == "temp_c")
    assert temp["label"] == "Temperature" and temp["check"] == "verified"
    assert temp["role_label"] == "Measured number"
    assert any(l["label"] == "Each Sensor Reading belongs to one Device (one Device can have many)"
               for l in v["links"])
    assert v["built"]["ai"]["used"] is True


def test_context_and_edits_publish_new_versions(api, built):
    out = api.post(f"/api/onto/{built}/context", json={"text": "battery_pct = Battery charge"})
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["changes"] and body["version"] == 2
    # Every response that carries the ontology carries what the screen reads.
    assert {"ai", "roles"} <= set(body["ontology"])
    field = api.put(f"/api/onto/{built}/fields",
                    json={"key": "iot.readings.status_code", "meaning": "Health reported "
                          "by the device firmware."})
    assert field.status_code == 200
    assert {"ai", "roles"} <= set(field.json())
    thing = api.put(f"/api/onto/{built}/things", json={"key": "Site", "name": "Plant"})
    assert {t["name"] for t in thing.json()["things"]} >= {"Plant"}
    assert thing.json()["version"] == 4
    bad = api.put(f"/api/onto/{built}/fields", json={"key": "iot.readings.temp_c",
                                                       "role": "nonsense"})
    assert bad.status_code == 400
    assert api.put(f"/api/onto/{built}/fields",
                   json={"key": "iot.x.y", "label": "z"}).status_code == 404
    assert api.post(f"/api/onto/{built}/context", json={"text": " "}).status_code == 400


def test_nexus_json_excel_and_use_links(api, built):
    data = api.get(f"/api/onto/{built}/nexus").json()
    assert set(data) == {"ontology", "things", "fields", "links", "calculations"}
    assert data["ontology"]["version"] >= 1
    assert {"Thing", "Field", "Meaning", "Role", "Unit", "Check", "Proof"} <= set(
        data["fields"][0])
    pinned = api.get(f"/api/onto/{built}/nexus?version=1").json()
    assert pinned["ontology"]["version"] == 1
    assert "Plant" not in {t["Thing"] for t in pinned["things"]}
    xlsx = api.get(f"/api/onto/{built}/excel")
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.headers["content-type"]
    assert zipfile.ZipFile(io.BytesIO(xlsx.content)).testzip() is None
    use = api.get(f"/api/onto/{built}/use").json()
    assert use["nexus"]["url"].endswith(f"/api/onto/{built}/nexus")
    assert use["agents"]["tool"] == "get_ontology"


def _mcp(api, name, args, scope=None):
    from api import mcp_server
    layer = api.app.state.platform.layer
    body = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": name, "arguments": args}}, layer,
                             scope=scope)
    if "error" in body:
        return body["error"]
    return json.loads(body["result"]["content"][0]["text"])


def test_agents_get_the_published_ontology_over_mcp(api, built):
    payload = _mcp(api, "get_ontology", {"ontology": built, "thing": "Sensor Reading"})
    assert [t["name"] for t in payload["things"]] == ["Sensor Reading"]
    temp = next(f for f in payload["things"][0]["fields"] if f["column"].endswith("temp_c"))
    assert temp["label"] == "Temperature" and temp["checked"] == "verified"
    assert payload["links"]
    missing = _mcp(api, "get_ontology", {"ontology": built, "thing": "Nope"})
    assert "no thing" in json.dumps(missing)
    other = _mcp(api, "get_ontology", {"ontology": built},
                 scope={"sources": ["clinic"], "metrics": [], "agent_id": "a"})
    assert "forbidden" in json.dumps(other).lower()


def test_metadata_added_later_triggers_a_rebuild(api, built, tmp_path):
    d = tmp_path / "dict.csv"
    d.write_text("table,column,description\nreadings,temp_c,Motor winding temperature\n",
                 encoding="utf-8")
    out = api.post(f"/api/onto/{built}/metadata", json={"path": str(d)})
    assert out.status_code == 202
    assert _wait(api, out.json()["job_id"])["status"] == "done"
    v = api.get(f"/api/onto/{built}").json()
    temp = next(f for t in v["things"] for f in t["fields"] if f["column"] == "temp_c")
    assert temp["meaning"] == "Motor winding temperature" and temp["by"] == "metadata"
    assert api.post(f"/api/onto/{built}/metadata",
                    json={"path": str(tmp_path / "nope.csv")}).status_code == 400


def test_errors_the_screens_will_hit(api):
    assert api.get("/api/onto/nope").status_code == 404
    assert api.post("/api/onto/build", json={"name": "x"}).status_code == 400
    assert api.post("/api/onto/build", json={"name": "x", "metadata": ["missing.bim"]}
                    ).status_code == 400
    failed = api.post("/api/onto/build", json={"name": "x", "sources": ["not_loaded"]})
    assert failed.status_code == 400 and "not loaded" in failed.text
    bad_path = api.post("/api/onto/build", json={"name": "x", "paths": [{"path": "nope/x"}]})
    job = _wait(api, bad_path.json()["job_id"])
    assert job["status"] == "failed" and "nope" in job["error"]
    assert "x" not in {o["id"] for o in api.get("/api/onto").json()["ontologies"]}


def test_second_source_and_delete(api):
    started = api.post("/api/onto/build", json={
        "name": "Clinic", "paths": [{"path": str(api.clinic), "name": "clinic"}]})
    job = _wait(api, started.json()["job_id"])
    assert job["status"] == "done", job
    oid = job["result"]["ontology"]
    assert api.delete(f"/api/onto/{oid}").json() == {"deleted": oid}
    assert api.get(f"/api/onto/{oid}").status_code == 404
    assert "clinic" in [s["id"] for s in api.get("/api/sources").json()["sources"]]
