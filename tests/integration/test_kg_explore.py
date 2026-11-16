"""The Knowledge graph tool: a virtual graph over an ontology's data.

Shop (SQLite, declared keys): 200 customers, 1,000 orders (10 point at a
customer that does not exist), ~1,950 order lines (composite key, so they are
addressed by row number), 40 products. Plus a small RDF graph."""

from __future__ import annotations

import csv
import io
import zipfile

import pytest

from api.service import MiddleLayer
from knowledge_graph import explore as kg
from ontology import simple
from tests.integration.test_declared_links import make_shop


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kg")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(make_shop(tmp / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


def _things(shop):
    layer, oid = shop
    return {t["name"]: t for t in simple.view(layer.graph, oid)["things"]}


# --------------------------------------------------------------- overview
def test_overview_counts_entities_and_connections(shop):
    layer, oid = shop
    o = kg.overview(layer, oid)
    assert o["summary"]["entities"] == 200 + 1000 + 40 + o["things"][0]["entities"] * 0 + \
        sum(t["entities"] for t in o["things"] if t["tables"] == ["shop.order_line"])
    by_link = {c["key"]: c for c in o["connections"]}
    orders = by_link["shop.orders.customer_id->shop.customer.id"]
    assert orders["connections"] == 990 and orders["orphans"] == 10
    assert o["summary"]["broken_links"] == 10
    assert 0 < o["summary"]["connected_pct"] < 100


def test_health_names_the_broken_links_in_plain_words(shop):
    layer, oid = shop
    texts = [h["text"] for h in kg.overview(layer, oid)["health"]]
    assert any(t.startswith("10 ") and "does not exist" in t for t in texts), texts


def test_a_placeholder_hub_is_flagged(tmp_path):
    """Half the orders on customer 0 ('unknown') is a data problem to show."""
    import sqlite3
    db = tmp_path / "hub.db"
    s = sqlite3.connect(db)
    s.executescript("""create table customer(id integer primary key, name text);
        create table orders(id integer primary key, customer_id integer references customer(id));""")
    s.executemany("insert into customer values(?,?)", [(i, "unknown" if i == 0 else f"C{i}") for i in range(0, 50)])
    s.executemany("insert into orders values(?,?)", [(i, 0 if i % 2 else i % 49 + 1) for i in range(1, 401)])
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="hub")
    oid = simple.create_and_build(layer, "Hub", ["hub"])["ontology"]
    hubs = [h for h in kg.overview(layer, oid)["health"] if h["kind"] == "hub"]
    assert len(hubs) == 1 and "(0)" in hubs[0]["text"] and "50%" in hubs[0]["text"]
    assert hubs[0]["entity"] == {"set": "hub.customer", "key": "0"}


# ----------------------------------------------------------------- search
def test_search_by_id_and_by_name(shop):
    layer, oid = shop
    by_id = kg.search(layer, oid, "42")["results"]
    assert by_id[0]["key"] == "42"                              # exact ids first
    by_name = kg.search(layer, oid, "customer 17")["results"]
    assert by_name[0] == {"set": "shop.customer", "thing": _thing_name(shop, "shop.customer"),
                          "key": "17", "label": "Customer 17"}
    assert kg.search(layer, oid, "Customer 1", thing="Nope")["results"] == []
    with pytest.raises(kg.GraphError):
        kg.search(layer, oid, "  ")


def test_search_is_safe_with_quotes_and_wildcards(shop):
    layer, oid = shop
    assert kg.search(layer, oid, "x' OR '1'='1")["results"] == []
    assert kg.search(layer, oid, "%")["results"] == []          # a literal %, not "everything"


def _thing_name(shop, member):
    return next(t["name"] for t in _things(shop).values() if member in t["tables"])


