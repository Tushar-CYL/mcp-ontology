"""Agent configuration: AI guardrail suggestions, certification, evidence."""

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


def test_agent_with_evidence_and_certification(client):
    created = client.post("/api/agents", json={
        "name": "Revenue Analyst",
        "purpose": "Explain revenue.",
        "problem_statement": "Why did West revenue fall, and can I trust it?",
        "instructions": "Use approved metrics and cite evidence.",
        "sources": ["revenue"],
        "metrics": ["revenue"],
        "skills": ["explain_metric", "compare_periods", "breakdown_by",
                   "graph_context", "evidence_search"],
        "guardrails": ["Never state a number that is not in the evidence."],
    })
    assert created.status_code == 200, created.text
    agent = created.json()
    assert agent["problem_statement"] == "Why did West revenue fall, and can I trust it?"
    assert agent["metrics"] == ["revenue"]

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


