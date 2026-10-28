"""Any source in, one Schema out.

These build real files and read them back, because the whole point of
connect.py is the bit a unit test cannot fake: whether a SQLite file really
reports its foreign keys, and whether a CSV folder can be read at all.

Fixtures are written to a temp directory, so the suite runs offline with
nothing installed beyond the project's own requirements.
"""

from __future__ import annotations

import sqlite3

import pytest

from ontology.connect import connect
from ontology.discover import discover
from ontology.schema import is_numeric, is_temporal


@pytest.fixture
def shop_db(tmp_path):
    """A small, clean relational source with real declared keys."""
    p = tmp_path / "shop.db"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE customers (
            id      INTEGER PRIMARY KEY,
            name    TEXT NOT NULL,
            country TEXT
        );
        CREATE TABLE orders (
            id          INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            placed_at   TIMESTAMP,
            total       REAL
        );
        INSERT INTO customers VALUES (1,'Ada','UK'), (2,'Grace','US');
        INSERT INTO orders VALUES
            (1, 1, '2024-01-05 10:00:00', 99.50),
            (2, 1, '2024-01-07 11:00:00', 12.00),
            (3, 2, '2024-02-01 09:30:00', 45.25);
    """)
    con.commit()
    con.close()
    return p


@pytest.fixture
def shop_csv(tmp_path):
    """The same shape with nothing declared: no keys, no types."""
    d = tmp_path / "csvshop"
    d.mkdir()
    (d / "customers.csv").write_text(
        "id,name,country\n1,Ada,UK\n2,Grace,US\n", encoding="utf-8")
    (d / "orders.csv").write_text(
        "id,customer_id,placed_at,total\n"
        "1,1,2024-01-05,99.5\n2,1,2024-01-07,12\n3,2,2024-02-01,45.25\n",
        encoding="utf-8")
    return d


class TestSqlite:
    def test_reads_every_table(self, shop_db):
        s = connect(str(shop_db))
        assert {t.name for t in s.tables} == {"customers", "orders"}

    def test_reads_columns_and_types(self, shop_db):
        """Assert the type FAMILY, never the vendor's spelling.

        SQLite calls it REAL, DuckDB reports DOUBLE, Postgres says float8 and
        Snowflake says NUMBER. All four are numbers. A test that pinned the
        spelling would have to be edited for every new source type, which is
        the exact thing this layer exists to avoid.
        """
        t = connect(str(shop_db)).table("orders")
        assert set(t.column_names) == {"id", "customer_id", "placed_at", "total"}
        assert is_numeric(t.column("total"))
        assert is_numeric(t.column("id"))
        assert is_temporal(t.column("placed_at"))

    def test_reads_the_primary_key(self, shop_db):
        assert connect(str(shop_db)).table("customers").primary_key == ["id"]

    def test_reads_declared_foreign_keys(self, shop_db):
        fks = connect(str(shop_db)).table("orders").foreign_keys
        assert len(fks) == 1
        assert fks[0].column == "customer_id"
        assert fks[0].ref_table == "customers"

    def test_counts_rows(self, shop_db):
        assert connect(str(shop_db)).table("orders").row_count == 3

    def test_discovery_runs_on_what_was_read(self, shop_db):
        onto = discover(connect(str(shop_db)))
        assert set(onto.classes) == {"Customer", "Order"}
        r = next(r for r in onto.relations.values() if r.domain == "Order")
        assert r.range == "Customer"
        assert r.provenance == "measured"   # SQLite declared it


class TestCsv:
    def test_each_file_becomes_a_table(self, shop_csv):
        s = connect(str(shop_csv))
        assert {t.name for t in s.tables} == {"customers", "orders"}

    def test_types_are_inferred_from_the_values(self, shop_csv):
        t = connect(str(shop_csv)).table("orders")
        assert "INT" in t.column("id").type.upper()
        assert "DOUBLE" in t.column("total").type.upper() or \
               "DECIMAL" in t.column("total").type.upper()

    def test_relationship_is_found_despite_nothing_being_declared(self, shop_csv):
        """A CSV declares no keys at all. The link has to be worked out, and
        it must be reported as a guess."""
        onto = discover(connect(str(shop_csv)))
        r = next(r for r in onto.relations.values() if r.domain == "Order")
        assert r.range == "Customer"
        assert r.provenance == "derived"
        assert r.confidence < 1.0

    def test_single_csv_file_works(self, shop_csv):
        s = connect(str(shop_csv / "customers.csv"))
        assert len(s.tables) == 1
        assert s.tables[0].name == "customers"


class TestSameAnswerFromBothSources:
    """The product claim, in one test: two different source TYPES holding the
    same data must produce the same ontology, with no code in between."""

    def test_classes_match(self, shop_db, shop_csv):
        a = discover(connect(str(shop_db)))
        b = discover(connect(str(shop_csv)))
        assert set(a.classes) == set(b.classes)

    def test_relations_match_in_shape(self, shop_db, shop_csv):
        a = discover(connect(str(shop_db)))
        b = discover(connect(str(shop_csv)))
        shape = lambda o: {(r.domain, r.range) for r in o.relations.values()}
        assert shape(a) == shape(b)

    def test_but_confidence_differs_and_says_so(self, shop_db, shop_csv):
        """SQLite declared the key; the CSV did not. Same answer, honestly
        different confidence - that difference must survive."""
        a = discover(connect(str(shop_db)))
        b = discover(connect(str(shop_csv)))
        assert next(iter(a.relations.values())).confidence == 1.0
        assert next(iter(b.relations.values())).confidence < 1.0


class TestFailures:
    def test_unknown_path_is_a_clear_error(self, tmp_path):
        with pytest.raises(Exception) as e:
            connect(str(tmp_path / "nope.db"))
        assert "not found" in str(e.value).lower()

    def test_empty_directory_says_so(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        with pytest.raises(Exception) as e:
            connect(str(d))
        assert "no" in str(e.value).lower()
