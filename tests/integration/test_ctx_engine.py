"""Context engineering, step by step (Nehme's method on Strata).

Shop (SQLite, declared keys): 200 customers, 1,000 orders (orders 1-10 point
at customer 999, which does not exist), order lines, 40 products."""

from __future__ import annotations

import pytest

from api.service import MiddleLayer
from context import engine as ctx
from ontology import simple
from tests.integration.test_declared_links import make_shop


class Writer:
    """A stand-in model for the final wording only."""

    mock = False
    model = "fake"

    def __init__(self, reply: str):
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, messages, max_tokens=600):
        self.prompts.append(messages[-1]["content"])
        return self.reply


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ctx")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(make_shop(tmp / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


def _view(shop):
    layer, oid = shop
    return simple.view(layer.graph, oid)


# ------------------------------------------------------------------ 1. link
def test_a_record_named_in_the_question_is_linked(shop):
    layer, oid = shop
    linked = ctx.link(layer, oid, "What did Customer 17 order?")
    assert [(r["set"], r["key"]) for r in linked["records"]] == [("shop.customer", "17")]


def test_the_word_before_an_id_says_which_thing(shop):
    """'order 3' is order 3, not customer 3 (found live: it linked customer 3)."""
    layer, oid = shop
    linked = ctx.link(layer, oid, "Who placed order 3?")
    assert [(r["set"], r["key"]) for r in linked["records"]] == [("shop.orders", "3")]


def test_a_bare_id_in_several_things_is_ambiguous_not_guessed(shop):
    layer, oid = shop
    linked = ctx.link(layer, oid, "what about 3?")
    assert linked["records"] == [] and linked["ambiguous"]


def test_an_id_alone_is_not_guessed_into_a_record_of_any_kind(shop):
    """'17' matches ids in several tables; it is linked only as an exact match."""
    layer, oid = shop
    linked = ctx.link(layer, oid, "tell me about 99999")
    assert linked["records"] == []


def test_a_note_synonym_links_a_field(shop):
    layer, oid = shop
    simple.add_context(layer, oid, "revenue = net_amount")
    linked = ctx.link(layer, oid, "What is the revenue of order 5?")
    via = {f["label"]: f["why"] for f in linked["fields"]}
    assert any("your note" in why for why in via.values()), via


def test_unknown_words_are_listed(shop):
    layer, oid = shop
    linked = ctx.link(layer, oid, "What is the churn of Customer 17?")
    assert "churn" in linked["unknown"]


# -------------------------------------------------------------- 2. traverse
def test_only_proven_links_within_two_steps(shop):
    layer, oid = shop
    view = _view(shop)
    linked = ctx.link(layer, oid, "What did Customer 17 order?", view)
    scope = ctx.traverse(layer, oid, linked, view)
    walk = scope["walks"][0]
    assert len(walk["steps"]) <= ctx.HOPS
    first = {x["thing"]: x["count"] for x in walk["steps"][0]["reached"]}
    assert list(first.values()) == [5]                      # customer 17 has 5 orders
    assert walk["records"] <= ctx.PER_RECORD * (1 + ctx.PER_RECORD * 2)
    assert set(scope["in_scope"]) | set(scope["not_looked_at"]) == {t["name"] for t in view["things"]}


# ---------------------------------------------------------------- 3. gather
def test_facts_carry_citations_and_mask_personal_data(shop):
    layer, oid = shop
    out = ctx.build(layer, oid, "Tell me about Customer 17")
    kept = out["steps"]["facts"]["kept"]
    assert kept and all(f["citation"] for f in kept)
    text = " ".join(f["text"] for f in kept)
    assert "c***@example.com" in text and "c17@example.com" not in text
    assert "Customer 17" in text


def test_a_broken_link_becomes_a_fact(shop):
    layer, oid = shop
    order = _view(shop)                                     # orders 1-10 -> customer 999
    out = ctx.build(layer, oid, "Who placed order 3?")
    texts = [f["text"] for f in out["steps"]["facts"]["kept"]]
    assert any("999" in t and "does not exist" in t for t in texts), texts
    assert order


