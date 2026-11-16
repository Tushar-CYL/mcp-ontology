"""Agents use the knowledge graph over MCP: find, 360, how connected - and a
scoped agent cannot read a source outside its scope."""

from __future__ import annotations

import json

import pytest

from api import mcp_server
from api.service import MiddleLayer
from ontology import publish as pub
from ontology import simple
from tests.integration.test_declared_links import make_shop


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kgmcp")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(make_shop(tmp / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    return layer, oid


def call(layer, name, args, scope=None):
    out = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": name, "arguments": args}}, layer, scope=scope)
    if "error" in out:
        return out["error"]
    return json.loads(out["result"]["content"][0]["text"])


def test_tools_are_listed():
    names = {t["name"] for t in mcp_server.allowed_tools(None)}
    assert {"find_entity", "get_entity", "how_connected"} <= names


def test_agent_finds_reads_and_connects(shop):
    layer, oid = shop
    hit = call(layer, "find_entity", {"query": "Customer 17", "ontology": oid})["results"][0]
    e = call(layer, "get_entity", {"set": hit["set"], "key": hit["key"], "ontology": oid})
    assert e["label"] == "Customer 17"
    assert next(f for f in e["fields"] if f["column"] == "email")["value"].startswith("c***@")
    p = call(layer, "how_connected", {"from_set": "shop.customer", "from_key": "2",
                                      "to_set": "shop.customer", "to_key": "42",
                                      "max_hops": 6, "ontology": oid})
    assert p["found"]


def test_scoped_agent_outside_its_sources_is_refused(shop):
    layer, oid = shop
    scope = {"sources": ["other"], "metrics": [], "agent_id": "a"}
    err = call(layer, "get_entity", {"set": "shop.customer", "key": "1", "ontology": oid}, scope)
    assert err["code"] == mcp_server.FORBIDDEN


def test_entity_investigator_preset_has_the_graph_tools():
    from agent.presets import PRESETS
    tools = set(PRESETS["entity"]["tools"])
    assert {"find_entity", "get_entity", "how_connected"} <= tools
