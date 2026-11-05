"""The simple flow end to end: any data in, an ontology in plain words out,
context applied, published, and readable by Excel / Nexus / agents."""

from __future__ import annotations

import io
import json
import zipfile
from xml.etree import ElementTree

import pytest

from ontology import publish as pub
from ontology import registry as reg
from ontology import simple
from tests.integration.simple_fixtures import TRUTH, FakeAI, load


def fields_by_column(v: dict) -> dict:
    """Column name -> field; a name used in several tables keys by table.column."""
    out, seen = {}, {}
    for t in v["things"]:
        for f in t["fields"]:
            seen[f["column"]] = seen.get(f["column"], 0) + 1
            out[f"{f['table'].split('.', 1)[1]}.{f['column']}"] = f
    for t in v["things"]:
        for f in t["fields"]:
            if seen[f["column"]] == 1:
                out[f["column"]] = f
    return out


# ------------------------------------------------------------ no AI at all
def test_builds_from_iot_data_without_any_model(tmp_path):
    layer = load(tmp_path, ["iot"])
    out = simple.create_and_build(layer, "Factory sensors", ["iot"])
    v = simple.view(layer.graph, out["ontology"])
    assert out["version"] == 1 and v["version"] == 1
    assert {t["name"] for t in v["things"]} == {"Site", "Device", "Reading"}
    f = fields_by_column(v)
    # Honest labelling: nothing claims to be AI when no model is configured.
    assert {x["by"] for x in f.values()} == {"engine"}
    assert f["lat"]["role"] == "location" and f["lng"]["role"] == "location"
    assert f["temp_c"]["role"] == "measure"
    assert f["is_active"]["role"] == "flag"
    assert f["status_code"]["role"] == "category"
    assert f["read_at"]["role"] == "date"
    assert all(x["meaning"] for x in f.values())
    links = {(l["from_thing"], l["to_thing"]) for l in v["links"]}
    assert ("Device", "Site") in links and ("Reading", "Device") in links
    assert v["built"]["ai"]["used"] is False


# --------------------------------------------------------------- with AI
def test_ai_names_any_domain_and_every_claim_is_checked(tmp_path):
    layer = load(tmp_path, ["iot", "clinic"])
    ai = FakeAI()
    iot = simple.create_and_build(layer, "Sensors", ["iot"], client=ai)
    clinic = simple.create_and_build(layer, "Clinic", ["clinic"], client=ai)
    for oid, tables in ((iot["ontology"], ("sites", "devices", "readings")),
                        (clinic["ontology"], ("patients", "doctors", "visits"))):
        v = simple.view(layer.graph, oid)
        assert {t["name"] for t in v["things"]} == {TRUTH[t]["thing"] for t in tables}
        f = fields_by_column(v)
        for table in tables:
            for name, (label, role, unit) in TRUTH[table]["columns"].items():
                col = f"{table}.{name}"
                assert f[col]["label"] == label, col
                assert f[col]["role"] == role, col
                assert f[col]["by"] == "ai"
                assert f[col]["check"] in ("verified", "unchecked"), (col, f[col]["proof"])
        assert v["summary"]["checks"]["conflict"] == 0
    f = fields_by_column(simple.view(layer.graph, clinic["ontology"]))
    assert f["fee_eur"]["unit"] == "EUR" and f["fee_eur"]["check"] == "verified"
    assert f["visits.pat_no"]["links_to"] == "Patient"
    assert f["visits.pat_no"]["proof"] == "values match Patient in the data"
    assert "unique" in f["visit_id"]["proof"]


def test_a_claim_the_data_contradicts_is_a_conflict_not_a_fact(tmp_path):
    layer = load(tmp_path, ["iot"])
    ai = FakeAI(lies={"status_code": "identifier", "site_name": "amount",
                      "model": "date"})
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=ai)["ontology"]
    f = fields_by_column(simple.view(layer.graph, oid))
    for col in ("status_code", "site_name", "model"):
        assert f[col]["check"] == "conflict", col
        assert f[col]["proof"].startswith("AI said"), f[col]["proof"]
        assert f[col]["confidence"] <= 0.5
    assert f["status_code"]["role"] == "category"     # the data's answer is kept


