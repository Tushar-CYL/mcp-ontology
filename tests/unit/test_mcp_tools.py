"""The curated MCP surface: names, read-only contract, scope and row caps.

Mirrors the NVIDIA auto-ontology pattern: a small, explicit, read-only tool
list, handshake instructions that tell an agent the order to call them in,
and results that say when rows were withheld.
"""

from __future__ import annotations

import pytest

from api import mcp_server
from api.mcp_server import Forbidden, cap_rows, check_metric, check_source

# Grouped by layer (each description starts with its layer tag).
EXPECTED_TOOLS = {
    "list_sources", "check_readiness", "search",              # general
    "list_entities", "describe_table",                        # ontology
    "graph_neighbours", "get_entity_context",                 # knowledge graph
    "list_metrics", "get_metric", "evaluate_metric", "validate_sql",  # semantic
    "check_answerable", "get_context", "explain_citation",    # context
    "propose_change",                                         # steward only
    "get_ontology",                                                   # simple flow
    "list_concepts", "get_concept", "map_column", "resolve_entity",   # enterprise
    "get_contract", "validate_rules", "ontology_version",             # ontology
}
LAYER_TAG = {
    "list_sources": "[General]", "check_readiness": "[General]",
    "search": "[General]", "list_entities": "[Ontology]",
    "describe_table": "[Ontology]", "graph_neighbours": "[Graph]",
    "get_entity_context": "[Graph]", "list_metrics": "[Semantic]",
    "get_metric": "[Semantic]", "evaluate_metric": "[Semantic]",
    "validate_sql": "[Semantic]", "check_answerable": "[Context]",
    "get_context": "[Context]", "explain_citation": "[Context]",
    "propose_change": "[Steward]",
    **dict.fromkeys(["get_ontology", "list_concepts", "get_concept", "map_column", "resolve_entity",
                     "get_contract", "validate_rules", "ontology_version"], "[Ontology]"),
}


def test_the_tool_list_is_exactly_the_curated_set():
    assert {tool["name"] for tool in mcp_server.TOOLS} == EXPECTED_TOOLS


def test_every_tool_has_a_description_and_an_object_schema():
    for tool in mcp_server.TOOLS:
        assert tool["description"].strip(), tool["name"]
        assert tool["inputSchema"]["type"] == "object", tool["name"]


def test_every_description_starts_with_its_layer():
    for tool in mcp_server.TOOLS:
        assert tool["description"].startswith(LAYER_TAG[tool["name"]]), tool["name"]


def test_only_propose_change_writes_and_it_is_never_destructive():
    """MCP is read-only except one tool that files a proposal for review."""
    for tool in mcp_server.TOOLS:
        hints = tool.get("annotations", {})
        if tool["name"] == "propose_change":
            assert hints["readOnlyHint"] is False
            assert hints["destructiveHint"] is False
        else:
            assert hints.get("readOnlyHint") is True, tool["name"]
        for verb in ("create", "update", "delete", "write", "approve"):
            assert verb not in tool["name"]


def test_tools_list_is_filtered_by_the_agent_scope():
    scope = {"agent_id": "a1", "sources": ["revenue"], "metrics": [],
             "tools": ["list_sources", "describe_table"]}
    response = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, layer=None,
        scope=scope)
    assert [t["name"] for t in response["result"]["tools"]] == [
        "list_sources", "describe_table"]


def test_a_tool_outside_the_agent_scope_is_forbidden():
    scope = {"agent_id": "a1", "sources": ["revenue"], "metrics": ["revenue"],
             "tools": ["list_sources"]}
    response = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "get_metric", "arguments": {"metric": "revenue"}}},
        layer=_FakeLayer(["revenue"]), scope=scope)
    assert response["error"]["code"] == mcp_server.FORBIDDEN
    assert "get_metric" in response["error"]["message"]


def test_server_identifies_as_strata_with_instructions():
    response = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"}, layer=None)
    result = response["result"]
    assert result["serverInfo"]["name"] == "strata"
    text = result["instructions"]
    # The handshake tells an agent the order: readiness, answerable, context.
    assert text.index("check_readiness") < text.index("check_answerable") \
        < text.index("get_context")


