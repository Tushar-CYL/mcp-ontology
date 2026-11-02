"""The EYQ chat client: the one place an agent may call a language model.

The LLM writes prose only. It never computes a number: the tools compute every
value and attach a citation, and `agent.guardrails` rejects an answer that
states a number the evidence pack does not contain.

Live contract (confirmed against the incubator deployment, not guessed):

    POST {EYQ_INCUBATOR_ENDPOINT}/openai/deployments/{model}/chat/completions
         ?api-version=2024-10-21
    header: api-key: <KEY>            (NOT an Authorization bearer token)
    body:   {"model": ..., "messages": [...], "max_completion_tokens": N}
    reply:  choices[0].message.content

`gpt-5.2` rejects `max_tokens` and `temperature`, so neither is sent. The key
is read from the environment only and is redacted from every error and log
line this module produces.

Mock mode: with no endpoint or key configured the client answers with a
deterministic offline reply and never opens a socket. That is what lets the
tests and an offline demo run the full agent loop.
"""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable

DEFAULT_MODEL = "gpt-5.2"
DEFAULT_API_VERSION = "2024-10-21"
REDACTED = "[redacted]"

# A transport is the test seam and the only network boundary:
# transport(url, headers, body, timeout) -> parsed JSON response.
Transport = Callable[[str, dict[str, str], dict[str, Any], float],
                     dict[str, Any]]

# How long to wait before the single retry. Kept short: an agent answer is
# interactive, and a second timeout fails the request anyway.
RETRY_BACKOFF_SECONDS = 0.2


