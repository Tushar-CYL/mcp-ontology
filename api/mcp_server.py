"""MCP server: the middle layer as tools an agent can call.

MCP is JSON-RPC 2.0 over stdio here — no extra dependency, which matters on a
locked-down machine. The tools are small on purpose: an agent should ask for
an ontology entry, a metric or a context pack; it should not get raw SQL.

    python -m api.mcp_server --graph data/graphs/shop.duckdb --source data/example.db

The same service object powers the HTTP API and the UI.
"""

from __future__ import annotations

import argparse
import json
import sys

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "middle-layer", "version": "0.2.0"}

TOOLS = [
    {
        "name": "ontology.list",
        "description": "List classes and relations for a source (or all sources).",
        "inputSchema": {"type": "object", "properties": {
            "source": {"type": "string",
                       "description": "source id; omit when only one is loaded"}},
            "required": []},
    },
    {
        "name": "ontology.describe",
        "description": "Describe one class: key, time column, measures, count.",
        "inputSchema": {"type": "object", "properties": {
            "class": {"type": "string"},
            "source": {"type": "string"}},
            "required": ["class"]},
    },
    {
        "name": "graph.neighbours",
        "description": "What one thing is linked to, with edge provenance.",
        "inputSchema": {"type": "object", "properties": {
            "class": {"type": "string"}, "key": {"type": "string"},
            "relation": {"type": "string"}, "source": {"type": "string"},
            "depth": {"type": "integer", "minimum": 1, "maximum": 4},
            "as_of": {"type": "string"}},
            "required": ["class", "key"]},
    },
    {
        "name": "metric.get",
        "description": "Get one governed metric from the semantic layer.",
        "inputSchema": {"type": "object", "properties": {
            "metric": {"type": "string"}, "source": {"type": "string"},
            "group_by": {"type": "string"}},
            "required": ["metric"]},
    },
    {
        "name": "context.build",
        "description": "Build the cited, budgeted evidence pack for a question.",
        "inputSchema": {"type": "object", "properties": {
            "task": {"type": "string"},
            "entity": {
                "type": "object",
                "properties": {"class": {"type": "string"},
                               "key": {"type": "string"},
                               "source": {"type": "string"}},
                "required": ["class", "key"]},
            "budget_chars": {"type": "integer", "minimum": 100},
            "as_of": {"type": "string"}},
            "required": []},
    },
    {
        "name": "provenance.explain",
        "description": "Explain one citation id.",
        "inputSchema": {"type": "object", "properties": {
            "citation": {"type": "string"}}, "required": ["citation"]},
    },
]


def _call(layer, name: str, args: dict):
    if name == "ontology.list":
        return layer.ontology(args.get("source"))
    if name == "ontology.describe":
        return layer.describe(args["class"], args.get("source"))
    if name == "graph.neighbours":
        return layer.neighbours(
            args["class"], args["key"], relation=args.get("relation"),
            source=args.get("source"), depth=int(args.get("depth", 1)),
            as_of=args.get("as_of"))
    if name == "metric.get":
        return layer.metric(args["metric"], source=args.get("source"),
                            group_by=args.get("group_by"))
    if name == "context.build":
        return layer.context(task=args.get("task", ""),
                             entity=args.get("entity"),
                             budget_chars=int(args.get("budget_chars", 1200)),
                             as_of=args.get("as_of"))
    if name == "provenance.explain":
        return layer.provenance(args["citation"])
    raise KeyError(f"unknown tool {name!r}")


def handle(request: dict, layer) -> dict | None:
    """Handle one JSON-RPC message. Returns None for notifications."""
    if not isinstance(request, dict):
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "invalid request"}}
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None and str(method).startswith("notifications/"):
        return None
    try:
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL_VERSION,
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": SERVER_INFO}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in {tool["name"] for tool in TOOLS}:
                raise KeyError(f"unknown tool {name!r}")
            payload = _call(layer, name, arguments)
            result = {"content": [
                {"type": "text", "text": json.dumps(payload, default=str)}],
                "isError": False}
        else:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601,
                              "message": f"method not found: {method}"}}
    except Exception as exc:                      # noqa: BLE001 - to the client
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32000,
                          "message": f"{type(exc).__name__}: {exc}"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(layer, stdin=sys.stdin, stdout=sys.stdout) -> None:
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout.

    A malformed line is answered, not fatal: an agent's bug must not kill the
    server.
    """
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": f"parse error: {exc}"}}
        else:
            response = handle(request, layer)
        if response is not None:
            stdout.write(json.dumps(response, default=str) + "\n")
            stdout.flush()


def _build_layer(graph_path, sources):
    from api.service import MiddleLayer
    layer = MiddleLayer(graph_path)
    for origin in sources:
        layer.add_source(origin)
    return layer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="MCP server for the middle layer (stdio, JSON-RPC).")
    parser.add_argument("--graph", help="graph file; omit for in-memory")
    parser.add_argument("--source", action="append", default=[],
                        help="a source to connect/build (repeatable)")
    args = parser.parse_args(argv)
    layer = _build_layer(args.graph, args.source)
    try:
        serve(layer)
    finally:
        layer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
