"""STRATA_DATA_ROOTS: on a shared server, only files under the allowed folders
can be read through the API. Unset, local use is unchanged."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import paths
from api.server import create_app
from tests.integration.simple_fixtures import make_iot


def test_roots_parse_and_check(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    (allowed / "sub").mkdir(parents=True)
    monkeypatch.delenv("STRATA_DATA_ROOTS", raising=False)
    paths.check("C:/Windows/win.ini")                         # unset: anything goes
    monkeypatch.setenv("STRATA_DATA_ROOTS", f"{allowed};{tmp_path / 'other'}")
    paths.check(str(allowed / "sub" / "x.csv"))
    paths.check(str(allowed))
    paths.check("postgres://user@host/db")                    # a URL is not a file read
    for bad in ("C:/Windows/win.ini", str(tmp_path / "allowed_not"),
                str(allowed / ".." / "secret.txt"), str(tmp_path)):
        with pytest.raises(PermissionError):
            paths.check(bad)


def test_the_api_refuses_files_outside_the_roots(tmp_path, monkeypatch):
    data = make_iot(tmp_path / "allowed")
    monkeypatch.setenv("STRATA_DATA_ROOTS", str(tmp_path / "allowed"))
    app = create_app(tmp_path / "graphs" / "g.duckdb", warm=False)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/api/sources", json={"path": "C:/Windows/win.ini"})
        assert r.status_code == 403 and "STRATA_DATA_ROOTS" in r.text
        r = c.post("/api/sources", json={"path": "C:/Windows/win.ini", "background": True})
        assert r.status_code == 403
        r = c.post("/api/onto/build", json={"name": "x", "paths": [{"path": "C:/Windows"}]})
        assert r.status_code == 403
        r = c.post("/api/onto/build", json={"name": "x", "metadata": [str(tmp_path / "m.csv")]})
        assert r.status_code == 403
        assert c.post("/api/sources", json={"path": str(data), "name": "iot"}).status_code == 200
