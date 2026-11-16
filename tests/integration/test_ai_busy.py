"""When the AI service is busy or down, the API says so in plain words
instead of answering 500 Internal Server Error (found end to end: a run of
questions hit EYQ's 429 rate limit and the Ask screen showed a crash)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent.llm import AgentLLMError
from api.server import create_app
from ontology import ask


def _boom(status):
    def fail(*a, **k):
        raise AgentLLMError(f"EYQ HTTP {status}", status=status)
    return fail


def test_rate_limit_is_a_503_with_a_plain_message(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setattr(ask, "ask", _boom(429))
    with TestClient(create_app(tmp_path / "g.duckdb", warm=False)) as c:
        r = c.post("/api/onto/anything/ask", json={"question": "How many orders?"})
    assert r.status_code == 503
    assert r.json()["error"]["type"] == "AIBusy"
    assert "try again" in r.json()["error"]["message"]


def test_ai_down_is_a_502_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setattr(ask, "ask", _boom(500))
    with TestClient(create_app(tmp_path / "g.duckdb", warm=False)) as c:
        r = c.post("/api/onto/anything/ask", json={"question": "How many orders?"})
    assert r.status_code == 502
    assert r.json()["error"]["type"] == "AIUnavailable"
