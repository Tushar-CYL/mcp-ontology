"""The agents of an ontology over HTTP and MCP: list, copy, create, ask,
keys, and an agent key that only reaches its own tools, ontology and metrics."""

from __future__ import annotations

import json
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from ontology import simple
from semantic import model as sem
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("agents_api")
    db = make_amounts(tmp / "amounts.db")
    application = create_app(tmp / "g.duckdb", warm=False)
    with TestClient(application) as c:
        layer = application.state.platform.layer
        layer.add_source(str(db), source="shop")
        c.oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        sem.propose(layer, c.oid)
        sem.certify(layer, c.oid, "total_gross_amount", owner="Finance")
        sem.certify(layer, c.oid, "total_net_amount", owner="Finance")
        yield c


def _u(agent_id: str) -> str:
    return quote(agent_id, safe="")


def test_list_built_ins_and_yours(app):
    r = app.get(f"/api/onto-agents/{app.oid}").json()
    assert 6 <= len(r["builtin"]) <= 10 and r["mine"] == []
    assert {k["kind"] for k in r["kinds"]} >= {"guide", "metric", "insight"}
    assert app.get("/api/onto-agents/nope").status_code == 404


def test_built_ins_cannot_be_changed_but_can_be_copied(app):
    guide = app.get(f"/api/onto-agents/{app.oid}").json()["builtin"][0]
    r = app.put(f"/api/oagents/{_u(guide['id'])}", json={"name": "Mine"})
    assert r.status_code == 403 and "make a copy" in r.json()["error"]["message"]
    assert app.delete(f"/api/oagents/{_u(guide['id'])}").status_code == 403
    copy = app.post(f"/api/oagents/{_u(guide['id'])}/copy", json={}).json()
    assert copy["base"] == guide["id"] and not copy["builtin"]
    changed = app.put(f"/api/oagents/{_u(copy['id'])}", json={"instructions": "Be brief."}).json()
    assert changed["version"] == 2 and changed["instructions"] == "Be brief."
    assert app.delete(f"/api/oagents/{_u(copy['id'])}").json() == {"deleted": copy["id"]}


def test_create_try_and_ask(app):
    bad = app.post(f"/api/onto-agents/{app.oid}", json={"name": "X", "kind": "insight",
                                                         "scope": {"things": ["Invoice"]}})
    assert bad.status_code == 400 and "no thing called Invoice" in bad.json()["error"]["message"]
    tried = app.post(f"/api/onto-agents/{app.oid}/try", json={
        "name": "Draft", "kind": "insight", "question": "How many Orders have Status cancelled?"}).json()
    assert tried["table"]["rows"][0][0] == 133                        # 400 orders, every third
    made = app.post(f"/api/onto-agents/{app.oid}", json={"name": "Cancellations", "kind": "insight",
                                                          "scope": {"things": ["Order"]}}).json()
    asked = app.post(f"/api/oagents/{_u(made['id'])}/ask",
                     json={"question": "How many Orders have Status cancelled?"}).json()
    assert asked["answerable"]["verdict"] == "yes" and asked["table"]["rows"][0][0] == 133
    assert app.get(f"/api/onto-agents/{app.oid}").json()["mine"][0]["name"] == "Cancellations"


def _mcp(app, key, name, args):
    r = app.post("/mcp", headers={"Authorization": f"Bearer {key}"},
                 json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": args}})
    return r.json()


def test_an_agent_key_reaches_only_its_tools_ontology_and_metrics(app):
    metric = next(a for a in app.get(f"/api/onto-agents/{app.oid}").json()["builtin"] if a["kind"] == "metric")
    narrow = app.post(f"/api/oagents/{_u(metric['id'])}/copy", json={"name": "Net only"}).json()
    app.put(f"/api/oagents/{_u(narrow['id'])}", json={"scope": {"metrics": ["total_net_amount"]}})
    key = app.post(f"/api/agents/{_u(narrow['id'])}/keys", json={"label": "test"}).json()["key"]
    listed = app.post("/mcp", headers={"Authorization": f"Bearer {key}"},
                      json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()
    names = {t["name"] for t in listed["result"]["tools"]}
    assert names == {"list_business_metrics", "get_business_metric", "get_ontology"}
    got = _mcp(app, key, "list_business_metrics", {})
    metrics = json.loads(got["result"]["content"][0]["text"])["metrics"]
    assert [m["metric"] for m in metrics] == ["total_net_amount"]
    refused = _mcp(app, key, "get_business_metric", {"metric": "total_gross_amount"})
    assert "outside this agent's scope" in json.dumps(refused)
    refused = _mcp(app, key, "find_entity", {"query": "GB"})
    assert "error" in refused or refused["result"].get("isError")
    usage = app.get(f"/api/agents/{_u(narrow['id'])}/usage").json()["calls"]
    assert {c["tool"] for c in usage} >= {"list_business_metrics", "get_business_metric"}
    conn = app.get(f"/api/oagents/{_u(narrow['id'])}/connection").json()
    assert conn["mcp_url"].endswith("/mcp") and "<YOUR_KEY>" in conn["claude_code"]
