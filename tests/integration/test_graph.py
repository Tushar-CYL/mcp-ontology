"""Layer 2: rows become nodes and edges, and the graph answers questions.

The test that matters most is at the bottom: a source the code has never
seen, built and queried with zero edits. If that ever needs a file changed,
the product claim is false.
"""

from __future__ import annotations

import sqlite3

import pytest

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover


@pytest.fixture
def shop(tmp_path):
    p = tmp_path / "shop.db"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY, name TEXT, country TEXT);
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            placed_at TIMESTAMP, total REAL);
        INSERT INTO customers VALUES (1,'Ada','UK'),(2,'Grace','US'),(3,'Alan','UK');
        INSERT INTO orders VALUES
            (1,1,'2024-01-05 10:00:00',99.5),
            (2,1,'2024-01-07 11:00:00',12.0),
            (3,2,'2024-02-01 09:30:00',45.25);
    """)
    con.commit(); con.close()
    return p


@pytest.fixture
def graph(shop, tmp_path):
    g = open_graph(tmp_path / "graph.duckdb")
    build(g, connect(str(shop)), discover(connect(str(shop))))
    return g


class TestNodes:
    def test_one_node_per_row(self, graph):
        assert graph.count_class("Customer") == 3
        assert graph.count_class("Order") == 3

    def test_node_key_is_readable_not_an_internal_id(self, graph):
        keys = graph.keys_of("Customer")
        assert keys == {"1", "2", "3"}

    def test_node_carries_its_columns(self, graph):
        props = graph.props_of("Customer", "1")
        assert props["name"] == "Ada"
        assert props["country"] == "UK"

    def test_ids_are_stable_across_rebuilds(self, graph, shop):
        before = graph.node_id("Customer", "1")
        build(graph, connect(str(shop)), discover(connect(str(shop))))
        assert graph.node_id("Customer", "1") == before

    def test_rebuild_does_not_duplicate(self, graph, shop):
        build(graph, connect(str(shop)), discover(connect(str(shop))))
        assert graph.count_class("Customer") == 3


class TestEdges:
    def test_foreign_key_becomes_an_edge(self, graph):
        assert graph.count_relation("customer") == 3

    def test_edge_points_the_right_way(self, graph):
        """orders.customer_id means Order -> Customer, not the reverse.

        Orders 1 and 2 were Ada's, order 3 was Grace's. Asserting the keys
        only - the timestamp is a separate concern, tested below.
        """
        assert set(graph.neighbours("Order", "1", "customer")) == {"1"}
        assert set(graph.neighbours("Order", "2", "customer")) == {"1"}
        assert set(graph.neighbours("Order", "3", "customer")) == {"2"}

    def test_every_edge_endpoint_exists(self, graph):
        assert graph.dangling_edges() == 0

    def test_edges_carry_the_time_from_the_row(self, graph):
        """orders.placed_at is when that link became true. Without it there
        is no time travel, which is most of the point of the graph."""
        assert graph.edge_time("Order", "1", "customer") is not None


class TestTimeTravel:
    def test_the_same_question_differs_by_date(self, graph):
        """Ada ordered in January, Grace in February. Asking 'who had
        ordered' must give a different answer at the two dates."""
        jan = graph.active_relations("customer", "2024-01-10")
        feb = graph.active_relations("customer", "2024-02-10")
        assert jan != feb
        assert jan < feb          # orders accumulate

    def test_a_date_before_any_data_returns_nothing(self, graph):
        assert graph.active_relations("customer", "2020-01-01") == 0


class TestTraversal:
    def test_reach_finds_connected_things(self, graph):
        assert graph.reach("Order", "1", "customer", depth=2) == {"Customer:1"}

    def test_reach_stops_at_the_depth_cap(self, graph):
        assert graph.reach("Order", "1", "customer", depth=0) == set()

    def test_unknown_node_is_empty_not_an_error(self, graph):
        assert graph.reach("Order", "does-not-exist", "customer", 2) == set()