def test_ai_sees_samples_but_never_rows_and_can_be_limited(tmp_path, monkeypatch):
    layer = load(tmp_path, ["iot"])
    ai = FakeAI()
    simple.create_and_build(layer, "Sensors", ["iot"], client=ai)
    sent = next(c for c in ai.calls if c.get("table") == "readings")["facts"]
    sites = next(c for c in ai.calls if c.get("table") == "sites")["facts"]["table"]
    # The AI is told which columns point at a table: the strongest naming clue.
    assert sites["pointed_at_by"] == ["iot.devices.site_id"]
    site_id = next(c for c in sites["columns"] if c["name"] == "site_id")
    assert site_id["used_as_key_by"] == ["iot.devices"]
    temp = next(c for c in sent["table"]["columns"] if c["name"] == "temp_c")
    assert 1 <= len(temp["samples"]) <= 5
    monkeypatch.setenv("STRATA_AI_SAMPLES", "0")
    ai2 = FakeAI()
    simple.create_and_build(layer, "Sensors 2", ["iot"], client=ai2)
    for call in ai2.calls:
        assert all("samples" not in c for c in call["facts"]["table"]["columns"])


def test_rebuild_reuses_ai_answers_and_one_failure_falls_back(tmp_path):
    layer = load(tmp_path, ["iot"])
    ai = FakeAI(fail_tables={"sites"})
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=ai)["ontology"]
    f = fields_by_column(simple.view(layer.graph, oid))
    assert f["site_name"]["by"] == "engine" and f["readings.device_id"]["by"] == "ai"
    built = simple.view(layer.graph, oid)["built"]
    assert len(built["ai"]["errors"]) == 1
    ai.fail_tables.clear()
    before = len(ai.calls)
    out = simple.build(layer, oid, client=ai)
    assert len(ai.calls) - before == 1                 # only the failed table again
    assert out["version"] == 2
    assert fields_by_column(simple.view(layer.graph, oid))["site_name"]["by"] == "ai"


# --------------------------------------------------------------- context
def test_context_note_without_ai_uses_simple_rules(tmp_path):
    layer = load(tmp_path, ["clinic"])
    oid = simple.create_and_build(layer, "Clinic", ["clinic"])["ontology"]
    out = simple.add_context(layer, oid,
                             "icd10 = Diagnosis code\nmins means the length of the visit "
                             "in minutes, measured by the booking system\n"
                             "Visit should be called Appointment")
    assert out["method"] == "rules" and out["version"] == 2
    v = simple.view(layer.graph, oid)
    f = fields_by_column(v)
    assert f["icd10"]["label"] == "Diagnosis code" and f["icd10"]["by"] == "you"
    assert f["mins"]["meaning"].startswith("the length of the visit")
    assert "Appointment" in {t["name"] for t in v["things"]}
    assert v["notes"][-1]["changes"]


def test_context_note_with_ai_and_corrections_survive_rebuilds(tmp_path):
    layer = load(tmp_path, ["iot"])
    ai = FakeAI(note_reply={"edits": [
        {"target": "field", "key": "iot.readings.temp_c", "label": "Motor temperature",
         "unit": "°C", "role": "measure"},
        {"target": "field", "key": "iot.nope.x", "label": "ignored"},
        {"target": "field", "key": "iot.devices.model", "role": "not-a-role"}],
        "reply": "Renamed the temperature."})
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=ai)["ontology"]
    out = simple.add_context(layer, oid, "temp_c is the motor temperature", client=ai)
    assert out["method"] == "ai" and out["reply"] == "Renamed the temperature."
    assert [c["key"] for c in out["changes"]] == ["iot.readings.temp_c"]
    simple.build(layer, oid, client=ai)                 # rebuild keeps the person's word
    f = fields_by_column(simple.view(layer.graph, oid))
    assert f["temp_c"]["label"] == "Motor temperature" and f["temp_c"]["by"] == "you"
    # The note also guides the AI on rebuilds.
    last = [c for c in ai.calls if c.get("table") == "readings"][-1]["facts"]
    assert "temp_c is the motor temperature" in last["client_notes"]


