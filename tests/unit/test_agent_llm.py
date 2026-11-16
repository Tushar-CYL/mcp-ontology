"""The EYQ client contract and the offline safety property."""

from __future__ import annotations

import json

import pytest

from agent.llm import AgentLLMError, EYQClient


def test_mock_mode_is_offline_and_returns_json():
    client = EYQClient(mock=True)
    assert client.mock is True
    content = client.complete([{"role": "user", "content": "hello"}])
    parsed = json.loads(content)
    assert parsed["mock"] is True


def test_live_contract_uses_api_key_path_and_completion_tokens():
    seen = {}

    def transport(url, headers, body, timeout):
        seen.update({"url": url, "headers": headers, "body": body})
        return {"choices": [{"message": {"content": '{"headline":"ok"}'}}]}

    client = EYQClient(
        "https://example.test/eyq/us/api", "super-secret-key", "gpt-5.2",
        transport=transport)
    assert client.complete([{"role": "user", "content": "hi"}]) == \
        '{"headline":"ok"}'
    assert seen["url"] == (
        "https://example.test/eyq/us/api/openai/deployments/gpt-5.2/"
        "chat/completions?api-version=2024-10-21")
    assert seen["headers"]["api-key"] == "super-secret-key"
    assert "Authorization" not in seen["headers"]
    assert seen["body"]["max_completion_tokens"] == 1200
    assert "max_tokens" not in seen["body"]
    assert "temperature" not in seen["body"]


def test_errors_redact_the_key():
    def transport(url, headers, body, timeout):
        raise RuntimeError("boom super-secret-key")

    client = EYQClient("https://example.test/eyq/us/api", "super-secret-key",
                       transport=transport)
    with pytest.raises(AgentLLMError) as info:
        client.complete([{"role": "user", "content": "hi"}])
    assert "super-secret-key" not in str(info.value)
    assert "super-secret-key" not in json.dumps(info.value.as_dict())


# ------------------------------------------------------------ rate limits
def _limited(times, retry_after=None):
    """A transport that answers 429 `times` times, then succeeds."""
    calls = {"n": 0}

    def transport(url, headers, body, timeout):
        calls["n"] += 1
        if calls["n"] <= times:
            raise AgentLLMError("EYQ HTTP 429 Too Many Requests", status=429,
                                retry_after=retry_after)
        return {"choices": [{"message": {"content": "ok"}}]}
    return transport, calls


def test_a_rate_limit_is_waited_out(monkeypatch):
    slept = []
    monkeypatch.setattr("agent.llm.time.sleep", slept.append)
    transport, calls = _limited(2)
    client = EYQClient("https://example.test/eyq/us/api", "k", transport=transport)
    assert client.complete([{"role": "user", "content": "hi"}]) == "ok"
    assert calls["n"] == 3 and slept == [2.0, 5.0]


def test_retry_after_is_honoured_but_capped(monkeypatch):
    slept = []
    monkeypatch.setattr("agent.llm.time.sleep", slept.append)
    transport, _ = _limited(1, retry_after=600)
    client = EYQClient("https://example.test/eyq/us/api", "k", transport=transport)
    assert client.complete([{"role": "user", "content": "hi"}]) == "ok"
    assert slept == [20.0]


def test_a_rate_limit_that_never_lifts_fails_cleanly(monkeypatch):
    monkeypatch.setattr("agent.llm.time.sleep", lambda s: None)
    transport, calls = _limited(99)
    client = EYQClient("https://example.test/eyq/us/api", "k", transport=transport)
    with pytest.raises(AgentLLMError) as info:
        client.complete([{"role": "user", "content": "hi"}])
    assert info.value.rate_limited
    assert calls["n"] == 4                    # first try + 3 waits, then give up


def test_other_4xx_still_fail_at_once(monkeypatch):
    monkeypatch.setattr("agent.llm.time.sleep", lambda s: None)
    calls = {"n": 0}

    def transport(url, headers, body, timeout):
        calls["n"] += 1
        raise AgentLLMError("EYQ HTTP 401 Unauthorized", status=401)
    client = EYQClient("https://example.test/eyq/us/api", "k", transport=transport)
    with pytest.raises(AgentLLMError):
        client.complete([{"role": "user", "content": "hi"}])
    assert calls["n"] == 1