# ----------------------------------------------------------------- entity
def test_entity_360_has_fields_and_both_directions(shop):
    layer, oid = shop
    e = kg.entity(layer, oid, "shop.customer", "17")
    assert e["label"] == "Customer 17"
    fields = {f["column"]: f for f in e["fields"]}
    assert fields["email"]["personal"] == "Email" and fields["email"]["value"] == "c***@example.com"
    incoming = [c for c in e["connections"] if c["direction"] == "in"]
    assert len(incoming) == 1 and incoming[0]["count"] == 5      # orders 16+200k ... -> 5 each
    assert all(i["set"] == "shop.orders" for i in incoming[0]["items"])


def test_order_points_at_its_customer_and_lists_its_lines(shop):
    layer, oid = shop
    e = kg.entity(layer, oid, "shop.orders", "500")
    out = [c for c in e["connections"] if c["direction"] == "out"]
    assert out[0]["items"][0]["key"] == "101" and not out[0]["broken"]
    lines = [c for c in e["connections"] if c["direction"] == "in"]
    assert lines and lines[0]["count"] == 2


def test_broken_link_is_shown_not_hidden(shop):
    layer, oid = shop
    e = kg.entity(layer, oid, "shop.orders", "3")                # customer 999 does not exist
    out = [c for c in e["connections"] if c["direction"] == "out"][0]
    assert out["broken"] and out["value"] == 999 and out["items"] == []


def test_unknown_entity_and_set_are_clear_errors(shop):
    layer, oid = shop
    with pytest.raises(kg.GraphError, match="no .* with id 99999"):
        kg.entity(layer, oid, "shop.customer", "99999")
    with pytest.raises(kg.GraphError, match="not part of this ontology"):
        kg.entity(layer, oid, "other.table", "1")


# ------------------------------------------------------------------- path
def test_path_between_two_customers_who_bought_the_same_product(shop):
    layer, oid = shop
    # Order 1 (customer 2) and order 41 (customer 42) both contain SKU002.
    p = kg.path(layer, oid, ("shop.customer", "2"), ("shop.customer", "42"), max_hops=6)
    assert p["found"]
    sets = [s["set"] for s in p["steps"]]
    assert sets[0] == "shop.customer" and sets[-1] == "shop.customer"
    assert "shop.product" in sets
    assert p["steps"][1]["via"].startswith("has ")


def test_no_path_is_said_plainly(shop):
    layer, oid = shop
    p = kg.path(layer, oid, ("shop.customer", "2"), ("shop.customer", "42"), max_hops=1)
    assert not p["found"] and "No connection within 1 steps" in p["text"]


def test_path_to_itself_is_zero_hops(shop):
    layer, oid = shop
    p = kg.path(layer, oid, ("shop.product", "SKU001"), ("shop.product", "SKU001"))
    assert p["found"] and p["hops"] == 0


# ----------------------------------------------------------------- export
def test_neo4j_export_has_nodes_rels_and_no_personal_data(shop, tmp_path):
    layer, oid = shop
    out = kg.export_neo4j(layer, oid, tmp_path / "neo")
    z = zipfile.ZipFile(out)
    names = z.namelist()
    assert "README.txt" in names and "neo4j-admin database import" in z.read("README.txt").decode()
    nodes = [n for n in names if n.startswith("nodes_")]
    rels = [n for n in names if n.startswith("rels_")]
    assert len(nodes) == 4 and len(rels) == 3
    customers = list(csv.reader(io.StringIO(z.read("nodes_shop_customer.csv").decode())))
    assert customers[0][0].startswith("id:ID(") and customers[0][-1] == ":LABEL"
    assert "email" not in customers[0] and len(customers) == 201
    rel = next(n for n in rels if "customer_id" in n)
    rows = list(csv.reader(io.StringIO(z.read(rel).decode())))
    assert rows[0][0].startswith(":START_ID(") and len(rows) == 1 + 990  # orphans have no edge


