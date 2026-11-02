"""Multi-source: several sources in one graph, one row set per source.

The manager's scenario: the same thing exists in several systems. The graph
must hold both without pretending they are one thing (that is a decision for
the cross-source resolver, later), and a query must never silently read the
wrong source.

These tests use the real public API only: connect -> discover -> build, then
read back through the Graph surface.
"""

from __future__ import annotations

import sqlite3

import pytest

from knowledge_graph.build import build, build_many, is_current, row_for, table_ref
from knowledge_graph.store import open_graph
from ontology.connect import connect, connect_many
from ontology.discover import discover
from semantic.compile import compile_metric
from semantic.discover import discover_metrics


@pytest.fixture
def two_sources(tmp_path):
    """Two CSVs with the SAME class names but different data and meaning."""
    erp = tmp_path / "erp"
    erp.mkdir()
    (erp / "customers.csv").write_text(
        "customer_id,name,city\nc1,Ada,London\nc2,Grace,York\n",
        encoding="utf-8")
    (erp / "orders.csv").write_text(
        "order_id,customer_id,total\no1,c1,10.0\no2,c2,20.0\n",
        encoding="utf-8")

    crm = tmp_path / "crm"
    crm.mkdir()
    (crm / "customers.csv").write_text(
        "customer_id,name,segment\nc1,Ada,Gold\nc9,Alan,Silver\n",
        encoding="utf-8")
    (crm / "orders.csv").write_text(
        "order_id,customer_id,total\nz1,c1,99.0\nz2,c9,1.0\nz3,c9,2.0\n",
        encoding="utf-8")
    return erp, crm


def _built(tmp_path, pairs):
    graph = open_graph(tmp_path / "multi.duckdb")
    for source, folder in pairs:
        schema = connect(str(folder))
        onto = discover(schema)
        build(graph, schema, onto, source=source)
    return graph


