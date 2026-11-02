"""A triple-store folder (entities + relations + train/test/valid splits).

This is the CSKG-style export. Before this support, the generic reader made six
unrelated classes and zero links; the correct graph is one Entity class and one
relation per predicate.
"""

from __future__ import annotations

import pytest

from context.assemble import build_context
from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover

ENTITIES = "0\tverification\n1\tformal_method\n2\tcontrol_system\n"
RELATIONS = "0\tsupportsMethod\n1\tusesMaterial\n2\tknows\n"
TRIPLES = "0\t0\t1\n1\t1\t2\n2\t2\t0\n0\t2\t2\n"
TRAIN = "0\t0\t1\n"
TEST = "1\t1\t2\n"
VALID = "2\t2\t0\n"


@pytest.fixture
def triple_folder(tmp_path):
    folder = tmp_path / "cskg"
    folder.mkdir()
    (folder / "entities.txt").write_text(ENTITIES, encoding="utf-8")
    (folder / "relations.txt").write_text(RELATIONS, encoding="utf-8")
    (folder / "triples.txt").write_text(TRIPLES, encoding="utf-8")
    (folder / "train.txt").write_text(TRAIN, encoding="utf-8")
    (folder / "test.txt").write_text(TEST, encoding="utf-8")
    (folder / "valid.txt").write_text(VALID, encoding="utf-8")
    return folder


class TestDetection:
    def test_the_folder_is_read_as_a_triple_store(self, triple_folder):
        schema = connect(str(triple_folder))
        names = {t.name for t in schema.tables}
        assert names == {"entities", "relations", "triples"}
        assert schema.triples["relations"] == "relations"
        assert schema.warnings and "triple-store" in schema.warnings[0]

    def test_lookup_tables_are_hidden_from_the_ontology(self, triple_folder):
        onto = discover(connect(str(triple_folder)))
        assert set(onto.classes) == {"Entity"}
        assert {"supportsMethod", "usesMaterial", "knows"} <= set(onto.relations)
        assert all(r.custom for r in onto.relations.values())
        assert all(r.domain == r.range == "Entity"
                   for r in onto.relations.values())

    def test_an_ordinary_folder_is_not_mistaken_for_triples(self, tmp_path):
        folder = tmp_path / "plain"
        folder.mkdir()
        (folder / "customers.csv").write_text("id,name\n1,Ada\n", encoding="utf-8")
        schema = connect(str(folder))
        assert schema.triples is None
        assert {t.name for t in schema.tables} == {"customers"}


class TestBuild:
    def test_entities_and_typed_edges_are_built(self, triple_folder, tmp_path):
        schema = connect(str(triple_folder))
        onto = discover(schema)
        g = open_graph(tmp_path / "triples.duckdb")
        stats = build(g, schema, onto, source="cskg")
        assert g.count_class("Entity") == 3
        assert stats["edges"] >= 3
        assert g.count_relation("supportsMethod") == 1
        assert g.count_relation("knows") == 2
        assert g.dangling_edges() == 0

    def test_a_cycle_is_allowed(self, triple_folder, tmp_path):
        schema = connect(str(triple_folder))
        g = open_graph(tmp_path / "loops.duckdb")
        build(g, schema, discover(schema), source="cskg")
        # 0 -knows-> 2 and 2 -knows-> 0: a cycle must not hang the build.
        assert g.count_relation("knows") == 2
        assert g.reach("Entity", "0", "knows", depth=3) >= {"Entity:2"}

    def test_context_can_walk_the_typed_edges(self, triple_folder, tmp_path):
        schema = connect(str(triple_folder))
        onto = discover(schema)
        g = open_graph(tmp_path / "ctx.duckdb")
        build(g, schema, onto, source="cskg")
        out = build_context(g, [("cskg", schema, onto)],
                            entity=("cskg", "Entity", "0"),
                            budget_chars=1200)
        assert any("links to" in fact["text"] for fact in out["facts"])
        assert any(fact["provenance"] == "measured" for fact in out["facts"])

    def test_the_same_graph_is_not_rebuilt(self, triple_folder, tmp_path):
        from knowledge_graph.build import is_current
        schema = connect(str(triple_folder))
        onto = discover(schema)
        g = open_graph(tmp_path / "warm.duckdb")
        build(g, schema, onto, source="cskg")
        assert is_current(g, schema, onto, source="cskg")
