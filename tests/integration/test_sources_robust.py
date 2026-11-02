"""Any data, every time: a bad file must not take the source down with it.

The product promise is "point it at anything and it completes". A thin answer
with a warning is acceptable; a crash, a silent empty graph, or one malformed
row losing a thousand good ones is not.

These tests are deliberately adversarial: corrupt files, duplicate stems,
malformed CSV, unsupported formats sitting next to good data.
"""

from __future__ import annotations

import pytest

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover


def _folder(tmp_path, files: dict[str, bytes | str]):
    d = tmp_path / "src"
    d.mkdir()
    for name, body in files.items():
        mode = "wb" if isinstance(body, bytes) else "w"
        if mode == "wb":
            (d / name).write_bytes(body)
        else:
            (d / name).write_text(body, encoding="utf-8")
    return d


class TestOneBadFileDoesNotKillTheSource:
    def test_corrupt_parquet_next_to_good_csv(self, tmp_path):
        d = _folder(tmp_path, {
            "good.csv": "id,name\n1,Ada\n2,Grace\n",
            "broken.parquet": b"this is not a parquet file at all",
        })
        schema = connect(str(d))
        assert {t.name for t in schema.tables} == {"good"}
        assert any("broken.parquet" in w for w in schema.warnings)

    def test_malformed_csv_is_tolerated(self, tmp_path):
        """DuckDB reads most malformed CSV without failing — better than a
        skip. The contract is only that it completes and the good file is
        untouched; if it ever does fail, the warning path covers it."""
        d = _folder(tmp_path, {
            "good.csv": "id,name\n1,Ada\n2,Grace\n",
            "bad.csv": 'id,name\n1,"unclosed\n2,ok\n',
        })
        schema = connect(str(d))
        names = {t.name for t in schema.tables}
        assert "good" in names
        assert "bad" in names, "DuckDB parsed the malformed CSV; keep it"
        onto = discover(schema)
        g = open_graph(tmp_path / "tolerant.duckdb")
        build(g, schema, onto)
        assert g.dangling_edges() == 0

    def test_zero_byte_file_is_skipped(self, tmp_path):
        d = _folder(tmp_path, {
            "good.csv": "id\n1\n2\n",
            "empty.csv": "",
        })
        schema = connect(str(d))
        assert "good" in {t.name for t in schema.tables}
        assert any("empty.csv" in w for w in schema.warnings)

    def test_a_folder_of_only_bad_files_is_a_clear_error(self, tmp_path):
        d = _folder(tmp_path, {"broken.parquet": b"nope"})
        with pytest.raises(SourceError) as exc:
            connect(str(d))
        assert "broken.parquet" in str(exc.value)

    def test_unsupported_files_are_ignored_with_the_good_ones(self, tmp_path):
        d = _folder(tmp_path, {
            "good.csv": "id\n1\n",
            "notes.docx": "not a table",
            "readme.md": "ignore me",
        })
        schema = connect(str(d))
        assert {t.name for t in schema.tables} == {"good"}


class TestNamesThatCollide:
    def test_two_files_with_the_same_stem_both_survive(self, tmp_path):
        """`orders.csv` and `orders.parquet` can legitimately both exist. The
        second must not silently replace the first."""
        import duckdb
        d = tmp_path / "src"
        d.mkdir()
        (d / "orders.csv").write_text("id,total\n1,10\n2,20\n", encoding="utf-8")
        duckdb.connect(":memory:").execute(
            f"COPY (SELECT 1 AS id, 99.0 AS total) TO "
            f"'{str(d / 'orders.parquet').replace(chr(92), '/')}' (FORMAT parquet)")
        schema = connect(str(d))
        names = {t.name for t in schema.tables}
        assert names == {"orders", "orders_2"}

    def test_two_files_with_the_same_stem_get_distinct_tables_in_the_graph(
            self, tmp_path):
        d = _folder(tmp_path, {
            "a.csv": "id,name\n1,one\n",
            "a.json": '{"id": 2, "name": "two"}',
        })
        schema = connect(str(d))
        onto = discover(schema)
        g = open_graph(tmp_path / "g.duckdb")
        build(g, schema, onto)
        names = {row[1] for row in g.sql("SELECT * FROM classes")}
        assert len(names) == 2, "two tables must not collapse into one class"
        assert g.dangling_edges() == 0


class TestTheGraphStillBuilds:
    def test_a_source_with_no_relations_is_a_valid_answer(self, tmp_path):
        d = _folder(tmp_path, {"notes.csv": "id,body\n1,hi\n2,there\n"})
        schema = connect(str(d))
        onto = discover(schema)
        assert onto.relations == {}
        g = open_graph(tmp_path / "g.duckdb")
        stats = build(g, schema, onto)
        assert stats["nodes"] == 2
        assert g.dangling_edges() == 0

    def test_warnings_do_not_stop_the_build(self, tmp_path):
        d = _folder(tmp_path, {
            "good.csv": "id,name\n1,Ada\n",
            "bad.parquet": b"nope",
        })
        schema = connect(str(d))
        assert schema.warnings
        g = open_graph(tmp_path / "g.duckdb")
        build(g, schema, discover(schema))
        assert g.one("SELECT count(*) FROM nodes") == 1

    def test_the_schema_exposes_warnings_to_the_caller(self, tmp_path):
        d = _folder(tmp_path, {
            "good.csv": "id\n1\n",
            "bad.parquet": b"nope",
        })
        schema = connect(str(d))
        assert isinstance(schema.warnings, list) and schema.warnings
