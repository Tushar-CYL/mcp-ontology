"""The Knowledge graph REST API, end to end through FastAPI."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from api.server import create_app
from tests.integration.test_declared_links import make_shop


def _client_with_shop(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setenv("STRATA_DATA_ROOTS", "")
    app = create_app(tmp_path / "g.duckdb", warm=False)
    c = TestClient(app)
    c.__enter__()
    db = make_shop(tmp_path / "shop.db")
    r = c.post("/api/onto/build", json={"name": "Shop", "paths": [{"path": str(db)}]})
    assert r.status_code == 202
    job = r.json()["job_id"]
    import time
    for _ in range(300):
        j = c.get(f"/api/jobs/{job}").json()
        if j["status"] != "running":
            break
        time.sleep(0.1)
    assert j["status"] == "done", j
    return c, j["result"]["ontology"]


def test_graph_api_overview_search_entity_path_export(tmp_path, monkeypatch):
    c, oid = _client_with_shop(tmp_path, monkeypatch)
    try:
        o = c.get(f"/api/kg/{oid}/overview").json()
        assert o["summary"]["broken_links"] == 10 and o["health"]

        hit = c.get(f"/api/kg/{oid}/search", params={"q": "Customer 17"}).json()["results"][0]
        assert hit["key"] == "17"

        e = c.get(f"/api/kg/{oid}/entity", params={"set": hit["set"], "key": "17"}).json()
        assert e["label"] == "Customer 17" and e["connections"]

        p = c.get(f"/api/kg/{oid}/path", params={"from_set": "shop.customer", "from_key": "2",
                                                 "to_set": "shop.customer", "to_key": "42",
                                                 "max_hops": 6}).json()
        assert p["found"]

        r = c.get(f"/api/kg/{oid}/neo4j")
        assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
        assert "README.txt" in zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    finally:
        c.__exit__(None, None, None)


def test_graph_api_errors_are_plain(tmp_path, monkeypatch):
    c, oid = _client_with_shop(tmp_path, monkeypatch)
    try:
        assert c.get("/api/kg/nope/overview").status_code == 404
        r = c.get(f"/api/kg/{oid}/search", params={"q": " "})
        assert r.status_code == 400 and "type an id" in r.json()["error"]["message"]
        r = c.get(f"/api/kg/{oid}/entity", params={"set": "shop.customer", "key": "99999"})
        assert r.status_code == 400 and "no " in r.json()["error"]["message"]
        assert c.get("/api/kg/../neo4j").status_code in (404, 400)
        assert c.get("/api/kg/nope/neo4j").status_code == 404
    finally:
        c.__exit__(None, None, None)
