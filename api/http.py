"""HTTP API: the same service over plain HTTP, with no framework dependency.

FastAPI would be nice, but a client machine may not be allowed to install it,
and this project's promise is "python and the requirements, nothing else".
The standard library is enough for a local, read-only API.

    python -m api.http --graph data/graphs/shop.duckdb --source data/example.db --port 8765

    curl http://127.0.0.1:8765/health
    curl http://127.0.0.1:8765/ontology
    curl -X POST http://127.0.0.1:8765/context \
         -H "Content-Type: application/json" \
         -d '{"entity":{"class":"Customer","key":"1","source":"shop"}}'

Endpoints are read-only. Nothing here can mutate a source or the graph; the
review decision endpoints are local CLI/UI operations on purpose.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def make_handler(layer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MiddleLayer/0.2"

        # ------------------------------------------------------ helpers
        def _send(self, payload, status: int = 200) -> None:
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _fail(self, status: int, exc: Exception) -> None:
            self._send({"error": {"type": type(exc).__name__,
                                  "message": str(exc)}}, status)

        def _query(self) -> dict:
            return {k: v[0] for k, v in
                    parse_qs(urlparse(self.path).query).items()}

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError(f"body is not JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError("body must be a JSON object")
            return data

        # -------------------------------------------------------- routes
        def do_GET(self) -> None:                # noqa: N802 - stdlib naming
            path = urlparse(self.path).path
            q = self._query()
            try:
                if path == "/health":
                    self._send({"status": "ok",
                                "sources": [s["source_id"]
                                            for s in layer.sources()]})
                elif path == "/sources":
                    self._send({"sources": layer.sources()})
                elif path == "/ontology":
                    self._send(layer.ontology(q.get("source")))
                elif path == "/describe":
                    if "class" not in q:
                        raise KeyError("query parameter 'class' is required")
                    self._send(layer.describe(q["class"], q.get("source")))
                elif path == "/metric":
                    if "name" not in q:
                        raise KeyError("query parameter 'name' is required")
                    self._send(layer.metric(q["name"],
                                            source=q.get("source"),
                                            group_by=q.get("group_by")))
                elif path == "/neighbours":
                    self._send(layer.neighbours(
                        q.get("class", ""), q.get("key", ""),
                        relation=q.get("relation"),
                        source=q.get("source"),
                        depth=int(q.get("depth", 1)),
                        as_of=q.get("as_of")))
                else:
                    self._send({"error": {"message": f"no route {path}"}}, 404)
            except Exception as exc:              # noqa: BLE001 - to the client
                self._fail(400, exc)

        def do_POST(self) -> None:               # noqa: N802 - stdlib naming
            path = urlparse(self.path).path
            try:
                body = self._body()
                if path == "/context":
                    entity = body.get("entity")
                    self._send(layer.context(
                        task=body.get("task", ""), entity=entity,
                        budget_chars=int(body.get("budget_chars", 1200)),
                        as_of=body.get("as_of")))
                elif path == "/resolve":
                    self._send({"candidates": layer.resolve()})
                else:
                    self._send({"error": {"message": f"no route {path}"}}, 404)
            except Exception as exc:              # noqa: BLE001 - to the client
                self._fail(400, exc)

        def log_message(self, format, *args):    # noqa: A002 - stdlib signature
            pass                                 # keep the demo console quiet

    return Handler


def make_server(layer, host: str = "127.0.0.1", port: int = 8765):
    """Create (but do not start) the HTTP server; port 0 picks a free port."""
    return ThreadingHTTPServer((host, port), make_handler(layer))


def main(argv=None) -> int:
    from api.service import MiddleLayer
    parser = argparse.ArgumentParser(description="Local HTTP API for the "
                                                 "middle layer.")
    parser.add_argument("--graph", help="graph file; omit for in-memory")
    parser.add_argument("--source", action="append", default=[],
                        help="a source to connect/build (repeatable)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    layer = MiddleLayer(args.graph)
    for origin in args.source:
        layer.add_source(origin)
    server = make_server(layer, args.host, args.port)
    host, port = server.server_address[:2]
    print(f"Middle layer API on http://{host}:{port}  (Ctrl+C stops it)")
    print("Try /health, /sources, /ontology; POST /context with a JSON body.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
        layer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
