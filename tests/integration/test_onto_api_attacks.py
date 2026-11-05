"""Trying to break the Ontology API: bad input, injection attempts, oversized
payloads, races between builds, edits and deletes. Every answer must be a
clean error with the standard envelope - never a 500, never corrupt data."""

from __future__ import annotations

import concurrent.futures as cf
import time

import pytest
from fastapi.testclient import TestClient

from api import onto_routes
from api.server import create_app
from tests.integration.simple_fixtures import make_iot


def _wait(client, job_id, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.1)
    raise AssertionError("job did not finish")


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    from agent.llm import EYQClient
    root = tmp_path_factory.mktemp("attack")
    original = onto_routes.ai_client
    onto_routes.ai_client = lambda: EYQClient(mock=True)       # offline: no AI calls
    app = create_app(root / "graphs" / "g.duckdb", warm=False)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.graph_file = root / "graphs" / "g.duckdb"
        started = c.post("/api/onto/build", json={
            "name": "Base", "paths": [{"path": str(make_iot(root / "data")), "name": "iot"}]})
        assert _wait(c, started.json()["job_id"])["status"] == "done"
        yield c
    onto_routes.ai_client = original


def build(api, name, sources=("iot",)):
    r = api.post("/api/onto/build", json={"name": name, "sources": list(sources)})
    assert r.status_code == 202, r.text
    return _wait(api, r.json()["job_id"])


def envelope(r):
    body = r.json()
    assert "error" in body or "detail" in body, body
    return body


@pytest.mark.parametrize("body", [
    {}, {"name": ""}, {"name": "x" * 121}, {"name": 123, "sources": "iot"},
    {"name": "x", "sources": [None]}, {"name": "x", "paths": [{"nope": 1}]},
])
def test_invalid_build_bodies_are_rejected(api, body):
    r = api.post("/api/onto/build", json=body)
    assert r.status_code in (400, 422), r.text
    envelope(r)


