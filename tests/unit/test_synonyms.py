"""Metric synonyms: the words people use for a governed metric.

Snowflake, Databricks and dbt all attach synonyms to the semantic object
(research: docs/research/2026/03_semantic_layer.md). In Strata they live in
their own table so re-seeding a definition never wipes them, and detection
uses them so "sales" finds Revenue. A synonym may point at one metric only.
"""

from __future__ import annotations

import pytest

from context.question import detect_metric
from knowledge_graph.store import open_graph
from semantic import definitions as d


@pytest.fixture
def graph(tmp_path):
    g = open_graph(str(tmp_path / "syn.duckdb"))
    for name, title in (("revenue", "Revenue"), ("order_volume", "Order volume"),
                        ("refund_rate", "Refund rate")):
        d.upsert_metric(g, source="shop", name=name, title=title,
                        base_sql="SELECT 1 AS x", value_expr="SUM(x)")
    yield g
    g.close()


def test_new_metrics_have_no_synonyms(graph):
    assert d.get_definition(graph, "revenue", "shop")["synonyms"] == []


def test_set_synonyms_cleans_and_deduplicates(graph):
    saved = d.set_synonyms(graph, "revenue", "shop",
                           ["sales", " Sales ", "turnover", "", "  "])
    assert saved == ["sales", "turnover"]
    assert d.get_definition(graph, "revenue", "shop")["synonyms"] == ["sales", "turnover"]
    assert {m["name"]: m["synonyms"] for m in d.list_definitions(graph, "shop")}[
        "revenue"] == ["sales", "turnover"]


def test_synonyms_survive_reseeding_the_definition(graph):
    d.set_synonyms(graph, "revenue", "shop", ["sales"])
    d.upsert_metric(graph, source="shop", name="revenue", title="Revenue",
                    base_sql="SELECT 2 AS x", value_expr="SUM(x)")
    assert d.get_definition(graph, "revenue", "shop")["synonyms"] == ["sales"]


def test_empty_list_clears_synonyms(graph):
    d.set_synonyms(graph, "revenue", "shop", ["sales"])
    assert d.set_synonyms(graph, "revenue", "shop", []) == []


def test_add_synonym_appends_without_duplicates(graph):
    d.set_synonyms(graph, "revenue", "shop", ["sales"])
    assert d.add_synonym(graph, "revenue", "shop", "Turnover") == ["sales", "Turnover"]
    assert d.add_synonym(graph, "revenue", "shop", "SALES") == ["sales", "Turnover"]


def test_unknown_metric_is_a_key_error(graph):
    with pytest.raises(KeyError):
        d.set_synonyms(graph, "profit", "shop", ["margin"])


@pytest.mark.parametrize("clash", ["order volume", "Refund rate", "refund_rate"])
def test_a_synonym_cannot_be_another_metrics_name(graph, clash):
    with pytest.raises(ValueError, match="already"):
        d.set_synonyms(graph, "revenue", "shop", [clash])


def test_a_synonym_cannot_belong_to_two_metrics(graph):
    d.set_synonyms(graph, "revenue", "shop", ["sales"])
    with pytest.raises(ValueError, match="(?i)sales"):
        d.set_synonyms(graph, "order_volume", "shop", ["Sales"])


def test_too_long_or_too_many_synonyms_are_refused(graph):
    with pytest.raises(ValueError, match="long"):
        d.set_synonyms(graph, "revenue", "shop", ["x" * 61])
    with pytest.raises(ValueError, match="at most"):
        d.set_synonyms(graph, "revenue", "shop", [f"s{i}" for i in range(21)])


def test_synonyms_are_per_source(graph):
    d.upsert_metric(graph, source="hr", name="revenue", title="Revenue",
                    base_sql="SELECT 1 AS x", value_expr="SUM(x)")
    d.set_synonyms(graph, "revenue", "shop", ["sales"])
    assert d.get_definition(graph, "revenue", "hr")["synonyms"] == []


def test_detection_uses_synonyms_as_whole_words(graph):
    d.set_synonyms(graph, "revenue", "shop", ["sales", "net sales"])
    defs = d.list_definitions(graph, "shop")
    assert detect_metric(defs, "Why did West sales fall?")["name"] == "revenue"
    assert detect_metric(defs, "What were net sales in October?")["name"] == "revenue"
    assert detect_metric(defs, "salesforce leads") is None      # not a whole word


def test_names_and_titles_still_win_over_synonyms(graph):
    d.set_synonyms(graph, "revenue", "shop", ["refund"])  # odd, but allowed
    defs = d.list_definitions(graph, "shop")
    assert detect_metric(defs, "What is the refund rate?")["name"] == "refund_rate"
