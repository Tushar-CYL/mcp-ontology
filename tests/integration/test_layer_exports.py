"""Each layer gives its result in a format another system already reads:
the knowledge graph as RDF and JSON, the semantic layer as SQL views and dbt
MetricFlow YAML, and context as an open Context Pack. Every export is checked
against the numbers Strata itself gives."""

from __future__ import annotations

import json
import pathlib
import sqlite3

import duckdb
import pytest
import yaml

from api.service import MiddleLayer
from context import engine as ctx
from knowledge_graph import explore as kg
from ontology import simple
from semantic import export
from semantic import model as sem
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("exports")
    db = make_amounts(tmp / "amounts.db")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    sem.certify(layer, oid, "total_gross_amount", owner="Finance")
    return layer, oid, db, tmp


# ------------------------------------------------------- knowledge graph
def test_the_graph_as_rdf_loads_in_a_triple_store(shop):
    rdflib = pytest.importorskip("rdflib")
    layer, oid, db, tmp = shop
    path = kg.export_rdf(layer, oid, tmp / "g.nt")
    g = rdflib.Graph()
    g.parse(path, format="nt")                         # every line is valid N-Triples
    rdf_type = rdflib.RDF.type
    typed = {}
    for _, _, cls in g.triples((None, rdf_type, None)):
        typed[str(cls).rsplit("/", 1)[-1]] = typed.get(str(cls).rsplit("/", 1)[-1], 0) + 1
    s = sqlite3.connect(db)
    counts = sorted(s.execute(f"select count(*) from {t}").fetchone()[0]
                    for t in ("customer", "orders", "order_line"))
    assert sorted(typed.values()) == counts             # one node per record
    links = [p for p in set(g.predicates()) if "/link/" in str(p)]
    assert links                                        # proven links are edges
    edges = sum(1 for p in links for _ in g.triples((None, p, None)))
    assert edges == s.execute("select count(*) from orders").fetchone()[0] + \
        s.execute("select count(*) from order_line").fetchone()[0]


def test_personal_data_never_leaves_in_an_export(tmp_path):
    rdflib = pytest.importorskip("rdflib")
    db = tmp_path / "p.db"
    s = sqlite3.connect(db)
    s.execute("create table member(id integer primary key, email text, city text)")
    s.executemany("insert into member values(?,?,?)",
                  [(i, f"person{i}@example.com", ["Pune", "Leeds"][i % 2]) for i in range(1, 30)])
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="p")
    oid = simple.create_and_build(layer, "P", ["p"])["ontology"]
    text = kg.export_rdf(layer, oid, tmp_path / "p.nt").read_text(encoding="utf-8")
    assert "@example.com" not in text and "Pune" in text
    rdflib.Graph().parse(data=text, format="nt")
    js = json.dumps(kg.export_json_graph(layer, oid))
    assert "@example.com" not in js and "Leeds" in js


def test_awkward_values_still_make_valid_rdf(tmp_path):
    rdflib = pytest.importorskip("rdflib")
    db = tmp_path / "w.db"
    s = sqlite3.connect(db)
    s.execute("create table note(id integer primary key, body text, kind text)")
    s.executemany("insert into note values(?,?,?)",
                  [(1, 'a "quoted"\nline\tand \\ slash', "x"), (2, "plain", "y"), (3, "ünïcödé ✓", "x")])
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="w")
    oid = simple.create_and_build(layer, "W", ["w"])["ontology"]
    g = rdflib.Graph()
    g.parse(kg.export_rdf(layer, oid, tmp_path / "w.nt"), format="nt")
    values = {str(o) for o in g.objects()}
    assert 'a "quoted"\nline\tand \\ slash' in values and "ünïcödé ✓" in values


