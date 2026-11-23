"""Readable records (plan step 1.1).

Every record a person sees has a readable name, a one-sentence summary built
from its own values, and one icon for its kind of thing. Where the data has no
name column, a person can say which field is the readable name; that choice is
kept with the ontology and used everywhere.

Shop: 200 customers (with names), 1,000 orders (no name column; 10 point at a
customer that does not exist), order lines, 40 products (with titles)."""

from __future__ import annotations

import pytest

from api.service import MiddleLayer
from knowledge_graph import explore as kg
from ontology import look, simple
from tests.integration.test_declared_links import make_shop


@pytest.fixture
def shop(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


def _thing(layer, oid, word):
    return next(t for t in simple.view(layer.graph, oid)["things"] if word in t["name"].lower())


# ---------------------------------------------------------------- icons
@pytest.mark.parametrize("name,icon", [
    ("Order", "order"), ("Sales Document", "order"), ("Customer", "person"),
    ("Product", "product"), ("Material", "product"), ("Invoice", "document"),
    ("Payment", "payment"), ("Zip Code Geolocation", "place"), ("Order Review", "review"),
    ("Seller", "store"), ("Sensor", "device"), ("Order Line", "line"), ("Widget Thing", "thing"),
])
def test_icon_names_the_kind_of_thing(name, icon):
    assert look.icon(name) == icon
    assert look.icon(name) in look.ICONS


# ---------------------------------------------------------------- summary
def test_record_has_a_one_sentence_summary_from_its_own_values(shop):
    layer, oid = shop
    e = kg.entity(layer, oid, _set_of(layer, oid, "order"), "11")
    s = e["summary"]
    assert s.startswith(e["label"])
    assert "paid" in s and "31" in s                  # its status and its amount, from the row
    assert "Customer 12" in s                         # who it belongs to, by name
    assert s.endswith(".") and s.count(".") <= 3
    assert e["icon"] == "order"


def test_summary_names_a_missing_parent_plainly(shop):
    layer, oid = shop
    e = kg.entity(layer, oid, _set_of(layer, oid, "order"), "1")      # points at customer 999
    assert "999" in e["summary"] and "not found" in e["summary"]


def test_summary_never_shows_personal_data(shop):
    layer, oid = shop
    e = kg.entity(layer, oid, _set_of(layer, oid, "customer"), "5")
    assert e["label"] == "Customer 5"
    assert "@example.com" not in e["summary"]


def test_search_and_overview_carry_icons(shop):
    layer, oid = shop
    hits = kg.search(layer, oid, "Customer 7")["results"]
    assert hits and all(h["icon"] for h in hits)
    assert all(t.get("icon") for t in kg.overview(layer, oid)["things"])
    assert all(t.get("icon") for t in simple.view(layer.graph, oid)["things"])


# ---------------------------------------------------------------- the name field
def test_a_person_can_choose_the_readable_name_field(shop):
    layer, oid = shop
    order = _thing(layer, oid, "order")
    assert kg.entity(layer, oid, _set_of(layer, oid, "order"), "11")["label"].startswith(order["name"])
    simple.edit_thing(layer, oid, order["key"], by="asha", name_field="status")
    e = kg.entity(layer, oid, _set_of(layer, oid, "order"), "11")
    assert e["label"] == "paid"
    assert _thing(layer, oid, "order")["name_field"] == "status"


def test_name_field_must_be_a_field_of_that_thing(shop):
    layer, oid = shop
    order = _thing(layer, oid, "order")
    with pytest.raises(ValueError, match="not a field"):
        simple.edit_thing(layer, oid, order["key"], name_field="title")     # a product field


def test_personal_data_cannot_be_the_name(shop):
    layer, oid = shop
    cust = _thing(layer, oid, "customer")
    with pytest.raises(ValueError, match="personal"):
        simple.edit_thing(layer, oid, cust["key"], name_field="email")


def test_name_suggestions_come_from_the_data(shop):
    layer, oid = shop
    order = _thing(layer, oid, "order")
    picks = look.name_candidates(layer, oid, order["key"])
    cols = [p["column"] for p in picks]
    assert "status" in cols and "id" not in cols and "net_amount" not in cols
    assert all("distinct" in p and "example" in p for p in picks)


def _set_of(layer, oid, word):
    m = kg.model(layer, oid)
    return next(k for k, s in m["sets"].items()
                if word in s["thing"].lower() and "line" not in s["thing"].lower())
