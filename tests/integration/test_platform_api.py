"""The production API surface: onboarding -> four layers -> agent evidence."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.server import create_app


def _write_revenue_source(folder):
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
    app = create_app(tmp_path / "api.duckdb", warm=False)
    with TestClient(app) as test_client:
        yield test_client


def test_health_without_a_source(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_onboarding_builds_metric_then_agent_and_evidence(client, tmp_path):
    source = tmp_path / "revenue"
    _write_revenue_source(source)

    added = client.post("/api/sources", json={"path": str(source),
                                               "name": "revenue"})
    assert added.status_code == 200, added.text
    payload = added.json()
    assert payload["id"] == "revenue"
    assert payload["nodes"] > 0
    assert payload["status"] == "built"

    metrics = client.get("/api/metrics", params={"source": "revenue"}).json()
    metric_names = {m["name"] for m in metrics["metrics"]}
    assert "revenue" in metric_names
    assert {"order_volume", "average_order_value", "refund_rate"} <= metric_names

    evaluated = client.post("/api/metrics/revenue/evaluate", json={
        "source": "revenue", "group_by": "segment"})
    assert evaluated.status_code == 200
    assert {row[0] for row in evaluated.json()["rows"]} == {"A", "B"}

    created = client.post("/api/agents", json={
        "name": "Revenue Analyst",
        "purpose": "Explain revenue with evidence.",
        "instructions": "Use only approved metrics.",
        "sources": ["revenue"],
        "guardrails": ["Never state a number that is not in evidence."],
        "skills": ["explain_metric", "compare_periods", "breakdown_by",
                   "graph_context", "evidence_search"],
    })
    assert created.status_code == 200, created.text
    agent = created.json()
    assert agent["id"]
    assert agent["source_id"] == "revenue"

    question = ("Why did West revenue fall in October 2026, which segments "
                "drove it, and can I trust it?")
    preview = client.post(f"/api/agents/{agent['id']}/preview",
                          json={"question": question})
    assert preview.status_code == 200, preview.text
    envelope = preview.json()
    assert envelope["answer"]["headline"]
    assert envelope["evidence"]["facts"]
    assert envelope["evidence"]["trace"]
    assert envelope["guardrails"]["passed"] is True
    assert any("metric:revenue:compare" in fact.get("citation", "")
               for fact in envelope["evidence"]["facts"])

    asked = client.post(f"/api/agents/{agent['id']}/ask",
                        json={"question": question})
    assert asked.status_code == 200
    run = asked.json()
    assert run["run_id"]
    stored = client.get(f"/api/runs/{run['run_id']}")
    assert stored.status_code == 200
    assert stored.json()["question"] == question


def test_bad_source_path_is_a_clean_400(client):
    response = client.post("/api/sources", json={"path": "does/not/exist"})
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "FileNotFoundError"


def test_agent_rejects_an_unknown_metric(client, tmp_path):
    source = tmp_path / "revenue"
    _write_revenue_source(source)
    added = client.post("/api/sources", json={"path": str(source),
                                               "name": "revenue"})
    assert added.status_code == 200
    response = client.post("/api/agents", json={
        "name": "Bad metric agent", "source_id": "revenue",
        "metrics": ["profit"], "skills": ["explain_metric"],
    })
    assert response.status_code == 400
    assert "profit" in json.dumps(response.json())
