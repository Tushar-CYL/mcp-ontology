"""The Semantic tool through REST and MCP."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from api import mcp_server, sem_routes
from api.server import create_app
from tests.integration.test_semantic_model import make_amounts


class Writer:
    mock = False
    model = "fake"

    def complete(self, messages, max_tokens=600):
        return ('{"title": "Paid net revenue", "agg": "sum", "field": "shop.orders.net_amount", '
                '"filters": [{"field": "shop.orders.status", "value": "paid"}]}')


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setattr(sem_routes, "ai_client", lambda: Writer())
    app = create_app(tmp_path / "g.duckdb", warm=False)
    with TestClient(app) as c:
        r = c.post("/api/onto/build", json={"name": "Shop", "paths": [{"path": str(make_amounts(tmp_path / "shop.db"))}]})
        job = r.json()["job_id"]
        for _ in range(300):
            j = c.get(f"/api/jobs/{job}").json()
            if j["status"] != "running":
                break
            time.sleep(0.1)
        yield c, j["result"]["ontology"], app


def test_overview_decide_detail_and_words(client):
    c, oid, _ = client
    o = c.get(f"/api/sem/{oid}").json()
    assert o["metrics"] and o["decisions"][0]["word"] == "revenue"
    assert all(m["status"] == "proposed" for m in o["metrics"])
    r = c.post(f"/api/sem/{oid}/decide", json={"word": "revenue", "metric": "total_gross_amount"})
    assert r.status_code == 200 and r.json()["status"] == "certified"
    d = c.get(f"/api/sem/{oid}/metric/total_gross_amount", params={"by": "customer_country"}).json()
    assert d["breakdown"]["by"] == "customer_country" and len(d["breakdown"]["rows"]) == 3
    assert d["receipt"]["sql"] and d["receipt"]["certified_at"]
    w = c.post(f"/api/sem/{oid}/words", json={"text": "Revenue is net amount of paid orders"}).json()
    assert w["status"] == "proposed" and w["value"] > 0
    assert c.post(f"/api/sem/{oid}/metric/nope/certify", json={}).status_code == 404
    assert c.post(f"/api/sem/{oid}/decide", json={"word": "revenue", "metric": "order_count"}).status_code == 400


def test_agents_see_certified_metrics_only(client):
    c, oid, app = client
    layer = app.state.platform.layer
    c.get(f"/api/sem/{oid}")                                          # proposals exist
    call = lambda name, args, scope=None: mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}},
        layer, scope=scope)
    listed = json.loads(call("list_business_metrics", {"ontology": oid})["result"]["content"][0]["text"])
    assert listed["metrics"] == []                                     # nothing certified yet
    c.post(f"/api/sem/{oid}/metric/total_net_amount/certify", json={"owner": "Finance"})
    listed = json.loads(call("list_business_metrics", {"ontology": oid})["result"]["content"][0]["text"])
    assert [m["metric"] for m in listed["metrics"]] == ["total_net_amount"]
    got = json.loads(call("get_business_metric", {"ontology": oid, "metric": "total_net_amount",
                                                  "by": "customer_segment"})["result"]["content"][0]["text"])
    assert len(got["rows"]) == 2 and got["receipt"]["owner"] == "Finance"
    assert "error" in call("get_business_metric", {"ontology": oid, "metric": "order_count"})
    denied = call("list_business_metrics", {"ontology": oid}, {"sources": ["other"], "metrics": [], "agent_id": "a"})
    assert denied["error"]["code"] == mcp_server.FORBIDDEN


def test_suggestions_for_every_layer_over_rest(client):
    c, oid, _ = client
    for kind in ("note", "ask", "metric", "search"):
        r = c.get(f"/api/onto/{oid}/suggest", params={"kind": kind, "ai": "false"})
        assert r.status_code == 200, (kind, r.text)
        body = r.json()
        assert body["suggestions"] and body["method"] == "data", (kind, body)
    assert c.get(f"/api/onto/{oid}/suggest", params={"kind": "poem"}).status_code == 400
    assert c.get("/api/onto/nope/suggest").status_code == 404
