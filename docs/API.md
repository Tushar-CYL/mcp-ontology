# API, MCP and the review gate

Three ways to consume the middle layer without touching its Python internals:
a local HTTP API, an MCP server for agents, and a review CLI for the human
gate. All three call the same `api.service.MiddleLayer`, so a metric or a
context pack cannot differ by transport.

## 1. Service (in-process)

```python
from api.service import MiddleLayer

layer = MiddleLayer("data/graphs/demo.duckdb")   # None = in-memory
layer.add_source("data/example.db")              # connect + discover + build
layer.add_source("data/raw/kaggledata", source="shop")

layer.ontology("shop")                           # classes + relations
layer.describe("Customer", "shop")               # key, time, metrics, count
layer.neighbours("Order", "o1", source="shop")   # links with provenance
layer.metric("total_sum", source="shop")         # definition + SQL + rows
layer.resolve()                                  # cross-source candidates
layer.context(entity=("shop", "Customer", "1"))  # cited, budgeted envelope
layer.provenance("edge:customer:c1")
```

## 2. Local HTTP API (standard library only)

```powershell
python -m api.http --graph data/graphs/demo.duckdb --source data/example.db --port 8765
```

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | status + loaded source ids |
| GET | `/sources` | registered sources |
| GET | `/ontology?source=` | classes, relations, counts |
| GET | `/describe?class=&source=` | one class |
| GET | `/neighbours?class=&key=&relation=&source=&depth=&as_of=` | links + provenance |
| GET | `/metric?name=&source=&group_by=` | definition, SQL, rows |
| POST | `/context` | envelope; body `{task, entity:{class,key,source}, budget_chars, as_of}` |
| POST | `/resolve` | cross-source candidates |

Errors are JSON with `{error:{type,message}}` and HTTP 400/404. The server is
read-only and binds to 127.0.0.1 by default.

## 3. MCP server (agents)

```powershell
python -m api.mcp_server --graph data/graphs/demo.duckdb --source data/example.db
```

JSON-RPC 2.0 over stdio; no dependency. Tools:

| Tool | Arguments | Use |
|---|---|---|
| `ontology.list` | `source?` | what exists |
| `ontology.describe` | `class`, `source?` | identity, time, measures |
| `graph.neighbours` | `class`, `key`, `relation?`, `source?`, `depth?`, `as_of?` | links with provenance |
| `metric.get` | `metric`, `source?`, `group_by?` | governed number |
| `context.build` | `task?`, `entity?`, `budget_chars?`, `as_of?` | cited evidence pack |
| `provenance.explain` | `citation` | where a fact came from |

Example session (one JSON object per line):

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"context.build","arguments":{"entity":{"class":"Customer","key":"1","source":"shop"}}}}
```

The `context.build` result is the Agent Context Builder envelope:

```json
{
  "focus": {"source": "shop", "class": "Customer", "key": "1"},
  "answer": "Customer 1 from shop: 6 facts kept, 0 dropped.",
  "facts": [{"text": "Its city is London.", "provenance": "measured",
             "citation": "customers.city", "as_of": null}],
  "dropped": [],
  "sources": ["shop"],
  "review_pending": 0,
  "budget_chars": 1200, "chars": 211,
  "latency_ms": 3.1
}
```

An agent cannot get a fact without a provenance label or a citation.

## 4. Human review gate (CLI)

```powershell
python -m review.cli --graph data/graphs/demo.duckdb list
python -m review.cli --graph data/graphs/demo.duckdb seed-relations --source shop
python -m review.cli --graph data/graphs/demo.duckdb approve <item-id> --reviewer arun
python -m review.cli --graph data/graphs/demo.duckdb reject <item-id> --rationale "not a KPI"
python -m review.cli --graph data/graphs/demo.duckdb publish semantic --source shop
python -m review.cli --graph data/graphs/demo.duckdb audit <item-id>
```

Rules enforced in `review/store.py`:

- ontology/KG may publish automatically (the graph is structural and carries
  confidence);
- semantic and context publishing is refused while a proposal of that kind is
  still `proposed`;
- a rejected proposal counts as decided and does not block;
- every decision is appended to `review_decisions` — the audit trail is data,
  not a log file;
- approval of a cross-source identity changes only the link's status; the
  per-source nodes stay, so the answer can still cite the source.

## 5. What is deliberately not exposed

- No raw SQL endpoint, no graph mutation, no file upload.
- No authentication/authorisation — this is a local prototype; the production
  design (RBAC, tenancy, network policy) is documented as out of scope.
- No LLM call in the service. The context pack is deterministic; a host agent
  may phrase the final sentence, but the facts do not move.
