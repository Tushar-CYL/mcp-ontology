"""Strata Model v1: our ontology as one open JSON document, and anyone's
ontology (written in that format) used exactly, on their own data, under our
Knowledge graph, Semantic and Context layers."""

from __future__ import annotations

import json

import pytest

from api.service import MiddleLayer
from context import engine as ctx
from knowledge_graph import explore as kg
from ontology import contract, simple
from ontology.metadata import MetadataError
from semantic import model as sem
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture()
def shop(tmp_path):
    db = make_amounts(tmp_path / "amounts.db")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    return layer, db, tmp_path


def _build(layer, name="Shop", metadata=None):
    return simple.create_and_build(layer, name, ["shop"], metadata=metadata)["ontology"]


def _write(tmp_path, doc, name="model.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


MINE = {
    "spec": "strata.model/v1", "name": "Our sales model",
    "things": [
        {"name": "Client", "description": "A company that buys from us.", "tables": ["sales.customer"],
         "key": ["id"],
         "fields": [{"column": "id", "name": "Client Number", "role": "identifier"},
                    {"column": "country", "name": "Home Country", "role": "location",
                     "meaning": "ISO country code of the client."},
                    {"column": "segment", "name": "Client Tier", "role": "category"}]},
        {"name": "Sale", "description": "One sale.", "tables": ["sales.orders"], "key": ["id"],
         "fields": [{"column": "id", "name": "Sale Number", "role": "identifier"},
                    {"column": "customer_id", "name": "Client", "role": "reference"},
                    {"column": "status", "name": "Sale Status", "role": "category"},
                    {"column": "gross_amount", "name": "Invoice Total", "role": "amount", "unit": "EUR"},
                    {"column": "placed", "name": "Sold On", "role": "date"}]},
    ],
    "links": [{"from": {"table": "sales.orders", "column": "customer_id"},
               "to": {"table": "sales.customer", "column": "id"}, "cardinality": "many-to-one"}],
    "notes": [{"text": "Invoice Total is in euros and includes tax."}],
}


# ------------------------------------------------------------- export
def test_our_ontology_is_a_valid_open_document(shop):
    layer, _, _ = shop
    oid = _build(layer)
    doc = contract.to_contract(layer.graph, oid)
    assert contract.validate(doc) == []
    assert doc["spec"] == "strata.model/v1"
    assert {t["name"] for t in doc["things"]} >= {"Order"} or len(doc["things"]) == 3
    link = doc["links"][0]
    assert set(link["from"]) == {"table", "column"} and link["cardinality"]
    json.dumps(doc)                                        # plain JSON, nothing exotic


def test_the_schema_file_agrees_with_the_code(shop):
    import pathlib
    schema = json.loads(pathlib.Path("docs/spec/strata-model.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["spec"]["const"] == contract.SPEC
    roles = schema["$defs"]["field"]["properties"]["role"]["enum"]
    assert set(roles) - {None, ""} == set(contract.ROLES)
    try:
        import jsonschema
    except ImportError:
        return
    layer, _, _ = shop
    jsonschema.validate(contract.to_contract(layer.graph, _build(layer)), schema)
    jsonschema.validate(MINE, schema)


# ----------------------------------------------------------- validate
def test_a_broken_document_lists_every_problem():
    bad = {"spec": "strata.model/v1", "things": [
        {"name": "A", "tables": []},
        {"name": "A", "tables": ["x.t"], "fields": [{"column": "c", "role": "money"}]}],
        "links": [{"from": {"table": "x.t"}, "to": {"table": "x.u", "column": "id"}}]}
    problems = contract.validate(bad)
    text = " | ".join(problems)
    assert '"name" is required' in text
    assert "tables must be a non-empty list" in text
    assert "used twice" in text
    assert "role must be one of" in text
    assert "links[0].from needs a table and a column" in text


def test_a_broken_file_is_refused_before_anything_is_built(shop):
    layer, _, tmp = shop
    path = _write(tmp, {"spec": "strata.model/v1", "name": "x", "things": []})
    with pytest.raises(MetadataError, match="things"):
        _build(layer, metadata=[path])
    assert not [o for o in __import__("ontology.registry", fromlist=["x"]).list_ontologies(layer.graph)]


# ------------------------------------------------------ use mine exactly
def test_your_model_is_used_exactly(shop):
    layer, _, tmp = shop
    oid = _build(layer, "Mine", [_write(tmp, MINE)])
    v = simple.view(layer.graph, oid)
    assert sorted(t["name"] for t in v["things"]) == ["Client", "Sale"]     # order_line left out
    sale = next(t for t in v["things"] if t["name"] == "Sale")
    labels = {f["column"]: f for f in sale["fields"]}
    assert labels["gross_amount"]["label"] == "Invoice Total"
    assert labels["gross_amount"]["unit"] == "EUR"
    assert labels["gross_amount"]["by"] == "metadata"
    assert "net_amount" not in labels                                      # not in your model
    assert labels["gross_amount"]["check"] == "verified"                   # still checked
    assert [(x["from_thing"], x["to_thing"]) for x in v["links"]] == [("Sale", "Client")]
    assert any("euros" in n["text"] for n in v["notes"])
    assert v["built"]["model"]["left_out"] == ["shop.order_line"]
    assert v["built"]["ai"]["used"] is False


def test_the_data_still_checks_your_model(shop):
    layer, _, tmp = shop
    doc = json.loads(json.dumps(MINE))
    doc["things"][1]["fields"][2]["role"] = "amount"             # status is text, not money
    oid = _build(layer, "Mine", [_write(tmp, doc)])
    sale = next(t for t in simple.view(layer.graph, oid)["things"] if t["name"] == "Sale")
    status = next(f for f in sale["fields"] if f["column"] == "status")
    assert status["role"] == "amount"                            # your word is kept...
    assert status["check"] == "conflict"                         # ...and the data disagrees, saying why
    assert "your model says" in status["proof"] and "not numbers" in status["proof"]


def test_a_declared_link_the_data_does_not_support_says_so(shop):
    layer, _, tmp = shop
    doc = json.loads(json.dumps(MINE))
    doc["links"] = [{"from": {"table": "sales.orders", "column": "status"},
                     "to": {"table": "sales.customer", "column": "id"}}]
    oid = _build(layer, "Mine", [_write(tmp, doc)])
    links = simple.view(layer.graph, oid)["links"]
    mine = next(x for x in links if x["from"].endswith(".status"))
    assert mine["check"] == "conflict" and (mine["match"] or 0) < 0.5
    # The key the database itself declares is a fact, so it stays.
    assert any(x["from"].endswith(".customer_id") and x["check"] == "verified" for x in links)


def test_every_layer_works_on_your_model(shop):
    layer, db, tmp = shop
    oid = _build(layer, "Mine", [_write(tmp, MINE)])
    # Knowledge graph: your names, your links.
    hit = kg.search(layer, oid, "GB")["results"][0]
    assert hit["thing"] == "Client"
    e = kg.entity(layer, oid, hit["set"], hit["key"])
    assert any(c["thing"] == "Sale" for c in e["connections"])
    # Semantic: a total of your money field, equal to the data.
    sem.propose(layer, oid)
    cards = {c["name"]: c for c in sem.overview(layer, oid)["metrics"]}
    total = cards["total_gross_amount"]
    import sqlite3
    want = sqlite3.connect(db).execute("select sum(gross_amount) from orders").fetchone()[0]
    assert abs(sem.value(layer, oid, total["name"])["rows"][0][0] - want) < 0.01
    # Context: the question in your words.
    out = ctx.build(layer, oid, "How many Sale records have Sale Status cancelled?")
    assert out["steps"]["understand"]["things"]


def test_export_then_import_gives_the_same_ontology(shop):
    """Round trip: our document, used exactly on a second copy of the data."""
    layer, _, tmp = shop
    first = _build(layer, "Original")
    doc = contract.to_contract(layer.graph, first)
    second = _build(layer, "Copy", [_write(tmp, doc)])
    a, b = simple.view(layer.graph, first), simple.view(layer.graph, second)

    def shape(v):
        return (sorted((t["name"], tuple(sorted((f["column"], f["label"], f["role"]) for f in t["fields"])))
                       for t in v["things"]),
                sorted((x["from"].split(".", 1)[1], x["to"].split(".", 1)[1]) for x in v["links"]))
    assert shape(a) == shape(b)
    va = {c["name"]: c.get("value") for c in sem.overview(layer, first)["metrics"]}
    vb = {c["name"]: c.get("value") for c in sem.overview(layer, second)["metrics"]}
    assert va == vb


def test_your_edits_after_import_survive_a_rebuild(shop):
    layer, _, tmp = shop
    oid = _build(layer, "Mine", [_write(tmp, MINE)])
    key = next(f["key"] for t in simple.view(layer.graph, oid)["things"] for f in t["fields"]
               if f["column"] == "segment")
    simple.edit_field(layer, oid, key, label="Account Tier")
    simple.build(layer, oid)
    labels = [f["label"] for t in simple.view(layer.graph, oid)["things"] for f in t["fields"]]
    assert "Account Tier" in labels and "Client Tier" not in labels
