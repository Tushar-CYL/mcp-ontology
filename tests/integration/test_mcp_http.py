"""External agents connect over MCP-over-HTTP with a per-agent key.

The end-to-end story this product is sold on:

    connect data -> metrics approved -> register an agent -> issue a key
    -> an external agent (Claude Desktop, Cursor, Copilot) calls /mcp
    -> gets readiness, the governed metric and a cited context pack
    -> the call shows up in that agent's usage log.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from tests.integration.test_semantic_context_intelligence import _write_source

QUESTION = "Why did West revenue fall in October 2026?"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("EYQ_INCUBATOR_ENDPOINT", raising=False)
    monkeypatch.delenv("EYQ_INCUBATOR_KEY", raising=False)
    app = create_app(tmp_path / "mcp.duckdb", warm=False)
    with TestClient(app) as test_client:
        folder = tmp_path / "revenue"
        _write_source(folder)
        response = test_client.post("/api/sources", json={
            "path": str(folder), "name": "revenue"})
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture
def agent(client):
    response = client.post("/api/agents", json={
        "name": "Revenue analyst",
        "purpose": "Explains revenue movements for finance.",
        "instructions": "Use approved metrics and cite evidence.",
        "sources": ["revenue"],
        "metrics": ["revenue"],
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def key(client, agent):
    response = client.post(f"/api/agents/{agent['id']}/keys",
                           json={"label": "claude desktop"})
    assert response.status_code == 200, response.text
    return response.json()["key"]


def _rpc(client, key, method, params=None, rpc_id=1, header="bearer"):
    headers = {}
    if key is not None:
        headers = ({"Authorization": f"Bearer {key}"} if header == "bearer"
                   else {"x-api-key": key})
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body, headers=headers)


def _tool(client, key, name, arguments=None):
    response = _rpc(client, key, "tools/call",
                    {"name": name, "arguments": arguments or {}})
    assert response.status_code == 200, response.text
    data = response.json()
    if "error" in data:
        return None, data["error"]
    return json.loads(data["result"]["content"][0]["text"]), None


# --------------------------------------------------------------- auth
def test_mcp_without_a_key_is_401(client):
    response = _rpc(client, None, "initialize")
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "Unauthorized"
    assert "Bearer" in response.headers.get("www-authenticate", "")


def test_mcp_with_a_wrong_key_is_401(client, key):
    assert _rpc(client, "strata_wrong", "initialize").status_code == 401


def test_both_bearer_and_x_api_key_headers_work(client, key):
    assert _rpc(client, key, "initialize").status_code == 200
    assert _rpc(client, key, "initialize", header="x-api-key").status_code == 200


def test_a_revoked_key_is_refused(client, agent, key):
    keys = client.get(f"/api/agents/{agent['id']}/keys").json()["keys"]
    revoked = client.delete(f"/api/agents/{agent['id']}/keys/{keys[0]['id']}")
    assert revoked.status_code == 200
    assert _rpc(client, key, "initialize").status_code == 401


def test_key_listing_never_returns_the_secret(client, agent, key):
    body = client.get(f"/api/agents/{agent['id']}/keys").text
    assert key not in body
    assert key[:12] in body


def test_notifications_get_202_and_no_body(client, key):
    response = client.post("/mcp", json={
        "jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 202
    assert response.content == b""


def test_get_on_mcp_is_405(client):
    assert client.get("/mcp").status_code == 405


# ---------------------------------------------------------- handshake
def test_initialize_and_tools_list(client, key):
    init = _rpc(client, key, "initialize").json()["result"]
    assert init["serverInfo"]["name"] == "strata"
    assert "check_readiness" in init["instructions"]
    tools = _rpc(client, key, "tools/list").json()["result"]["tools"]
    assert {"get_context", "get_metric", "check_readiness"} <= {
        tool["name"] for tool in tools}


# -------------------------------------------------------------- tools
def test_list_sources_shows_only_the_agents_scope(client, key):
    payload, error = _tool(client, key, "list_sources")
    assert error is None
    assert [item["source"] for item in payload["sources"]] == ["revenue"]


def test_check_readiness(client, key):
    payload, error = _tool(client, key, "check_readiness")
    assert error is None
    assert payload["source"] == "revenue"
    assert payload["status"] in {"pass", "warn", "fail"}
    assert isinstance(payload["blockers"], list)
    assert {layer["layer"] for layer in payload["layers"]} >= {
        "Ontology", "Semantic layer", "Context"}


def test_check_answerable_true_for_an_in_scope_metric(client, key):
    payload, error = _tool(client, key, "check_answerable",
                           {"question": QUESTION})
    assert error is None
    assert payload["answerable"] is True
    assert payload["metric"] == "revenue"
    assert payload["filters"] == {"region": "West"}


def test_check_answerable_false_for_an_out_of_scope_metric(client, key):
    payload, error = _tool(client, key, "check_answerable",
                           {"question": "What is the refund rate?"})
    assert error is None
    assert payload["answerable"] is False
    assert "refund_rate" in payload["reason"]
    assert payload["available_metrics"] == ["revenue"]


def test_check_answerable_false_when_no_metric_matches(client, key):
    payload, _ = _tool(client, key, "check_answerable",
                       {"question": "What colour is the sky?"})
    assert payload["answerable"] is False
    assert payload["metric"] is None


def test_get_metric_returns_the_governed_definition(client, key):
    payload, error = _tool(client, key, "get_metric", {"metric": "revenue"})
    assert error is None
    assert payload["name"] == "revenue"
    assert payload["status"] == "approved"
    assert payload["value_expr"]
    assert "base_sql" in payload


def test_get_metric_outside_scope_is_forbidden(client, key):
    payload, error = _tool(client, key, "get_metric", {"metric": "refund_rate"})
    assert payload is None
    assert error["code"] == -32001


def test_evaluate_metric_returns_sql_rows_and_truncation(client, key):
    payload, error = _tool(client, key, "evaluate_metric", {
        "metric": "revenue", "group_by": "segment",
        "time_from": "2026-10-01", "time_to": "2026-11-01"})
    assert error is None
    assert payload["sql"].lower().startswith(("select", "with"))
    assert payload["rows"]
    assert payload["truncated"] is False
    assert payload["row_count"] == len(payload["rows"])


def test_get_context_returns_a_cited_pack_with_full_coverage(client, key):
    payload, error = _tool(client, key, "get_context", {
        "question": QUESTION, "budget_chars": 5000})
    assert error is None
    assert payload["metric"]["name"] == "revenue"
    assert payload["coverage"]["score"] == 100
    assert all(fact["citation"] for fact in payload["facts"])
    assert "source_row" in {fact["kind"] for fact in payload["facts"]}


def test_get_context_for_an_out_of_scope_metric_is_forbidden(client, key):
    _, error = _tool(client, key, "get_context",
                     {"question": "Why did the refund rate rise?"})
    assert error["code"] == -32001


def test_another_source_is_forbidden(client, key):
    _, error = _tool(client, key, "describe_table",
                     {"table": "orders", "source": "hr"})
    assert error["code"] == -32001


def test_describe_table_lists_columns_metrics_and_flags_pii(client, key):
    payload, error = _tool(client, key, "describe_table", {"table": "customers"})
    assert error is None
    assert payload["table"] == "customers"
    names = {column["name"] for column in payload["columns"]}
    assert {"customer_id", "name", "region"} <= names
    assert payload["class"]
    # PII policy lives in agent.guardrails; an id or region is never flagged.
    assert all(isinstance(c["pii"], bool) for c in payload["columns"])
    assert not any(c["pii"] for c in payload["columns"]
                   if c["name"] in {"customer_id", "region"})
    orders, _ = _tool(client, key, "describe_table", {"table": "orders"})
    assert "revenue" in orders["metrics"]


def test_search_and_list_metrics(client, key):
    found, error = _tool(client, key, "search", {"query": "revenue"})
    assert error is None
    assert [m["name"] for m in found["metrics"]] == ["revenue"]
    listed, error = _tool(client, key, "list_metrics")
    assert error is None
    assert [m["name"] for m in listed["metrics"]] == ["revenue"]   # scope only
    entities, _ = _tool(client, key, "list_entities")
    assert {"Customer", "Order"} <= {e["name"] for e in entities["entities"]}


def test_explain_citation(client, key):
    payload, error = _tool(client, key, "explain_citation",
                           {"citation": "metric:revenue:current"})
    assert error is None
    assert payload["kind"] == "metric"


# --------------------------------------------------------------- usage
def test_every_tool_call_is_logged_for_the_agent(client, agent, key):
    _tool(client, key, "get_context", {"question": QUESTION})
    _tool(client, key, "get_metric", {"metric": "refund_rate"})
    usage = client.get(f"/api/agents/{agent['id']}/usage").json()["calls"]
    assert [call["tool"] for call in usage[:2]] == ["get_metric", "get_context"]
    assert usage[0]["ok"] is False
    assert usage[1]["ok"] is True
    assert usage[1]["summary"] == QUESTION


def test_connection_details_give_snippets_without_the_secret(client, agent, key):
    response = client.get(f"/api/agents/{agent['id']}/connection")
    assert response.status_code == 200
    data = response.json()
    assert data["mcp_url"].endswith("/mcp")
    assert key not in response.text
    for name in ("claude_desktop", "cursor", "curl", "powershell"):
        assert "<YOUR_KEY>" in data["snippets"][name]
    # Windows PowerShell 5.1 aliases `curl` to Invoke-WebRequest, so the
    # PowerShell snippet must use native cmdlets and a hashtable of headers.
    ps = data["snippets"]["powershell"]
    assert "Invoke-RestMethod" in ps
    assert "@{" in ps and "ConvertTo-Json" in ps
    assert "curl" not in ps.lower()


def test_keys_for_an_unknown_agent_are_404(client):
    assert client.post("/api/agents/nope/keys", json={}).status_code == 404


# ----------------------------------------------------------- end to end
def test_end_to_end_external_agent_story(client):
    """The demo, as one test: no step may be skipped or faked."""
    # 1. data is connected and the layers are certified enough to serve.
    cert = client.get("/api/certification", params={"source": "revenue"})
    assert cert.status_code == 200
    # 2. an approved metric exists.
    metrics = client.get("/api/metrics", params={"source": "revenue"}).json()
    assert any(m["name"] == "revenue" and m["status"] == "approved"
               for m in metrics["metrics"])
    # 3. a steward registers the external agent with a narrow scope.
    agent = client.post("/api/agents", json={
        "name": "Finance copilot", "instructions": "Cite everything.",
        "sources": ["revenue"], "metrics": ["revenue"]}).json()
    # 4. and issues it a key.
    key = client.post(f"/api/agents/{agent['id']}/keys",
                      json={"label": "copilot"}).json()["key"]
    # 5. the external agent follows the handshake order.
    assert _rpc(client, key, "initialize").status_code == 200
    ready, _ = _tool(client, key, "check_readiness")
    assert ready["status"] != "fail"
    answerable, _ = _tool(client, key, "check_answerable", {"question": QUESTION})
    assert answerable["answerable"] is True
    pack, _ = _tool(client, key, "get_context",
                    {"question": QUESTION, "budget_chars": 5000})
    assert pack["coverage"]["score"] == 100
    assert pack["answer"].startswith("Revenue:")
    # 6. the steward sees exactly what the agent did.
    calls = client.get(f"/api/agents/{agent['id']}/usage").json()["calls"]
    assert [c["tool"] for c in calls] == [
        "get_context", "check_answerable", "check_readiness"]


def test_readiness_is_cached_and_says_so(client, key):
    first, _ = _tool(client, key, "check_readiness")
    second, _ = _tool(client, key, "check_readiness")
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["checked_at"] == first["checked_at"]
    fresh, _ = _tool(client, key, "check_readiness", {"refresh": True})
    assert fresh["cached"] is False


def test_certification_page_shares_the_cache(client, key):
    _tool(client, key, "check_readiness")
    page = client.get("/api/certification", params={"source": "revenue"}).json()
    assert page["cached"] is True
    forced = client.get("/api/certification",
                        params={"source": "revenue", "refresh": "true"}).json()
    assert forced["cached"] is False


def test_deleting_an_agent_removes_it_and_kills_its_keys(client, agent, key):
    _tool(client, key, "list_sources")
    deleted = client.delete(f"/api/agents/{agent['id']}")
    assert deleted.status_code == 200
    assert agent["id"] not in {a["id"] for a in client.get("/api/agents").json()["agents"]}
    assert _rpc(client, key, "initialize").status_code == 401
    assert client.get(f"/api/agents/{agent['id']}/usage").status_code == 404


def test_deleting_an_unknown_agent_is_404(client):
    assert client.delete("/api/agents/nope").status_code == 404
