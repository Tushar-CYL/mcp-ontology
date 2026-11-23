"""Business rules you can check: a person writes a rule in plain words,
Strata turns it into a check on the real data, shows how many records follow
it (with examples of the ones that do not), and the person activates it with
an owner. Active rules reach the AI as facts, and a counting rule ("cancelled
orders do not count") is compared with every metric that should obey it.

Rules come from people, or are suggested from the data; the data checks them;
a person decides. They survive rebuilds."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from api.service import MiddleLayer
from context import engine as ctx
from ontology import business_rules as rules
from ontology import simple
from semantic import model as sem
from tests.integration.test_declared_links import make_shop


def _shop_with_problems(path):
    make_shop(path)
    s = sqlite3.connect(path)
    s.executescript("""
        UPDATE orders SET status = 'cancelled' WHERE id % 10 = 0 AND id > 10;   -- 99 cancelled
        UPDATE orders SET net_amount = -5 WHERE id IN (11, 12, 13);              -- 3 negative
        UPDATE customer SET email = NULL WHERE id <= 4;                          -- 4 without email
    """)
    s.commit()
    s.close()
    return path


@pytest.fixture
def shop(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(_shop_with_problems(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


# ------------------------------------------------------------- reading a rule
@pytest.mark.parametrize("text, kind, field", [
    ("Every order must belong to an existing customer", "exists", "shop.orders.customer_id"),
    ("Net amount must be positive", "range", "shop.orders.net_amount"),
    ("Order status must be one of paid, cancelled", "allowed", "shop.orders.status"),
    ("Every customer must have an email", "required", "shop.customer.email"),
    ("Product sku must be unique", "unique", "shop.product.sku"),
    ("Cancelled orders do not count", "excluded", "shop.orders.status"),
])
def test_plain_words_become_a_check_on_a_real_field(shop, text, kind, field):
    layer, oid = shop
    spec = rules.read(layer, oid, text)
    assert spec["type"] == kind and spec["field"] == field


def test_a_rule_naming_nothing_real_is_refused_with_real_fields_to_try(shop):
    layer, oid = shop
    with pytest.raises(rules.RuleError) as e:
        rules.read(layer, oid, "The weather must be nice")
    msg = str(e.value)
    assert "field" in msg.lower() and any(w in msg for w in ("Net amount", "Status", "Email"))


# ------------------------------------------------------------- the data checks it
def test_exists_counts_orders_pointing_at_a_missing_customer(shop):
    layer, oid = shop
    r = rules.add(layer, oid, "Every order must belong to an existing customer", by="ops")
    res = r["result"]
    assert (res["checked"], res["failed"]) == (1000, 10)
    assert res["passed_pct"] == 99.0
    assert any("999" in str(x) for x in res["examples"])
    assert r["status"] == "proposed" and r["by"] == "ops"


def test_range_allowed_required_unique_on_the_data(shop):
    layer, oid = shop
    neg = rules.add(layer, oid, "Net amount must be positive")["result"]
    assert neg["failed"] == 3 and len(neg["examples"]) == 3
    ok = rules.add(layer, oid, "Order status must be one of paid, cancelled")["result"]
    assert ok["failed"] == 0 and ok["passed_pct"] == 100.0
    only_paid = rules.add(layer, oid, "Order status must be one of paid")["result"]
    assert only_paid["failed"] == 99
    email = rules.add(layer, oid, "Every customer must have an email")["result"]
    assert (email["checked"], email["failed"]) == (200, 4)
    sku = rules.add(layer, oid, "Product sku must be unique")["result"]
    assert sku["failed"] == 0


def test_a_counting_rule_finds_the_records_and_the_metrics_that_ignore_it(shop):
    layer, oid = shop
    sem.propose(layer, oid)
    sem.certify(layer, oid, "total_net_amount", owner="Finance")
    r = rules.add(layer, oid, "Cancelled orders do not count")
    assert r["spec"]["values"] == ["cancelled"]
    assert r["result"]["affected"] == 99
    conflicts = rules.conflicts(layer, oid)
    hit = next(c for c in conflicts if c["metric"] == "total_net_amount")
    assert hit["rule"] == r["id"] and "cancelled" in hit["text"] and hit["certified"] is True


# ------------------------------------------------------------- a person decides
def test_activate_retire_remove_and_rules_survive_a_rebuild(shop):
    layer, oid = shop
    r = rules.add(layer, oid, "Net amount must be positive", by="ravi")
    a = rules.activate(layer, oid, r["id"], by="meera", owner="Finance")
    assert a["status"] == "active" and a["owner"] == "Finance" and a["decided_by"] == "meera"
    simple.build(layer, oid)
    again = {x["id"]: x for x in rules.listing(layer, oid)["rules"]}
    assert again[r["id"]]["status"] == "active"
    assert rules.retire(layer, oid, r["id"], by="meera")["status"] == "retired"
    rules.remove(layer, oid, r["id"])
    assert r["id"] not in {x["id"] for x in rules.listing(layer, oid)["rules"]}
    with pytest.raises(KeyError):
        rules.activate(layer, oid, "nope", by="x")


def test_check_again_sees_fixed_data(shop, tmp_path):
    layer, oid = shop
    r = rules.add(layer, oid, "Net amount must be positive")
    s = sqlite3.connect(tmp_path / "shop.db")
    s.execute("UPDATE orders SET net_amount = 5 WHERE id IN (11, 12, 13)")
    s.commit()
    s.close()
    layer.refresh_source("shop") if hasattr(layer, "refresh_source") else None
    again = rules.check(layer, oid, r["id"])
    assert again["result"]["checked"] == 1000            # re-measured, with a new time
    assert again["result"]["at"] >= r["result"]["at"]


# ------------------------------------------------------------- suggested from the data
def test_suggestions_come_from_the_data_and_skip_rules_already_written(shop):
    layer, oid = shop
    out = rules.listing(layer, oid)
    sugg = out["suggestions"]
    assert 3 <= len(sugg) <= rules.MAX_SUGGESTIONS
    kinds = {s["spec"]["type"] for s in sugg}
    assert "exists" in kinds                              # the orphan orders make it worth a rule
    fields = {f["key"]: f for t in simple.view(layer.graph, oid)["things"] for f in t["fields"]}
    for s in sugg:
        assert s["spec"]["field"] in fields
        assert fields[s["spec"]["field"]]["label"].lower() in s["text"].lower()
        assert rules.read(layer, oid, s["text"])["type"] == s["spec"]["type"]   # the words read back
    first = sugg[0]
    rules.add(layer, oid, first["text"])
    assert first["text"] not in {s["text"] for s in rules.listing(layer, oid)["suggestions"]}


# ------------------------------------------------------------- reaching the AI
def test_only_active_rules_reach_the_context_pack(shop):
    layer, oid = shop
    r = rules.add(layer, oid, "Net amount must be positive", by="ravi")
    q = "What is the total net amount of orders?"

    def texts():
        return [f["text"] for f in ctx.build(layer, oid, q, phrase=False)["steps"]["facts"]["kept"]]

    assert not any("must be positive" in t for t in texts())
    rules.activate(layer, oid, r["id"], by="meera", owner="Finance")
    fact = next(t for t in texts() if "must be positive" in t)
    assert "Finance" in fact and "3 " in fact                 # the owner and what the data found


# ------------------------------------------------------------- API
def test_rules_api(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATA_API_TOKENS", raising=False)
    monkeypatch.setenv("STRATA_DATA_ROOTS", "")
    app = create_app(tmp_path / "g.duckdb", warm=False)
    with TestClient(app) as c:
        layer = app.state.platform.layer
        layer.add_source(str(_shop_with_problems(tmp_path / "shop.db")), source="shop")
        oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        r = c.post(f"/api/rules/{oid}", json={"text": "Net amount must be positive"})
        assert r.status_code == 200 and r.json()["result"]["failed"] == 3
        rid = r.json()["id"]
        assert c.post(f"/api/rules/{oid}/{rid}/activate", json={"owner": "Finance"}).json()["status"] == "active"
        listing = c.get(f"/api/rules/{oid}").json()
        assert listing["rules"][0]["id"] == rid and "suggestions" in listing and "conflicts" in listing
        assert c.post(f"/api/rules/{oid}", json={"text": "The weather must be nice"}).status_code == 400
        assert c.post(f"/api/rules/{oid}/{rid}/check").status_code == 200
        assert c.delete(f"/api/rules/{oid}/{rid}").status_code == 200
