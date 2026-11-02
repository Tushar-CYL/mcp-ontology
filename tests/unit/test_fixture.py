"""The benchmark fixture must be the same lake every time.

A benchmark whose input changes between runs cannot measure anything. These
tests pin the properties the fixture promises: exactly 100 tables, mixed
formats, the three overlapping product masters, deterministic bytes and
ground truth, no network use, and the deliberately awkward shapes the
benchmark relies on (keyless tables, composite identities, reserved-word
columns, non-ASCII values).

They do not test the application. They test the ruler.

    python -m pytest tests/unit/test_fixture.py -q
"""

from __future__ import annotations

import csv
import hashlib
import json
import socket

import pytest

from benchmarks import fixture_lake100 as lake

TRUTH_PATH = lake.DEFAULT_TRUTH


def _generate(folder, truth=None):
    return lake.generate(folder, truth_path=truth, quiet=True)


def _file_hashes(folder):
    """SHA-256 of every data file, keyed by name; independent of the module."""
    out = {}
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[path.name] = digest
    return out


def _column(folder, filename, column):
    """Read one column from any of the fixture's three formats."""
    path = folder / filename
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return [int(row[column]) for row in csv.DictReader(f)]
    if path.suffix == ".parquet":
        # DuckDB is the project's engine and, unlike pyarrow's array API, does
        # not lazily import pandas (which Application Control blocks here).
        import duckdb
        con = duckdb.connect(":memory:")
        try:
            quoted = '"' + column.replace('"', '""') + '"'
            escaped = str(path).replace("'", "''")
            rows = con.execute(
                f"SELECT {quoted} FROM read_parquet('{escaped}')").fetchall()
            return [int(row[0]) for row in rows]
        finally:
            con.close()
    records = json.loads(path.read_text(encoding="utf-8"))
    return [int(row[column]) for row in records]


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    folder = tmp_path_factory.mktemp("lake100") / "lake"
    truth = _generate(folder)
    return folder, truth


class TestTheLake:
    def test_exactly_100_tables_in_one_folder(self, generated):
        folder, truth = generated
        files = [p for p in folder.iterdir() if p.is_file()]
        assert len(files) == 100
        assert truth["table_count"] == 100
        assert len(truth["tables"]) == 100
        names = [t["name"] for t in truth["tables"]]
        assert len(set(names)) == 100
        assert set(truth["files"]) == {p.name for p in files}

    def test_mixed_formats_are_present(self, generated):
        _, truth = generated
        formats = truth["counts"]["formats"]
        assert set(formats) == {"csv", "parquet", "json"}
        for fmt in ("csv", "parquet", "json"):
            assert formats[fmt] > 0
        suffixes = {t["format"] for t in truth["tables"]}
        assert suffixes == {"csv", "parquet", "json"}

    def test_three_overlapping_product_masters(self, generated):
        folder, truth = generated
        masters = truth["product_masters"]
        assert masters["tables"] == [
            "erp_products.csv", "pim_products.parquet",
            "marketplace_products.json"]
        assert masters["shared_key"] == "product_id"
        assert len(set(masters["expected_classes"].values())) == 3

        erp = set(_column(folder, "erp_products.csv", "product_id"))
        pim = set(_column(folder, "pim_products.parquet", "product_id"))
        market = set(_column(folder, "marketplace_products.json", "product_id"))
        # Same id space, different coverage: the demo is three views of the
        # same products, not three unrelated tables.
        assert erp and pim < erp and market < erp
        assert len(erp) == masters["coverage_rows"]["erp_products"]
        assert len(pim) == masters["coverage_rows"]["pim_products"]
        assert len(market) == masters["coverage_rows"]["marketplace_products"]
        assert len({frozenset(erp), frozenset(pim), frozenset(market)}) == 3

    def test_the_awkward_shapes_are_really_there(self, generated):
        _, truth = generated
        counts = truth["counts"]
        # The benchmark's claims about difficult input depend on these.
        assert counts["tables_with_fk_columns"] >= 10
        assert counts["tables_with_no_usable_key"] >= 5
        assert truth["counts"]["key_kinds"]["composite"] >= 3
        assert truth["counts"]["key_kinds"]["none"] >= 5

        reserved = truth["special_cases"]["reserved_word_columns"]
        all_reserved = {col for cols in reserved.values() for col in cols}
        assert {"order", "select", "group"} <= all_reserved
        assert len(reserved) >= 3
        assert counts["tables_with_non_ascii_values"] >= 1
        assert truth["special_cases"]["non_ascii_tables"]

        # Composite identities are intended to be composite; current file
        # discovery must fall back to the synthetic row key.
        for table in truth["special_cases"]["composite_key_tables"]:
            record = next(t for t in truth["tables"] if t["name"] == table)
            assert len(record["intended_key"]) >= 2
            assert record["expected_key"] == ["__row"]

        # Every table with no usable key says so, and every natural key does
        # not pretend to be synthetic.
        for record in truth["tables"]:
            if record["key_kind"] == "none":
                assert record["expected_key"] == ["__row"]
            if record["key_kind"] == "natural":
                assert record["expected_key"] == record["intended_key"]
                assert record["expected_key"] != ["__row"]
            assert record["declared_key"] is None   # a file declares nothing

        assert truth["expected_relations"], "no relations to infer"
        for relation in truth["expected_relations"]:
            assert relation["domain_table"] in {
                t["name"] for t in truth["tables"]}
            assert relation["range_table"] in {
                t["name"] for t in truth["tables"]}


class TestDeterminism:
    def test_two_generations_are_byte_identical(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        truth_a, truth_b = tmp_path / "a.json", tmp_path / "b.json"
        _generate(a, truth_a)
        _generate(b, truth_b)

        assert _file_hashes(a) == _file_hashes(b)
        assert truth_a.read_bytes() == truth_b.read_bytes()

        # The hashes in the ground truth are the hashes on disk.
        truth = json.loads(truth_a.read_text(encoding="utf-8"))
        assert truth["files"] == _file_hashes(a)

    def test_generated_ground_truth_matches_the_tracked_file(self, tmp_path):
        assert TRUTH_PATH.exists(), (
            "benchmarks/lake100_ground_truth.json must be tracked in git; "
            "run: python benchmarks/fixture_lake100.py --out data/fixtures/lake100"
        )
        folder = tmp_path / "lake"
        fresh = tmp_path / "truth.json"
        _generate(folder, fresh)
        assert fresh.read_bytes() == TRUTH_PATH.read_bytes()

        tracked = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
        assert tracked["fixture"] == "lake100"
        assert tracked["generator_version"] == lake.GENERATOR_VERSION
        assert tracked["seed"] == lake.SEED
        assert tracked["table_count"] == 100
        assert tracked["counts"]["rows"] > 0
        assert tracked["product_masters"]["tables"]
        assert tracked["expected_relations"]


class TestNoNetwork:
    def test_generation_needs_no_network_at_all(self, tmp_path, monkeypatch):
        # Warm the imports that happen during generation (they must not socket).
        import duckdb  # noqa: F401

        def refused(*_args, **_kwargs):
            raise AssertionError("lake100 tried to use the network")

        monkeypatch.setattr(socket, "socket", refused)
        monkeypatch.setattr(socket, "create_connection", refused)
        monkeypatch.setattr(socket, "getaddrinfo", refused)

        folder = tmp_path / "lake"
        truth = _generate(folder)
        assert truth["table_count"] == 100
        assert len([p for p in folder.iterdir() if p.is_file()]) == 100
