"""A server can offer only some layers: the web app, the API and MCP agree.
And /api/health/layers says, per layer, whether it is ready."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import layers, mcp_server
from api.server import create_app
from ontology import simple
from tests.integration.test_semantic_model import make_amounts


def test_parse_the_choice():
    assert layers.parse("") == layers.LAYERS
    assert layers.parse("semantic") == ("ontology", "semantic")
    assert layers.parse("kg, metrics") == ("ontology", "graph", "semantic")
    assert layers.parse("all") == layers.LAYERS
    with pytest.raises(ValueError, match="unknown layer"):
        layers.parse("dashboards")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db = make_amounts(tmp_path / "amounts.db")
    application = create_app(tmp_path / "g.duckdb", warm=False)
    with TestClient(application) as c:
        layer = application.state.platform.layer
        layer.add_source(str(db), source="shop")
        c.oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        c.layer = layer
        yield c


def test_semantic_only_server(app, monkeypatch):
    monkeypatch.setenv("STRATA_LAYERS", "semantic")
    assert app.get("/api/health").json()["layers"] == ["ontology", "semantic"]
    assert app.get(f"/api/sem/{app.oid}").status_code == 200
    r = app.get(f"/api/kg/{app.oid}/overview")
    assert r.status_code == 404 and r.json()["error"]["type"] == "LayerOff"
    assert "STRATA_LAYERS=" in r.json()["error"]["message"]
    assert app.post(f"/api/ctx/{app.oid}/build", json={"question": "x"}).status_code == 404
    assert app.get(f"/api/onto/{app.oid}").status_code == 200          # the ontology is always on
    names = {t["name"] for t in mcp_server.allowed_tools(None)}
    assert "list_business_metrics" in names and "get_ontology" in names
    assert "find_entity" not in names and "context_for_question" not in names
    with pytest.raises(mcp_server.Forbidden, match="switched off"):
        mcp_server.call_tool(app.layer, "find_entity", {"ontology": app.oid, "query": "GB"})


def test_everything_is_on_by_default(app, monkeypatch):
    monkeypatch.delenv("STRATA_LAYERS", raising=False)
    assert app.get("/api/health").json()["layers"] == list(layers.LAYERS)
    assert app.get(f"/api/kg/{app.oid}/overview").status_code == 200
    assert len(mcp_server.allowed_tools(None)) == len(mcp_server.TOOLS)


def test_each_layer_says_if_it_is_ready(app, monkeypatch):
    monkeypatch.delenv("STRATA_LAYERS", raising=False)
    rows = {r["layer"]: r for r in app.get("/api/health/layers").json()["layers"]}
    assert rows["ontology"]["status"] == "ready" and "% confirmed" in rows["ontology"]["text"]
    assert rows["graph"]["status"] in ("ready", "needs attention")
    assert rows["semantic"]["status"] == "not ready"          # nothing proposed yet
    app.get(f"/api/sem/{app.oid}")                              # proposes
    rows = {r["layer"]: r for r in app.get("/api/health/layers").json()["layers"]}
    assert rows["semantic"]["status"] == "needs attention" and "certify" in rows["semantic"]["text"]
    monkeypatch.setenv("STRATA_LAYERS", "semantic")
    rows = {r["layer"]: r for r in app.get("/api/health/layers").json()["layers"]}
    assert rows["graph"]["status"] == "off" and rows["context"]["status"] == "off"


def test_no_ontology_yet_says_what_to_do(tmp_path):
    with TestClient(create_app(tmp_path / "e.duckdb", warm=False)) as c:
        rows = c.get("/api/health/layers").json()["layers"]
        assert rows[0]["status"] == "not ready" and "import yours" in rows[0]["text"]


def test_download_a_ready_to_run_copy_of_one_layer(app, monkeypatch):
    import io
    import zipfile
    monkeypatch.delenv("STRATA_LAYERS", raising=False)
    r = app.get(f"/api/bundle?layers=semantic&ontology={app.oid}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "strata-semantic.zip" in r.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "strata-semantic/start.bat" in names
    assert f"strata-semantic/models/{app.oid}.strata-model.json" in names
    assert app.get("/api/bundle?layers=dashboards").status_code == 400
    assert app.get("/api/bundle?ontology=nope").status_code == 404
    assert "strata-all.zip" in app.get("/api/bundle").headers["content-disposition"]
