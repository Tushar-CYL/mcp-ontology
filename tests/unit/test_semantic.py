"""Layer 3: the numbers, defined once.

A metric catalogue exists so that `revenue` means one thing everywhere. The
catalogue is built from the ontology, so no dataset needs its own metric
file - but what a dataset CANNOT support must be absent rather than faked.
"""

from __future__ import annotations

import pytest

from ontology.discover import discover
from ontology.schema import Column, ForeignKey, Schema, Table
from semantic.discover import discover_metrics
from semantic.compile import compile_metric


def tbl(name, cols, pk=None, fks=(), rows=100):
    return Table(name=name, columns=[Column(n, t) for n, t in cols],
                 primary_key=list(pk or []), foreign_keys=list(fks),
                 row_count=rows)


SHOP = Schema(tables=[
    tbl("customers", [("id", "INTEGER"), ("country", "VARCHAR")], pk=["id"]),
    tbl("orders", [("id", "INTEGER"), ("customer_id", "INTEGER"),
                   ("placed_at", "TIMESTAMP"), ("total", "DOUBLE"),
                   ("status", "VARCHAR")],
        pk=["id"], fks=[ForeignKey("customer_id", "customers", "id")]),
])
ONTO = discover(SHOP)


class TestWhatIsProposed:
    def test_a_numeric_column_yields_aggregates(self):
        names = {m.name for m in discover_metrics(ONTO)}
        assert "total_sum" in names
        assert "total_avg" in names

    def test_every_class_can_be_counted(self):
        names = {m.name for m in discover_metrics(ONTO)}
        assert "order_count" in names
        assert "customer_count" in names

    def test_a_key_is_never_proposed_as_a_measure(self):
        """Summing customer ids is meaningless and looks authoritative."""
        names = {m.name for m in discover_metrics(ONTO)}
        assert not any(n.startswith("id_") for n in names)

    def test_a_metric_knows_its_table_and_column(self):
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        assert m.table == "orders"
        assert m.column == "total"
        assert m.agg == "sum"

    def test_a_metric_carries_how_it_can_be_grouped(self):
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        assert "status" in m.dimensions

    def test_a_time_column_is_offered_as_a_grouping(self):
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        assert m.time_column == "placed_at"

    def test_a_class_with_no_numbers_still_gets_a_count(self):
        onto = discover(Schema(tables=[
            tbl("tags", [("id", "INTEGER"), ("label", "VARCHAR")], pk=["id"])]))
        names = {m.name for m in discover_metrics(onto)}
        assert names == {"tag_count"}

    def test_metrics_are_the_same_every_run(self):
        a = [m.name for m in discover_metrics(ONTO)]
        b = [m.name for m in discover_metrics(ONTO)]
        assert a == b


class TestCompile:
    def test_a_plain_metric_compiles(self):
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        sql, params = compile_metric(m)
        assert "sum" in sql.lower()
        assert "total" in sql

    def test_grouping_adds_the_column_to_select_and_group_by(self):
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        sql, _ = compile_metric(m, group_by="status")
        assert sql.lower().count("group by") == 1
        assert "status" in sql

    def test_an_unknown_grouping_is_refused_not_guessed(self):
        """Compiling against a column that happens to share a name is how a
        metric starts returning a number nobody can explain."""
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        with pytest.raises(KeyError, match="nonsense"):
            compile_metric(m, group_by="nonsense")

    def test_filter_values_are_bound_not_pasted(self):
        """A value interpolated into SQL is an injection, even from a
        catalogue we generated."""
        m = next(m for m in discover_metrics(ONTO) if m.name == "total_sum")
        sql, params = compile_metric(m, where={"status": "x'; DROP TABLE t;--"})
        assert "DROP TABLE" not in sql
        assert params == ["x'; DROP TABLE t;--"]

    def test_identifiers_with_quotes_are_escaped(self):
        onto = discover(Schema(tables=[
            tbl("weird", [("id", "INTEGER"), ('it"s', "DOUBLE")], pk=["id"])]))
        m = next(m for m in discover_metrics(onto) if m.agg == "sum")
        sql, _ = compile_metric(m)
        assert '"it""s"' in sql
