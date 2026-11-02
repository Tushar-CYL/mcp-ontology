"""Agent builder: custom skills, AI guardrail suggestions, certification, evidence."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app


def _write_source(folder):
    folder.mkdir(parents=True)
    (folder / "customers.csv").write_text(
        "customer_id,name,region,segment\n"
        "c1,Ada,West,A\nc2,Grace,West,B\n", encoding="utf-8")
    (folder / "products.csv").write_text(
        "product_id,name,category\np1,Widget,Hardware\n",
        encoding="utf-8")
    (folder / "orders.csv").write_text(
        "order_id,customer_id,region,segment,order_date,status,channel\n"
        "o1,c1,West,A,2026-09-10,completed,web\n"
        "o2,c2,West,B,2026-09-11,completed,web\n"
        "o3,c1,West,A,2026-10-10,completed,web\n"
        "o4,c2,West,B,2026-10-11,completed,web\n", encoding="utf-8")
    (folder / "order_lines.csv").write_text(
        "order_id,line_no,product_id,quantity,unit_price,discount_pct,"
        "line_revenue\n"
        "o1,1,p1,2,10.0,0,20.0\no2,1,p1,2,10.0,0,20.0\n"
        "o3,1,p1,1,10.0,0,10.0\no4,1,p1,1,10.0,0,10.0\n",
        encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("EYQ_INCUBATOR_ENDPOINT", raising=False)
    monkeypatch.delenv("EYQ_INCUBATOR_KEY", raising=False)
    app = create_app(tmp_path / "builder.duckdb", warm=False)
    with TestClient(app) as test_client:
        source = tmp_path / "revenue"
        _write_source(source)
        response = test_client.post("/api/sources",
                                    json={"path": str(source), "name": "revenue"})
        assert response.status_code == 200, response.text
        yield test_client


def test_custom_skill_then_agent_with_evidence_and_certification(client):
    skills = client.get("/api/skills", params={"source": "revenue"})
    assert skills.status_code == 200
    assert {item["id"] for item in skills.json()["skills"]} >= {
        "explain_metric", "compare_periods", "breakdown_by",
        "graph_context", "evidence_search"}

    created_skill = client.post("/api/skills", json={
        "name": "West focus", "description": "Focus on the West region.",
        "source_id": "revenue", "kind": "breakdown", "metric": "revenue",
        "dimension": "segment",
    })
    assert created_skill.status_code == 200, created_skill.text
    skill_id = created_skill.json()["id"]
    assert skill_id.startswith("skill_")

    suggested = client.post("/api/agents/suggest-guardrails", json={
        "problem_statement": "Why did revenue fall, and can I trust it?",
        "source_id": "revenue", "metrics": ["revenue"],
    })
    assert suggested.status_code == 200
    assert suggested.json()["guardrails"]
    assert suggested.json()["configured"] is False

    created = client.post("/api/agents", json={
        "name": "Revenue Analyst",
        "purpose": "Explain revenue.",
        "problem_statement": "Why did West revenue fall, and can I trust it?",
        "instructions": "Use approved metrics and cite evidence.",
        "sources": ["revenue"],
        "metrics": ["revenue"],
        "skills": ["explain_metric", "compare_periods", "breakdown_by",
                   "graph_context", "evidence_search", skill_id],
        "guardrails": ["Never state a number that is not in the evidence."],
    })
    assert created.status_code == 200, created.text
    agent = created.json()
    assert agent["problem_statement"] == "Why did West revenue fall, and can I trust it?"
    assert agent["metrics"] == ["revenue"]
    assert skill_id in agent["skills"]

    published = client.post(f"/api/agents/{agent['id']}/publish")
    assert published.status_code == 200

    preview = client.post(f"/api/agents/{agent['id']}/preview", json={
        "question": "Why did West revenue fall in October 2026, and can I trust it?",
    })
    assert preview.status_code == 200, preview.text
    envelope = preview.json()
    evidence = envelope["evidence"]
    assert evidence["facts"]
    assert evidence["source_records"], "a source-row sample is required evidence"
    assert evidence["prior_evidence"], "prior-period evidence is required"
    assert evidence["lineage"]["sql"], "metric lineage must include compiled SQL"
    assert evidence["relationships"], "schema relationship evidence is guaranteed"
    assert any(str(fact.get("citation", "")).startswith("relationship:")
               for fact in evidence["relationships"])
    assert any(step.get("tool") == "source_rows" for step in evidence["trace"])
    assert envelope["guardrails"]["passed"] is True

    certification = client.get("/api/certification", params={"source": "revenue"})
    assert certification.status_code == 200, certification.text
    data = certification.json()
    assert [layer["layer"] for layer in data["layers"]] == [
        "Ontology", "Knowledge graph", "Semantic layer", "Context"]
    assert data["status"] in ("pass", "warn")


def test_source_guardrails_persist_and_are_inherited(client):
    saved = client.put("/api/sources/revenue/guardrails", json={
        "rules": ["Never expose customer contact details."],
    })
    assert saved.status_code == 200, saved.text
    rules = saved.json()["rules"]
    assert any("contact details" in rule["instruction"] for rule in rules)
    fetched = client.get("/api/sources/revenue/guardrails")
    assert fetched.status_code == 200
    assert any("contact details" in rule["instruction"]
               for rule in fetched.json()["rules"])


def test_custom_skill_rejects_an_unapproved_metric(client):
    response = client.post("/api/skills", json={
        "name": "Profit focus", "source_id": "revenue", "kind": "metric_focus",
        "metric": "profit",
    })
    assert response.status_code == 400
    assert "approved" in response.text
