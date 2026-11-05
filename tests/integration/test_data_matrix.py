"""Every kind of data through the whole Ontology journey, as a regression
suite: CSV in all its shapes (Unicode, emoji, SQL-like names, 400 columns,
duplicate columns, header only, BOM + semicolon, quoted newlines), TSV, JSON,
NDJSON, Parquet with rich types (time zones, decimals, lists, structs),
Excel, SQLite with views, mixed folders, N-Triples, Turtle - and broken input
that must be rejected cleanly (empty file, binary garbage, no data, missing
path).

Each case: load -> build -> invariants -> Excel -> MCP -> context note ->
edit -> rebuild keeps the edit -> delete leaves no rows. The harness is
`scripts/qa_data_matrix.py`; run it with --real for the large datasets.
"""

from __future__ import annotations

import pytest

from scripts.qa_data_matrix import run_case
from scripts.qa_datasets import make_all


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    return make_all(tmp_path_factory.mktemp("qa_data"))


CASES = [
    "csv_two_tables", "csv_unicode_names", "csv_sql_like_names", "csv_long_names_and_cells",
    "csv_wide_400_columns", "csv_duplicate_columns", "csv_header_only", "csv_single_cell",
    "csv_all_null_column", "csv_bom_semicolon", "csv_quoted_newlines", "tsv_file",
    "csv_leading_zero_ids", "csv_mixed_date_formats", "odd_table_names", "json_nested",
    "ndjson", "parquet_rich_types", "xlsx_file", "sqlite_fk_and_view", "mixed_csv_parquet_json",
    "rdf_ntriples_typed", "rdf_turtle", "csv_zero_bytes", "binary_garbage_csv",
    "folder_without_data", "path_not_found",
]


@pytest.mark.parametrize("name", CASES)
def test_every_kind_of_data(name, cases, tmp_path):
    path, expect = cases[name]
    result = run_case(name, path, expect, None, tmp_path)
    assert result["status"].startswith("pass"), (result["problems"], result.get("trace", ""))


def test_the_excel_export_opens_in_a_strict_reader(tmp_path):
    """Excel forgives an incomplete styles.xml; DuckDB's reader (and some
    add-ins) do not. Our workbook must read back cell for cell."""
    import duckdb
    from ontology.xlsx import workbook
    path = tmp_path / "export.xlsx"
    path.write_bytes(workbook([("Fields", [{"Field": "Prix (€) 😀", "Rows": 3, "Ok": True},
                                           {"Field": "a<b & 'c'", "Rows": 4.5, "Ok": False}]),
                               ("Empty", [])]))
    rows = duckdb.connect().execute(
        f"SELECT * FROM read_xlsx('{path.as_posix()}', sheet='Fields')").fetchall()
    assert rows == [("Prix (€) 😀", 3.0, True), ("a<b & 'c'", 4.5, False)]


def test_excel_export_never_writes_formulas(tmp_path):
    """Formula injection: a label like =HYPERLINK(...) from client data must
    stay text in the workbook Nexus/Excel opens, never become a formula."""
    import io
    import zipfile
    from ontology.xlsx import workbook
    blob = workbook([("F", [{"Field": '=HYPERLINK("http://evil","x")'}, {"Field": "+1+1"},
                            {"Field": "@SUM(A1)"}, {"Field": "-2+3"}])])
    sheet = zipfile.ZipFile(io.BytesIO(blob)).read("xl/worksheets/sheet1.xml").decode()
    assert "<f>" not in sheet and "<f " not in sheet
    assert sheet.count('t="inlineStr"') == 5                      # header + 4 values


def test_owl_and_shacl_exports_stay_valid_with_hostile_names(tmp_path):
    import rdflib
    from api.service import MiddleLayer
    from ontology import publish as pub
    from ontology import simple
    from tests.integration.simple_fixtures import write_csv
    folder = tmp_path / "evil"
    write_csv(folder / "evil.csv", [{"id": i, 'name"; DROP': f"x{i}", "emoji_😀": "✓",
                                     "<script>alert(1)</script>": i} for i in range(30)])
    layer = MiddleLayer(str(tmp_path / "e.duckdb"))
    layer.add_source(str(folder), source="evil")
    oid = simple.create_and_build(layer, 'Evil "quotes" \n newline <b>', ["evil"])["ontology"]
    simple.edit_field(layer, oid, "evil.evil.id", meaning='He said "hi"\nthen \\left> & <')
    for text in (pub.to_turtle(layer.graph, oid), pub.to_shacl(layer.graph, oid)):
        rdflib.Graph().parse(data=text, format="turtle")          # must parse
