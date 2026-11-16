"""Optional access token for the REST API and the web app.

On a laptop nothing is configured and the API is open to the machine, as
before. On a shared server set one or more tokens:

    STRATA_API_TOKENS=long-random-string-1,long-random-string-2

Then every /api/* request needs one of them, as `Authorization: Bearer
<token>`, `x-api-key: <token>`, or the `strata_token` cookie the web app's
sign-in page sets. `/api/health` stays open (it carries no data and says
whether a token is required). MCP keeps its own agent keys.
"""

from __future__ import annotations

import hmac
import os

COOKIE = "strata_token"
OPEN_PATHS = {"/api/health", "/api/auth/login"}


def tokens() -> set[str]:
    raw = os.environ.get("STRATA_API_TOKENS") or os.environ.get("STRATA_API_TOKEN") or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


def required() -> bool:
    return bool(tokens())


def valid(token: str | None) -> bool:
    if not token:
        return False
    return any(hmac.compare_digest(token, t) for t in tokens())


def token_from(request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    return request.cookies.get(COOKIE)


def allows(request) -> bool:
    """True when the request may proceed under the token policy."""
    if not required():
        return True
    path = request.url.path
    if not path.startswith("/api/") or path in OPEN_PATHS or request.method == "OPTIONS":
        return True
    return valid(token_from(request))
