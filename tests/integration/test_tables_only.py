"""A graph source above STRATA_GRAPH_BUILD_MAX_ROWS is loaded as tables only:
no nodes/edges (whose unique indexes must fit in memory), the ontology still
comes out, and a restart does not reload it."""

from __future__ import annotations

from api.service import MiddleLayer
from knowledge_graph.build import is_tables_only
from ontology import simple
from tests.integration.test_graph_ontology import write_cskg


def test_big_graph_sources_skip_the_graph_rows_but_keep_the_ontology(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_GRAPH_BUILD_MAX_ROWS", "100")        # the fixture has ~300 rows
    folder = write_cskg(tmp_path / "cskg")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    lines = []
    out = layer.add_source(str(folder), source="kg", progress=lines.append)
    assert out["nodes"] == 0 and out["edges"] == 0
    assert any("tables only" in w for w in out["warnings"])
    assert is_tables_only(layer.graph, "kg")
    assert "kg" in layer.graph.source_ids()
    # The ontology works from the tables alone.
    oid = simple.create_and_build(layer, "KG", ["kg"])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {"Method", "Task", "Metric"} <= {t["name"] for t in v["things"]}
    assert v["summary"]["links"] >= 4
    # A second start finds it current: no second copy of the tables.
    lines.clear()
    layer2 = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer2.add_source(str(folder), source="kg", progress=lines.append)
    assert any("already up to date" in line for line in lines)


def test_small_graph_sources_still_build_the_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_GRAPH_BUILD_MAX_ROWS", "1000000")
    folder = write_cskg(tmp_path / "cskg")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    out = layer.add_source(str(folder), source="kg")
    assert out["nodes"] > 0 and out["edges"] > 0
    assert not is_tables_only(layer.graph, "kg")


def test_tables_only_never_applies_to_ordinary_tables(tmp_path, monkeypatch):
    from tests.integration.simple_fixtures import make_iot
    monkeypatch.setenv("STRATA_GRAPH_BUILD_MAX_ROWS", "1")
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    out = layer.add_source(str(make_iot(tmp_path / "iot")), source="iot")
    assert out["nodes"] > 0
