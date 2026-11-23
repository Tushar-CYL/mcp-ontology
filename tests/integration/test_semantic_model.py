"""The semantic layer of an ontology: proposals, decisions, safe joins,
drift, receipts and verified questions."""

from __future__ import annotations

import sqlite3

import duckdb
import pytest

from api.service import MiddleLayer
from ontology import simple
from semantic import model as sem


def make_amounts(path):
    """An order table with five money columns (the 'which amount is right?'
    problem), customers, and order lines (one order has many lines)."""
    s = sqlite3.connect(path)
    s.executescript("""
        create table customer(id integer primary key, name text, country text, segment text);
        create table orders(id integer primary key, customer_id integer references customer(id),
                            status text, placed date, net_amount real, tax_amount real,
                            gross_amount real, discount_amount real, freight_amount real);
        create table order_line(id integer primary key, order_id integer references orders(id),
                                sku text, qty integer, line_amount real);""")
    s.executemany("insert into customer values(?,?,?,?)",
                  [(i, f"Customer {i}", ["IN", "GB", "US"][i % 3], ["SMB", "Enterprise"][i % 2])
                   for i in range(1, 61)])
    orders, lines, lid = [], [], 0
    for i in range(1, 401):
        net = float(50 + i % 90)
        orders.append((i, i % 60 + 1, ["paid", "shipped", "cancelled"][i % 3],
                       f"2024-{i % 12 + 1:02d}-{i % 28 + 1:02d}", net, round(net * 0.18, 2),
                       round(net * 1.18, 2), float(i % 7), float(5 + i % 4)))
        for k in range(1 + i % 3):                 # 1-3 lines per order
            lid += 1
            lines.append((lid, i, f"SKU{k}", 1 + k, round(net / (1 + i % 3), 2)))
    s.executemany("insert into orders values(?,?,?,?,?,?,?,?,?)", orders)
    s.executemany("insert into order_line values(?,?,?,?,?)", lines)
    s.commit()
    s.close()
    return path


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sem")
    db = make_amounts(tmp / "amounts.db")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid, db


def truth(db, sql):
    return duckdb.connect().execute(f"ATTACH '{db.as_posix()}' AS s (TYPE sqlite, READ_ONLY); USE s; {sql}").fetchall()


# --------------------------------------------------------------- propose
def test_proposals_are_counts_and_verified_money_never_ids(shop):
    layer, oid, _ = shop
    names = {d["name"] for d in sem.propose(layer, oid)}
    assert {"customer_count", "order_count", "order_line_count"} <= names
    assert "total_net_amount" in names and "total_gross_amount" in names
    assert not any(n in names for n in ("total_id", "total_customer_id", "total_order_id"))


def test_values_equal_independent_sql(shop):
    layer, oid, db = shop
    sem.propose(layer, oid)
    got = sem.value(layer, oid, "total_net_amount")["rows"][0][0]
    want = truth(db, "SELECT sum(net_amount) FROM orders")[0][0]
    assert abs(got - want) < 1e-6


def test_a_join_never_inflates_a_total(shop):
    """Order lines join to their order (many-to-one): fine. An order total
    must never join to its lines (one-to-many), which would repeat orders."""
    layer, oid, db = shop
    sem.propose(layer, oid)
    by_country = sem.value(layer, oid, "total_net_amount", by="customer_country")["rows"]
    want = dict(truth(db, "SELECT c.country, sum(o.net_amount) FROM orders o JOIN customer c "
                          "ON c.id = o.customer_id GROUP BY 1"))
    assert {k: round(v, 6) for k, v in by_country} == {k: round(v, 6) for k, v in want.items()}
    lines = sem.value(layer, oid, "total_line_amount", by="order_status")["rows"]
    want = dict(truth(db, "SELECT o.status, sum(l.line_amount) FROM order_line l JOIN orders o "
                          "ON o.id = l.order_id GROUP BY 1"))
    assert {k: round(v, 4) for k, v in lines} == {k: round(v, 4) for k, v in want.items()}


def test_dimensions_reach_two_steps_through_one_sides(shop):
    layer, oid, _ = shop
    sem.propose(layer, oid)
    dims = {d["name"] for d in sem.card(layer, oid, "total_line_amount")["dims"]}
    assert {"order_status", "customer_country"} <= dims           # line -> order -> customer


# --------------------------------------------------------------- decide
def test_competing_money_totals_become_one_decision(shop):
    layer, oid, _ = shop
    sem.propose(layer, oid)
    ds = sem.decisions(layer, oid)
    assert len(ds) == 1 and ds[0]["word"] == "revenue"
    names = [c["name"] for c in ds[0]["candidates"]]
    assert {"total_net_amount", "total_gross_amount", "total_tax_amount"} <= set(names)
    assert all(c["value"] is not None for c in ds[0]["candidates"])


