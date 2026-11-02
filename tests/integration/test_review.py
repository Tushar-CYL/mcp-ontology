"""Human review gate: proposals, decisions, audit, publish refusal."""

from __future__ import annotations

import sqlite3

import pytest

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover
from review import store as review


@pytest.fixture
def graph(tmp_path):
    db = tmp_path / "shop.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id), total REAL);
        INSERT INTO customers VALUES (1,'Ada'),(2,'Grace');
        INSERT INTO orders VALUES (1,1,10.0),(2,2,20.0);
    """)
    con.commit()
    con.close()
    schema = connect(str(db))
    g = open_graph(tmp_path / "g.duckdb")
    build(g, schema, discover(schema), source="shop")
    return g


class TestProposals:
    def test_a_proposal_is_recorded_and_readable(self, graph):
        iid = review.propose(graph, "semantic", "revenue",
                             source="shop", confidence=0.8,
                             payload={"metric": "total_sum"})
        item = review.get(graph, iid)
        assert item is not None
        assert item["kind"] == "semantic"
        assert item["subject"] == "revenue"
        assert item["status"] == "proposed"
        assert item["payload"]["metric"] == "total_sum"

    def test_reproposing_the_same_thing_is_idempotent(self, graph):
        review.propose(graph, "semantic", "revenue", source="shop")
        review.propose(graph, "semantic", "revenue", source="shop",
                       payload={"changed": True})
        assert len(review.pending(graph, kind="semantic")) == 1

    def test_an_unknown_kind_is_refused(self, graph):
        with pytest.raises(ValueError, match="unknown review kind"):
            review.propose(graph, "nonsense", "x")

    def test_pending_can_be_filtered(self, graph):
        review.propose(graph, "semantic", "revenue", source="shop")
        review.propose(graph, "context", "policy", source="shop")
        assert len(review.pending(graph, kind="semantic")) == 1
        assert len(review.pending(graph, kind="context")) == 1
        assert len(review.pending(graph, source="shop")) == 2
        assert review.pending(graph, source="other") == []


class TestDecisions:
    def test_approval_changes_status_and_writes_audit(self, graph):
        iid = review.propose(graph, "semantic", "revenue", source="shop")
        review.approve(graph, iid, reviewer="arun", rationale="checked")
        assert review.get(graph, iid)["status"] == "approved"
        history = review.audit(graph, iid)
        assert history[-1]["decision"] == "approved"
        assert history[-1]["reviewer"] == "arun"

    def test_rejection_is_a_decision_too(self, graph):
        iid = review.propose(graph, "semantic", "margin", source="shop")
        review.reject(graph, iid, rationale="not a KPI")
        assert review.get(graph, iid)["status"] == "rejected"

    def test_an_unknown_item_cannot_be_decided(self, graph):
        with pytest.raises(KeyError):
            review.approve(graph, "does-not-exist")

    def test_an_unknown_decision_is_refused(self, graph):
        iid = review.propose(graph, "semantic", "revenue", source="shop")
        with pytest.raises(ValueError):
            review.decide(graph, iid, "maybe")


class TestPublishGate:
    def test_publishing_is_refused_while_a_proposal_is_pending(self, graph):
        review.propose(graph, "semantic", "revenue", source="shop")
        with pytest.raises(KeyError, match="still need a decision"):
            review.publish(graph, "semantic", source="shop")

    def test_after_approval_the_artifact_can_be_served(self, graph):
        iid = review.propose(graph, "semantic", "revenue", source="shop")
        review.approve(graph, iid)
        assert review.can_serve(graph, "semantic", "shop") is False
        review.publish(graph, "semantic", source="shop")
        assert review.can_serve(graph, "semantic", "shop") is True
        assert review.publish_state(graph, "semantic", "shop") == "approved"

    def test_a_rejected_proposal_does_not_block_publishing(self, graph):
        iid = review.propose(graph, "context", "policy", source="shop")
        review.reject(graph, iid)
        review.publish(graph, "context", source="shop")
        assert review.can_serve(graph, "context", "shop") is True

    def test_the_gate_is_per_artifact_and_source(self, graph):
        review.propose(graph, "semantic", "revenue", source="shop")
        review.publish(graph, "context", source="shop")   # different artifact
        assert review.can_serve(graph, "context", "shop") is True
        assert review.can_serve(graph, "semantic", "shop") is False


class TestSeeding:
    def test_inferred_relations_become_review_items(self, tmp_path):
        d = tmp_path / "csv"
        d.mkdir()
        (d / "customers.csv").write_text("customer_id,name\nc1,Ada\n",
                                         encoding="utf-8")
        (d / "orders.csv").write_text("order_id,customer_id\no1,c1\n",
                                      encoding="utf-8")
        schema = connect(str(d))
        g = open_graph(tmp_path / "g.duckdb")
        build(g, schema, discover(schema), source="csv")
        ids = review.seed_from_relations(g, "csv")
        assert ids, "the inferred customer link must be proposed"
        items = review.pending(g, kind="relation")
        assert all(i["status"] == "proposed" for i in items)
        assert all(i["source"] == "csv" for i in items)


class TestCli:
    @pytest.fixture
    def graph_file(self, tmp_path):
        db = tmp_path / "shop.db"
        con = sqlite3.connect(db)
        con.executescript("""
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE orders (id INTEGER PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id));
            INSERT INTO customers VALUES (1,'Ada');
            INSERT INTO orders VALUES (1,1);
        """)
        con.commit()
        con.close()
        schema = connect(str(db))
        path = tmp_path / "cli.duckdb"
        g = open_graph(path)
        build(g, schema, discover(schema), source="shop")
        iid = review.propose(g, "semantic", "revenue", source="shop")
        g.close()
        return path, iid

    def test_list_shows_the_proposal(self, graph_file, capsys):
        path, iid = graph_file
        from review.cli import main as cli
        assert cli(["--graph", str(path), "list"]) == 0
        out = capsys.readouterr().out
        assert iid in out and "revenue" in out

    def test_approve_then_publish_from_the_cli(self, graph_file, capsys):
        path, iid = graph_file
        from review.cli import main as cli
        assert cli(["--graph", str(path), "approve", iid, "--reviewer",
                    "arun"]) == 0
        assert "approved" in capsys.readouterr().out
        assert cli(["--graph", str(path), "publish", "semantic",
                    "--source", "shop"]) == 0
        assert '"state": "approved"' in capsys.readouterr().out

    def test_publish_refuses_while_pending(self, graph_file, capsys):
        path, _ = graph_file
        from review.cli import main as cli
        assert cli(["--graph", str(path), "publish", "semantic",
                    "--source", "shop"]) == 1
        assert "cannot publish" in capsys.readouterr().out
