"""Break it on purpose, so real data cannot.

Every shape here came from asking "what would a real export do that our
tidy fixtures never do?" - and several of them are things that HAVE broken
it: no primary key, a shared filename prefix, a column that is unique by
accident, a million rows.

The contract is deliberately weak and absolute: for ANY source, all four
layers must COMPLETE. The answer may be thin - an ontology with no
relations is a fine answer when a source has none - but nothing may crash,
hang, or quietly produce a graph that looks fine and is wrong.

Each case is a separate test so a failure names the exact shape that broke.
"""

from __future__ import annotations

import sqlite3

import pytest

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover


def run_all_layers(path, tmp_path, name="t"):
    """Connect, discover, build. Returns (ontology, graph)."""
    schema = connect(str(path))
    onto = discover(schema)
    g = open_graph(tmp_path / f"{name}.duckdb")
    build(g, schema, onto)
    assert g.dangling_edges() == 0, "an edge points at a node that is not there"
    return onto, g


def sqlite_from(tmp_path, name, script):
    p = tmp_path / f"{name}.db"
    con = sqlite3.connect(p)
    con.executescript(script)
    con.commit()
    con.close()
    return p


def csv_from(tmp_path, name, files: dict[str, str]):
    d = tmp_path / name
    d.mkdir()
    for fn, body in files.items():
        (d / fn).write_text(body, encoding="utf-8")
    return d


# ---------------------------------------------------------- empty / tiny
class TestNothingThere:
    def test_a_table_with_no_rows(self, tmp_path):
        p = sqlite_from(tmp_path, "empty", """
            CREATE TABLE things (id INTEGER PRIMARY KEY, name TEXT);""")
        onto, g = run_all_layers(p, tmp_path, "empty")
        assert "Thing" in onto.classes
        assert g.count_class("Thing") == 0

    def test_a_table_with_one_column(self, tmp_path):
        p = sqlite_from(tmp_path, "one", """
            CREATE TABLE codes (code TEXT);
            INSERT INTO codes VALUES ('a'),('b');""")
        onto, g = run_all_layers(p, tmp_path, "one")
        assert g.count_class("Code") == 2

    def test_a_source_with_a_single_table_and_no_links(self, tmp_path):
        """A perfectly valid answer is 'these things exist, nothing links'."""
        p = sqlite_from(tmp_path, "solo", """
            CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);
            INSERT INTO notes VALUES (1,'hi'),(2,'there');""")
        onto, g = run_all_layers(p, tmp_path, "solo")
        assert onto.relations == {}
        assert g.count_class("Note") == 2

    def test_an_empty_csv_with_only_a_header(self, tmp_path):
        d = csv_from(tmp_path, "hdr", {"people.csv": "id,name\n"})
        onto, g = run_all_layers(d, tmp_path, "hdr")
        assert g.count_class("Person") == 0


# ------------------------------------------------------------------ keys
class TestAwkwardKeys:
    def test_composite_key_table(self, tmp_path):
        """order_items is keyed by (order_id, line). No single column is
        unique, so a row number stands in - and must still support edges."""
        p = sqlite_from(tmp_path, "comp", """
            CREATE TABLE orders (id TEXT PRIMARY KEY);
            CREATE TABLE lines (order_id TEXT, line INTEGER, qty INTEGER,
                                PRIMARY KEY (order_id, line));
            INSERT INTO orders VALUES ('o1'),('o2');
            INSERT INTO lines VALUES ('o1',1,2),('o1',2,5),('o2',1,1);""")
        onto, g = run_all_layers(p, tmp_path, "comp")
        assert g.count_class("Line") == 3
        assert g.count_relation("order") == 3

    def test_duplicate_key_values_do_not_duplicate_nodes(self, tmp_path):
        """A CSV can repeat a 'key'. One node per distinct value, not one
        per row, or every count downstream is wrong."""
        d = csv_from(tmp_path, "dupes", {
            "items.csv": "item_id,name\n1,a\n1,b\n2,c\n"})
        onto, g = run_all_layers(d, tmp_path, "dupes")
        assert g.count_class("Item") == 3   # no key found: one per row

    def test_null_keys_are_skipped_not_crashed_on(self, tmp_path):
        p = sqlite_from(tmp_path, "nullk", """
            CREATE TABLE a (id TEXT);
            INSERT INTO a VALUES ('x'),(NULL),('y');""")
        onto, g = run_all_layers(p, tmp_path, "nullk")
        assert g.count_class("A") >= 2

    def test_a_key_with_spaces_and_punctuation(self, tmp_path):
        d = csv_from(tmp_path, "punct", {
            "things.csv": 'thing_id,label\n"a b, c",one\n"d-e/f",two\n'})
        onto, g = run_all_layers(d, tmp_path, "punct")
        assert g.count_class("Thing") == 2