def test_direct_edits_validate_and_publish(tmp_path):
    layer = load(tmp_path, ["iot"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"])["ontology"]
    simple.edit_field(layer, oid, "iot.readings.battery_pct", label="Battery", unit="%")
    simple.edit_thing(layer, oid, "Reading", name="Sensor Reading")
    with pytest.raises(ValueError):
        simple.edit_field(layer, oid, "iot.readings.battery_pct", role="bogus")
    with pytest.raises(KeyError):
        simple.edit_field(layer, oid, "iot.readings.nope", label="x")
    v = simple.view(layer.graph, oid)
    assert v["version"] == 3
    assert fields_by_column(v)["battery_pct"]["unit"] == "%"
    assert "Sensor Reading" in {t["name"] for t in v["things"]}
    with pytest.raises(ValueError):
        simple.add_context(layer, oid, "   ")


# -------------------------------------------------------------- metadata
def test_data_dictionary_and_dbt_links_are_used_and_checked(tmp_path):
    layer = load(tmp_path, ["clinic"])
    dictionary = tmp_path / "dictionary.csv"
    dictionary.write_text("Table,Column,Description,Unit\n"
                          "visits,fee_eur,Amount invoiced to the insurer for the visit,EUR\n"
                          ",city,City where the patient lives,\n", encoding="utf-8")
    dbt = tmp_path / "schema.yml"
    dbt.write_text(
        "version: 2\nmodels:\n  - name: visits\n    description: One consultation.\n"
        "    columns:\n      - name: doc_id\n        tests:\n          - relationships:\n"
        "              to: ref('doctors')\n              field: doc_id\n", encoding="utf-8")
    oid = simple.create_and_build(layer, "Clinic", ["clinic"],
                                  metadata=[str(dictionary), str(dbt)])["ontology"]
    v = simple.view(layer.graph, oid)
    f = fields_by_column(v)
    assert f["fee_eur"]["by"] == "metadata"
    assert f["fee_eur"]["meaning"] == "Amount invoiced to the insurer for the visit"
    assert f["fee_eur"]["unit"] == "EUR" and f["fee_eur"]["check"] == "verified"
    assert f["city"]["meaning"] == "City where the patient lives"
    visit = next(t for t in v["things"] if "visits" in t["tables"][0])
    assert visit["description"] == "One consultation."
    assert any(l["from"] == "clinic.visits.doc_id" for l in v["links"])
    assert sorted(v["metadata"]) == ["dictionary.csv", "schema.yml"]


def test_semantic_model_alone_gives_an_ontology_marked_unchecked(tmp_path):
    from tests.unit.test_metadata import BIM
    layer = load(tmp_path, [])
    path = tmp_path / "model.bim"
    path.write_text(json.dumps(BIM), encoding="utf-8")
    oid = simple.create_and_build(layer, "Finance model", [], metadata=[str(path)])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {t["name"] for t in v["things"]} == {"Customer", "Sale"}
    assert v["links"] and v["links"][0]["from_thing"] == "Sale"
    assert v["calculations"][0]["name"] == "Total Sales"
    assert all(f["check"] == "unchecked" for t in v["things"] for f in t["fields"])
    assert v["version"] == 1


def test_ids_never_collide_with_screen_addresses(tmp_path):
    layer = load(tmp_path, ["iot"])
    assert simple.unique_id(layer.graph, "New") == "new-2"
    assert simple.unique_id(layer.graph, "All") == "all-2"
    assert simple.unique_id(layer.graph, "Plant sensors") == "plant-sensors"


def test_bad_inputs_leave_nothing_behind(tmp_path):
    layer = load(tmp_path, ["iot"])
    with pytest.raises(ValueError):
        simple.create_and_build(layer, "x", ["not_loaded"])
    with pytest.raises(ValueError):
        simple.create_and_build(layer, "x", [])
    with pytest.raises(ValueError):
        simple.create_and_build(layer, "x", ["iot"], metadata=[str(tmp_path / "nope.bim")])
    assert reg.list_ontologies(layer.graph) == []


# ------------------------------------------------------------- consumers
def test_excel_tables_and_xlsx_for_nexus(tmp_path):
    layer = load(tmp_path, ["iot"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI())["ontology"]
    data = simple.for_excel(layer.graph, oid)
    assert data["ontology"]["version"] == 1
    assert len(data["things"]) == 3 and len(data["fields"]) == 16
    row = next(r for r in data["fields"] if r["Column"] == "temp_c")
    assert row["Field"] == "Temperature" and row["Unit"] == "°C"
    assert row["Check"] == "Checked in data" and row["Set by"] == "AI, checked against data"
    assert {"From", "To", "Meaning", "Match"} <= set(data["links"][0])
    blob = simple.to_xlsx(layer.graph, oid)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        book = ElementTree.fromstring(z.read("xl/workbook.xml"))
        names = [s.get("name") for s in book.iter() if s.tag.endswith("sheet")]
        assert names == ["Things", "Fields", "Links", "About"]
        sheet = z.read("xl/worksheets/sheet2.xml").decode("utf-8")
        ElementTree.fromstring(sheet)
        assert "Temperature" in sheet and "°C" in sheet


def test_agents_read_the_same_published_meanings(tmp_path):
    layer = load(tmp_path, ["iot"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI())["ontology"]
    concepts = pub.list_concepts(layer.graph, oid)["concepts"]
    reading = next(c for c in concepts if c["label"] == "Sensor Reading")
    detail = pub.get_concept(layer.graph, oid, reading["name"])
    temp = next(p for p in detail["properties"] if p["column"].endswith("temp_c"))
    assert temp["label"] == "Temperature" and temp["unit"] == "°C"
    assert temp["check"] == "verified"
    column = pub.map_column(layer.graph, oid, "iot.readings.temp_c")
    assert column["label"] == "Temperature" and column["meaning"]


def test_delete_removes_only_the_ontology(tmp_path):
    layer = load(tmp_path, ["iot", "clinic"])
    keep = simple.create_and_build(layer, "Keep", ["clinic"])["ontology"]
    # Two sources: the identity step also writes the eo_crosswalk table.
    oid = simple.create_and_build(layer, "Sensors", ["iot", "clinic"])["ontology"]
    simple.add_context(layer, oid, "temp_c = Temperature")
    tables = [r[0] for r in layer.graph.sql(
        "SELECT DISTINCT table_name FROM information_schema.columns"
        " WHERE column_name = 'ontology_id' AND table_name LIKE 'eo_%'")]
    assert "eo_crosswalk" in tables and "eo_versions" in tables
    reg.delete_ontology(layer.graph, oid)
    assert [o["id"] for o in reg.list_ontologies(layer.graph)] == [keep]
    for table in tables:                          # nothing about it in ANY table
        assert layer.graph.one(f"SELECT count(*) FROM {table} WHERE ontology_id = ?",
                               [oid]) == 0, table
    assert layer.graph.one("SELECT count(*) FROM eo_ontologies WHERE id = ?", [oid]) == 0
    # The other ontology and the data itself are untouched.
    assert simple.view(layer.graph, keep)["summary"]["things"] == 3
    assert {"iot", "clinic"} <= set(layer.graph.source_ids())
    with pytest.raises(KeyError):
        reg.delete_ontology(layer.graph, oid)


def test_indirect_and_reverse_links_are_dropped(tmp_path):
    from api.service import MiddleLayer
    from tests.integration.simple_fixtures import write_csv
    folder = tmp_path / "shop"
    write_csv(folder / "orders.csv", [{"order_id": f"O{i:03d}", "placed": "2024-01-01"}
                                      for i in range(60)])
    write_csv(folder / "order_items.csv", [{"item_id": i, "order_id": f"O{i % 60:03d}",
                                            "qty": i % 4 + 1} for i in range(150)])
    write_csv(folder / "reviews.csv", [{"review_id": f"R{i:03d}", "order_id": f"O{i:03d}",
                                        "score": i % 5 + 1} for i in range(60)])
    layer = MiddleLayer(str(tmp_path / "shop.duckdb"))
    layer.add_source(str(folder), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    links = {(l["from"], l["to"]) for l in simple.view(layer.graph, oid)["links"]}
    assert ("shop.order_items.order_id", "shop.orders.order_id") in links
    assert ("shop.reviews.order_id", "shop.orders.order_id") in links
    assert not any(to == "shop.reviews.order_id" for _, to in links), links


def test_findings_speak_in_thing_names(tmp_path):
    from api.service import MiddleLayer
    from tests.integration.simple_fixtures import write_csv
    folder = tmp_path / "crm"
    rows = [{"cust_id": f"C{i:03d}", "addr_id": f"A{i:03d}"} for i in range(60)]
    rows += [{"cust_id": "C001", "addr_id": "A900"}]            # one customer twice
    write_csv(folder / "customers.csv", rows)
    layer = MiddleLayer(str(tmp_path / "crm.duckdb"))
    layer.add_source(str(folder), source="crm")
    oid = simple.create_and_build(layer, "CRM", ["crm"])["ontology"]
    for f in simple.view(layer.graph, oid)["findings"]:
        assert "crm.customers" not in f["detail"] and "value(s)" not in f["detail"]