def test_deciding_certifies_one_and_teaches_the_words(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_amounts(tmp_path / "a.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    out = sem.decide(layer, oid, "revenue", "total_gross_amount")
    assert out["status"] == "certified" and "revenue" in out["synonyms"]
    assert sem.decisions(layer, oid) == []                         # settled once
    others = {c["name"]: c["status"] for c in sem.overview(layer, oid)["metrics"]}
    assert others["total_net_amount"] == "proposed"
    hit = sem.match(layer, oid, "What is our revenue by customer country?")
    assert hit["metric"] == "total_gross_amount" and hit["by"] == "customer_country"
    with pytest.raises(sem.SemanticError):
        sem.decide(layer, oid, "revenue", "order_count")            # not money


def test_proposals_are_never_served_as_answers(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_amounts(tmp_path / "a.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    assert sem.match(layer, oid, "total net amount") is None        # not certified yet
    sem.certify(layer, oid, "total_net_amount", owner="Finance")
    assert sem.match(layer, oid, "total net amount")["metric"] == "total_net_amount"


# ------------------------------------------------------------ receipt, drift
def test_the_receipt_explains_the_number(shop):
    layer, oid, _ = shop
    sem.propose(layer, oid)
    r = sem.receipt(layer, oid, "total_line_amount")
    assert "sum" in r["formula"].lower() and r["sql"].lower().startswith("select")
    assert r["joins"] and "counted twice" in r["safe_joins"]


def test_drift_is_flagged_when_the_data_changes_shape(tmp_path):
    db = make_amounts(tmp_path / "a.db")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    sem.certify(layer, oid, "total_net_amount")
    assert sem.drift(layer, oid, "total_net_amount") == []
    s = sqlite3.connect(db)                                          # a bad migration
    s.execute("update orders set net_amount = net_amount * 1000 where id % 2 = 0")
    s.execute("update orders set net_amount = null where id % 3 = 0")
    s.commit()
    s.close()
    layer.add_source(str(db), source="shop", rebuild=True)
    reasons = sem.drift(layer, oid, "total_net_amount")
    assert any("largest value moved" in r for r in reasons), reasons
    assert any("empty" in r for r in reasons), reasons


# ------------------------------------------------------------ verified Qs
def test_verified_question_passes_then_fails_when_numbers_change(tmp_path):
    db = make_amounts(tmp_path / "a.db")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    sem.add_verified(layer, oid, "Net amount by country", "total_net_amount", by="customer_country")
    assert all(v["passed"] for v in sem.check_verified(layer, oid))
    s = sqlite3.connect(db)
    s.execute("update orders set net_amount = net_amount + 1")
    s.commit()
    s.close()
    layer.add_source(str(db), source="shop", rebuild=True)
    v = sem.check_verified(layer, oid)
    assert not v[0]["passed"] and "changed" in v[0]["why"]


def test_deleting_the_ontology_removes_its_metrics(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_amounts(tmp_path / "a.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    from ontology import registry as reg
    reg.delete_ontology(layer.graph, oid)
    assert layer.graph.sql("SELECT count(*) FROM metric_definitions WHERE source_id = ?",
                           [sem.source_of(oid)])[0][0] == 0


# ------------------------------------------- one definition everywhere
class Writer:
    mock = False
    model = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def complete(self, messages, max_tokens=600):
        self.calls += 1
        return self.reply


def _fresh(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    db = make_amounts(tmp_path / "a.db")
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    return layer, oid, db


def test_context_answers_from_the_certified_metric_without_ai_sql(tmp_path, monkeypatch):
    from context import engine as ctx
    layer, oid, db = _fresh(tmp_path)
    sem.decide(layer, oid, "revenue", "total_gross_amount")
    monkeypatch.setattr(ctx.ask, "ask", lambda *a, **k: pytest.fail("AI SQL must not run"))
    out = ctx.build(layer, oid, "What is the revenue by customer country?", client=Writer("Revenue by country [1]."))
    f = out["steps"]["facts"]
    assert f["metric"]["name"] == "total_gross_amount"
    assert any(x["text"].startswith("From the certified metric") for x in f["kept"])
    got = {r[0]: r[1] for r in f["table"]["rows"]}
    want = dict(truth(db, "SELECT c.country, sum(o.gross_amount) FROM orders o JOIN customer c "
                          "ON c.id = o.customer_id GROUP BY 1"))
    assert {k: round(v, 4) for k, v in got.items()} == {k: round(v, 4) for k, v in want.items()}


def test_ask_answers_from_the_certified_metric(tmp_path):
    from ontology import ask
    layer, oid, _ = _fresh(tmp_path)
    sem.decide(layer, oid, "revenue", "total_net_amount")
    w = Writer("{}")
    out = ask.ask(layer, oid, "total sales per customer segment", client=w)
    assert out["certified_metric"]["metric"] == "total_net_amount" and w.calls == 0
    assert out["columns"][0] == "customer_segment" and len(out["rows"]) == 2


def test_a_metric_in_words_is_checked_before_it_is_proposed(tmp_path):
    layer, oid, db = _fresh(tmp_path)
    good = Writer('{"title": "Paid net revenue", "agg": "sum", "field": "shop.orders.net_amount", '
                  '"filters": [{"field": "shop.orders.status", "value": "paid"}], "why": "x"}')
    out = sem.from_words(layer, oid, "Revenue is net amount of paid orders", good)
    want = truth(db, "SELECT sum(net_amount) FROM orders WHERE status = 'paid'")[0][0]
    assert out["status"] == "proposed" and abs(out["value"] - want) < 1e-6
    with pytest.raises(sem.SemanticError, match="no record has"):
        sem.from_words(layer, oid, "x", Writer('{"title": "X", "agg": "sum", "field": "shop.orders.net_amount", '
                                                '"filters": [{"field": "shop.orders.status", "value": "refunded"}]}'))
    with pytest.raises(sem.SemanticError, match="no field"):
        sem.from_words(layer, oid, "x", Writer('{"title": "X", "agg": "sum", "field": "shop.orders.nope"}'))
    with pytest.raises(sem.SemanticError, match="not a number"):
        sem.from_words(layer, oid, "x", Writer('{"title": "X", "agg": "sum", "field": "shop.orders.status"}'))


def test_certified_metrics_reach_excel_and_ossie(tmp_path):
    import io
    import zipfile

    import yaml

    from ontology import ossie
    layer, oid, _ = _fresh(tmp_path)
    sem.decide(layer, oid, "revenue", "total_gross_amount")
    feed = simple.for_excel(layer.graph, oid)
    assert [m["Metric"] for m in feed["metrics"]] == ["Total Gross amount"]
    assert "revenue" in feed["metrics"][0]["Also called"]
    sheets = zipfile.ZipFile(io.BytesIO(simple.to_xlsx(layer.graph, oid))).read("xl/workbook.xml").decode()
    assert "Metrics" in sheets
    doc = yaml.safe_load(ossie.to_ossie(layer.graph, oid))
    metrics = [m for ds in doc["datasets"] for m in ds.get("metrics") or []]
    assert any(m["name"] == "total_gross_amount" and "revenue" in m["ai_context"]["synonyms"] for m in metrics)



def test_only_meaningful_numbers_are_totalled(tmp_path):
    """Live on Olist: 'Total Review Score' and 'Total Product Height' were proposed."""
    db = tmp_path / "p.db"
    s = sqlite3.connect(db)
    s.executescript("""create table product(id integer primary key, title text, weight_g real,
                                            name_length integer, price real, units_in_stock integer);
                       create table review(id integer primary key, product_id integer references product(id),
                                           review_score integer);""")
    s.executemany("insert into product values(?,?,?,?,?,?)",
                  [(i, f"P{i}", 100.0 + i, 10 + i % 20, 9.5 + i, i % 50) for i in range(1, 201)])
    s.executemany("insert into review values(?,?,?)", [(i, i % 200 + 1, 1 + i % 5) for i in range(1, 501)])
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="p")
    oid = simple.create_and_build(layer, "P", ["p"])["ontology"]
    names = {d["name"] for d in sem.propose(layer, oid)}
    assert "total_price" in names
    assert not {"total_weight_g", "total_name_length", "total_review_score"} & names, names
    stale = "total_weight_g"
    from semantic import definitions as defs
    defs.upsert_metric(layer.graph, sem.source_of(oid), stale, "Total weight", "SELECT 1 AS x", "sum(x)",
                       status="draft")
    sem.propose(layer, oid)
    assert defs.get_definition(layer.graph, stale, sem.source_of(oid)) is None   # stale proposal removed


def test_company_meaning_marks_only_a_metric_a_person_annotated(tmp_path):
    """The 'company meaning' mark is set only when a person spelled out a note
    for the metric (on certify or a decision); a plain proposal has none."""
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_amounts(tmp_path / "amounts.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    cards = {c["name"]: c for c in sem.overview(layer, oid)["metrics"]}
    assert all(c.get("company_meaning") is None for c in cards.values())   # nothing claimed
    name = next(iter(cards))
    sem.certify(layer, oid, name, owner="Finance",
                note="Billed orders only; cancelled do not count")
    after = next(c for c in sem.overview(layer, oid)["metrics"] if c["name"] == name)
    assert after["company_meaning"] == "Billed orders only; cancelled do not count"
