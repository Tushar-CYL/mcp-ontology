"""A triple store loaded into a graph that already holds other big sources.

Found in use: data/raw/benchmark/cskg_dataset_sup_3 (91 MB, 188 relations)
loaded in 7 seconds into an empty graph, but ran DuckDB out of memory
(6.2 GiB) in the shared platform graph. Each of the 188 per-relation inserts
anti-joined against EVERY edge in the graph - tens of millions from other
sources - to skip duplicates that cannot exist (the source's edges are
cleared first and the staged triples are already distinct).
"""

from __future__ import annotations

import random

import pytest

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.discover import discover

RELATIONS = 60
ENTITIES = 3000
TRIPLES = 20000


@pytest.fixture
def triple_folder(tmp_path):
    rnd = random.Random(5)
    folder = tmp_path / "cskg_like"
    folder.mkdir()
    (folder / "entities.txt").write_text(
        "".join(f"{i}\tthing_{i}\n" for i in range(ENTITIES)), encoding="utf-8")
    (folder / "relations.txt").write_text(
        "".join(f"{i}\trel{i}\n" for i in range(RELATIONS)), encoding="utf-8")
    rows = {(rnd.randrange(ENTITIES), rnd.randrange(RELATIONS), rnd.randrange(ENTITIES))
            for _ in range(TRIPLES)}
    (folder / "triples.txt").write_text(
        "".join(f"{h}\t{r}\t{t}\n" for h, r, t in sorted(rows)), encoding="utf-8")
    return folder, len(rows)


def _fill_with_another_source(graph, edges: int) -> None:
    """Millions of edges belonging to some other source, as in the platform graph."""
    graph.con.execute(f"""
        INSERT INTO edges (src, rel, dst, source_id, valid_from, valid_to)
        SELECT i, i % 50, i + 1, 'someone_else', '-infinity'::TIMESTAMP, NULL
        FROM range({edges}) t(i)""")


def test_a_triple_store_builds_beside_millions_of_other_edges(tmp_path, triple_folder):
    folder, distinct = triple_folder
    graph = open_graph(str(tmp_path / "shared.duckdb"))
    try:
        _fill_with_another_source(graph, 6_000_000)
        graph.con.execute("SET memory_limit='250MB'")
        graph.con.execute("SET threads=2")
        schema = connect(str(folder))
        onto = discover(schema)
        build(graph, schema, onto, source="cskg_like")
        made = graph.one("SELECT count(*) FROM edges WHERE source_id = 'cskg_like'")
        assert made == distinct
        dupes = graph.one("""SELECT count(*) FROM (SELECT src, rel, dst FROM edges
                             WHERE source_id = 'cskg_like' GROUP BY ALL HAVING count(*) > 1)""")
        assert dupes == 0
        assert graph.one("SELECT count(*) FROM edges WHERE source_id = 'someone_else'") == 6_000_000
    finally:
        graph.close()


def test_rebuilding_does_not_duplicate_edges(tmp_path, triple_folder):
    folder, distinct = triple_folder
    graph = open_graph(str(tmp_path / "rebuild.duckdb"))
    try:
        schema = connect(str(folder))
        onto = discover(schema)
        build(graph, schema, onto, source="cskg_like")
        build(graph, schema, onto, source="cskg_like")
        assert graph.one("SELECT count(*) FROM edges WHERE source_id = 'cskg_like'") == distinct
    finally:
        graph.close()