def test_a_meaning_the_data_disagrees_with_is_quarantined(shop):
    """The validation gate: a field whose meaning failed its data check is
    reported, never handed to the model."""
    import copy
    layer, oid = shop
    view = copy.deepcopy(_view(shop))
    status = next(f for t in view["things"] for f in t["fields"] if f["column"] == "status")
    status.update(check="conflict", proof="the values are not numbers")
    question = "What is the status of order 5?"
    linked = ctx.link(layer, oid, question, view)
    assert [f["label"] for f in linked["fields"]] == [status["label"]]
    scope = ctx.traverse(layer, oid, linked, view)
    got = ctx.gather(layer, oid, question, linked, scope, view)
    assert any("data disagrees" in q["why"] for q in got["quarantined"]), got["quarantined"]
    assert not any(" means: " in f.text and status["label"] in f.text for f in got["facts"])


def test_only_the_field_the_question_names_is_linked(shop):
    layer, oid = shop
    linked = ctx.link(layer, oid, "What is the status of order 5?")
    assert [f["label"] for f in linked["fields"]] == ["Status"] or \
        [f["key"] for f in linked["fields"]] == ["shop.orders.status"]


# -------------------------------------------------------------- 4. assemble
def test_the_pack_fits_the_budget_and_says_what_was_dropped(shop):
    layer, oid = shop
    out = ctx.build(layer, oid, "Tell me about Customer 17", budget_chars=250)
    facts = out["steps"]["facts"]
    assert facts["chars"] <= 250
    assert facts["dropped"] and all(d["reason"] for d in facts["dropped"])
    assert len(out["context"].splitlines()) == len(facts["kept"])


def test_the_same_question_gives_the_same_pack(shop):
    layer, oid = shop
    a = ctx.build(layer, oid, "What did Customer 17 order?")["context"]
    b = ctx.build(layer, oid, "What did Customer 17 order?")["context"]
    assert a == b


# ---------------------------------------------------------------- 5. answer
def test_without_ai_the_context_is_still_built(shop):
    layer, oid = shop
    out = ctx.build(layer, oid, "What did Customer 17 order?")
    assert out["steps"]["answer"]["status"] == "no_ai" and out["context"]


def test_the_ai_sees_only_the_pack_and_cites_it(shop):
    layer, oid = shop
    w = Writer("Customer 17 has 5 orders [1].")
    out = ctx.build(layer, oid, "What did Customer 17 order?", client=w)
    assert out["steps"]["answer"]["status"] == "answered"
    assert w.prompts[0].endswith(out["context"])           # nothing else was sent


def test_an_invented_number_is_rejected(shop):
    layer, oid = shop
    w = Writer("Customer 17 spent 123456.78 in total [1].")
    out = ctx.build(layer, oid, "What did Customer 17 order?", client=w)
    a = out["steps"]["answer"]
    assert a["status"] == "unverified" and 123456.78 in a["unsupported_numbers"]


def test_not_enough_evidence_is_said(shop):
    layer, oid = shop
    w = Writer("NOT ENOUGH: no facts about refunds.")
    out = ctx.build(layer, oid, "What refunds did Customer 17 get?", client=w)
    assert out["steps"]["answer"] == {"status": "not_enough", "text": "no facts about refunds.",
                                      "cited": []}


def test_the_version_and_data_time_are_reported(shop):
    layer, oid = shop
    out = ctx.build(layer, oid, "Tell me about Customer 17")
    assert out["ontology"]["version"] and out["data_as_of"]


def test_empty_and_huge_questions_are_refused(shop):
    layer, oid = shop
    with pytest.raises(ctx.ContextError):
        ctx.build(layer, oid, "   ")
    with pytest.raises(ctx.ContextError):
        ctx.build(layer, oid, "x" * 1001)


# ------------------------------------------ found live on Olist and CSKG
def test_a_value_in_the_data_is_linked_with_its_count(shop):
    """'customers in GB': GB is a Country value, not a record (live: 'sao
    paulo' was not understood, so the computed total ignored the filter)."""
    layer, oid = shop
    linked = ctx.link(layer, oid, "How many orders from customers in GB?")
    v = linked["values"]
    assert v and v[0]["value"] == "GB" and v[0]["records"] == 100
    assert "gb" not in linked["unknown"]
    out = ctx.build(layer, oid, "How many orders from customers in GB?")
    assert any("100 Customer records have" in f["text"] for f in out["steps"]["facts"]["kept"])


