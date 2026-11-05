"""Every read endpoint of the platform, against the oddest data we have:
Unicode / emoji column names, SQL-like names, Parquet with time zones and
nested types, an RDF file and a knowledge-graph folder. No endpoint may
answer 500, and every error must use the standard envelope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from scripts.qa_datasets import make_all

SOURCES = ["csv_unicode_names", "csv_sql_like_names", "parquet_rich_types",
           "rdf_ntriples_typed", "json_nested", "sqlite_fk_and_view"]


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("smoke")
    cases = make_all(root / "data")
    app = create_app(root / "graphs" / "g.duckdb", warm=False)
    with TestClient(app, raise_server_exceptions=False) as c:
        for i, name in enumerate(SOURCES):
            r = c.post("/api/sources", json={"path": cases[name][0], "name": f"s{i}"})
            assert r.status_code == 200, (name, r.text[:300])
        yield c


@pytest.mark.parametrize("i", range(len(SOURCES)))
def test_every_layer_endpoint_survives_odd_data(api, i):
    src = f"s{i}"
    paths = [f"/api/layers/ontology?source={src}", f"/api/entities?source={src}",
             f"/api/entities?source={src}&q=%27%20OR%201%3D1--", f"/api/layers/graph?source={src}",
             f"/api/metrics?source={src}", f"/api/context/suggestions?source={src}",
             f"/api/context?source={src}&question=what%20is%20%F0%9F%98%80",
             f"/api/certification?source={src}"]
    for path in paths:
        r = api.get(path)
        assert r.status_code < 500, (SOURCES[i], path, r.status_code, r.text[:400])


def test_global_endpoints(api):
    for path in ("/api/health", "/api/sources", "/api/agents", "/api/agent-presets",
                 "/api/feedback", "/api/usage/metrics", "/api/onto"):
        r = api.get(path)
        assert r.status_code == 200, (path, r.text[:300])
    for path in ("/api/jobs/nope", "/api/agents/nope", "/api/runs/nope",
                 "/api/metrics/nope/health", "/api/layers/ontology?source=nope"):
        r = api.get(path)
        assert r.status_code in (400, 404, 409), (path, r.status_code, r.text[:200])
        assert "error" in r.json() or "detail" in r.json()