def test_malformed_json_is_rejected(api):
    r = api.post("/api/onto/build", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_hostile_names_are_stored_as_text_and_ids_stay_safe(api):
    for name in ("<script>alert(1)</script>", "Robert'); DROP TABLE eo_items;--", "顧客 データ 😀",
                 "!!!", "../../etc/passwd"):
        job = build(api, name)
        assert job["status"] == "done", job
        oid = job["result"]["ontology"]
        assert all(ch.isalnum() or ch == "-" for ch in oid), oid
        v = api.get(f"/api/onto/{oid}").json()
        assert v["name"] == name                    # kept verbatim, escaped by the UI
    # The registry survived the "DROP TABLE" name.
    assert api.get("/api/onto").status_code == 200


@pytest.mark.parametrize("oid", ["..%2F..%2Fetc%2Fpasswd", "x'%20OR%201=1--", "%00", "a" * 500,
                                 "new", "all"])
def test_unknown_or_hostile_ids_are_404(api, oid):
    for path in ("", "/nexus", "/excel", "/use"):
        r = api.get(f"/api/onto/{oid}{path}")
        assert r.status_code in (404, 405), (oid, path, r.status_code, r.text[:200])


def test_versions_that_do_not_exist(api):
    for v in ("-1", "0", "999999"):
        assert api.get(f"/api/onto/base/nexus?version={v}").status_code == 404
    assert api.get("/api/onto/base/nexus?version=abc").status_code == 422


def test_oversized_and_empty_context(api):
    assert api.post("/api/onto/base/context", json={"text": "x" * 4001}).status_code in (400, 422)
    assert api.post("/api/onto/base/context", json={"text": "   "}).status_code == 400
    assert api.post("/api/onto/base/context", json={}).status_code == 422


def test_bad_edits(api):
    assert api.put("/api/onto/base/fields", json={"key": "iot.readings.temp_c"}).status_code == 400
    assert api.put("/api/onto/base/fields", json={"key": "iot.readings.temp_c",
                                                  "role": "admin"}).status_code == 400
    assert api.put("/api/onto/base/fields", json={"key": "'; DROP TABLE x;--",
                                                  "label": "x"}).status_code == 404
    assert api.put("/api/onto/base/things", json={"key": "Nope", "name": "x"}).status_code == 404
    assert api.put("/api/onto/base/things", json={"key": "Site"}).status_code == 400


def test_a_huge_source_list_fails_fast(api):
    r = api.post("/api/onto/build", json={"name": "x", "sources": [f"s{i}" for i in range(10000)]})
    assert r.status_code == 400


def test_metadata_paths_that_are_not_metadata(api, tmp_path):
    (tmp_path / "empty").mkdir()
    for path in (str(tmp_path / "empty"), str(tmp_path / "missing.bim"), "C:/Windows/win.ini"):
        r = api.post("/api/onto/build", json={"name": "x", "sources": ["iot"], "metadata": [path]})
        assert r.status_code == 400, (path, r.text)


def test_the_live_database_cannot_be_loaded_as_a_source(api):
    """Pointing the loader at the platform's own database must fail cleanly,
    not lock or corrupt it."""
    r = api.post("/api/onto/build", json={"name": "self", "paths": [{"path": str(api.graph_file)}]})
    job = _wait(api, r.json()["job_id"])
    assert job["status"] == "failed"
    assert api.get("/api/onto/base").status_code == 200        # still healthy


def test_parallel_builds_with_the_same_name_all_succeed(api):
    with cf.ThreadPoolExecutor(5) as pool:
        starts = list(pool.map(lambda _: api.post("/api/onto/build", json={
            "name": "Same Name", "sources": ["iot"]}), range(5)))
    jobs = [_wait(api, s.json()["job_id"]) for s in starts]
    assert [j["status"] for j in jobs] == ["done"] * 5, [j.get("error") for j in jobs]
    ids = {j["result"]["ontology"] for j in jobs}
    assert len(ids) == 5


def test_parallel_edits_publish_distinct_versions(api):
    before = api.get("/api/onto/base").json()["version"]

    def edit(i):
        return api.put("/api/onto/base/fields", json={"key": "iot.readings.battery_pct",
                                                      "label": f"Battery {i}"})
    with cf.ThreadPoolExecutor(8) as pool:
        codes = [r.status_code for r in pool.map(edit, range(16))]
    assert codes == [200] * 16, codes
    after = api.get("/api/onto/base").json()["version"]
    assert after == before + 16
    data = api.get("/api/onto/base/nexus").json()
    assert data["ontology"]["version"] == after


def test_deleting_during_a_rebuild_leaves_nothing_behind(api):
    oid = build(api, "Doomed")["result"]["ontology"]
    started = api.post(f"/api/onto/{oid}/rebuild")
    assert api.delete(f"/api/onto/{oid}").status_code == 200
    job = _wait(api, started.json()["job_id"])
    assert job["status"] in ("done", "failed")
    platform = api.app.state.platform
    tables = [t for (t,) in platform.layer.graph.sql(
        "SELECT DISTINCT table_name FROM information_schema.columns"
        " WHERE column_name = 'ontology_id' AND table_name LIKE 'eo_%'")]
    left = {t: platform.layer.graph.one(f'SELECT count(*) FROM "{t}" WHERE ontology_id = ?', [oid])
            for t in tables}
    assert not any(left.values()), left
    assert api.get(f"/api/onto/{oid}").status_code == 404
    assert api.delete(f"/api/onto/{oid}").status_code == 404


def test_many_parallel_reads(api):
    paths = ["/api/onto", "/api/onto/base", "/api/onto/base/nexus", "/api/onto/base/use"] * 25
    with cf.ThreadPoolExecutor(16) as pool:
        codes = list(pool.map(lambda p: api.get(p).status_code, paths))
    assert codes == [200] * len(paths)
