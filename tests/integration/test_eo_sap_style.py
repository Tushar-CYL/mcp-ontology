"""The accelerator on SAP-style exports (shaped like the real SALT dataset).

Found when the accelerator first ran on SALT: column names are run-together
capitals with no id suffix (SALESDOCUMENT, SOLDTOPARTY), the customer number
is an ALTERNATE key (the table is keyed on ADDRESSID because two customer
numbers repeat), and the ontology covers one source. The synthetic BI/MDM
scenario hid all three. This fixture reproduces them on a small scale.
"""

from __future__ import annotations

import csv
import random

import pytest

from api.service import MiddleLayer
from ontology import accelerator, maturity
from ontology import registry as reg


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture(scope="module")
def sap(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sap")
    folder = tmp / "salt_like"
    folder.mkdir()
    rnd = random.Random(3)
    regions = {"DE": ["BY", "BW", "NW"], "FR": ["IDF", "ARA"], "US": ["CA", "NY", "TX"]}
    addresses = []
    for i in range(1000):
        country = rnd.choice(list(regions))
        addresses.append([f"A{i:06d}", country, rnd.choice(regions[country])])
    for i in range(1000, 1020):                       # missing country written as ''
        addresses.append([f"A{i:06d}", "", ""])
    _write(folder / "i_addrorgnamepostaladdress.csv", ["ADDRESSID", "COUNTRY", "REGION"],
           addresses)
    customers = [[f"{1000 + i:07d}", f"A{i * 4:06d}"] for i in range(200)]
    customers.append([customers[5][0], "A000999"])       # a repeated customer number
    customers.append([customers[9][0], "A000998"])
    _write(folder / "i_customer.csv", ["CUSTOMER", "ADDRESSID"], customers)
    docs = []
    for i in range(300):
        currency = "DEM" if i < 3 else "RMB" if i < 5 else rnd.choice(["EUR", "USD", "EGP"])
        docs.append([f"{9000000 + i}", rnd.choice(["1010", "1020", "2010"]),
                     f"2024-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}", currency])
    _write(folder / "salesdocuments.csv",
           ["SALESDOCUMENT", "SALESORGANIZATION", "CREATIONDATE", "TRANSACTIONCURRENCY"],
           docs)
    items = []
    for d in docs:
        sold_to = rnd.choice(customers[:200])[0]
        for pos in range(rnd.randint(1, 5)):
            items.append([d[0], f"{(pos + 1) * 10:06d}", sold_to, rnd.choice(["P1", "P2"])])
    _write(folder / "i_salesdocumentitem.csv",
           ["SALESDOCUMENT", "SALESDOCUMENTITEM", "SOLDTOPARTY", "PLANT"], items)

    layer = MiddleLayer(str(tmp / "sap.duckdb"))
    layer.add_source(str(folder), source="salt_like")
    reg.create(layer.graph, "sap", name="SAP sales", problem="sales documents",
               sources=[{"source_id": "salt_like", "role": "source_system",
                         "owner_team": "SAP SD"}])
    run = accelerator.run(layer, "sap")
    yield layer, run
    layer.close()


def _concepts(layer):
    return {i["key"]: i["payload"] for i in reg.items(layer.graph, "sap", kind="concept")}


def _rels(layer):
    return {(i["payload"]["from"], i["payload"]["to"]): i["payload"]
            for i in reg.items(layer.graph, "sap", kind="relationship")}


def _prop(layer, column):
    return reg.get_item(layer.graph, "sap", "mapping", column)["payload"]["property"]


def test_concept_names_are_readable(sap):
    layer, _ = sap
    assert set(_concepts(layer)) == {"SalesDocument", "SalesDocumentItem", "Customer",
                                     "AddrOrgNamePostalAddress"}


def test_links_without_id_suffixes_are_found(sap):
    layer, _ = sap
    rels = _rels(layer)
    item_doc = rels[("salt_like.i_salesdocumentitem.SALESDOCUMENT",
                     "salt_like.salesdocuments.SALESDOCUMENT")]
    assert item_doc["cardinality"] == "many-to-one" and item_doc["required"]


def test_links_to_an_alternate_key_are_found(sap):
    layer, _ = sap
    rels = _rels(layer)
    assert ("salt_like.i_salesdocumentitem.SOLDTOPARTY",
            "salt_like.i_customer.CUSTOMER") in rels
    assert ("salt_like.i_customer.ADDRESSID",
            "salt_like.i_addrorgnamepostaladdress.ADDRESSID") in rels


def test_low_cardinality_codes_never_become_links(sap):
    layer, _ = sap
    for frm, _to in _rels(layer):
        assert not frm.endswith((".PLANT", ".SALESORGANIZATION", ".TRANSACTIONCURRENCY",
                                 ".COUNTRY", ".REGION"))


def test_sap_field_names_get_meaning(sap):
    layer, _ = sap
    assert _prop(layer, "salt_like.salesdocuments.SALESORGANIZATION") == "sales_organization"
    assert _prop(layer, "salt_like.salesdocuments.TRANSACTIONCURRENCY") == "currency"
    assert _prop(layer, "salt_like.salesdocuments.CREATIONDATE").endswith("_date")
    assert _prop(layer, "salt_like.i_salesdocumentitem.PLANT") == "plant"
    assert _prop(layer, "salt_like.i_salesdocumentitem.SOLDTOPARTY") == "identifier"
    assert _prop(layer, "salt_like.i_addrorgnamepostaladdress.COUNTRY") == "country"


def test_repeated_business_keys_are_a_finding(sap):
    layer, _ = sap
    found = [i["payload"] for i in reg.items(layer.graph, "sap", kind="finding")
             if i["payload"]["type"] == "duplicate_business_key"]
    assert found and found[0]["column"] == "salt_like.i_customer.CUSTOMER"
    assert found[0]["repeated_values"] == 2


def test_region_sits_under_country(sap):
    layer, _ = sap
    hier = [i["payload"] for i in reg.items(layer.graph, "sap", kind="hierarchy")]
    assert any(h["levels"] == ["country", "region"] for h in hier)


def test_a_single_source_ontology_reaches_level_one(sap):
    layer, _ = sap
    assert maturity.score(layer.graph, "sap")["level"] == 1


def _rule(layer, key):
    return reg.get_item(layer.graph, "sap", "rule", key)["payload"]


def test_currency_rule_knows_every_iso_code_and_names_legacy_ones(sap):
    layer, _ = sap
    r = _rule(layer, "allowed:salt_like.salesdocuments.TRANSACTIONCURRENCY")
    assert r["violations"] == 5                      # EGP is valid ISO 4217
    offending = {o["value"]: o for o in r["offending"]}
    assert offending["DEM"]["count"] == 3 and offending["DEM"]["label"] == "withdrawn ISO code"
    assert offending["RMB"]["label"] == "not an ISO code"


def test_blank_values_are_counted_as_missing_not_invalid(sap):
    layer, _ = sap
    r = _rule(layer, "allowed:salt_like.i_addrorgnamepostaladdress.COUNTRY")
    assert r["violations"] == 0
    assert r["blank"] == 20


def test_a_column_other_tables_point_at_is_an_identifier(sap):
    layer, _ = sap
    assert _prop(layer, "salt_like.i_customer.CUSTOMER") == "identifier"
