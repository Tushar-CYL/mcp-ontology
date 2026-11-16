"""Suggestions taken from the data itself: notes for the ontology, questions,
metrics in words and values to search. Never a generic placeholder; every
suggestion names a real thing, field or value of THIS data. The AI may pick and
complete them, but anything it invents is dropped."""

from __future__ import annotations

import json

import pytest

from api.service import MiddleLayer
from ontology import simple, suggest
from semantic import model as sem
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture()
def shop(tmp_path):
    db = make_amounts(tmp_path / "amounts.db")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    suggest.forget()
    return layer, oid


def _names(layer, oid) -> set[str]:
    v = simple.view(layer.graph, oid)
    out = {t["name"].lower() for t in v["things"]}
    for t in v["things"]:
        for f in t["fields"]:
            out |= {str(f["label"]).lower(), str(f["column"]).lower()}
    return out


def _mentions_real(text: str, names: set[str]) -> bool:
    low = text.lower()
    return any(n and len(n) > 2 and n in low for n in names)


# ------------------------------------------------------------- notes
def test_note_suggestions_come_from_this_data(shop):
    layer, oid = shop
    out = suggest.suggest(layer, oid, "note")
    texts = [s["text"] for s in out["suggestions"]]
    assert 3 <= len(texts) <= 5, texts
    assert len(set(texts)) == len(texts)                       # no duplicates
    assert all("Rows where" not in t for t in texts)           # no generic filler
    names = _names(layer, oid)
    assert all(_mentions_real(t, names) for t in texts), texts
    assert all(s["why"] for s in out["suggestions"])            # each says why, from the data
    # The data has a "cancelled" status next to money: ask whether it counts.
    assert any("cancelled" in t for t in texts), texts
    # Money with no currency: ask for it.
    assert any(" is in " in t for t in texts), texts
    assert out["method"] == "data"


def test_a_field_already_explained_in_a_note_is_not_suggested_again(shop):
    layer, oid = shop
    first = suggest.suggest(layer, oid, "note")["suggestions"]
    money = next(s for s in first if " is in " in s["text"])
    label = money["text"].split(" is in ")[0]
    simple.add_context(layer, oid, f"{label} is in euros")
    again = [s["text"] for s in suggest.suggest(layer, oid, "note")["suggestions"]]
    assert not any(t.startswith(label + " is in") for t in again), again


class FakeAI:
    mock = False

    def __init__(self, reply: dict | Exception):
        self.reply, self.calls = reply, 0

    def complete(self, messages, max_tokens=600):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return json.dumps(self.reply)


def test_the_ai_picks_and_completes_but_cannot_invent(shop, monkeypatch):
    layer, oid = shop
    monkeypatch.setenv("STRATA_AI", "on")
    ai = FakeAI({"suggestions": [
        {"text": "Gross Amount is in Indian rupees", "why": "country values include IN"},
        {"text": "Sensor Reading means temperature", "why": "invented"},          # not in this data
        {"text": "Orders with status cancelled do not count in revenue", "why": "cancelled orders exist"},
    ]})
    out = suggest.suggest(layer, oid, "note", client=ai)
    texts = [s["text"] for s in out["suggestions"]]
    assert out["method"] == "ai"
    assert "Gross Amount is in Indian rupees" in texts
    assert not any("Sensor Reading" in t for t in texts)
    assert len(texts) >= 3                                     # topped up from the data
    suggest.suggest(layer, oid, "note", client=ai)
    assert ai.calls == 1                                       # cached until the ontology changes


def test_an_ai_failure_falls_back_to_the_data(shop, monkeypatch):
    layer, oid = shop
    monkeypatch.setenv("STRATA_AI", "on")
    out = suggest.suggest(layer, oid, "note", client=FakeAI(RuntimeError("429")))
    assert out["method"] == "data" and len(out["suggestions"]) >= 3


# ------------------------------------------------- the other layers
def test_questions_name_real_things_and_values(shop):
    layer, oid = shop
    qs = [s["text"] for s in suggest.suggest(layer, oid, "ask")["suggestions"]]
    assert 3 <= len(qs) <= 5 and all(q.endswith("?") for q in qs), qs
    names = _names(layer, oid)
    assert all(_mentions_real(q, names) for q in qs), qs
    assert any(v in q.lower() for q in qs for v in ("paid", "shipped", "cancelled")), qs


