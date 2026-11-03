"""Ground, validate, learn over HTTP and MCP.

Each test drives the real FastAPI app on a small revenue source, the same way
the UI and an external agent would.
"""

from __future__ import annotations

import pytest

from tests.integration.test_mcp_http import QUESTION, _rpc, _tool
from tests.integration.test_mcp_http import agent, client, key  # noqa: F401 - fixtures


# ------------------------------------------------- Ground: metric synonyms
def test_synonyms_ground_the_words_people_use(client, key):  # noqa: F811
    saved = client.put("/api/metrics/revenue/synonyms",
                       json={"source": "revenue", "synonyms": ["sales"]})
    assert saved.status_code == 200
    found, error = _tool(client, key, "search", {"query": "sales"})
    assert error is None
    assert [m["name"] for m in found["metrics"]] == ["revenue"]
    answerable, _ = _tool(client, key, "check_answerable",
                          {"question": "Why did West sales fall in October 2026?"})
    assert answerable["verdict"] == "yes" and answerable["metric"] == "revenue"


# ---------------------------------------------------------- Phase 5: validate
GOOD_SQL = ("SELECT o.region, SUM(l.line_revenue) FROM order_lines l "
            "JOIN orders o ON o.order_id = l.order_id "
            "WHERE o.status = 'completed' GROUP BY o.region")


def test_validate_passes_sql_that_follows_the_definition_and_compiles(client):
    result = client.post("/api/validate/sql", json={
        "source": "revenue", "metric": "revenue", "sql": GOOD_SQL}).json()
    assert result["status"] == "pass", result["checks"]
    assert any(c["name"] == "Compiles against the source" and c["passed"]
               for c in result["checks"])


def test_validate_warns_when_the_certified_filter_is_missing(client):
    result = client.post("/api/validate/sql", json={
        "source": "revenue", "metric": "revenue",
        "sql": "SELECT SUM(line_revenue) FROM order_lines"}).json()
    assert result["status"] == "warn"
    assert "status = 'completed'" in str(result["checks"])
    assert result["certified"]["value_expr"] == "SUM(revenue)"


def test_validate_fails_sql_that_does_not_compile(client):
    result = client.post("/api/validate/sql", json={
        "source": "revenue", "sql": "SELECT no_such_column FROM orders"}).json()
    assert result["status"] == "fail"
    compiled = next(c for c in result["checks"]
                    if c["name"] == "Compiles against the source")
    assert not compiled["passed"]


def test_validate_refuses_writes_without_running_them(client):
    result = client.post("/api/validate/sql", json={
        "source": "revenue", "sql": "DROP TABLE orders"}).json()
    assert result["status"] == "fail"
    rows = client.post("/api/metrics/revenue/evaluate",
                       json={"source": "revenue"})
    assert rows.status_code == 200                 # the table is still there


def test_mcp_validate_sql_respects_scope(client, key):  # noqa: F811
    result, error = _tool(client, key, "validate_sql",
                          {"sql": GOOD_SQL, "metric": "revenue"})
    assert error is None and result["status"] == "pass"
    _, forbidden = _tool(client, key, "validate_sql",
                         {"sql": "SELECT 1", "metric": "refund_rate"})
    assert forbidden["code"] == -32001


# ------------------------------------------------------------- Phase 6: learn
def _feedback(client, **overrides):
    body = {"source": "revenue", "question": QUESTION,
            "answer": "Revenue fell 70%.",
            "correction": "October excludes a late batch of West orders.",
            "kind": "missing_context", "metric": "revenue"}
    body.update(overrides)
    return client.post("/api/feedback", json=body)


def test_feedback_lands_in_review_and_a_steward_decides(client):
    created = _feedback(client)
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["status"] == "proposed"
    listed = client.get("/api/feedback", params={"source": "revenue"}).json()["items"]
    assert [i["id"] for i in listed] == [item["id"]]
    decided = client.post(f"/api/feedback/{item['id']}/decision",
                          json={"decision": "approved", "note": "Confirmed."})
    assert decided.json()["status"] == "approved"
    pending = client.get("/api/feedback", params={
        "source": "revenue", "pending": "true"}).json()["items"]
    assert pending == []


def test_bad_feedback_is_a_400(client):
    assert _feedback(client, correction=" ").status_code == 400
    assert _feedback(client, kind="nope").status_code == 400


def test_feedback_can_name_the_agent_that_was_wrong(client, agent):  # noqa: F811
    item = _feedback(client, agent_id=agent["id"]).json()
    listed = client.get("/api/feedback", params={"source": "revenue"}).json()["items"]
    assert listed[0]["agent_id"] == agent["id"]
    assert item["id"] == listed[0]["id"]


def test_feedback_for_an_unknown_agent_is_a_404(client):
    assert _feedback(client, agent_id="ghost").status_code == 404


def test_metric_usage_reflects_agent_calls(client, key):  # noqa: F811
    _tool(client, key, "get_context", {"question": QUESTION})
    _tool(client, key, "get_metric", {"metric": "revenue"})
    _tool(client, key, "get_metric", {"metric": "refund_rate"})       # refused
    usage = client.get("/api/usage/metrics", params={"source": "revenue"}).json()
    assert usage["metrics"] == [{**usage["metrics"][0], "metric": "revenue",
                                 "calls": 2, "agents": 1}]


# ----------------------------------------------------------- Phase 7: package
def test_connection_details_include_a_claude_code_command(client, agent):  # noqa: F811
    data = client.get(f"/api/agents/{agent['id']}/connection").json()
    command = data["snippets"]["claude_code"]
    assert command.startswith("claude mcp add --transport http ")
    assert data["mcp_url"] in command
    assert '--header "Authorization: Bearer <YOUR_KEY>"' in command


def test_full_story_ground_validate_learn(client, key):  # noqa: F811
    """Ground a word, validate the agent's SQL, then a person corrects it."""
    client.put("/api/metrics/revenue/synonyms",
               json={"source": "revenue", "synonyms": ["sales"]})
    metrics, _ = _tool(client, key, "list_metrics")
    assert metrics["metrics"][0]["synonyms"] == ["sales"]
    checked, _ = _tool(client, key, "validate_sql", {
        "sql": "SELECT SUM(line_revenue) FROM order_lines", "metric": "revenue"})
    assert checked["status"] == "warn"
    item = _feedback(client, kind="wrong_number").json()
    assert item["review_kind"] == "semantic"
    assert _rpc(client, key, "tools/list").json()["result"]["tools"]
