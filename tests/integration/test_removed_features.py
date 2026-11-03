"""Removals stay removed: Strata is the four layers plus agents.

Phase 1 removed the agent builder (publishing, custom skills) and the second
Streamlit UI. The simplification removes every screen that is not one of the
four layers or Agents: Context Factory, Glossary, Certification as its own
page, Corrections as its own panel, and the stdlib HTTP server. Their useful
parts are folded into the layers (health strips, metric synonyms, Steward).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "removed.duckdb", warm=False)) as c:
        yield c


@pytest.mark.parametrize("method, path", [
    ("post", "/api/agents/any/publish"),
    ("post", "/api/skills"),
    ("delete", "/api/skills/skill_x"),
    ("get", "/api/skills"),
    ("get", "/api/tools"),
    ("post", "/api/agents/suggest-guardrails"),
    ("get", "/api/sources/revenue/guardrails"),
    ("put", "/api/sources/revenue/guardrails"),
    ("get", "/api/factory/overview"),
    ("get", "/api/factory/assets"),
    ("post", "/api/factory/discover"),
    ("get", "/api/factory/conflicts"),
    ("get", "/api/factory/quality"),
    ("get", "/api/glossary"),
    ("put", "/api/glossary/x"),
])
def test_removed_endpoints_are_gone(client, method, path):
    response = getattr(client, method)(path, json={}) if method in ("post", "put") \
        else getattr(client, method)(path)
    assert response.status_code in (404, 405), (path, response.status_code)


@pytest.mark.parametrize("path", [
    "app.py", "ui.py", "api/http.py", "factory", "semantic/glossary.py",
])
def test_removed_backend_files_are_gone(path):
    assert not (ROOT / path).exists(), path


@pytest.mark.parametrize("page", [
    "Solutions.tsx", "Platform.tsx", "PublishedAgent.tsx", "AgentStudio.tsx",
    "Factory.tsx", "Glossary.tsx", "Certification.tsx", "AgentConnections.tsx",
])
def test_removed_frontend_pages_are_gone(page):
    assert not (ROOT / "frontend" / "src" / "pages" / page).exists()


@pytest.mark.parametrize("component", ["CorrectionsPanel.tsx", "BeforeAfterCard.tsx"])
def test_removed_frontend_components_are_gone(component):
    assert not (ROOT / "frontend" / "src" / "components" / component).exists()


def test_the_layers_and_agents_still_answer(client):
    # Not removed: each of the four layers and the agents keep their routes.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/agents").status_code == 200
    assert client.get("/api/agent-presets").status_code == 200


def test_api_identifies_as_strata(client):
    assert client.get("/openapi.json").json()["info"]["title"] == "Strata"
