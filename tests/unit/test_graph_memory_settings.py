"""DuckDB settings for laptops: spill to disk instead of failing.

DuckDB's default memory limit is 80% of RAM. On an 8 GB laptop running the
API, a browser and Windows, that leaves nothing for anyone else, and a big
build fails with OutOfMemory instead of spilling. The graph is opened with a
smaller limit, a temp directory to spill into, and insertion order not
preserved (DuckDB's own first suggestion for memory-heavy loads).
"""

from __future__ import annotations

from knowledge_graph.store import memory_settings, open_graph


def _setting(graph, name):
    return graph.one(f"SELECT current_setting('{name}')")


def test_a_file_graph_spills_next_to_itself(tmp_path):
    g = open_graph(str(tmp_path / "g.duckdb"))
    try:
        assert str(_setting(g, "temp_directory")).replace("\\", "/").endswith("g.duckdb.tmp")
        assert _setting(g, "preserve_insertion_order") is False
    finally:
        g.close()


def test_the_memory_limit_leaves_room_for_everything_else(tmp_path):
    settings = memory_settings(total_bytes=8 * 1024 ** 3, cores=8)
    assert settings["memory_limit"] == "4GB"                  # half of 8 GB
    assert settings["threads"] == 4


def test_tiny_and_huge_machines_get_sane_limits():
    assert memory_settings(total_bytes=2 * 1024 ** 3, cores=2)["memory_limit"] == "1GB"
    assert memory_settings(total_bytes=256 * 1024 ** 3, cores=64)["threads"] == 8


def test_the_limit_can_be_set_by_the_operator(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_DUCKDB_MEMORY", "3GB")
    monkeypatch.setenv("STRATA_DUCKDB_THREADS", "2")
    g = open_graph(str(tmp_path / "g.duckdb"))
    try:
        assert _setting(g, "memory_limit") == "2.7 GiB"     # DuckDB reports 3GB this way
        assert _setting(g, "threads") == 2
    finally:
        g.close()


def test_an_in_memory_graph_still_opens(monkeypatch):
    g = open_graph(None)
    try:
        assert g.one("SELECT 1") == 1
    finally:
        g.close()


def test_out_of_memory_is_explained_in_plain_words():
    from api.server import memory_message
    text = memory_message(RuntimeError("Out of Memory Error: could not allocate\nmore"), 7)
    assert "7 other source(s)" in text and "STRATA_DUCKDB_MEMORY" in text
    assert "could not allocate" in text and "more" not in text.split("Detail:")[1]
