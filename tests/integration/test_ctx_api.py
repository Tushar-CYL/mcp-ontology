"""The Context tool through the REST API and MCP."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from api import ctx_routes, mcp_server
from api.server import create_app
from tests.integration.test_declared_links import make_shop


class Writer:
    mock = False
    model = "fake"

    def complete(self, messages, max_tokens=600):
        if "ONTOLOGY:" in messages[-1]["content"]:
            return json.dumps({"edits": [], "reply": "noted"})
        return "Customer 17 placed 5 orders [1]."


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setattr(ctx_routes, "ai_client", lambda: Writer())
    app = create_app(tmp_path / "g.duckdb", warm=False)
    with TestClient(app) as c:
        r = c.post("/api/onto/build", json={"name": "Shop", "paths": [{"path": str(make_shop(tmp_path / "shop.db"))}]})
        job = r.json()["job_id"]
        for _ in range(300):
            j = c.get(f"/api/jobs/{job}").json()
            if j["status"] != "running":
                break
            time.sleep(0.1)
        yield c, j["result"]["ontology"], app


def test_build_returns_every_step_and_the_answer(client):
    c, oid, _ = client
    r = c.post(f"/api/ctx/{oid}/build", json={"question": "What did Customer 17 order?"})
    assert r.status_code == 200, r.text
    out = r.json()
    s = out["steps"]
    assert s["understand"]["records"][0]["key"] == "17"
    assert s["follow"]["walks"] and s["facts"]["kept"]
    assert s["answer"]["status"] == "answered" and s["answer"]["cited"] == [1]
    assert out["context"].startswith("[1] ")


def test_bad_questions_and_unknown_ontologies_are_plain_errors(client):
    c, oid, _ = client
    assert c.post(f"/api/ctx/{oid}/build", json={"question": "  "}).status_code == 400
    assert c.post("/api/ctx/nope/build", json={"question": "x"}).status_code == 404
    assert c.post(f"/api/ctx/{oid}/build", json={"question": "x", "budget_chars": 5}).status_code == 422


def test_feedback_becomes_a_note_the_next_build_uses(client):
    c, oid, _ = client
    r = c.post(f"/api/ctx/{oid}/feedback", json={"question": "What did Customer 17 order?",
                                                 "text": "Orders with status cancelled are not real orders"})
    assert r.status_code == 200 and r.json()["saved"]
    out = c.post(f"/api/ctx/{oid}/build", json={"question": "Which orders are cancelled?"}).json()
    assert any("cancelled are not real orders" in f["text"] for f in out["steps"]["facts"]["kept"])


def test_agents_get_the_same_pack_over_mcp_within_their_scope(client):
    c, oid, app = client
    layer = app.state.platform.layer if hasattr(app.state, "platform") else None
    if layer is None:
        pytest.skip("platform not exposed on app.state")
    call = lambda scope: mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "context_for_question", "arguments": {"question": "Tell me about Customer 17", "ontology": oid}}},
        layer, scope=scope)
    ok = json.loads(call(None)["result"]["content"][0]["text"])
    assert ok["facts"] and ok["context"].startswith("[1] ")
    denied = call({"sources": ["other"], "metrics": [], "agent_id": "a"})
    assert denied["error"]["code"] == mcp_server.FORBIDDEN