class TestNeverSeenBefore:
    """THE ACCEPTANCE TEST.

    A completely different shape - a library, not a shop - built and queried
    with no edits anywhere. If this needs a single line changed, the claim
    that any source works is false.
    """

    @pytest.fixture
    def library(self, tmp_path):
        p = tmp_path / "library.db"
        con = sqlite3.connect(p)
        con.executescript("""
            CREATE TABLE authors (
                id INTEGER PRIMARY KEY, name TEXT, nationality TEXT);
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                author_id INTEGER REFERENCES authors(id),
                title TEXT, published_on DATE, pages INTEGER);
            CREATE TABLE loans (
                id INTEGER PRIMARY KEY,
                book_id INTEGER REFERENCES books(id),
                borrowed_on DATE, days INTEGER);
            INSERT INTO authors VALUES (1,'Woolf','UK'),(2,'Borges','AR');
            INSERT INTO books VALUES
                (1,1,'The Waves','1931-01-01',  297),
                (2,2,'Ficciones','1944-01-01',  174),
                (3,1,'Orlando',  '1928-01-01',  333);
            INSERT INTO loans VALUES
                (1,1,'2024-03-01',14),(2,2,'2024-03-05',7),
                (3,1,'2024-04-02',21);
        """)
        con.commit(); con.close()
        return p

    def test_four_layers_on_an_unseen_source(self, library, tmp_path):
        schema = connect(str(library))
        onto = discover(schema)

        # LAYER 1 - it worked out what exists, unaided
        assert set(onto.classes) == {"Author", "Book", "Loan"}
        assert onto.classes["Book"].time_column == "published_on"
        assert "pages" in onto.classes["Book"].measures

        # LAYER 2 - and what connects to what
        g = open_graph(tmp_path / "lib.duckdb")
        build(g, schema, onto)
        assert g.count_class("Author") == 2
        assert g.count_class("Book") == 3
        assert g.count_relation("author") == 3
        assert g.count_relation("book") == 3
        assert g.dangling_edges() == 0

        # Two hops: a loan reaches an author through a book. Nothing in the
        # code knows what a library is.
        # A loan reaches its book, and through it the author. Nothing in
        # the code knows what a library is.
        reached = g.reach("Loan", "1", None, depth=3)
        assert "Book:1" in reached
        assert "Author:1" in reached

    def test_a_chain_of_relations_is_walkable(self, library, tmp_path):
        schema = connect(str(library))
        g = open_graph(tmp_path / "lib2.duckdb")
        build(g, schema, discover(schema))
        # Loan 1 -> Book 1 -> Author 1 (Woolf)
        assert g.reach("Loan", "1", "book", depth=1) == {"Book:1"}


class TestTableWithNoKey:
    """A CSV often has no unique column at all - order_items is keyed by
    (order_id, item_number) and nothing else. Such a table still has to
    become nodes, and still has to be the SOURCE of edges.

    The row number that stands in for a key must be computed ONCE. Two
    separate row_number() calls are not guaranteed to agree, so a key
    recomputed per query can silently point edges at the wrong nodes.
    """

    @pytest.fixture
    def keyless(self, tmp_path):
        d = tmp_path / "keyless"
        d.mkdir()
        (d / "orders.csv").write_text(
            "order_id,placed_at\no1,2024-01-01\no2,2024-01-02\n",
            encoding="utf-8")
        # No unique column: o1 appears twice.
        (d / "order_items.csv").write_text(
            "order_id,line,price\no1,1,10.0\no1,2,5.5\no2,1,7.25\n",
            encoding="utf-8")
        return d

    def test_the_keyless_table_still_becomes_nodes(self, keyless, tmp_path):
        schema = connect(str(keyless))
        onto = discover(schema)
        assert onto.classes["OrderItem"].key_is_synthetic is True
        g = open_graph(tmp_path / "k.duckdb")
        build(g, schema, onto)
        assert g.count_class("OrderItem") == 3

    def test_edges_from_a_keyless_table_are_built(self, keyless, tmp_path):
        """This is what failed on a real export: the edge query looked for
        the synthetic column in the raw table, where it does not exist."""
        schema = connect(str(keyless))
        g = open_graph(tmp_path / "k2.duckdb")
        build(g, schema, discover(schema))
        assert g.count_relation("order") == 3
        assert g.dangling_edges() == 0

    def test_synthetic_ids_are_stable_across_rebuilds(self, keyless, tmp_path):
        schema = connect(str(keyless))
        onto = discover(schema)
        g = open_graph(tmp_path / "k3.duckdb")
        build(g, schema, onto)
        before = sorted(g.keys_of("OrderItem"))
        build(g, schema, onto)
        assert sorted(g.keys_of("OrderItem")) == before
        assert g.count_class("OrderItem") == 3


