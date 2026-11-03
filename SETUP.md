# SETUP

## What this is

One product, not one project per dataset. Point it at a data source and it
derives four layers — ontology, knowledge graph, semantic metrics, agent
context — then serves them to a UI, an API and an MCP agent.

```
   ANY DATA SOURCE   ──▶   THE MIDDLE LAYER   ──▶   BI / AI
   database file            1 ontology
   folder of files          2 knowledge graph
   postgres:// URL          3 semantic
                            4 context
```

No code is written per dataset. The same code reads a hospital database and a
121 MB, 1.55M-row shop export.

## Quick start

```powershell
python -m pip install -r requirements.txt
python run.py                 # all four layers in the terminal
python run_server.py --port 8000   # UI, API and MCP on http://127.0.0.1:8000
python -m pytest -q           # the test suite
```

`run.py` with no argument builds a small example shop, so a fresh copy always
has something to show.

Sources: a database file (`.db`, `.sqlite`, `.duckdb`), a folder of
CSV/TSV/Parquet/JSON/Excel files, an RDF graph file (`.nt`, `.nq`, and
`.ttl`/`.rdf`/`.jsonld` with `rdflib`), an `http(s)://` URL to one of those
files, `postgres://` / `mysql://` / `snowflake://` / `databricks://` URLs.
Snowflake and Databricks need their vendor driver (`pip install
snowflake-connector-python` or `databricks-sql-connector`); the connector copies
the tables to a temporary local CSV before the build, because the graph owns its
data to reopen warm.

### Several sources at once

```powershell
python run.py C:\data\erp C:\data\crm
python run.py orders.csv customers.csv
```

Each source is read separately and built into one graph. Nothing is merged
silently: every class, node and edge carries its source, and a query names a
source when the graph has more than one. A query that does not name one refuses
to guess.

### When a file is unreadable

A bad file does not take the folder down. It is skipped, the rest of the source
is still read, and the reason is reported as a warning (CLI, UI and
`schema.warnings` in code). A zero-byte file is skipped; two files with the same
name but different extensions both survive (`orders`, `orders_2`).

### Review what the machine proposed

Ontology and graph structure publish themselves. Business names, metric
definitions and the answer policy are proposals until a person decides.

```powershell
python -m review.cli --graph data\graphs\<graph>.duckdb list
python -m review.cli --graph data\graphs\<graph>.duckdb seed-relations --source <source>
python -m review.cli --graph data\graphs\<graph>.duckdb approve <item-id> --reviewer you
python -m review.cli --graph data\graphs\<graph>.duckdb reject <item-id> --rationale "not a KPI"
python -m review.cli --graph data\graphs\<graph>.duckdb publish semantic --source <source>
python -m review.cli --graph data\graphs\<graph>.duckdb audit <item-id>
```

`publish` refuses while an item of that kind is still pending. Every decision is
stored in the graph, not in a log file.

### Give an agent the evidence pack

```powershell
python -m api.http --graph data\graphs\<graph>.duckdb --port 8765
# GET /health /sources /ontology /describe /metric /neighbours
# POST /context with {"entity":{"class":"Customer","key":"1","source":"shop"}}

python -m api.mcp_server --graph data\graphs\<graph>.duckdb
# JSON-RPC over stdio:
#   ontology.list, ontology.describe, graph.neighbours,
#   metric.get, context.build, provenance.explain
```

Every fact in the pack has a provenance label and a citation; the pack respects
`budget_chars` and reports what it dropped. See [docs/API.md](docs/API.md).

### Benchmark it

```powershell
python benchmark.py --source data\example.db
python benchmark.py --fixture lake100
```

Writes a table to the terminal and, with `--json` / `--md`, a reproducible
report. Baselines are in `docs/benchmark/`.

## What you need

| | |
|---|---|
| **Python 3.10 or newer** | from [python.org](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"** |
| **~250 MB free disk** | the packages only; sample data is made on the spot |
| **Internet** | once, to install the packages |

## What it cannot do

It reads **structure** from the data — tables, keys, types, dates. It cannot
read **business names**: nothing in a schema says `tbl_cust_01` means Customer.
Discovery accepts a stored rename map (`discover(schema, names={...})`), but the
UI does not yet offer a place to enter one.

Not built yet: a Streamlit review screen, source-of-truth precedence between
sources, search over documents, cloud connectors, a time-travel UI control, and
any wired-in LLM. See [STATUS.txt](STATUS.txt).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | Run `python -m pip install -r requirements.txt` |
| `python` not found | Reinstall Python from python.org and tick "Add python.exe to PATH" |
| Port 8000 in use | Stop the other server, or pass `--port 8001` |
| App shows old code | Rebuild the UI: `cd frontend && npm run build`, then restart the server |
| Database is locked | DuckDB allows one writer; close other terminals/notebooks |
| First run feels slow | It is building the graph; later runs reopen it warm |
| `CERTIFICATE_VERIFY_FAILED` | Corporate TLS interception; see the `truststore` note in `requirements.txt` |

## What is in this folder

```
run.py          terminal demo of all four layers
run_server.py   Strata server: React UI, REST API and MCP over HTTP (/mcp)
frontend/       the React UI (npm run build -> frontend/dist)
benchmark.py    timing harness, current code
benchmarks/     deterministic 100-table lake + ground truth
ontology/       source readers, key inference, discovery
knowledge_graph/ graph store, build, cross-source resolution
semantic/       metric proposals + SQL compiler
context/        budget/packing + Agent Context Builder
review/         human review gate (store + CLI)
api/            service, local HTTP API, MCP stdio server
tests/          unit + integration (281 tests)
docs/           research pack, strategy pack, API, benchmark, proof
```

The two files that make this a product rather than a project are the engine
above `ontology/` (which is dataset-agnostic) and the review gate (which decides
what a human has to own).