# ---------------------------------------------------------------- graph sources
@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kb")
    lab = "<http://www.w3.org/2000/01/rdf-schema#label>"
    kbn, prop, con = "https://kb.org/entity/", "https://kb.org/prop/", "https://kb.org/concept/"
    lines = [f'<{prop}P0> {lab} "instanceOf" .', f'<{prop}P40> {lab} "locatedIn" .',
             f'<{con}C0> {lab} "person" .', f'<{con}C1> {lab} "city" .']
    for i in range(30):
        lines += [f'<{kbn}P{i}> {lab} "Person {i}" .', f"<{kbn}P{i}> <{prop}P0> <{con}C0> .",
                  f"<{kbn}P{i}> <{prop}P40> <{kbn}T{i % 5}> ."]
    for k in range(5):
        lines += [f'<{kbn}T{k}> {lab} "Town {k}" .', f"<{kbn}T{k}> <{prop}P0> <{con}C1> ."]
    nt = tmp / "kb.nt"
    nt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    layer = MiddleLayer(str(tmp / "kb.duckdb"))
    layer.add_source(str(nt), source="kb")
    oid = simple.create_and_build(layer, "KB", ["kb"])["ontology"]
    return layer, oid


def test_rdf_graph_overview_search_entity_and_path(kb):
    layer, oid = kb
    o = kg.overview(layer, oid)
    assert o["graphs"] and o["graphs"][0]["entities"] >= 35
    hit = kg.search(layer, oid, "Town 3")["results"][0]
    assert hit["label"] == "Town 3" and hit["set"] == "graph:kb"
    e = kg.entity(layer, oid, hit["set"], hit["key"])
    pointing = [c for c in e["connections"] if c["direction"] == "in"]
    assert pointing and pointing[0]["count"] == 6                # P3, P8, ... P28
    assert pointing[0]["text"].startswith("located in")      # "P40" in words, from the data
    a = kg.search(layer, oid, "Person 3")["results"][0]
    b = kg.search(layer, oid, "Person 8")["results"][0]
    p = kg.path(layer, oid, (a["set"], a["key"]), (b["set"], b["key"]))
    assert p["found"] and p["hops"] == 2 and p["steps"][1]["label"] == "Town 3"


# ------------------------------------------------- found live on real data
def test_search_finds_plain_text_fields_and_says_which(shop):
    """Olist customers have no name column: 'sao paulo' is in their city."""
    layer, oid = shop
    hits = kg.search(layer, oid, "GB")["results"]           # customer.country
    assert hits and all(h["set"] == "shop.customer" for h in hits)
    assert hits[0]["matched"].endswith(": GB")


def test_personal_columns_are_never_searched(shop):
    layer, oid = shop
    assert kg.search(layer, oid, "example.com")["results"] == []


def test_a_space_matches_an_underscore(kb):
    layer, oid = kb
    assert kg.search(layer, oid, "Town 3")["results"]       # label has a space
    from knowledge_graph.explore import _pattern
    assert _pattern("neural network") == "'%neural_network%'"   # _ = any one character
    assert _pattern("a_b%") == "'%a\_b\%%'"


def test_never_100_percent_while_links_are_broken():
    from knowledge_graph.explore import _share
    assert _share(672_829, 672_842) == 99.9
    assert _share(10, 10) == 100.0 and _share(0, 0) == 100.0
    assert _share(50, 100) == 50.0


def test_every_step_of_a_path_reads_from_start_to_end(shop):
    """Searching from both ends must not read the far half backwards."""
    layer, oid = shop
    p = kg.path(layer, oid, ("shop.customer", "2"), ("shop.product", "SKU002"), max_hops=4)
    assert p["found"]
    pairs = [(s["thing"], s["via"]) for s in p["steps"]]
    things = [_thing_name(shop, m) for m in ("shop.customer", "shop.orders", "shop.order_line", "shop.product")]
    assert [t for t, _ in pairs] == things
    assert [v for _, v in pairs] == [None, f"has {things[1]}", f"has {things[2]}", f"belongs to {things[3]}"]
    back = kg.path(layer, oid, ("shop.product", "SKU002"), ("shop.customer", "2"), max_hops=4)
    assert [s["via"] for s in back["steps"]] == [None, f"has {things[2]}", f"belongs to {things[1]}",
                                                  f"belongs to {things[0]}"]


