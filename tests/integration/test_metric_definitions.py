"""Approved semantic metric definitions: the business layer, not proposals."""

from __future__ import annotations

import sqlite3

import pytest

from knowledge_graph.build import build, table_ref
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover
from semantic import definitions


@pytest.fixture
def shop(tmp_path):
    db = tmp_path / "shop.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id), total REAL,
            placed_at TIMESTAMP);
        INSERT INTO customers VALUES (1,'Ada'),(2,'Grace');
        INSERT INTO orders VALUES
            (1,1,10.0,'2026-09-10'),(2,1,20.0,'2026-09-11'),
            (3,2,5.0,'2026-10-10');
    """)
    con.commit(); con.close()
    schema = connect(str(db)); onto = discover(schema)
    graph = open_graph(tmp_path / "g.duckdb")
    build(graph, schema, onto, source="shop")
    base_sql = (f"SELECT CAST(placed_at AS DATE) AS order_date, "
                f"total AS revenue FROM "
                f"{table_ref(graph, schema, 'orders', source='shop')}")
    definitions.upsert_metric(
        graph, "shop", "revenue", "Revenue", base_sql=base_sql,
        value_expr="SUM(revenue)", time_column="order_date",
        dimensions=[], owner="finance")
    return graph


def test_list_and_get(shop):
    items = definitions.list_definitions(shop)
    assert len(items) == 1
    assert items[0]["name"] == "revenue"
    assert items[0]["status"] == "approved"
    assert definitions.get_definition(shop, "revenue", "shop")["title"] == "Revenue"


def test_evaluate_total_and_time_window(shop):
    total = definitions.evaluate_definition(shop, "revenue", "shop")
    assert total["rows"] == [[35.0]]
    september = definitions.evaluate_definition(
        shop, "revenue", "shop", time_from="2026-09-01",
        time_to="2026-10-01")
    assert september["rows"] == [[30.0]]
    assert "SUM(revenue)" in september["sql"]


def test_unknown_metric_is_a_clear_error(shop):
    with pytest.raises(KeyError, match="no approved metric"):
        definitions.evaluate_definition(shop, "profit", "shop")


def test_unknown_dimension_is_refused(shop):
    with pytest.raises(KeyError, match="no dimension"):
        definitions.evaluate_definition(shop, "revenue", "shop",
                                        group_by="nonsense")


def test_filters_are_bound(shop):
    result = definitions.evaluate_definition(
        shop, "revenue", "shop", filters={"order_date": "2026-09-10"})
    assert result["params"] == ["2026-09-10"]
    assert "?" in result["sql"]


def test_unapproved_metric_cannot_be_served(shop):
    definitions.upsert_metric(
        shop, "shop", "draft_metric", "Draft",
        base_sql="SELECT 1 AS revenue", value_expr="SUM(revenue)",
        status="draft")
    with pytest.raises(KeyError, match="cannot be served"):
        definitions.evaluate_definition(shop, "draft_metric", "shop")


def test_seed_revenue_metric_on_real_shape(tmp_path):
    d = tmp_path / "rev"
    d.mkdir()
    (d / "customers.csv").write_text(
        "customer_id,name,region,segment\nc1,Ada,West,A\n", encoding="utf-8")
    (d / "products.csv").write_text(
        "product_id,name,category\np1,Widget,Hardware\n", encoding="utf-8")
    (d / "orders.csv").write_text(
        "order_id,customer_id,region,segment,order_date,status,channel\n"
        "o1,c1,West,A,2026-09-10,completed,web\n"
        "o2,c1,West,A,2026-10-10,completed,web\n", encoding="utf-8")
    (d / "order_lines.csv").write_text(
        "order_id,line_no,product_id,quantity,unit_price,discount_pct,"
        "line_revenue\n"
        "o1,1,p1,2,10.0,0,20.0\no2,1,p1,1,10.0,0,10.0\n", encoding="utf-8")
    schema = connect(str(d)); onto = discover(schema)
    graph = open_graph(tmp_path / "rev.duckdb")
    build(graph, schema, onto, source="rev")
    definition = definitions.seed_revenue_metric(graph, schema, onto, "rev")
    assert definition["name"] == "revenue"
    total = definitions.evaluate_definition(graph, "revenue", "rev")
    assert total["rows"] == [[30.0]]
    october = definitions.evaluate_definition(
        graph, "revenue", "rev", time_from="2026-10-01",
        time_to="2026-11-01")
    assert october["rows"] == [[10.0]]
