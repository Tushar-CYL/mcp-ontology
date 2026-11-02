"""The consumption surface: service methods, MCP JSON-RPC, local HTTP."""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.request

import pytest

from api.http import make_server
from api.mcp_server import TOOLS, handle
from api.service import MiddleLayer


@pytest.fixture
def layer(tmp_path):
    db = tmp_path / "shop.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id), total REAL);
        INSERT INTO customers VALUES (1,'Ada'),(2,'Grace');
        INSERT INTO orders VALUES (1,1,10.0),(2,2,20.0);
    """)
    con.commit()
    con.close()
    service = MiddleLayer(str(tmp_path / "g.duckdb"))
    service.add_source(str(db), source="shop")
    yield service
    service.close()


class TestService:
    def test_sources_are_reported(self, layer):
        assert [s["source_id"] for s in layer.sources()] == ["shop"]

    def test_ontology_lists_classes_and_relations(self, layer):
        out = layer.ontology()
        names = {c["name"] for c in out["classes"]}
        assert {"Customer", "Order"} <= names
        assert out["relations"]

    def test_describe_one_class(self, layer):
        out = layer.describe("Customer")
        assert out["key"] == "id" and out["count"] == 2
        assert out["sample_keys"] == ["1", "2"]

    def test_neighbours_carry_provenance(self, layer):
        out = layer.neighbours("Order", "1")
        assert out["neighbours"]
        assert out["neighbours"][0]["provenance"] == "measured"
        assert out["neighbours"][0]["target_key"] == "1"

    def test_metric_returns_rows_and_definition(self, layer):
        out = layer.metric("total_sum")
        assert out["rows"][0][0] == 30.0
        assert out["definition"]["column"] == "total"
        assert "sum" in out["sql"].lower()

    def test_context_returns_a_cited_envelope(self, layer):
        out = layer.context(entity=("shop", "Customer", "1"))
        assert out["facts"] and out["focus"]["key"] == "1"
        assert all(f["citation"] for f in out["facts"])

    def test_an_unknown_metric_is_a_clear_error(self, layer):
        with pytest.raises(KeyError, match="no metric"):
            layer.metric("does_not_exist")

    def test_provenance_explains_a_citation(self, layer):
        out = layer.provenance("edge:customer:1")
        assert out["kind"] == "edge"
        assert "review_pending" in out


class TestMultipleSources:
    def test_ontology_without_a_source_lists_every_source(self, tmp_path):
        a = tmp_path / "a"
        a.mkdir()
        (a / "customers.csv").write_text("customer_id,name\nc1,Ada\n")
        b = tmp_path / "b"
        b.mkdir()
        (b / "customers.csv").write_text("customer_id,name\nd1,Grace\n")
        service = MiddleLayer(str(tmp_path / "g.duckdb"))
        service.add_source(str(a), source="a")
        service.add_source(str(b), source="b")
        try:
            out = service.ontology()
            assert "sources" in out and len(out["sources"]) == 2
            with pytest.raises(KeyError, match="pass source"):
                service.describe("Customer")
            assert service.describe("Customer", "a")["count"] == 1
        finally:
            service.close()

    def test_cross_source_candidates_are_exposed(self, tmp_path):
        for name, rel in (("erp", "products.csv"), ("pim", "products.csv")):
            d = tmp_path / name
            d.mkdir()
            body = ("product_id,name,price\np1,A-pack,10.0\np2,B-pack,20.0\n"
                    if name == "erp" else
                    "product_id,title\np1,A-pack\np2,B-pack\n")
            (d / rel).write_text(body, encoding="utf-8")
        service = MiddleLayer(str(tmp_path / "g.duckdb"))
        service.add_source(str(tmp_path / "erp"), source="erp")
        service.add_source(str(tmp_path / "pim"), source="pim")
        try:
            found = service.resolve()
            assert found, "the same products in two sources must be proposed"
            items = service.identity_candidates()
            assert items and items[0]["status"] == "proposed"
            info = service.explain_entity("erp", "Product", "p1")
            assert info["matches"]
            out = service.context(entity=("erp", "Product", "p1"),
                                  budget_chars=1000)
            assert "pim" in out["sources"]
            assert any("appears in pim" in f["text"] for f in out["facts"])
        finally:
            service.close()


class TestMcp:
    def test_initialize_is_a_valid_mcp_response(self, layer):
        response = handle({"jsonrpc": "2.0", "id": 1,
                           "method": "initialize", "params": {}}, layer)
        assert response["result"]["serverInfo"]["name"] == "middle-layer"
        assert response["result"]["protocolVersion"]

    def test_tools_are_listed(self, layer):
        response = handle({"jsonrpc": "2.0", "id": 2,
                           "method": "tools/list"}, layer)
        names = {tool["name"] for tool in response["result"]["tools"]}
        assert names == {tool["name"] for tool in TOOLS}
        assert "context.build" in names

    def test_a_tool_call_returns_text_content(self, layer):
        response = handle({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "context.build",
                       "arguments": {"entity": {"class": "Customer",
                                                "key": "1",
                                                "source": "shop"}}}}, layer)
        content = response["result"]["content"][0]
        assert content["type"] == "text"
        payload = json.loads(content["text"])
        assert payload["focus"]["key"] == "1"

    def test_an_unknown_tool_is_an_error_not_a_crash(self, layer):
        response = handle({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "nope", "arguments": {}}}, layer)
        assert response["error"]["code"] == -32000
        assert "unknown tool" in response["error"]["message"]

    def test_an_unknown_method_is_32601(self, layer):
        response = handle({"jsonrpc": "2.0", "id": 5,
                           "method": "nope"}, layer)
        assert response["error"]["code"] == -32601

    def test_a_notification_gets_no_response(self, layer):
        assert handle({"jsonrpc": "2.0",
                       "method": "notifications/initialized"}, layer) is None


class TestHttp:
    @pytest.fixture
    def server(self, layer):
        httpd = make_server(layer, "127.0.0.1", 0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address[:2]
        yield f"http://{host}:{port}"
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    def _get(self, url):
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, json.loads(response.read())

    def _post(self, url, payload):
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())

    def test_health(self, server):
        status, body = self._get(f"{server}/health")
        assert status == 200 and body["status"] == "ok"
        assert body["sources"] == ["shop"]

    def test_ontology(self, server):
        status, body = self._get(f"{server}/ontology")
        assert status == 200
        assert {c["name"] for c in body["classes"]} >= {"Customer", "Order"}

    def test_metric(self, server):
        status, body = self._get(f"{server}/metric?name=total_sum")
        assert status == 200 and body["rows"][0][0] == 30.0

    def test_context_post(self, server):
        status, body = self._post(
            f"{server}/context",
            {"entity": {"class": "Customer", "key": "1", "source": "shop"}})
        assert status == 200
        assert body["facts"] and body["focus"]["class"] == "Customer"
        assert body["chars"] <= body["budget_chars"]

    def test_unknown_route_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as exc:
            self._get(f"{server}/nope")
        assert exc.value.code == 404