def test_the_value_filter_is_passed_to_the_query_writer(shop, monkeypatch):
    layer, oid = shop
    seen = {}

    def fake_ask(layer, oid, question, client=None, max_rows=10, things=None):
        seen["q"] = question
        seen["things"] = things
        return {"rows": [[42]], "columns": ["orders"], "sql": "SELECT 42"}
    monkeypatch.setattr(ctx.ask, "ask", fake_ask)
    from agent import quick_numbers
    monkeypatch.setattr(quick_numbers, "compute", lambda *a, **k: None)   # the AI path
    ctx.build(layer, oid, "How many orders from customers in GB?", client=Writer("42 orders [1]."))
    assert "Filter:" in seen["q"] and "country = 'GB'" in seen["q"]
    assert "Customer" in seen["things"]                      # scope passed, not re-guessed


def test_a_word_is_not_split_off_a_name_that_has_no_id():
    """'methods neural' must not become 'neural' inside Method (live CSKG bug)."""
    assert not ctx._id_like("neural") and ctx._id_like("17") and ctx._id_like("00010242fe8c5a6d")


def test_the_records_linked_to_it_are_summarised(shop):
    layer, oid = shop
    out = ctx.build(layer, oid, "What is in order 500?")
    texts = [f["text"] for f in out["steps"]["facts"]["kept"]]
    assert any("(linked to" in t for t in texts), texts


def test_records_two_steps_away_get_a_line_too(shop):
    """An order's product sits two steps away (order -> line -> product)."""
    layer, oid = shop
    out = ctx.build(layer, oid, "What is in order 500?", budget_chars=4000)
    texts = [f["text"] for f in out["steps"]["facts"]["kept"]]
    assert any("(2 steps from" in t and "Product" in t for t in texts), texts
    assert not any("Customer Customer" in t or "Order Order" in t for t in texts)


def test_a_generic_word_alone_does_not_link_a_field(shop):
    """'value' must not link every *_value column; 'net amount' links net_amount."""
    from context.engine import GENERIC
    assert "value" in GENERIC
    layer, oid = shop
    linked = ctx.link(layer, oid, "What is the net amount of order 5?")
    assert "shop.orders.net_amount" in [f["key"] for f in linked["fields"]]
    linked = ctx.link(layer, oid, "What is the id of order 5?")
    assert linked["fields"] == []                            # "id" alone names no field


def test_list_numbering_is_not_a_number_claim(shop):
    """Live: '1. credit_card ... 2. boleto ...' was rejected for numbers 1-5."""
    layer, oid = shop
    w = Writer("Customer 17 orders:\n1. Order 16 [1]\n2. Order 216 [1]\nTop 3 shown.")
    out = ctx.build(layer, oid, "What did Customer 17 order?", client=w)
    assert out["steps"]["answer"]["status"] == "answered", out["steps"]["answer"]


def test_the_computed_fact_says_its_filter(shop, monkeypatch):
    """Live: the AI distrusted a correct filtered total because the fact
    did not say it was filtered."""
    layer, oid = shop
    monkeypatch.setattr(ctx.ask, "ask", lambda *a, **k: {
        "rows": [[100]], "columns": ["orders"], "sql": "SELECT 100", "things": ["Order", "Customer"]})
    from agent import quick_numbers
    monkeypatch.setattr(quick_numbers, "compute", lambda *a, **k: None)   # the AI path
    out = ctx.build(layer, oid, "How many orders from customers in GB?", client=Writer("100 orders [1]."))
    fact = next(f["text"] for f in out["steps"]["facts"]["kept"] if f["text"].startswith("Computed"))
    assert "filtered to Country = GB" in fact and "Order, Customer" in fact


def test_a_counting_question_is_answered_by_strata_without_ai_sql(shop):
    """One engine: Context counts the way the agents do - Strata's own query
    over proven links, before any AI-written SQL. It counts the thing named
    after 'how many' (orders), filtered by the customer's country."""
    layer, oid = shop
    out = ctx.build(layer, oid, "How many orders from customers in GB?")
    f = out["steps"]["facts"]
    assert f["table"]["rows"] == [[495]], f["table"]
    fact = next(x["text"] for x in f["kept"] if x["citation"] == "sql:strata")
    assert "Order" in fact and "GB" in fact


def test_a_two_letter_code_filters_only_when_written_as_a_code(shop):
    """Live on SALT: 'How many customers in DE?' ignored DE (values under 3
    characters were skipped) and gave every customer. Found by the report check."""
    layer, oid = shop
    f = ctx.build(layer, oid, "How many customers in GB?")["steps"]["facts"]
    assert f["table"]["rows"] == [[100]], f["table"]