def test_metric_suggestions_are_definitions_over_real_fields(shop):
    layer, oid = shop
    sem.propose(layer, oid)
    ms = [s["text"] for s in suggest.suggest(layer, oid, "metric")["suggestions"]]
    assert ms, ms
    assert any("paid" in m.lower() or "shipped" in m.lower() for m in ms), ms
    assert all(_mentions_real(m, _names(layer, oid)) for m in ms), ms


def test_search_suggestions_are_real_values_and_never_personal(shop):
    layer, oid = shop
    vals = [s["text"] for s in suggest.suggest(layer, oid, "search")["suggestions"]]
    assert vals and any(v in ("IN", "GB", "US", "SMB", "Enterprise", "paid", "shipped") for v in vals), vals
    assert not any(v.startswith("Customer ") for v in vals)   # names are personal data


def test_unknown_kind_is_refused(shop):
    layer, oid = shop
    with pytest.raises(ValueError):
        suggest.suggest(layer, oid, "poem")


# -------------------------------------- a note reaches the semantic layer
def test_a_note_naming_a_metric_becomes_its_other_name(shop):
    layer, oid = shop
    sem.propose(layer, oid)
    simple.add_context(layer, oid, "revenue = Gross Amount")
    card = sem.card(layer, oid, "total_gross_amount")
    assert "revenue" in card["synonyms"]
    rec = sem.receipt(layer, oid, "total_gross_amount")
    assert any("Gross Amount" in n for n in rec["notes"])


def test_ai_suggestions_must_read_well_and_match_their_filter(shop, monkeypatch):
    """Live on Olist the AI named a metric 'Delivered ...' while filtering on
    credit_card, and wrote questions full of column names and value lists."""
    layer, oid = shop
    monkeypatch.setenv("STRATA_AI", "on")
    ai = FakeAI({"suggestions": [
        {"text": "Paid gross is the total Gross Amount of Order records with Status shipped", "why": "x"},
        {"text": "Shipped gross is the total Gross Amount of Order records with Status shipped", "why": "y"},
    ]})
    texts = [s["text"] for s in suggest.suggest(layer, oid, "metric", client=ai)["suggestions"]]
    assert not any(t.startswith("Paid gross") for t in texts), texts
    assert "Shipped gross is the total Gross Amount of Order records with Status shipped" in texts
    suggest.forget()
    ai = FakeAI({"suggestions": [
        {"text": "What is the total gross_amount per status (paid, shipped, cancelled)?", "why": "x"},
        {"text": "What is the total Gross Amount per Status?", "why": "y"},
    ]})
    qs = [s["text"] for s in suggest.suggest(layer, oid, "ask", client=ai)["suggestions"]]
    assert "What is the total Gross Amount per Status?" in qs
    assert not any("gross_amount" in q for q in qs), qs


def test_sequence_numbers_are_never_money(tmp_path):
    import sqlite3
    db = tmp_path / "p.db"
    s = sqlite3.connect(db)
    s.executescript("""create table payment(id integer primary key, payment_sequential integer,
                                            payment_value real, status text);""")
    s.executemany("insert into payment values(?,?,?,?)",
                  [(i, 1 + i % 3, 10.0 + i, ["paid", "failed"][i % 2]) for i in range(1, 301)])
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="p")
    oid = simple.create_and_build(layer, "P", ["p"])["ontology"]
    suggest.forget()
    all_text = " ".join(x["text"] for k in ("note", "metric", "ask")
                        for x in suggest.suggest(layer, oid, k)["suggestions"])
    assert "Sequential" not in all_text and "sequential" not in all_text, all_text


def test_a_value_that_means_itself_is_not_a_suggestion():
    """Live: the AI suggested '"SP" means SP'."""
    from ontology.suggest import _valid
    facts, names = {"fields": []}, {"state"}
    assert not _valid("note", 'In State, "SP" means SP and "MG" means MG', names, facts)
    assert _valid("note", 'In State, "SP" means São Paulo and "MG" means Minas Gerais', names, facts)
    assert _valid("note", 'In State, "SP" means ... and "MG" means ...', names, facts)
