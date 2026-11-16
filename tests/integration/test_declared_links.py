"""Links in a database with declared foreign keys.

Found end to end on a real SQLite shop: plain integer ids overlap by
accident (customer 1..200 sits inside order 1..1000), so value matching
alone invented "each Customer has one Order" and "each Order belongs to one
Order Line". The database's own foreign keys are the truth; guesses must not
add to a column the database already explains, and a link target must be a
real key.
"""

from __future__ import annotations

import sqlite3

from api.service import MiddleLayer
from ontology import simple


def make_shop(path):
    s = sqlite3.connect(path)
    s.executescript("""
        create table customer(id integer primary key, name text, country text, email text);
        create table product(sku text primary key, title text, list_price real);
        create table orders(id integer primary key,
                            customer_id integer references customer(id),
                            status text, net_amount real);
        create table order_line(order_id integer references orders(id),
                                sku text references product(sku),
                                qty integer, primary key(order_id, sku));""")
    s.executemany("insert into customer values(?,?,?,?)",
                  [(i, f"Customer {i}", ["IN", "GB"][i % 2], f"c{i}@example.com")
                   for i in range(1, 201)])
    s.executemany("insert into product values(?,?,?)",
                  [(f"SKU{i:03d}", f"Product {i}", 10.0 + i) for i in range(1, 41)])
    # 10 orders point at customer 999, which does not exist: an orphan the
    # declared link must still show, not drop.
    s.executemany("insert into orders values(?,?,?,?)",
                  [(i, 999 if i <= 10 else i % 200 + 1, "paid", 20.0 + i) for i in range(1, 1001)])
    s.executemany("insert into order_line values(?,?,?)",
                  [(o, f"SKU{(o * k) % 40 + 1:03d}", k) for o in range(1, 1001) for k in (1, 2)
                   if (o * 1) % 40 != (o * 2) % 40])
    s.commit()
    s.close()
    return path


def test_declared_foreign_keys_are_the_links_and_nothing_is_invented(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    v = simple.view(layer.graph, oid)

    pairs = {(link["from"], link["to"]) for link in v["links"]}
    assert pairs == {
        ("shop.orders.customer_id", "shop.customer.id"),
        ("shop.order_line.order_id", "shop.orders.id"),
        ("shop.order_line.sku", "shop.product.sku"),
    }, pairs

    by_from = {link["from"]: link for link in v["links"]}
    orphaned = by_from["shop.orders.customer_id"]
    assert orphaned["declared"] == "the database"
    # Kept although 1 of 201 distinct values (999) has no customer.
    assert orphaned["match"] is not None and orphaned["match"] < 1


def test_personal_data_is_marked_on_screen_and_in_the_excel_feed(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    v = simple.view(layer.graph, oid)
    personal = {f["column"]: f["personal"] for t in v["things"] for f in t["fields"]
                if f["personal"]}
    assert personal == {"email": "Email"}
    feed = simple.for_excel(layer.graph, oid)
    flagged = {r["Column"]: r["Personal data"] for r in feed["fields"] if r["Personal data"]}
    assert flagged == {"email": "Email"}