class AgentLLMError(RuntimeError):
    """A clean LLM failure carrying status and a redacted body excerpt.

    The API key never appears in the message, in `body_excerpt`, or in the
    traceback: every message is built through `_safe`, which strips it.
    """

    def __init__(self, message: str, *, status: int | None = None,
                 body_excerpt: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.body_excerpt = body_excerpt

    def as_dict(self) -> dict:
        return {"type": type(self).__name__, "status": self.status,
                "message": str(self), "body_excerpt": self.body_excerpt}


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _excerpt(text: str, limit: int = 320) -> str:
    """One line, bounded. Response bodies can be enormous and multi-line."""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean[:limit]


def _redact(value: Any, secret: str) -> str:
    """Remove the API key from any text that may end up in a log or error."""
    text = str(value if value is not None else "")
    if secret:
        text = text.replace(secret, REDACTED)
        # A URL-encoded or JSON-escaped echo is still the same secret.
        text = text.replace(json.dumps(secret)[1:-1], REDACTED)
    return text


def extract_json_object(text: str) -> dict:
    """The first JSON object in an LLM reply, fences or prose stripped.

    Models wrap JSON in ```json fences and occasionally add a sentence. The
    runtime must not fail because of decoration around an otherwise valid
    object, and it must never accept a non-object.
    """
    if not isinstance(text, str):
        raise ValueError("LLM content is not text")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except (ValueError, TypeError):
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the LLM reply")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("the LLM reply was not a JSON object")
    return value


class EYQClient:
    """Azure-OpenAI-compatible chat client for the incubator deployment.

    Parameters mirror the environment exactly, so either style works:

        EYQClient()                                  # everything from env
        EYQClient(mock=True)                         # forced offline
        EYQClient(endpoint=..., api_key=..., model=...)

    `transport` is an optional keyword-only seam used by the tests. It
    receives the fully built request (url, headers, body, timeout) and returns
    the parsed JSON response, which is what makes header/body assertions
    possible without a socket.
    """

    def __init__(self, endpoint: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: float = 60,
                 mock: bool = False, *, transport: Transport | None = None,
                 api_version: str | None = None) -> None:
        self.endpoint = str(endpoint if endpoint is not None
                            else _env("EYQ_INCUBATOR_ENDPOINT")).strip().rstrip("/")
        self.api_key = str(api_key if api_key is not None
                           else _env("EYQ_INCUBATOR_KEY")).strip()
        self.model = str(model or _env("EYQ_MODEL") or DEFAULT_MODEL).strip()
        self.api_version = str(api_version or _env("EYQ_API_VERSION")
                               or DEFAULT_API_VERSION).strip()
        self.timeout = float(timeout)
        self._transport: Transport = transport or self._http_transport
        # An explicit mock always wins; otherwise the absence of configuration
        # means there is no live endpoint to call.
        self.mock = bool(mock) or not (self.endpoint and self.api_key)

    # ------------------------------------------------------------ status
    @property
    def configured(self) -> bool:
        """True when a live endpoint and key are available."""
        return bool(self.endpoint and self.api_key)

    def describe(self) -> dict:
        """Non-secret facts about the client, safe for a health endpoint."""
        return {"mock": self.mock, "configured": self.configured,
                "model": self.model, "api_version": self.api_version,
                "endpoint": self.endpoint or None}

    @property
    def url(self) -> str:
        """The full chat-completions URL for the configured deployment."""
        return (f"{self.endpoint}/openai/deployments/{self.model}"
                f"/chat/completions?api-version={self.api_version}")

    # ------------------------------------------------------------ errors
    def _safe(self, value: Any) -> str:
        return _redact(value, self.api_key)

    def _fail(self, message: str, *, status: int | None = None,
              body: Any = "") -> AgentLLMError:
        return AgentLLMError(self._safe(message), status=status,
                             body_excerpt=self._safe(_excerpt(body)))

    # ---------------------------------------------------------- complete
    def complete(self, messages: list[dict], max_tokens: int = 1200) -> str:
        """One chat completion. Retries once on a timeout or a 5xx.

        A 4xx is a caller/credential problem: retrying it would only spend
        another request to get the same refusal. `max_completion_tokens` is
        used because gpt-5.2 rejects the older `max_tokens` field.
        """
        messages = self._messages(messages)
        if self.mock:
            return self.mock_complete(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": int(max_tokens),
        }
        headers = {"Content-Type": "application/json", "api-key": self.api_key}
        url = self.url
        last = self._fail("EYQ request failed before it was sent")
        for attempt in (1, 2):
            try:
                data = self._transport(url, headers, body, self.timeout)
                return self._content(data)
            except AgentLLMError as exc:
                if exc.status is not None and 400 <= int(exc.status) < 500:
                    raise
                last = exc
            except (TimeoutError, socket.timeout) as exc:
                last = self._fail(f"EYQ request timed out: {exc}")
            except urllib.error.URLError as exc:
                last = self._fail(f"EYQ request could not connect: {exc}")
            except Exception as exc:                  # noqa: BLE001 - clean 5xx
                last = self._fail(
                    f"EYQ request failed: {type(exc).__name__}: {exc}")
            if attempt == 1:
                time.sleep(RETRY_BACKOFF_SECONDS)
        raise last

    def _messages(self, messages: list[dict]) -> list[dict]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list of "
                             "{'role', 'content'} dicts")
        out = []
        for item in messages:
            if not isinstance(item, dict):
                raise ValueError("every message must be an object with a role")
            role = str(item.get("role") or "user").strip()
            if role not in ("system", "user", "assistant"):
                raise ValueError(f"unsupported message role {role!r}")
            content = item.get("content")
            if content is None:
                raise ValueError("every message needs content")
            out.append({"role": role, "content": str(content)})
        return out

    def _content(self, data: Any) -> str:
        """Pull `choices[0].message.content` out of an Azure-style reply."""
        try:
            choices = data["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise self._fail(
                "unexpected EYQ response shape (wanted choices[0].message."
                "content)",
                body=json.dumps(data, default=str)[:500]) from None
        if content is None or (isinstance(content, str)
                               and not content.strip()):
            raise self._fail("EYQ returned empty message content",
                             body=json.dumps(data, default=str)[:500])
        return str(content)

    # --------------------------------------------------------- transport
    def _http_transport(self, url: str, headers: dict[str, str],
                        body: dict[str, Any], timeout: float) -> dict:
        """The real HTTP call. The only function here that opens a socket."""
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=headers,
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            payload = ""
            try:
                payload = exc.read().decode("utf-8", "replace")
            except Exception:                          # noqa: BLE001 - optional
                payload = ""
            raise self._fail(
                f"EYQ HTTP {exc.code} {exc.reason or ''}".strip(),
                status=int(exc.code), body=payload) from None
        except (TimeoutError, socket.timeout):
            raise
        except urllib.error.URLError as exc:
            raise
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise self._fail("EYQ response was not JSON", body=raw[:400]) \
                from None

    # -------------------------------------------------------------- mock
    def mock_complete(self, messages: list[dict]) -> str:
        """Deterministic offline reply, built only from the prompt facts.

        The runtime normally writes its own deterministic narrative in mock
        mode; this exists so the client contract is complete on its own and a
        test can run with no network at all. The reply never introduces a
        number: it echoes the first supplied fact, or says there is none.
        """
        prompt = "\n".join(str(m.get("content") or "") for m in messages)
        facts = _facts_from_prompt(prompt)
        headline = "Mock mode: no live model is configured."
        cause = "This answer is assembled deterministically from the supplied facts."
        impact = "No live narrative was generated."
        if facts:
            first = facts[0].get("text") if isinstance(facts[0], dict) else ""
            if first:
                headline = str(first)
            numeric = [f for f in facts if isinstance(f, dict)
                       and isinstance(f.get("value"), (int, float))
                       and not isinstance(f.get("value"), bool)]
            if len(numeric) > 1:
                impact = "See the supplied facts for the measured values."
        return json.dumps({
            "headline": headline,
            "cause": cause,
            "impact": impact,
            "recommendation": "Review the cited facts before acting.",
            "confidence": "medium",
            "mock": True,
        }, sort_keys=True)


def _facts_from_prompt(prompt: str) -> list[dict]:
    """Facts the runtime embeds after a FACTS_JSON marker, for mock mode."""
    marker = "FACTS_JSON:"
    index = prompt.find(marker)
    if index < 0:
        return []
    try:
        value = json.loads(prompt[index + len(marker):].strip())
    except (ValueError, TypeError):
        return []
    if isinstance(value, dict):
        facts = value.get("facts")
        return facts if isinstance(facts, list) else []
    return value if isinstance(value, list) else []


def client_from_env(mock: bool = False, **kwargs: Any) -> EYQClient:
    """Convenience constructor for callers that want env-only configuration."""
    return EYQClient(mock=mock, **kwargs)
