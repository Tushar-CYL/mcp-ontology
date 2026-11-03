"""Picking an entity to inspect works for every kind of thing, on any size.

The Context page used to offer only entities that happened to be in a
300-node graph sample, so most kinds showed "No entities for this class".
Keys now come straight from the graph for the chosen kind, with search and a
hard limit, so a class with a million records still answers instantly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from tests.integration.test_autopilot import _write_salt_like


@pytest.fixture
def client(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    with TestClient(create_app(tmp_path / "e.duckdb", warm=False)) as c:
        assert c.post("/api/sources", json={"path": str(folder), "name": "salt"}).status_code == 200
        yield c


@pytest.mark.parametrize("cls", ["Customer", "Document", "DocumentItem"])
def test_every_kind_lists_real_keys(client, cls):
    data = client.get("/api/entities", params={"source": "salt", "class": cls}).json()
    assert data["class"] == cls
    assert data["keys"], cls
    assert data["total"] >= len(data["keys"])


def test_search_narrows_keys(client):
    data = client.get("/api/entities", params={
        "source": "salt", "class": "Customer", "q": "A1"}).json()
    assert data["keys"]
    assert all("a1" in key.lower() for key in data["keys"])


def test_limit_is_capped(client):
    data = client.get("/api/entities", params={
        "source": "salt", "class": "Document", "limit": 10_000}).json()
    assert len(data["keys"]) <= 100
    small = client.get("/api/entities", params={
        "source": "salt", "class": "Document", "limit": 5}).json()
    assert len(small["keys"]) == 5


def test_unknown_class_is_404(client):
    response = client.get("/api/entities", params={"source": "salt", "class": "Nope"})
    assert response.status_code == 404


def test_a_listed_key_builds_a_context_pack(client):
    key = client.get("/api/entities", params={
        "source": "salt", "class": "Document"}).json()["keys"][0]
    pack = client.get("/api/context", params={
        "source": "salt", "class": "Document", "key": key})
    assert pack.status_code == 200, pack.text
    assert pack.json()["facts"]


def test_search_text_is_treated_as_data(client):
    response = client.get("/api/entities", params={
        "source": "salt", "class": "Customer", "q": "' OR 1=1 --"})
    assert response.status_code == 200
    assert response.json()["keys"] == []