def test_cap_rows_reports_truncation():
    rows, truncated = cap_rows([[i] for i in range(150)], limit=100)
    assert len(rows) == 100 and truncated is True
    rows, truncated = cap_rows([[1], [2]], limit=100)
    assert rows == [[1], [2]] and truncated is False


def test_no_scope_means_local_and_unrestricted():
    assert check_source(None, "shop", ["shop", "other"]) == "shop"
    check_metric(None, "anything")            # does not raise


def test_scope_defaults_to_the_agents_source():
    scope = {"agent_id": "a1", "sources": ["revenue"], "metrics": ["revenue"]}
    assert check_source(scope, None, ["revenue", "hr"]) == "revenue"


def test_scope_refuses_a_source_outside_it():
    scope = {"agent_id": "a1", "sources": ["revenue"], "metrics": ["revenue"]}
    with pytest.raises(Forbidden, match="hr"):
        check_source(scope, "hr", ["revenue", "hr"])


def test_scope_refuses_a_metric_outside_it():
    scope = {"agent_id": "a1", "sources": ["revenue"], "metrics": ["revenue"]}
    check_metric(scope, "revenue")
    with pytest.raises(Forbidden, match="refund_rate"):
        check_metric(scope, "refund_rate")


def test_forbidden_is_a_distinct_json_rpc_error():
    scope = {"agent_id": "a1", "sources": ["revenue"], "metrics": []}
    response = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
         "params": {"name": "get_metric",
                    "arguments": {"metric": "revenue", "source": "hr"}}},
        layer=_FakeLayer(["revenue", "hr"]), scope=scope)
    assert response["error"]["code"] == mcp_server.FORBIDDEN
    assert "forbidden" in response["error"]["message"].lower()


class _FakeLayer:
    """Just enough of MiddleLayer for scope checks that fail before any I/O."""

    def __init__(self, sources):
        self._sources = sources

        class _Graph:
            def source_ids(inner):
                return list(sources)

        self.graph = _Graph()
        self.bundles = []


def test_describe_table_flags_pii_columns_by_the_guardrail_policy(monkeypatch):
    from types import SimpleNamespace as NS

    from semantic import definitions as metric_defs
    monkeypatch.setattr(metric_defs, "list_definitions",
                        lambda graph, source=None: [])

    table = NS(name="people", row_count=2, columns=[
        NS(name="person_id", type="TEXT"), NS(name="email", type="TEXT"),
        NS(name="phone_number", type="TEXT"), NS(name="city", type="TEXT")])
    klass = NS(name="Person", table="people", key="person_id",
               time_column=None)
    bundle = NS(source="crm", schema=NS(tables=[table]),
                onto=NS(classes={"Person": klass}, relations={}))
    layer = _FakeLayer(["crm"])
    layer.bundles = [bundle]
    layer._bundle = lambda source: bundle
    result = mcp_server.call_tool(layer, "describe_table",
                                  {"table": "people"})
    flagged = {c["name"] for c in result["columns"] if c["pii"]}
    assert flagged == {"email", "phone_number"}
    assert result["class"] == "Person"


def test_describe_table_links_metrics_by_exact_table_reference(monkeypatch):
    """`lines` must not match a metric built on `order_lines`."""
    from types import SimpleNamespace as NS

    from knowledge_graph import build as kg_build
    from semantic import definitions as metric_defs

    def make(name):
        return NS(name=name, row_count=1, columns=[NS(name="id", type="TEXT")])

    bundle = NS(source="s",
                schema=NS(tables=[make("lines"), make("order_lines")]),
                onto=NS(classes={}, relations={}))
    layer = _FakeLayer(["s"])
    layer.bundles = [bundle]
    layer._bundle = lambda source: bundle
    # The build materialises every table as "src_<source>__<table>".
    monkeypatch.setattr(kg_build, "table_ref",
                        lambda graph, schema, table, source="":
                        f'"src_{source}__{table}"')
    monkeypatch.setattr(metric_defs, "list_definitions",
                        lambda graph, source=None: [
                            {"name": "m", "status": "approved",
                             "base_sql": 'SELECT * FROM "src_s__order_lines"'}])
    assert mcp_server.call_tool(layer, "describe_table",
                                {"table": "lines"})["metrics"] == []
    assert mcp_server.call_tool(layer, "describe_table",
                                {"table": "order_lines"})["metrics"] == ["m"]