class TestSkipRebuild:
    """Rebuilding a graph that is already correct is pure waiting.

    The app opens the same source repeatedly; on a large export that was
    minutes of spinner every time, which reads as 'broken' long before it
    reads as 'thorough'.
    """

    @pytest.fixture
    def src(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        (d / "customers.csv").write_text("customer_id,city\nc1,X\nc2,Y\n",
                                         encoding="utf-8")
        (d / "orders.csv").write_text("order_id,customer_id\no1,c1\n",
                                      encoding="utf-8")
        return d

    def test_an_unchanged_source_is_not_rebuilt(self, src, tmp_path):
        from knowledge_graph.build import is_current
        schema = connect(str(src))
        onto = discover(schema)
        g = open_graph(tmp_path / "skip.duckdb")
        assert not is_current(g, schema, onto)
        build(g, schema, onto)
        assert is_current(g, schema, onto)

    def test_a_changed_source_is_rebuilt(self, src, tmp_path):
        from knowledge_graph.build import is_current
        schema = connect(str(src))
        g = open_graph(tmp_path / "chg.duckdb")
        build(g, schema, discover(schema))
        (src / "orders.csv").write_text(
            "order_id,customer_id\no1,c1\no2,c2\n", encoding="utf-8")
        schema2 = connect(str(src))
        assert not is_current(g, schema2, discover(schema2))

    def test_a_renamed_class_forces_a_rebuild(self, src, tmp_path):
        """The ontology is part of the signature: the same rows modelled
        differently is a different graph."""
        from knowledge_graph.build import is_current
        schema = connect(str(src))
        g = open_graph(tmp_path / "ren.duckdb")
        build(g, schema, discover(schema))
        renamed = discover(schema, names={"customers": "Buyer"})
        assert not is_current(g, schema, renamed)


class TestSeeTheRealRows:
    """Counts and ids are abstractions. Being able to show the actual row a
    node came from is what makes a graph believable rather than asserted."""

    @pytest.fixture
    def src(self, tmp_path):
        d = tmp_path / "raw"
        d.mkdir()
        (d / "customers.csv").write_text(
            "customer_id,name,city\nc1,Ada,London\nc2,Grace,York\n",
            encoding="utf-8")
        return d

    def test_rows_can_be_read_back(self, src, tmp_path):
        from knowledge_graph.build import source_rows
        schema = connect(str(src))
        g = open_graph(tmp_path / "rows.duckdb")
        build(g, schema, discover(schema))
        cols, rows = source_rows(g, schema, "customers", limit=10)
        assert cols == ["customer_id", "name", "city"]
        assert ("c1", "Ada", "London") in [tuple(r) for r in rows]

    def test_the_row_behind_one_node(self, src, tmp_path):
        from knowledge_graph.build import row_for
        schema = connect(str(src))
        onto = discover(schema)
        g = open_graph(tmp_path / "one.duckdb")
        build(g, schema, onto)
        got = row_for(g, schema, onto, "Customer", "c2")
        assert got["name"] == "Grace"
        assert got["city"] == "York"

    def test_a_missing_row_gives_nothing_not_an_error(self, src, tmp_path):
        from knowledge_graph.build import row_for
        schema = connect(str(src))
        onto = discover(schema)
        g = open_graph(tmp_path / "miss.duckdb")
        build(g, schema, onto)
        assert row_for(g, schema, onto, "Customer", "nope") == {}


class TestSubgraph:
    """A graph you look at, not one you query a node at a time.

    Picking one node from a dropdown and seeing its neighbours is a lookup.
    Seeing many nodes and the real edges between them is a graph, and it is
    the only view that shows shape - hubs, clusters, things joined to
    nothing.
    """

    @pytest.fixture
    def shop(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        (d / "customers.csv").write_text(
            "customer_id,city\n" + "".join(f"c{i},X\n" for i in range(6)),
            encoding="utf-8")
        (d / "orders.csv").write_text(
            "order_id,customer_id\n"
            + "".join(f"o{i},c{i % 6}\n" for i in range(12)),
            encoding="utf-8")
        g = open_graph(tmp_path / "sub.duckdb")
        schema = connect(str(d))
        build(g, schema, discover(schema))
        return g

    def test_it_returns_nodes_and_the_edges_between_them(self, shop):
        nodes, edges = shop.subgraph(limit=50)
        assert nodes and edges
        ids = {n["id"] for n in nodes}
        for e in edges:
            assert e["source"] in ids and e["target"] in ids, \
                "an edge must not point outside the returned nodes"

    def test_every_node_says_what_kind_it_is(self, shop):
        nodes, _ = shop.subgraph(limit=50)
        assert all(n["class"] for n in nodes)
        assert {"Customer", "Order"} == {n["class"] for n in nodes}

    def test_the_limit_is_respected(self, shop):
        _, edges = shop.subgraph(limit=3)
        assert len(edges) <= 3

    def test_it_can_be_narrowed_to_one_relation(self, shop):
        _, edges = shop.subgraph(limit=50, relation="customer")
        assert all(e["relation"] == "customer" for e in edges)

    def test_an_empty_graph_returns_empty_not_an_error(self, tmp_path):
        g = open_graph(tmp_path / "none.duckdb")
        assert g.subgraph(limit=10) == ([], [])


class TestKeyedTableSurvivesReopen:
    """The rewritten tables must be found again after the process restarts.

    A table with no key of its own gets a stored row number in a side
    table. Which tables were rewritten was remembered on the Graph object,
    in memory - so once an unchanged source was opened WITHOUT rebuilding,
    nothing remembered, and reading a row back looked for a column that
    only exists in the rewrite. Where the rewrite lives has to be a fact
    about the database, not about this process.
    """

    @pytest.fixture
    def keyless(self, tmp_path):
        d = tmp_path / "kl"
        d.mkdir()
        (d / "readings.csv").write_text(
            "sensor,value\na,1\na,2\nb,3\n", encoding="utf-8")
        return d

    def test_a_row_can_be_read_after_reopening_without_a_rebuild(
            self, keyless, tmp_path):
        from knowledge_graph.build import is_current, row_for
        path = tmp_path / "kl.duckdb"
        schema = connect(str(keyless))
        onto = discover(schema)
        g = open_graph(path)
        build(g, schema, onto)
        key = sorted(g.keys_of("Reading"))[0]
        g.close()

        # Reopen exactly as the app does: no rebuild, because nothing moved.
        g2 = open_graph(path)
        assert is_current(g2, schema, onto)
        got = row_for(g2, schema, onto, "Reading", key)
        assert got, "the source row must still be findable"
        assert "sensor" in got


class TestSubgraphIsRepresentative:
    """A sample that shows one link type is not a picture of the graph.

    LIMIT without ordering returns the first N rows, which are all from
    whichever relation was inserted first. On a real export that meant the
    graph view showed 2 kinds out of 9 and claimed to be the graph.
    """

    @pytest.fixture
    def many(self, tmp_path):
        d = tmp_path / "many"
        d.mkdir()
        (d / "customers.csv").write_text(
            "customer_id\n" + "".join(f"c{i}\n" for i in range(40)),
            encoding="utf-8")
        (d / "products.csv").write_text(
            "product_id\n" + "".join(f"p{i}\n" for i in range(40)),
            encoding="utf-8")
        # Every order points at a customer AND a product, so both
        # relations have the same number of edges available.
        (d / "orders.csv").write_text(
            "order_id,customer_id,product_id\n"
            + "".join(f"o{i},c{i % 40},p{i % 40}\n" for i in range(120)),
            encoding="utf-8")
        g = open_graph(tmp_path / "many.duckdb")
        schema = connect(str(d))
        build(g, schema, discover(schema))
        return g

    def test_every_relation_appears_in_the_sample(self, many):
        _, edges = many.subgraph(limit=40)
        kinds = {e["relation"] for e in edges}
        assert kinds == {"customer", "product"}, \
            "a sample showing one link type is not a picture of the graph"

    def test_every_kind_of_thing_appears(self, many):
        nodes, _ = many.subgraph(limit=40)
        assert {"Order", "Customer", "Product"} == {n["class"] for n in nodes}

    def test_nodes_carry_how_connected_they_are(self, many):
        """Without degree every node is drawn the same size, so a hub and a
        leaf look identical and the picture says nothing."""
        nodes, _ = many.subgraph(limit=60)
        assert all("degree" in n for n in nodes)
        assert max(n["degree"] for n in nodes) > 1


class TestKeysAreNotAllLoaded:
    def test_keys_of_takes_a_limit(self, tmp_path):
        """Pulling a million keys into Python to show 300 of them is a
        million strings of work for nothing."""
        d = tmp_path / "big"
        d.mkdir()
        (d / "rows.csv").write_text(
            "row_id\n" + "".join(f"r{i}\n" for i in range(5000)),
            encoding="utf-8")
        g = open_graph(tmp_path / "big.duckdb")
        schema = connect(str(d))
        build(g, schema, discover(schema))
        assert len(g.keys_of("Row", limit=50)) == 50
        assert len(g.keys_of("Row")) == 5000


class TestMetricsWorkOnEverySourceType:
    """A metric must compute whatever the source was.

    File sources are COPIED into the graph as s_<table>; a database is
    ATTACHED as s."<table>". The metric compiler assumed the first shape,
    so every metric worked on CSV and none worked on a database - which is
    the shape a real client brings.
    """

    @pytest.fixture
    def as_db(self, tmp_path):
        p = tmp_path / "shop.db"
        con = sqlite3.connect(p)
        con.executescript("""
            CREATE TABLE sales (id INTEGER PRIMARY KEY, amount REAL);
            INSERT INTO sales VALUES (1,10.0),(2,20.0),(3,30.0);""")
        con.commit(); con.close()
        return str(p)

    @pytest.fixture
    def as_csv(self, tmp_path):
        d = tmp_path / "csv"
        d.mkdir()
        (d / "sales.csv").write_text("id,amount\n1,10.0\n2,20.0\n3,30.0\n",
                                     encoding="utf-8")
        return str(d)

    def _total(self, source, tmp_path, tag):
        from knowledge_graph.build import table_ref
        from semantic.compile import compile_metric
        from semantic.discover import discover_metrics
        schema = connect(source)
        onto = discover(schema)
        g = open_graph(tmp_path / f"{tag}.duckdb")
        build(g, schema, onto)
        m = next(x for x in discover_metrics(onto)
                 if x.column == "amount" and x.agg == "sum")
        sql, params = compile_metric(
            m, table_sql=table_ref(g, schema, m.table))
        return g.sql(sql, params)[0][0]

    def test_a_database_source(self, as_db, tmp_path):
        assert self._total(as_db, tmp_path, "db") == 60.0

    def test_a_csv_source(self, as_csv, tmp_path):
        assert self._total(as_csv, tmp_path, "csv") == 60.0

    def test_both_give_the_same_answer(self, as_db, as_csv, tmp_path):
        assert self._total(as_db, tmp_path, "d2") == \
               self._total(as_csv, tmp_path, "c2")