def test_the_graph_as_json(shop):
    layer, oid, db, _ = shop
    out = kg.export_json_graph(layer, oid)
    assert out["spec"] == "strata.graph/v1" and not out["truncated"]
    ids = {n["id"] for n in out["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in out["edges"])
    small = kg.export_json_graph(layer, oid, limit=10)
    assert len(small["nodes"]) == 10 and small["truncated"]


# --------------------------------------------------------------- semantic
def test_sql_views_give_exactly_the_certified_number(shop):
    layer, oid, db, _ = shop
    sql = export.sql_views(layer, oid, portable=False)
    assert "metric_total_gross_amount" in sql and "owner Finance" in sql
    assert "number_of" not in sql                       # only certified by default
    con = layer.graph.con.cursor()
    con.execute(sql)
    got = con.execute('SELECT * FROM "metric_total_gross_amount"').fetchone()[0]
    assert abs(got - sem.value(layer, oid, "total_gross_amount")["rows"][0][0]) < 1e-6


def test_portable_views_run_on_the_clients_own_tables(shop):
    """The views name the source tables, so they run in the client's database."""
    layer, oid, db, _ = shop
    sql = export.sql_views(layer, oid)
    con = duckdb.connect()
    con.execute(f"ATTACH '{pathlib.Path(db).as_posix()}' AS client (TYPE sqlite)")
    con.execute("USE client")
    con.execute(sql)
    got = con.execute('SELECT * FROM "metric_total_gross_amount"').fetchone()[0]
    want = sqlite3.connect(db).execute("select sum(gross_amount) from orders").fetchone()[0]
    assert abs(got - want) < 0.01


def test_metricflow_yaml_describes_models_and_metrics(shop):
    layer, oid, db, _ = shop
    doc = yaml.safe_load(export.metricflow(layer, oid, status="all"))
    models = {m["name"]: m for m in doc["semantic_models"]}
    order = next(m for m in models.values() if "orders" in m["model"])
    assert any(e["type"] == "primary" for e in order["entities"])
    assert any(e["type"] == "foreign" for e in order["entities"])      # proven link
    assert any(d["type"] == "time" for d in order["dimensions"])
    measures = {x["name"] for m in models.values() for x in m.get("measures", [])}
    assert {m["type_params"]["measure"] for m in doc["metrics"]} <= measures
    gross = next(m for m in doc["metrics"] if m["name"] == "total_gross_amount")
    assert gross["meta"]["owner"] == "Finance"


def test_a_filtered_metric_keeps_its_filter_in_metricflow(shop, monkeypatch):
    layer, oid, db, _ = shop
    monkeypatch.setenv("STRATA_AI", "on")

    class AI:
        mock = False

        def complete(self, messages, max_tokens=600):
            gross = next(f["key"] for t in simple.view(layer.graph, oid)["things"] for f in t["fields"]
                         if f["column"] == "gross_amount")
            status = next(f["key"] for t in simple.view(layer.graph, oid)["things"] for f in t["fields"]
                          if f["column"] == "status")
            return json.dumps({"title": "Paid gross", "agg": "sum", "field": gross,
                               "filters": [{"field": status, "value": "paid"}]})
    sem.from_words(layer, oid, "Paid gross is the total Gross Amount of paid orders", AI())
    doc = yaml.safe_load(export.metricflow(layer, oid, status="all"))
    paid = next(m for m in doc["metrics"] if m["name"] == "paid_gross")
    assert "status') }} = 'paid'" in paid["filter"]


# ---------------------------------------------------------------- context
def test_the_context_pack_matches_its_open_schema(shop):
    jsonschema = pytest.importorskip("jsonschema")
    layer, oid, _, _ = shop
    pack = ctx.to_pack(ctx.build(layer, oid, "total Gross Amount by Status"))
    schema = json.loads(pathlib.Path("docs/spec/context-pack.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(pack, schema)
    assert pack["facts"] and pack["metric"]["name"] == "total_gross_amount"   # certified first
    assert all(f["n"] == i for i, f in enumerate(pack["facts"], 1))
