"""A key column's distinct count must be exact: it is shown as proof."""

import duckdb

from ontology.profile import profile_table
from ontology.schema import Column, Schema, Table


class Graph:
    def __init__(self):
        self.con = duckdb.connect()

    def sql(self, q):
        return self.con.execute(q).fetchall()


def test_unique_ids_are_counted_exactly(monkeypatch):
    g = Graph()
    g.con.execute("CREATE TABLE t AS SELECT range AS id, range % 7 AS bucket FROM range(1000)")
    monkeypatch.setattr("ontology.profile.table_ref", lambda *a, **k: "t")
    table = Table(name="t", columns=[Column("id", "BIGINT"), Column("bucket", "BIGINT")],
                  primary_key=["id"], foreign_keys=[], row_count=1000)
    out = profile_table(g, Schema(tables=[table], name="s"), table, "s")
    by = {c["name"]: c for c in out["columns"]}
    assert by["id"]["distinct"] == 1000          # approx says ~977-1020
    assert by["bucket"]["distinct"] == 7
