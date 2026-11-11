"""Apache Ossie export and import: the document follows the 0.3.0.dev0
schema (required keys, no unknown keys), carries every field with its meaning
and data check, and round-trips into a build as metadata."""

from __future__ import annotations

import yaml

from ontology import metadata as md
from ontology import ossie, simple
from tests.integration.simple_fixtures import FakeAI, load

# Allowed keys per object, from core-spec/ossie-schema.json (additionalProperties: false).
ALLOWED = {
    "model": {"version", "name", "description", "ai_context", "datasets", "relationships",
              "metrics", "nonportable_extensions"},
    "dataset": {"name", "source", "primary_key", "unique_keys", "description", "ai_context",
                "fields", "metrics", "nonportable_extensions"},
    "field": {"name", "expression", "dimension", "label", "description", "datatype",
              "ai_context", "nonportable_extensions"},
    "metric": {"name", "expression", "description", "datatype", "ai_context",
               "nonportable_extensions"},
    "relationship": {"name", "from", "to", "from_columns", "to_columns", "ai_context",
                     "nonportable_extensions"},
}
DATATYPES = {"String", "Integer", "Decimal", "Float", "Boolean", "Date", "Time", "DateTime",
             "DateTimeTz", "Opaque"}


def check_schema(doc: dict) -> None:
    assert set(doc) <= ALLOWED["model"], set(doc) - ALLOWED["model"]
    assert doc["version"] == "0.3.0.dev0" and doc["name"] and doc["datasets"]
    names = set()
    for ds in doc["datasets"]:
        assert set(ds) <= ALLOWED["dataset"], set(ds) - ALLOWED["dataset"]
        assert ds["name"] and ds["source"] and ds["name"] not in names
        names.add(ds["name"])
        fnames = set()
        for f in ds.get("fields") or []:
            assert set(f) <= ALLOWED["field"], set(f) - ALLOWED["field"]
            assert f["name"] and (f["expression"].get("sql") or f["expression"].get("dialects"))
            assert f.get("datatype") in DATATYPES | {None}
            assert f["name"] not in fnames
            fnames.add(f["name"])
        for m in ds.get("metrics") or []:
            assert set(m) <= ALLOWED["metric"] and m["name"] and m["expression"].get("sql")
    for r in doc.get("relationships") or []:
        assert set(r) <= ALLOWED["relationship"]
        assert r["from"] in names and r["to"] in names
        assert len(r["from_columns"]) == len(r["to_columns"]) >= 1
    for ext in doc.get("nonportable_extensions") or []:
        assert set(ext) == {"vendor_name", "data"}


def test_export_follows_the_spec_and_carries_the_meanings(tmp_path):
    layer = load(tmp_path, ["iot"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI())["ontology"]
    simple.add_context(layer, oid, "temp_c = Motor temperature")
    text = ossie.to_ossie(layer.graph, oid)
    doc = yaml.safe_load(text)
    check_schema(doc)
    ds = {d["name"]: d for d in doc["datasets"]}
    assert set(ds) == {"site", "device", "sensor_reading"}
    assert ds["sensor_reading"]["source"] == "iot.readings"
    assert ds["site"]["primary_key"] == ["site_id"]
    temp = next(f for f in ds["sensor_reading"]["fields"] if f["name"] == "temp_c")
    assert temp["datatype"] == "Float" and temp["ai_context"]["synonyms"] == ["Motor temperature"]
    assert "Unit: °C" in temp["ai_context"]["instructions"]
    assert "Confirmed by the data" in temp["ai_context"]["instructions"]
    when = next(f for f in ds["sensor_reading"]["fields"] if f["name"] == "read_at")
    assert when["dimension"] == {"is_time": True}
    rels = {(r["from"], r["to"]): r for r in doc["relationships"]}
    assert rels[("device", "site")]["from_columns"] == ["site_id"]
    assert "100% of rows match" in rels[("sensor_reading", "device")]["ai_context"]["instructions"]
    ext = doc["nonportable_extensions"][0]
    assert ext["vendor_name"] == "strata" and ext["data"]["published_version"] == 2
    assert 0 < ext["data"]["confirmed_pct"] <= 100
    assert "temp_c = Motor temperature" in doc["ai_context"]["examples"]


def test_an_ossie_model_imports_as_metadata_and_guides_a_build(tmp_path):
    layer = load(tmp_path, ["iot", "clinic"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI())["ontology"]
    path = tmp_path / "sensors.ossie.yaml"
    path.write_text(ossie.to_ossie(layer.graph, oid), encoding="utf-8")
    meta = md.parse(path)
    assert meta["kind"] == "ossie" and set(meta["tables"]) == {"sites", "devices", "readings"}
    col = md.column_info(meta, "readings", "temp_c")
    assert col["label"] == "Temperature" and col["unit"] == "°C" and col["type"] == "DOUBLE"
    assert any(r["from_table"] == "devices" and r["to_table"] == "sites" for r in meta["relationships"])
    # Build the clinic-free copy again WITHOUT the AI: the Ossie file supplies the meanings.
    second = simple.create_and_build(layer, "Sensors from Ossie", ["iot"], metadata=[str(path)])["ontology"]
    v = simple.view(layer.graph, second)
    f = {x["column"]: x for t in v["things"] for x in t["fields"]}
    assert f["temp_c"]["by"] == "metadata" and f["temp_c"]["meaning"] == "The temperature (from the model)."
    assert f["temp_c"]["unit"] == "°C"
    assert v["summary"]["links"] >= 2


def test_a_hand_written_ossie_file_with_model_metrics(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("""
version: 0.3.0.dev0
name: sales
datasets:
  - name: orders
    source: shop.public.orders
    primary_key: [order_id]
    description: One row per order.
    fields:
      - name: order_id
        expression: {sql: order_id}
        datatype: Integer
      - name: amount
        expression: {sql: amount}
        datatype: Decimal
        description: Net amount.
        ai_context: {synonyms: [Net value], instructions: "Unit: EUR. Money."}
    metrics:
      - name: total_amount
        expression: {sql: SUM(amount)}
  - name: customers
    source: shop.public.customers
    fields:
      - name: id
        expression: {sql: id}
relationships:
  - name: o2c
    from: orders
    to: customers
    from_columns: [customer_id]
    to_columns: [id]
metrics:
  - name: orders_per_customer
    expression: {sql: COUNT(orders.order_id) / COUNT(DISTINCT customers.id)}
""", encoding="utf-8")
    meta = md.parse(path)
    assert meta["tables"]["orders"]["description"] == "One row per order."
    amount = md.column_info(meta, "orders", "amount")
    assert amount == {"description": "Net amount.", "type": "DECIMAL", "label": "Net value",
                      "unit": "EUR", "source_column": "amount"}
    assert [m["name"] for m in meta["measures"]] == ["total_amount", "orders_per_customer"]
    assert meta["relationships"][0]["to_table"] == "customers"
    assert ossie.is_ossie({"version": 1, "name": "x", "datasets": []}) is True
    assert ossie.is_ossie({"models": []}) is False