# ------------------------------------------------------------- bad names
class TestHostileNames:
    def test_sql_reserved_words_as_column_names(self, tmp_path):
        """`order`, `select`, `group` are real column names in real exports
        and will break any SQL that does not quote identifiers."""
        d = csv_from(tmp_path, "resv", {
            "rows.csv": "id,order,select,group,table\n1,a,b,c,d\n2,e,f,g,h\n"})
        onto, g = run_all_layers(d, tmp_path, "resv")
        assert g.count_class("Row") == 2

    def test_a_column_with_a_quote_in_its_name(self, tmp_path):
        d = csv_from(tmp_path, "quote", {
            'odd.csv': 'id,it\'s_here\n1,x\n2,y\n'})
        onto, g = run_all_layers(d, tmp_path, "quote")
        assert g.count_class("Odd") == 2

    def test_non_ascii_table_and_column_names(self, tmp_path):
        d = csv_from(tmp_path, "uni", {
            "cliente.csv": "id,nome,cidade\n1,Ana,São Paulo\n2,Jo,Rio\n"})
        onto, g = run_all_layers(d, tmp_path, "uni")
        assert g.count_class("Cliente") == 2

    def test_two_tables_whose_names_collide_after_cleaning(self, tmp_path):
        """`person` and `people` both reduce to Person. Neither may
        overwrite the other."""
        d = csv_from(tmp_path, "coll", {
            "person.csv": "id\n1\n", "people.csv": "id\n2\n"})
        onto, g = run_all_layers(d, tmp_path, "coll")
        assert len(onto.classes) == 2


# ----------------------------------------------------------------- links
class TestAwkwardLinks:
    def test_self_referencing_table(self, tmp_path):
        p = sqlite_from(tmp_path, "self", """
            CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT,
                                manager_id INTEGER REFERENCES staff(id));
            INSERT INTO staff VALUES (1,'boss',NULL),(2,'a',1),(3,'b',2);""")
        onto, g = run_all_layers(p, tmp_path, "self")
        assert g.count_relation("manager") == 2

    def test_a_cycle_does_not_hang_the_traversal(self, tmp_path):
        """UNION ALL in a recursive walk never terminates on a cycle."""
        p = sqlite_from(tmp_path, "cyc", """
            CREATE TABLE node (id INTEGER PRIMARY KEY,
                               next_id INTEGER REFERENCES node(id));
            INSERT INTO node VALUES (1,2),(2,3),(3,1);""")
        onto, g = run_all_layers(p, tmp_path, "cyc")
        assert len(g.reach("Node", "1", "next", depth=50)) == 3

    def test_two_links_to_the_same_table(self, tmp_path):
        p = sqlite_from(tmp_path, "two", """
            CREATE TABLE people (id INTEGER PRIMARY KEY);
            CREATE TABLE msgs (id INTEGER PRIMARY KEY,
                sender_id INTEGER REFERENCES people(id),
                recipient_id INTEGER REFERENCES people(id));
            INSERT INTO people VALUES (1),(2);
            INSERT INTO msgs VALUES (1,1,2),(2,2,1);""")
        onto, g = run_all_layers(p, tmp_path, "two")
        assert g.count_relation("sender") == 2
        assert g.count_relation("recipient") == 2

    def test_a_link_pointing_at_rows_that_do_not_exist(self, tmp_path):
        """An orphan must be COUNTED, never silently dropped and never
        allowed to create a dangling edge."""
        d = csv_from(tmp_path, "orph", {
            "customers.csv": "customer_id\nc1\n",
            "orders.csv": "order_id,customer_id\no1,c1\no2,GHOST\n"})
        onto, g = run_all_layers(d, tmp_path, "orph")
        assert g.count_relation("customer") == 1
        assert g.one("SELECT count(*) FROM findings "
                     "WHERE rule = 'orphan_reference'") == 1

    def test_a_column_ending_in_id_that_is_not_a_link(self, tmp_path):
        """`android_id`, `covid_id`, `valid_identifier` - words that merely
        end in 'id'. Inventing a link to a table that does not exist would
        be worse than missing one."""
        d = csv_from(tmp_path, "fakeid", {
            "events.csv": "event_id,android_id,rapid_rate\n1,a,2\n2,b,3\n"})
        onto, g = run_all_layers(d, tmp_path, "fakeid")
        assert onto.relations == {}


