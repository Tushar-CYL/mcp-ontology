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
