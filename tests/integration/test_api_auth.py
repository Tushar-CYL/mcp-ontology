"""The optional access token: open on a laptop, required when configured."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.server import create_app
from tests.integration.simple_fixtures import make_iot


def test_open_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.delenv("STRATA_API_TOKEN", raising=False)
    with TestClient(create_app(tmp_path / "g.duckdb", warm=False)) as c:
        assert c.get("/api/onto").status_code == 200
        assert c.get("/api/health").json()["auth"] == {"required": False}
        assert c.post("/api/auth/login", json={"token": "anything"}).json() == {"ok": True, "required": False}


def test_token_required_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_API_TOKENS", "alpha-token, beta-token")
    with TestClient(create_app(tmp_path / "g.duckdb", warm=False)) as c:
        # Open: health (says a token is needed) and login.
        assert c.get("/api/health").json()["auth"] == {"required": True}
        # Everything else: 401 with the standard envelope, for every method.
        for method, path in (("get", "/api/onto"), ("get", "/api/sources"), ("post", "/api/sources"),
                             ("delete", "/api/onto/x"), ("get", "/api/onto/x/excel")):
            r = getattr(c, method)(path, **({"json": {"path": "x"}} if method == "post" else {}))
            assert r.status_code == 401, (method, path, r.status_code)
            assert r.json()["error"]["type"] == "Unauthorized"
            assert r.headers["www-authenticate"].startswith("Bearer")
        # Header, x-api-key and cookie all work; a wrong token does not.
        assert c.get("/api/onto", headers={"Authorization": "Bearer beta-token"}).status_code == 200
        assert c.get("/api/onto", headers={"x-api-key": "alpha-token"}).status_code == 200
        assert c.get("/api/onto", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 401
        r = c.post("/api/auth/login", json={"token": "alpha-token"})
        assert r.status_code == 200 and "strata_token" in r.cookies
        assert c.get("/api/onto").status_code == 200           # the cookie carries it
        # A real action works with the cookie: load a source.
        r = c.post("/api/sources", json={"path": str(make_iot(tmp_path / "d")), "name": "iot"})
        assert r.status_code == 200
        assert c.post("/api/auth/logout").status_code == 200
        assert c.get("/api/onto").status_code == 401
        # MCP keeps its own agent-key check (not the token).
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert r.status_code == 401 and "agent key" in r.json()["error"]["message"]
        # The web app itself is served without a token (it holds no data).
        assert c.get("/").status_code == 200