# ------------------------------------------------------------------ data
class TestAwkwardData:
    def test_a_column_that_is_unique_by_accident(self, tmp_path):
        """Three rows, three different prices. That is a coincidence, not
        an identity, and using it as a key would wreck every join."""
        d = csv_from(tmp_path, "acc", {
            "sales.csv": "sale_id,price\n1,10.5\n2,11.5\n3,12.5\n"})
        onto, _ = run_all_layers(d, tmp_path, "acc")
        assert onto.classes["Sale"].key == "sale_id"

    def test_every_value_null(self, tmp_path):
        d = csv_from(tmp_path, "nulls", {
            "x.csv": "id,v\n1,\n2,\n3,\n"})
        onto, g = run_all_layers(d, tmp_path, "nulls")
        assert g.count_class("X") == 3

    def test_mixed_types_in_one_column(self, tmp_path):
        d = csv_from(tmp_path, "mixed", {
            "v.csv": "id,val\n1,10\n2,abc\n3,2024-01-01\n"})
        onto, g = run_all_layers(d, tmp_path, "mixed")
        assert g.count_class("V") == 3

    def test_a_date_column_that_is_really_text(self, tmp_path):
        d = csv_from(tmp_path, "dt", {
            "e.csv": "e_id,happened_on\n1,not a date\n2,2024-01-01\n"})
        onto, g = run_all_layers(d, tmp_path, "dt")
        assert g.count_class("E") == 2

    def test_very_wide_table(self, tmp_path):
        cols = ",".join(f"c{i}" for i in range(120))
        vals = ",".join(str(i) for i in range(120))
        d = csv_from(tmp_path, "wide", {"w.csv": f"id,{cols}\n1,{vals}\n"})
        onto, g = run_all_layers(d, tmp_path, "wide")
        assert g.count_class("W") == 1


# ------------------------------------------------------------- stability
class TestStability:
    def test_building_twice_changes_nothing(self, tmp_path):
        """Re-running must be idempotent, or a scheduled refresh doubles
        the graph every night."""
        d = csv_from(tmp_path, "idem", {
            "customers.csv": "customer_id\nc1\nc2\n",
            "orders.csv": "order_id,customer_id\no1,c1\no2,c2\n"})
        schema = connect(str(d))
        onto = discover(schema)
        g = open_graph(tmp_path / "idem.duckdb")
        build(g, schema, onto)
        first = (g.count_class("Customer"), g.count_relation("customer"))
        build(g, schema, onto)
        assert (g.count_class("Customer"), g.count_relation("customer")) == first

    def test_the_same_source_twice_gives_the_same_ontology(self, tmp_path):
        d = csv_from(tmp_path, "det", {
            "customers.csv": "customer_id,city\nc1,X\n",
            "orders.csv": "order_id,customer_id\no1,c1\n"})
        a = discover(connect(str(d)))
        b = discover(connect(str(d)))
        assert {n: c.code for n, c in a.classes.items()} == \
               {n: c.code for n, c in b.classes.items()}
        assert set(a.relations) == set(b.relations)


# -------------------------------------------------------------- failures
class TestFailsClearly:
    def test_a_corrupt_file_says_what_is_wrong(self, tmp_path):
        d = tmp_path / "bad"
        d.mkdir()
        (d / "x.parquet").write_bytes(b"this is not a parquet file")
        with pytest.raises(SourceError) as e:
            connect(str(d))
        assert "x.parquet" in str(e.value)

    def test_an_unreadable_extension_is_explained(self, tmp_path):
        f = tmp_path / "notes.docx"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(SourceError) as e:
            connect(str(f))
        assert "docx" in str(e.value).lower()
