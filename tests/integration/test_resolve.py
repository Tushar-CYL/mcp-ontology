"""Cross-source identity: candidates are proposed, never silently merged."""

from __future__ import annotations

import pytest

from knowledge_graph.build import build
from knowledge_graph.resolve import (approve, candidates, class_stem, explain,
                                     name_similarity, resolve)
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover


@pytest.fixture
def three_systems(tmp_path):
    """The same products in ERP and PIM, plus an unrelated customer table."""
    erp = tmp_path / "erp"
    erp.mkdir()
    (erp / "products.csv").write_text(
        "product_id,name,price\np1,A-pack,10.0\np2,B-pack,20.0\np3,C-pack,30.0\n",
        encoding="utf-8")
    pim = tmp_path / "pim"
    pim.mkdir()
    (pim / "products.csv").write_text(
        "product_id,title,category\np1,A-pack,Office\np2,B-pack,Home\n",
        encoding="utf-8")
    crm = tmp_path / "crm"
    crm.mkdir()
    (crm / "customers.csv").write_text(
        "customer_id,name\np1,Ada\np2,Grace\n", encoding="utf-8")
    return erp, pim, crm


def _build(tmp_path, folders):
    g = open_graph(tmp_path / "g.duckdb")
    for source, folder in folders:
        schema = connect(str(folder))
        build(g, schema, discover(schema), source=source)
    return g


class TestNameSimilarity:
    def test_same_name_is_strong(self):
        assert name_similarity("Product", "Product") >= 0.9

    def test_vendor_prefix_is_ignored(self):
        assert name_similarity("ErpProduct", "PimProduct") >= 0.6

    def test_different_things_do_not_match(self):
        assert name_similarity("Customer", "Product") == 0.0

    def test_stem_keeps_the_meaningful_tail(self):
        assert class_stem("ErpProduct") == "product"
        assert class_stem("OrderItem") == "order_item"


class TestResolve:
    def test_shared_keys_across_sources_become_candidates(self, three_systems,
                                                          tmp_path):
        g = _build(tmp_path, [("erp", three_systems[0]),
                              ("pim", three_systems[1]),
                              ("crm", three_systems[2])])
        found = resolve(g)
        assert found, "the two product tables share keys and a class name"
        assert all(c.method == "same_key+name_similarity" for c in found)
        # p1 and p2 are in both product tables; p3 only in ERP.
        pairs = {(c.a_key, c.b_key) for c in found}
        assert ("p1", "p1") in pairs and ("p2", "p2") in pairs
        assert ("p3", "p3") not in pairs
        assert len(candidates(g)) == len(found)

    def test_candidates_never_merge_nodes(self, three_systems, tmp_path):
        g = _build(tmp_path, [("erp", three_systems[0]),
                              ("pim", three_systems[1])])
        before = g.one("SELECT count(*) FROM nodes")
        resolve(g)
        assert g.one("SELECT count(*) FROM nodes") == before
        assert g.class_code("Product", "erp") != g.class_code("Product", "pim")

    def test_unrelated_classes_with_the_same_ids_are_not_linked(
            self, three_systems, tmp_path):
        g = _build(tmp_path, [("erp", three_systems[0]),
                              ("crm", three_systems[2])])
        resolve(g)
        # Customer keys p1/p2 happen to overlap product keys, but the classes
        # describe different things.
        assert not any(c.a_class == c.b_class or
                       {c.a_class, c.b_class} == {"Customer"}
                       for c in candidates(g) if c["a_key"] in {"p1", "p2"})

    def test_explain_returns_both_directions(self, three_systems, tmp_path):
        g = _build(tmp_path, [("erp", three_systems[0]),
                              ("pim", three_systems[1])])
        resolve(g)
        info = explain(g, "erp", "Product", "p1")
        assert info["matches"], "the p1 product exists in pim too"
        other = info["matches"][0]["other"]
        assert other["source"] == "pim"
        assert other["class"] == "Product"
        assert other["key"] == "p1"
        assert 0 < info["matches"][0]["confidence"] <= 1

    def test_approval_changes_only_the_link_status(self, three_systems,
                                                   tmp_path):
        g = _build(tmp_path, [("erp", three_systems[0]),
                              ("pim", three_systems[1])])
        resolve(g)
        item = candidates(g)[0]
        approve(g, item["a_source"], item["a_class"], item["a_key"],
                item["b_source"], item["b_class"], item["b_key"])
        statuses = {c["status"] for c in candidates(g, status=None)}
        assert "approved" in statuses

    def test_resolve_is_idempotent(self, three_systems, tmp_path):
        g = _build(tmp_path, [("erp", three_systems[0]),
                              ("pim", three_systems[1])])
        first = len(resolve(g))
        second = len(resolve(g))
        assert first == second
        assert len(candidates(g)) == second
