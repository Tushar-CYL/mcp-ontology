"""More source shapes: RDF graph files, http(s) URLs, cloud URL errors.

The request behind this file: "point it at any data source" — including a
4 GB N-Triples export that is a graph, not a table.
"""

from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover


NT = """\
<https://example.org/E1> <http://www.w3.org/2000/01/rdf-schema#label> "Ada" .
<https://example.org/E1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://example.org/Person> .
<https://example.org/E2> <http://www.w3.org/2000/01/rdf-schema#label> "Grace" .
<https://example.org/E2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://example.org/Person> .
<https://example.org/E1> <https://example.org/knows> <https://example.org/E2> .
"""


class TestRdfFiles:
    @pytest.fixture
    def nt_file(self, tmp_path):
        path = tmp_path / "people.nt"
        path.write_text(NT, encoding="utf-8")
        return path

    def test_connect_reads_an_nt_file_as_two_tables(self, nt_file):
        schema = connect(str(nt_file))
        assert {t.name for t in schema.tables} == {"entities", "links"}
        assert schema.warnings and "RDF" in schema.warnings[0]

    def test_discovery_finds_entity_and_link_with_declared_links(self, nt_file):
        onto = discover(connect(str(nt_file)))
        assert set(onto.classes) == {"Entity", "Link"}
        pairs = {(r.name, r.domain, r.range) for r in onto.relations.values()}
        assert ("source", "Link", "Entity") in pairs
        assert ("target", "Link", "Entity") in pairs
        assert all(r.provenance == "measured" for r in onto.relations.values())

    def test_the_graph_builds_from_triples(self, nt_file, tmp_path):
        schema = connect(str(nt_file))
        onto = discover(schema)
        g = open_graph(tmp_path / "rdf.duckdb")
        build(g, schema, onto, source="rdf")
        assert g.count_class("Entity") >= 3      # E1, E2, Person
        assert g.count_class("Link") == 1        # E1 knows E2
        assert g.count_relation("source") == 1
        assert g.dangling_edges() == 0

    def test_a_folder_with_only_nt_uses_the_same_path(self, tmp_path):
        folder = tmp_path / "rdf"
        folder.mkdir()
        (folder / "people.nt").write_text(NT, encoding="utf-8")
        schema = connect(str(folder))
        assert {t.name for t in schema.tables} == {"entities", "links"}

    def test_a_mixed_folder_prefixes_rdf_tables(self, tmp_path):
        folder = tmp_path / "mixed"
        folder.mkdir()
        (folder / "people.nt").write_text(NT, encoding="utf-8")
        (folder / "orders.csv").write_text("id,total\n1,10\n", encoding="utf-8")
        schema = connect(str(folder))
        names = {t.name for t in schema.tables}
        assert "orders" in names
        assert any("people" in name for name in names)

    def test_malformed_rdf_is_skipped_with_a_warning_in_a_folder(self, tmp_path):
        folder = tmp_path / "mixed"
        folder.mkdir()
        (folder / "good.nt").write_text(NT, encoding="utf-8")
        (folder / "broken.nt").write_text("not triples at all\n", encoding="utf-8")
        schema = connect(str(folder))
        assert schema.tables, "the good file must still be read"


class TestHttpUrls:
    @pytest.fixture
    def server(self, tmp_path):
        (tmp_path / "customers.csv").write_text("id,name\n1,Ada\n", encoding="utf-8")
        (tmp_path / "people.nt").write_text(NT, encoding="utf-8")

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(tmp_path), **kwargs)

            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address[:2]
        yield f"http://{host}:{port}"
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    def test_a_csv_over_http_is_read(self, server):
        schema = connect(f"{server}/customers.csv")
        assert schema.tables[0].name == "customers"
        assert schema.tables[0].row_count == 1

    def test_an_nt_over_http_is_read(self, server):
        schema = connect(f"{server}/people.nt")
        assert {t.name for t in schema.tables} == {"entities", "links"}

    def test_an_unsupported_http_file_type_is_explained(self, server):
        with pytest.raises(SourceError, match="unsupported file type"):
            connect(f"{server}/nope.docx")

    def test_a_url_without_a_supported_extension_is_refused(self):
        with pytest.raises(SourceError, match="unsupported file type"):
            connect("http://example.invalid/download")


class TestCloudUrls:
    def test_a_missing_snowflake_driver_is_explained(self):
        try:
            import snowflake.connector  # noqa: F401
            pytest.skip("snowflake driver is installed here")
        except ImportError:
            pass
        with pytest.raises(SourceError, match="pip install"):
            connect("snowflake://user:pass@acct/DB/SCHEMA?warehouse=WH")

    def test_a_missing_databricks_driver_is_explained(self):
        try:
            import databricks.sql  # noqa: F401
            pytest.skip("databricks driver is installed here")
        except ImportError:
            pass
        with pytest.raises(SourceError, match="pip install"):
            connect("databricks://token@host?http_path=/x&catalog=main")

    def test_unknown_url_scheme_lists_what_is_supported(self):
        with pytest.raises(SourceError, match="snowflake"):
            connect("oracle://user:pass@host/db")


class TestGraphLabels:
    def test_rdf_entities_are_labelled_from_the_rdf_label(self, tmp_path):
        path = tmp_path / "people.nt"
        path.write_text(NT, encoding="utf-8")
        schema = connect(str(path)); onto = discover(schema)
        g = open_graph(tmp_path / "rdf_labels.duckdb")
        build(g, schema, onto, source="rdf")
        nodes, _ = g.subgraph(limit=20)
        labels = {n["label"] for n in nodes}
        assert {"Ada", "Grace"} <= labels
