"""Agent Context Builder: cited facts under a hard budget, with dropped facts."""

from __future__ import annotations

import sqlite3

import pytest

from context.assemble import build_context
from knowledge_graph.build import build
from knowledge_graph.resolve import resolve
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover
from review import store as review


def _shop_db(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id), total REAL,
            placed_at TIMESTAMP);
        INSERT INTO customers VALUES (1,'Ada','London'),(2,'Grace','York');
        INSERT INTO orders VALUES
            (1,1,10.0,'2024-01-05 10:00:00'),(2,2,20.0,'2024-01-06 10:00:00');
    """)
    con.commit()
    con.close()


@pytest.fixture
def shop(tmp_path):
    db = tmp_path / "shop.db"
    _shop_db(db)
    schema = connect(str(db))
    onto = discover(schema)
    g = open_graph(tmp_path / "shop.duckdb")
    build(g, schema, onto, source="shop")
    return g, [(("shop", schema, onto))]


@pytest.fixture
def csv_source(tmp_path):
    d = tmp_path / "csv"
    d.mkdir()
    (d / "customers.csv").write_text("customer_id,name\nc1,Ada\n",
                                     encoding="utf-8")
    (d / "orders.csv").write_text("order_id,customer_id,total\no1,c1,10.0\n",
                                  encoding="utf-8")
    schema = connect(str(d))
    onto = discover(schema)
    g = open_graph(tmp_path / "csv.duckdb")
    build(g, schema, onto, source="csv")
    return g, [(("csv", schema, onto))]


class TestExplicitEntity:
    def test_the_envelope_has_every_required_field(self, shop):
        g, bundles = shop
        out = build_context(g, bundles, entity=("shop", "Customer", "1"))
        assert set(out) >= {"focus", "answer", "facts", "dropped", "sources",
                            "review_pending", "budget_chars", "chars",
                            "as_of", "latency_ms", "rendered"}
        assert out["focus"] == {"source": "shop", "class": "Customer",
                                "key": "1"}

    def test_every_fact_carries_provenance_and_a_citation(self, shop):
        g, bundles = shop
        out = build_context(g, bundles, entity=("shop", "Customer", "1"))
        assert out["facts"]
        for fact in out["facts"]:
            assert fact["provenance"] in {"measured", "derived", "external"}
            assert fact["citation"], "a fact without a citation is not usable"

    def test_the_budget_is_respected_and_dropped_is_reported(self, shop):
        g, bundles = shop
        out = build_context(g, bundles, entity=("shop", "Customer", "1"),
                            budget_chars=10)
        assert out["chars"] <= 10
        assert out["dropped"], "a tiny budget must drop facts, not truncate"
        assert all(f["text"] for f in out["dropped"])

    def test_a_larger_budget_keeps_more(self, shop):
        g, bundles = shop
        small = build_context(g, bundles, entity=("shop", "Customer", "1"),
                              budget_chars=10)
        large = build_context(g, bundles, entity=("shop", "Customer", "1"),
                              budget_chars=1000)
        assert len(large["facts"]) > len(small["facts"])

    def test_an_unmeasured_link_is_labelled_derived(self, csv_source):
        g, bundles = csv_source
        out = build_context(g, bundles, entity=("csv", "Order", "o1"))
        link_facts = [f for f in out["facts"] if "links to" in f["text"]]
        assert link_facts, "the inferred customer link must be evidence"
        assert link_facts[0]["provenance"] == "derived"

    def test_a_measured_link_is_labelled_measured(self, shop):
        g, bundles = shop
        out = build_context(g, bundles, entity=("shop", "Order", "1"))
        link_facts = [f for f in out["facts"] if "links to" in f["text"]]
        assert link_facts and link_facts[0]["provenance"] == "measured"


class TestTaskParsing:
    def test_a_class_and_key_in_the_question_are_found(self, shop):
        g, bundles = shop
        out = build_context(g, bundles, task="Where is Customer 1 based?")
        assert out["focus"]["class"] == "Customer"
        assert out["focus"]["key"] == "1"

    def test_a_bare_key_that_is_unique_is_found(self, shop):
        g, bundles = shop
        out = build_context(g, bundles, task="Tell me about 2")
        assert out["focus"]["class"] in {"Customer", "Order"}
        assert out["focus"]["key"] == "2"

    def test_an_unknown_question_is_a_clear_error(self, shop):
        g, bundles = shop
        with pytest.raises(ValueError, match="could not find"):
            build_context(g, bundles, task="something unrelated entirely")

    def test_an_unknown_entity_is_a_clear_error(self, shop):
        g, bundles = shop
        with pytest.raises(ValueError, match="no Customer"):
            build_context(g, bundles, entity=("shop", "Customer", "nope"))


class TestCrossSourceEvidence:
    @pytest.fixture
    def two(self, tmp_path):
        erp = tmp_path / "erp"
        erp.mkdir()
        (erp / "products.csv").write_text(
            "product_id,name,price\np1,A-pack,10.0\n", encoding="utf-8")
        pim = tmp_path / "pim"
        pim.mkdir()
        (pim / "products.csv").write_text(
            "product_id,title\np1,A-pack\n", encoding="utf-8")
        g = open_graph(tmp_path / "two.duckdb")
        bundles = []
        for source, folder in (("erp", erp), ("pim", pim)):
            schema = connect(str(folder))
            onto = discover(schema)
            build(g, schema, onto, source=source)
            bundles.append((source, schema, onto))
        resolve(g)
        return g, bundles

    def test_a_cross_source_match_is_mentioned_with_confidence(self, two):
        g, bundles = two
        out = build_context(g, bundles, entity=("erp", "Product", "p1"))
        assert "pim" in out["sources"]
        match = [f for f in out["facts"] if "appears in pim" in f["text"]]
        assert match, "the same product in PIM must be evidence"
        assert "confidence" in match[0]["text"]


class TestReviewStateIsVisible:
    def test_pending_reviews_are_reported_in_the_pack(self, shop):
        g, bundles = shop
        review.propose(g, "semantic", "revenue", source="shop")
        out = build_context(g, bundles, entity=("shop", "Customer", "1"))
        assert out["review_pending"] >= 1
        assert any("await review" in f["text"] for f in out["facts"])
