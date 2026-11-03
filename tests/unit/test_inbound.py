"""Inbound links: which records point AT this one.

The Entity Investigator asks "tell me about customer c1"; the links run
Order -> Customer, so it needs edges INTO the customer, with a SQL limit so a
super-node stays cheap (docs/research/2026/02_knowledge_graph.md).
"""

from __future__ import annotations

import sqlite3

import pytest

from api.service import MiddleLayer


@pytest.fixture
def layer(tmp_path):
    db = tmp_path / "shop.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id), total REAL);
        INSERT INTO customers VALUES (1,'Ada'),(2,'Grace'),(3,'Linus');
        INSERT INTO orders VALUES (10,1,5),(11,1,6),(12,1,7),(13,2,8);
    """)
    con.commit()
    con.close()
    service = MiddleLayer(str(tmp_path / "g.duckdb"))
    service.add_source(str(db), source="shop")
    yield service
    service.close()


def _rel(layer):
    rel = next(r for r in layer._bundle("shop").onto.relations.values()
               if r.domain == "Order" and r.range == "Customer")
    return rel.name


def test_inbound_returns_the_records_that_link_here(layer):
    found = layer.graph.inbound("Customer", "1", _rel(layer), source="shop")
    assert sorted(found) == ["10", "11", "12"]


def test_inbound_limit_caps_fan_out(layer):
    found = layer.graph.inbound("Customer", "1", _rel(layer), source="shop", limit=2)
    assert len(found) == 2
    assert layer.graph.inbound_count("Customer", "1", _rel(layer), source="shop") == 3


def test_a_record_nobody_links_to_has_no_inbound(layer):
    assert layer.graph.inbound("Customer", "3", _rel(layer), source="shop") == {}
    assert layer.graph.inbound_count("Customer", "3", _rel(layer), source="shop") == 0


def test_unknown_node_or_relation_is_empty_not_an_error(layer):
    assert layer.graph.inbound("Customer", "999", _rel(layer), source="shop") == {}
    assert layer.graph.inbound("Customer", "1", "no_such_rel", source="shop") == {}
    assert layer.graph.inbound_count("Customer", "999", _rel(layer), source="shop") == 0
