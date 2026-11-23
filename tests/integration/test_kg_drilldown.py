"""Knowledge graph drill-down: links named by their role (sold-to vs ship-to),
and every record linked to one record, page by page, narrowed by a word."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from api.service import MiddleLayer
from knowledge_graph import explore as kg
from knowledge_graph.explore import GraphError
from ontology import simple


def make_sales(path):
    s = sqlite3.connect(path)
    s.executescript("""
        create table customer(id integer primary key, name text);
        create table sales_doc(id integer primary key,
            sold_to integer references customer(id), ship_to integer references customer(id),
            placed date);
        create table sales_item(id integer primary key, doc_id integer references sales_doc(id),
            sku text, qty integer);""")
    s.executemany("insert into customer values(?,?)", [(i, f"Customer {i}") for i in range(1, 11)])
    s.executemany("insert into sales_doc values(?,?,?,?)",
                  [(d, 1 if d <= 120 else 2, 3 if d % 2 else 1, f"2024-01-{d % 28 + 1:02d}")
                   for d in range(1, 201)])
    s.executemany("insert into sales_item values(?,?,?,?)",
                  [(i, 1 + i % 5, f"SKU{i % 7}", 1) for i in range(1, 301)])
    s.commit()
    s.close()
    return path


@pytest.fixture(scope="module")
def sales(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("drill")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(make_sales(tmp / "sales.db")), source="sales")
    oid = simple.create_and_build(layer, "Sales", ["sales"])["ontology"]
    return layer, oid


def _conn(entity, role_word, direction):
    return [c for c in entity["connections"] if c["direction"] == direction
            and role_word.lower() in str(c.get("role") or "").lower()]


def test_two_links_to_the_same_thing_are_named_by_role(sales):
    layer, oid = sales
    e = kg.entity(layer, oid, "sales.customer", "1")
    sold = _conn(e, "sold", "in")
    ship = _conn(e, "ship", "in")
    assert sold and ship, [c["text"] for c in e["connections"]]
    assert sold[0]["count"] == 120                      # documents 1-120 are sold to customer 1
    assert ship[0]["count"] == 100                      # even documents ship to customer 1
    assert "as" in sold[0]["text"] and sold[0]["text"] != ship[0]["text"]
    doc = kg.entity(layer, oid, "sales.sales_doc", "2")
    outs = [c for c in doc["connections"] if c["direction"] == "out"]
    assert len({c["text"] for c in outs}) == len(outs) == 2


def test_a_single_plain_link_needs_no_role(sales):
    layer, oid = sales
    e = kg.entity(layer, oid, "sales.sales_doc", "1")
    lines = next(c for c in e["connections"] if c["direction"] == "in")
    assert lines["role"] is None and lines["text"].endswith("records linked to it")


def test_drill_down_pages_through_every_linked_record(sales):
    layer, oid = sales
    sold = _conn(kg.entity(layer, oid, "sales.customer", "1"), "sold", "in")[0]
    seen, offset = [], 0
    while True:
        page = kg.connection(layer, oid, "sales.customer", "1", sold["link"], offset=offset, limit=50)
        assert page["total"] == 120 and page["direction"] == "in"
        if not page["items"]:
            break
        seen += [i["key"] for i in page["items"]]
        offset += 50
    assert len(seen) == len(set(seen)) == 120


def test_drill_down_narrows_by_a_word(sales):
    layer, oid = sales
    sold = _conn(kg.entity(layer, oid, "sales.customer", "1"), "sold", "in")[0]
    page = kg.connection(layer, oid, "sales.customer", "1", sold["link"], q="11")
    assert page["total"] == 120 and page["matching"] == len(page["items"])
    assert {i["key"] for i in page["items"]} == {"11", "110", "111", "112", "113", "114", "115",
                                                   "116", "117", "118", "119"}


def test_drill_down_up_the_link_gives_the_one_parent(sales):
    layer, oid = sales
    doc = kg.entity(layer, oid, "sales.sales_doc", "7")
    up = next(c for c in doc["connections"] if c["direction"] == "out" and "ship" in str(c["role"]).lower())
    page = kg.connection(layer, oid, "sales.sales_doc", "7", up["link"])
    assert page["total"] == 1 and page["items"][0]["key"] == "3"


def test_drill_down_refuses_what_is_not_there(sales):
    layer, oid = sales
    link = kg.entity(layer, oid, "sales.customer", "1")["connections"][0]["link"]
    with pytest.raises(GraphError):
        kg.connection(layer, oid, "sales.customer", "999", link)
    with pytest.raises(GraphError):
        kg.connection(layer, oid, "sales.customer", "1", "no-such-link")
    with pytest.raises(GraphError):
        kg.connection(layer, oid, "sales.nowhere", "1", link)
    item_link = next(c["link"] for c in kg.entity(layer, oid, "sales.sales_item", "1")["connections"])
    with pytest.raises(GraphError):
        kg.connection(layer, oid, "sales.customer", "1", item_link)   # not a link of Customer
    page = kg.connection(layer, oid, "sales.customer", "1", link, q="'; drop table x; --")
    assert page["matching"] == 0


def test_drill_down_through_the_api(sales, tmp_path):
    app = create_app(tmp_path / "graphs" / "g.duckdb", warm=False)
    with TestClient(app) as c:
        layer = c.app.state.platform.layer
        layer.add_source(str(make_sales(tmp_path / "sales.db")), source="sales")
        oid = simple.create_and_build(layer, "Sales", ["sales"])["ontology"]
        e = c.get(f"/api/kg/{oid}/entity", params={"set": "sales.customer", "key": "1"}).json()
        link = next(x["link"] for x in e["connections"] if "sold" in str(x.get("role")).lower())
        page = c.get(f"/api/kg/{oid}/connection", params={"set": "sales.customer", "key": "1",
                                                          "link": link, "limit": 10, "offset": 10}).json()
        assert page["total"] == 120 and len(page["items"]) == 10
        bad = c.get(f"/api/kg/{oid}/connection", params={"set": "sales.customer", "key": "1", "link": "x"})
        assert bad.status_code == 400
        assert c.get(f"/api/kg/{oid}/connection", params={"set": "sales.customer", "key": "1",
                                                          "link": link, "limit": 999}).status_code == 422


def test_a_value_on_a_parent_with_many_values_still_filters(tmp_path):
    """Live on SALT: 'How many customers in DE?' gave every customer, because
    Country (on the address) has too many values to group by, so it was never
    selected and the filter was dropped. Found by the report check."""
    from context import engine as ctx
    s = sqlite3.connect(tmp_path / "geo.db")
    s.executescript("""
        create table address(id integer primary key, country text);
        create table customer(id integer primary key, address_id integer references address(id),
                              name text);""")
    codes = [f"C{i:03d}" for i in range(120)] + ["DE"]        # 121 countries: too many to group by
    s.executemany("insert into address values(?,?)", [(i, codes[i % len(codes)]) for i in range(1, 1211)])
    s.executemany("insert into customer values(?,?,?)", [(i, i, f"Customer {i}") for i in range(1, 1211)])
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(tmp_path / "geo.db"), source="geo")
    oid = simple.create_and_build(layer, "Geo", ["geo"])["ontology"]
    f = ctx.build(layer, oid, "How many customers in DE?")["steps"]["facts"]
    assert f["table"]["rows"] == [[10]], (f["table"], f["sql"])
