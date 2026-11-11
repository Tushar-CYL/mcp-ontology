"""The web app served by the API: files only from inside frontend/dist, and a
helpful page (not a bare 404) when the app has not been built yet."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import server


def make_app(tmp_path, monkeypatch, built: bool):
    dist = tmp_path / "frontend" / "dist"
    if built:
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<html>STRATA UI</html>", encoding="utf-8")
        (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
        (dist / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "frontend" / "secret.txt").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "frontend" / "secret.txt").write_text("API_KEY=leak", encoding="utf-8")
    (tmp_path / ".env").write_text("EYQ_INCUBATOR_KEY=leak", encoding="utf-8")
    monkeypatch.setattr(server, "FRONTEND_DIST", dist)
    monkeypatch.delenv("STRATA_NO_UI", raising=False)
    return server.create_app(tmp_path / "graphs" / "g.duckdb", warm=False)


def test_the_built_app_is_served_and_routes_fall_back_to_it(tmp_path, monkeypatch):
    with TestClient(make_app(tmp_path, monkeypatch, built=True)) as c:
        assert "STRATA UI" in c.get("/").text
        assert "STRATA UI" in c.get("/tools/ontology/abc").text      # client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/logo.svg").text == "<svg/>"
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.get("/api/nope").status_code == 404


def test_no_file_outside_the_build_can_be_downloaded(tmp_path, monkeypatch):
    with TestClient(make_app(tmp_path, monkeypatch, built=True)) as c:
        for path in ("/..%2Fsecret.txt", "/..%2F..%2F.env", "/%2e%2e/secret.txt",
                     "/%2e%2e%2f%2e%2e%2f.env", "/assets/..%2F..%2Fsecret.txt",
                     "/..\\secret.txt"):
            r = c.get(path)
            assert "leak" not in r.text, path


def test_an_unbuilt_app_explains_what_to_do(tmp_path, monkeypatch):
    with TestClient(make_app(tmp_path, monkeypatch, built=False)) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "python run_server.py" in r.text and "npm run build" in r.text
        assert c.get("/api/health").json()["status"] == "ok"


def test_an_unknown_api_route_explains_itself_for_every_method(tmp_path, monkeypatch):
    with TestClient(make_app(tmp_path, monkeypatch, built=True)) as c:
        for method in ("get", "post", "put", "delete"):
            kwargs = {"json": {}} if method in ("post", "put") else {}
            r = getattr(c, method)("/api/onto/x/future-route", **kwargs)
            assert r.status_code == 404, (method, r.status_code)
            body = r.json()["error"]
            assert body["type"] == "NotFound" and "older version" in body["message"]
        # Real routes are untouched by the catch-all.
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/onto").status_code == 200
