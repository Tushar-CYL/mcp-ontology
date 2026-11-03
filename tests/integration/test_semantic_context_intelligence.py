"""Semantic intelligence and question-first context."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from api.server import create_app


def _write_source(folder):
    folder.mkdir(parents=True)
    (folder / "customers.csv").write_text(
        "customer_id,name,region,segment\n"
        "c1,Ada,West,A\nc2,Grace,West,B\nc3,Linus,East,A\n", encoding="utf-8")
    (folder / "products.csv").write_text(
        "product_id,name,category\np1,Widget,Hardware\n", encoding="utf-8")
    # Build the fixture directly and simply.
    orders = ["order_id,customer_id,region,segment,order_date,status,channel"]
    lines = ["order_id,line_no,product_id,quantity,unit_price,discount_pct,"
             "line_revenue"]
    data = [
        ("o1", "c1", "West", "A", "2026-08-10", 10),
        ("o2", "c1", "West", "A", "2026-09-10", 20),
        ("o3", "c2", "West", "B", "2026-09-11", 30),
        ("o4", "c1", "West", "A", "2026-10-10", 10),
        ("o5", "c2", "West", "B", "2026-10-11", 5),
    ]
    for order_id, customer, region, segment, day, amount in data:
        orders.append(f"{order_id},{customer},{region},{segment},{day},completed,web")
        lines.append(f"{order_id},1,p1,1,{amount},0,{amount}")
    (folder / "orders.csv").write_text("\n".join(orders) + "\n", encoding="utf-8")
    (folder / "order_lines.csv").write_text("\n".join(lines) + "\n",
                                            encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("EYQ_INCUBATOR_ENDPOINT", raising=False)
    monkeypatch.delenv("EYQ_INCUBATOR_KEY", raising=False)
    app = create_app(tmp_path / "context.duckdb", warm=False)
    with TestClient(app) as test_client:
        source = tmp_path / "revenue"
        _write_source(source)
        response = test_client.post("/api/sources", json={
            "path": str(source), "name": "revenue"})
        assert response.status_code == 200, response.text
        yield test_client


def test_metric_catalog_and_intelligence(client):
    metrics = client.get("/api/metrics", params={
        "source": "revenue"}).json()["metrics"]
    names = {metric["name"] for metric in metrics}
    assert {"revenue", "order_volume", "average_order_value",
            "refund_rate", "customer_count"} <= names
    revenue = next(metric for metric in metrics if metric["name"] == "revenue")
    assert revenue["format"] == "currency"
    assert revenue["precision"] == 2

    health = client.get("/api/metrics/revenue/health",
                        params={"source": "revenue"})
    assert health.status_code == 200
    assert health.json()["score"] == 100
    assert health.json()["checks"]

    insights = client.get("/api/metrics/revenue/insights", params={
        "source": "revenue", "time_from": "2026-09-01",
        "time_to": "2026-10-01", "group_by": "segment"})
    assert insights.status_code == 200
    data = insights.json()
    assert data["comparison"]["prior"] is not None
    assert data["contributors"]
    assert any(row["contribution_pct"] is not None
               for row in data["contributors"])


def test_question_context_has_metric_evidence_and_coverage(client):
    response = client.get("/api/context", params={
        "source": "revenue", "budget_chars": 400,
        "question": "Why did West revenue fall in October 2026?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["focus"]["type"] == "question"
    assert data["metric"]["name"] == "revenue"
    assert data["facts"]
    assert data["coverage"]["score"] > 0
    kinds = {fact["kind"] for fact in data["facts"]}
    assert {"definition", "metric", "change"} <= kinds
    assert any(fact["citation"] and fact["citation"].startswith("metric:")
               for fact in data["facts"])
    # A tight budget still must not exceed itself.
    assert data["chars"] <= 400
    assert data["dropped"]
    assert all(fact["reason"] for fact in data["dropped"])


def test_question_context_full_coverage_with_room(client):
    """With enough budget every evidence kind is present, including a real
    source row — the audit trail behind the numbers."""
    data = client.get("/api/context", params={
        "source": "revenue", "budget_chars": 5000,
        "question": "Why did West revenue fall in October 2026?",
    }).json()
    assert data["coverage"]["missing"] == [], data["coverage"]
    assert data["coverage"]["score"] == 100
    row = next(f for f in data["facts"] if f["kind"] == "source_row")
    assert row["text"].startswith("Sample source row from orders:")
    assert "order_id=" in row["text"]
    assert "__row" not in row["text"]