class TestTwoSources:
    def test_both_sources_are_registered(self, two_sources, tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        assert {s["source_id"] for s in g.sources()} == {"erp", "crm"}
        assert len(g.sources()) == 2

    def test_same_class_name_resolves_per_source(self, two_sources, tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        assert g.count_class("Customer", "erp") == 2
        assert g.count_class("Customer", "crm") == 2
        assert g.count_class("Order", "erp") == 2
        assert g.count_class("Order", "crm") == 3

    def test_the_same_class_in_two_sources_has_different_codes(self,
                                                               two_sources,
                                                               tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        assert g.class_code("Customer", "erp") != g.class_code("Customer", "crm")

    def test_the_same_key_in_two_sources_is_two_nodes(self, two_sources,
                                                      tmp_path):
        """`c1` exists in both. They are different rows from different systems
        until resolution says otherwise, so they must be two nodes."""
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        a = g.node_id("Customer", "c1", "erp")
        b = g.node_id("Customer", "c1", "crm")
        assert a is not None and b is not None and a != b

    def test_an_ambiguous_class_name_refuses_to_guess(self, two_sources,
                                                      tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        with pytest.raises(KeyError, match="pass source"):
            g.count_class("Customer")

    def test_rows_are_read_back_from_the_right_source(self, two_sources,
                                                      tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        assert g.props_of("Customer", "c1", "erp")["city"] == "London"
        assert g.props_of("Customer", "c1", "crm")["segment"] == "Gold"
        assert row_for(g, connect(str(erp)), discover(connect(str(erp))),
                       "Customer", "c1", source="erp")["city"] == "London"

    def test_edges_stay_inside_their_source(self, two_sources, tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        assert g.count_relation("customer", "erp") == 2
        assert g.count_relation("customer", "crm") == 3
        # A customer from crm must not appear under erp's neighbour lookup.
        assert set(g.neighbours("Order", "o1", "customer", "erp")) == {"c1"}
        assert "z1" not in {o for o in g.keys_of("Order", source="erp")}

    def test_rebuilding_one_source_leaves_the_other_alone(self, two_sources,
                                                          tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        schema = connect(str(crm))
        onto = discover(schema)
        assert is_current(g, schema, onto, source="crm")
        build(g, schema, onto, source="crm")
        assert g.count_class("Customer", "erp") == 2
        assert g.count_class("Customer", "crm") == 2

    def test_metrics_work_per_source(self, two_sources, tmp_path):
        erp, crm = two_sources
        g = _built(tmp_path, [("erp", erp), ("crm", crm)])
        for source, folder, expected in (("erp", erp, 30.0), ("crm", crm, 102.0)):
            schema = connect(str(folder))
            onto = discover(schema)
            metric = next(m for m in discover_metrics(onto)
                          if m.column == "total" and m.agg == "sum")
            sql, params = compile_metric(
                metric, table_sql=table_ref(g, schema, metric.table,
                                            source=source))
            assert g.sql(sql, params)[0][0] == expected

    def test_build_many_reports_one_result_per_source(self, two_sources,
                                                      tmp_path):
        erp, crm = two_sources
        g = open_graph(tmp_path / "many.duckdb")
        bundles = []
        for source, folder in (("erp", erp), ("crm", crm)):
            schema = connect(str(folder))
            bundles.append((schema, discover(schema), source))
        results = build_many(g, bundles)
        assert set(results) == {"erp", "crm"}
        assert results["erp"]["nodes"] > 0 and results["crm"]["nodes"] > 0


class TestConnectMany:
    def test_two_sources_become_two_schemas(self, two_sources):
        erp, crm = two_sources
        schemas = connect_many([str(erp), str(crm)])
        assert len(schemas) == 2
        assert {s.name for s in schemas} == {"erp", "crm"}

    def test_names_can_be_overridden(self, two_sources):
        erp, crm = two_sources
        schemas = connect_many([str(erp), str(crm)], names=["ERP", "CRM"])
        assert {s.name for s in schemas} == {"ERP", "CRM"}


class TestWarmReopen:
    """The second process must not need a rebuild and must not crash.

    This is the defect found in the baseline: attach happened only during
    build, so an unchanged database source reopened without its tables.
    """

    @pytest.fixture
    def shop(self, tmp_path):
        p = tmp_path / "shop.db"
        con = sqlite3.connect(p)
        con.executescript("""
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE orders (id INTEGER PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id), total REAL);
            INSERT INTO customers VALUES (1,'Ada'),(2,'Grace');
            INSERT INTO orders VALUES (1,1,10.0),(2,2,20.0);
        """)
        con.commit()
        con.close()
        return p

    def test_database_source_reopens_warm_and_answers(self, shop, tmp_path):
        path = tmp_path / "shop.duckdb"
        schema = connect(str(shop))
        onto = discover(schema)

        g = open_graph(path)
        build(g, schema, onto)
        g.close()

        # A new process: no build, no attach, just open and query.
        g2 = open_graph(path)
        try:
            assert is_current(g2, schema, onto)
            metric = next(m for m in discover_metrics(onto)
                          if m.column == "total" and m.agg == "sum")
            sql, params = compile_metric(
                metric, table_sql=table_ref(g2, schema, metric.table))
            assert g2.sql(sql, params)[0][0] == 30.0
            assert row_for(g2, schema, onto, "Customer", "1")["name"] == "Ada"
        finally:
            g2.close()

    def test_raw_rows_survive_the_reopen(self, shop, tmp_path):
        from knowledge_graph.build import source_rows
        path = tmp_path / "rows.duckdb"
        schema = connect(str(shop))
        onto = discover(schema)
        g = open_graph(path)
        build(g, schema, onto)
        g.close()
        g2 = open_graph(path)
        try:
            cols, rows = source_rows(g2, schema, "customers", limit=10)
            assert cols == ["id", "name"]
            assert (1, "Ada") in [tuple(r) for r in rows]
        finally:
            g2.close()
