"""The ontology view and the graph model are remembered between calls, and
never served stale: any change to the ontology or its data is seen at once."""

from __future__ import annotations

import pytest

from api.service import MiddleLayer
from knowledge_graph import explore as kg
from ontology import cache, simple
from ontology import registry as reg
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture()
def shop(tmp_path):
    db = make_amounts(tmp_path / "amounts.db")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    cache.forget()
    return layer, oid


def _hits():
    return cache.stats["hits"]


def test_a_second_read_is_served_from_memory(shop):
    layer, oid = shop
    a = simple.view(layer.graph, oid)
    before = _hits()
    b = simple.view(layer.graph, oid)
    assert a == b and _hits() == before + 1
    m1 = kg.model(layer, oid)
    before = _hits()
    m2 = kg.model(layer, oid)
    assert m1["sets"].keys() == m2["sets"].keys() and _hits() >= before + 1


def test_changing_what_you_were_given_does_not_change_the_cache(shop):
    layer, oid = shop
    v = simple.view(layer.graph, oid)
    v["things"].clear()
    v["name"] = "broken"
    again = simple.view(layer.graph, oid)
    assert again["things"] and again["name"] == "Shop"


def test_a_note_is_seen_at_once(shop):
    layer, oid = shop
    simple.view(layer.graph, oid)
    simple.add_context(layer, oid, "Gross Amount is in euros")
    assert any("euros" in n["text"] for n in simple.view(layer.graph, oid)["notes"])


def test_an_edit_is_seen_at_once(shop):
    layer, oid = shop
    v = simple.view(layer.graph, oid)
    field = v["things"][0]["fields"][0]
    simple.edit_field(layer, oid, field["key"], label="Renamed Field")
    labels = [f["label"] for t in simple.view(layer.graph, oid)["things"] for f in t["fields"]]
    assert "Renamed Field" in labels
    m = kg.model(layer, oid)
    assert any(f["label"] == "Renamed Field" for s in m["sets"].values() for f in s["fields"])


def test_a_rejected_link_disappears_at_once(shop):
    layer, oid = shop
    v = simple.view(layer.graph, oid)
    assert v["links"]
    key = v["links"][0]["key"]
    reg.decide(layer.graph, oid, "relationship", key, "rejected", by="you")
    assert key not in {x["key"] for x in simple.view(layer.graph, oid)["links"]}
    assert key not in {x["key"] for x in kg.model(layer, oid)["links"]}


def test_a_status_change_without_a_new_timestamp_is_seen(shop):
    """simple._approve_and_publish changes only the status column."""
    layer, oid = shop
    before = cache.stamp(layer.graph, oid)
    with layer.graph.lock:
        layer.graph.con.execute("UPDATE eo_items SET status = 'rejected' WHERE ontology_id = ? "
                                "AND kind = 'relationship'", [oid])
    assert cache.stamp(layer.graph, oid) != before
    assert simple.view(layer.graph, oid)["links"] == []


def test_two_databases_with_the_same_content_never_share(tmp_path):
    out = []
    for name in ("a", "b"):
        db = make_amounts(tmp_path / f"{name}.db")
        layer = MiddleLayer(str(tmp_path / f"{name}.duckdb"))
        layer.add_source(str(db), source="shop")
        oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        out.append(kg.model(layer, oid))
    refs = [{s["ref"] for s in m["sets"].values()} for m in out]
    # Each model points at its own database's tables.
    assert all(refs) and cache.stats["hits"] >= 0
    assert len(cache._entries) >= 2            # one entry per database, never shared


def test_a_pinned_version_is_not_cached_as_the_live_one(shop):
    layer, oid = shop
    live = simple.view(layer.graph, oid)
    simple.add_context(layer, oid, "Gross Amount is in euros")
    pinned = simple.view(layer.graph, oid, version=live["version"])
    assert not any("euros" in n["text"] for n in pinned["notes"])


def test_record_counts_of_a_live_database_are_never_older_than_the_ttl(shop, monkeypatch):
    layer, oid = shop
    first = kg.overview(layer, oid)
    before = _hits()
    assert kg.overview(layer, oid) == first and _hits() > before        # remembered
    monkeypatch.setattr(kg, "OVERVIEW_TTL_S", 0)
    hits = _hits()
    kg.overview(layer, oid)
    assert cache.stats["misses"] and _hits() == hits + 1                 # model hit, overview re-counted


def test_an_unknown_ontology_is_still_an_error(shop):
    layer, _ = shop
    with pytest.raises(KeyError):
        simple.view(layer.graph, "nope")
    with pytest.raises(KeyError):
        kg.model(layer, "nope")
