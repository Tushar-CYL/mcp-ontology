"""AI claims are checked against the data; names read like a person wrote them."""

from __future__ import annotations

import json

import pytest

from ontology import meaning as mn
from ontology.xlsx import workbook


def col(**kw):
    base = {"name": "x", "family": "text", "distinct": 10, "null_ratio": 0.0,
            "top_values": []}
    return {**base, **kw}


@pytest.mark.parametrize("table,source,expected", [
    ("olist_order_items_dataset", "olist", "Order Item"),
    ("olist_customers_dataset", "olist", "Customer"),
    ("readings", "iot", "Reading"),
    ("dim_customer", "", "Customer"),
    ("KNA1", "", "Kna1"),
    ("I_SalesDocumentItem", "salt", "Sales Document Item"),
])
def test_thing_names(table, source, expected):
    assert mn.thing_name(table, source) == expected


@pytest.mark.parametrize("role,column,rows,ref,samples,check", [
    ("identifier", col(distinct=100), 100, None, [], "verified"),
    ("identifier", col(distinct=3), 100, None, [], "conflict"),
    ("identifier", col(distinct=3), 100, "shop.customers", [], "verified"),
    ("reference", col(), 100, None, [], "unchecked"),
    ("amount", col(family="numeric", min=1.5, max=9.0), 100, None, [], "verified"),
    ("amount", col(family="text"), 100, None, [], "conflict"),
    ("date", col(family="temporal", min="2024-01-01", max="2024-02-01"), 9, None, [],
     "verified"),
    ("date", col(), 9, None, ["2024-01-01", "2024-03-05 10:00:00"], "verified"),
    ("date", col(), 9, None, ["abc"], "conflict"),
    ("flag", col(distinct=2), 50, None, [], "verified"),
    ("flag", col(distinct=7), 50, None, [], "conflict"),
    ("category", col(distinct=12), 5000, None, [], "verified"),
    ("category", col(distinct=4000), 5000, None, [], "conflict"),
    ("location", col(family="numeric", min=-97.7, max=135.5), 6, None, [], "verified"),
    ("location", col(family="numeric", min=0, max=5000), 6, None, [], "conflict"),
    ("name", col(), 5, None, [], "verified"),
])
def test_verify_checks_claims_against_the_profile(role, column, rows, ref, samples, check):
    assert mn.verify(role, column, rows, ref, samples)[0] == check


def test_engine_roles_for_common_shapes():
    assert mn.engine_role("amount_unclassified", col(name="geolocation_lat",
                                                     family="numeric"), False, 9) == "location"
    assert mn.engine_role("identifier", col(name="customer_id"), True, 9) == "reference"
    assert mn.engine_role("number", col(name="battery_pct", family="numeric",
                                        distinct=90), False, 900) == "measure"
    assert mn.engine_role("number", col(name="items_qty", family="numeric",
                                        distinct=9), False, 900) == "quantity"
    assert mn.engine_role("attribute", col(name="notes", distinct=900), False, 900) == "text"
    assert mn.engine_role("attribute", col(name="status", distinct=4), False, 900) == \
        "category"


def table_with(c):
    return {"key": "s.t", "table": "t", "source": "s", "rows": 100, "columns": [c]}


def test_precedence_metadata_over_ai_over_engine():
    c = col(name="fee", key="s.t.fee", family="numeric", distinct=80, min=1, max=9,
            property="number")
    ai = {"label": "Fee", "meaning": "What was charged.", "role": "amount", "unit": "EUR",
          "confidence": "high"}
    r = mn.decide_column(table_with(c), c, ai)
    assert (r["by"], r["role"], r["unit"], r["check"]) == ("ai", "amount", "EUR", "verified")
    given = {**c, "given": {"description": "Fee billed to the insurer", "unit": "USD"}}
    r = mn.decide_column(table_with(given), given, ai)
    assert r["by"] == "metadata" and r["meaning"] == "Fee billed to the insurer"
    assert r["unit"] == "USD"
    r = mn.decide_column(table_with(c), c, None)
    assert r["by"] == "engine" and r["meaning"]


class Reply:
    mock = False
    model = "m"

    def __init__(self, payload):
        self.payload, self.calls = payload, 0

    def complete(self, messages, max_tokens=0):
        self.calls += 1
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


def test_ask_ai_keeps_only_valid_answers_and_chunks_wide_tables(monkeypatch):
    monkeypatch.setattr(mn, "COLUMNS_PER_CALL", 2)
    cols = [col(name=n) for n in ("a", "b", "c")]
    client = Reply({"thing": {"name": "Widget", "description": "A widget"}, "columns": [
        {"name": "a", "label": "A", "meaning": "first", "role": "IDENTIFIER", "unit": "null"},
        {"name": "b", "label": "B", "role": "made-up"},
        {"name": "zzz", "label": "ignored"}]})
    out = mn.ask_ai(client, {}, {"table": "w", "source": "s", "rows": 3, "columns": cols},
                    [], [])
    assert client.calls == 2
    assert out["thing"]["name"] == "Widget"
    assert out["columns"]["a"]["role"] == "identifier" and out["columns"]["a"]["unit"] is None
    assert out["columns"]["b"]["role"] == ""
    assert "zzz" not in out["columns"]


def test_ai_switch_and_sample_setting(monkeypatch):
    monkeypatch.setenv("STRATA_AI", "off")
    assert mn.ai_enabled() is False
    monkeypatch.setenv("STRATA_AI_SAMPLES", "99")
    assert mn.sample_count() == 20
    monkeypatch.setenv("STRATA_AI_SAMPLES", "x")
    assert mn.sample_count() == 5


def test_workbook_is_valid_xlsx():
    import io
    import zipfile
    from xml.etree import ElementTree
    blob = workbook([("A", [{"x": 1, "y": "a<b & \x01c"}]), ("B", [])])
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            ElementTree.fromstring(z.read(name))
        assert "a&lt;b &amp; c" in z.read("xl/worksheets/sheet1.xml").decode()
    with pytest.raises(ValueError):
        workbook([("A", []), ("A", [])])


def test_a_key_others_point_at_stays_a_key_even_with_repeats():
    """SALT: Customer.ADDRESSID points at Address.ADDRESSID, but 9% of the
    address ids repeat. That is a key with a data problem, not free text."""
    c = col(name="ADDRESSID", key="salt.addr.ADDRESSID", distinct=1_634_707, property="identifier",
            referenced_by=["salt.i_customer"])
    t = {"key": "salt.addr", "table": "addr", "source": "salt", "rows": 1_788_887, "columns": [c]}
    ai = {"label": "Address ID", "meaning": "Id of the address.", "role": "identifier",
          "confidence": "high"}
    for answer in (ai, None):
        r = mn.decide_column(t, c, answer)
        assert r["role"] == "identifier" and r["check"] == "conflict"
        assert r["proof"].startswith("Customer points here as the key, but only 1,634,707")
        assert r["proof"].endswith("some records repeat")