def test_graph_path_wording_and_speed_shape(kb):
    layer, oid = kb
    a = kg.search(layer, oid, "Person 3")["results"][0]
    b = kg.search(layer, oid, "Person 8")["results"][0]
    vias = [s["via"] for s in kg.path(layer, oid, (a["set"], a["key"]), (b["set"], b["key"]))["steps"]]
    assert vias == [None, "located in", "located in (reversed)"]


def test_records_without_a_name_column_read_as_thing_and_id(shop):
    """Order lines have no name: '<thing> <id>', not a bare '16|SKU017'."""
    layer, oid = shop
    e = kg.entity(layer, oid, "shop.orders", "500")
    line = next(c for c in e["connections"] if c["set"] == "shop.order_line")["items"][0]
    assert line["label"].startswith(_thing_name(shop, "shop.order_line") + " ")


def test_search_takes_each_kind_of_thing_in_turn(shop):
    """'1' matches ids in every table: the list must not be one table only."""
    layer, oid = shop
    sets = {h["set"] for h in kg.search(layer, oid, "1", limit=8)["results"]}
    assert len(sets) >= 2


# ------------------------------------- found on the user's server (salt = 0)
def test_a_source_not_reopened_at_start_is_opened_on_demand(tmp_path):
    """MIDDLE_LAYER_WARM_SOURCES named only another source, so after a restart
    'salt' was in the database but not open: the graph showed 0 entities."""
    db = make_shop(tmp_path / "shop.db")
    first = MiddleLayer(str(tmp_path / "g.duckdb"))
    first.add_source(str(db), source="shop")
    oid = simple.create_and_build(first, "Shop", ["shop"])["ontology"]
    first.graph.close()

    restarted = MiddleLayer(str(tmp_path / "g.duckdb"))      # nothing reopened
    assert restarted.bundles == []
    o = kg.overview(restarted, oid)
    assert o["summary"]["entities"] > 3000 and o["summary"]["connections"] > 0


def test_an_unreadable_source_is_reported_not_shown_as_zero(tmp_path):
    db = make_shop(tmp_path / "shop.db")
    first = MiddleLayer(str(tmp_path / "g.duckdb"))
    first.add_source(str(db), source="shop")
    oid = simple.create_and_build(first, "Shop", ["shop"])["ontology"]
    first.graph.close()
    db.unlink()                                              # the file has gone

    restarted = MiddleLayer(str(tmp_path / "g.duckdb"))
    health = kg.overview(restarted, oid)["health"]
    assert health and health[0]["kind"] == "unreadable"
    assert "could not be opened" in health[0]["text"]


# ------------------------------------------------- the simple build page
def test_overview_explains_the_schema_step(shop):
    layer, oid = shop
    schema = {x["table"]: x for x in kg.overview(layer, oid)["schema"]}
    assert set(schema) == {"shop.customer", "shop.orders", "shop.order_line", "shop.product"}
    assert schema["shop.customer"]["key"] == ["id"] and schema["shop.customer"]["rows"] == 200
    assert schema["shop.order_line"]["key"] == ["order_id", "sku"]
    assert len(schema["shop.orders"]["columns"]) >= 4


def test_sample_draws_real_records_and_their_links(shop):
    layer, oid = shop
    pic = kg.sample(layer, oid)
    ids = {n["id"] for n in pic["nodes"]}
    assert 5 < len(ids) <= 5 * (1 + 8)
    assert pic["edges"] and all(e["source"] in ids and e["target"] in ids for e in pic["edges"])
    assert len({n["thing"] for n in pic["nodes"]}) >= 2          # more than one kind of thing


def test_expand_adds_one_records_neighbours(shop):
    layer, oid = shop
    pic = kg.expand(layer, oid, "shop.customer", "17")
    ids = {n["id"] for n in pic["nodes"]}
    assert "shop.customer|17" in ids and len(ids) == 1 + 5        # customer 17 has 5 orders
    with pytest.raises(kg.GraphError):
        kg.expand(layer, oid, "nope.table", "1")


def test_graph_sample_skips_nothing_and_has_edges(kb):
    layer, oid = kb
    pic = kg.sample(layer, oid)
    assert pic["nodes"] and pic["edges"]
