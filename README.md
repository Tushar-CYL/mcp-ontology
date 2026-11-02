# The middle layer

Turn any data source into four things an AI or a BI tool can use:

```
  ANY DATA SOURCE   ──▶   THE MIDDLE LAYER   ──▶   BI / AI
  database file            1 ontology
  folder of files          2 knowledge graph
  postgres:// URL          3 semantic
                           4 context
```

No per-dataset code: the same command reads a shop, a hospital, a 121 MB
e-commerce export, or a 100-table lake.

## Start here

One file with everything you need: **[START_HERE.md](START_HERE.md)**

```powershell
python -m pip install -r requirements.txt
python run.py                         # built-in example
python run.py "C:\data\your.db"       # or a folder, a file, a URL
python ui.py                          # four tabs on localhost:8501
python -m pytest -q                   # 281 tests
```

## The four layers

| Folder | Layer | What it does |
|---|---|---|
| `ontology/` | 1 | Works out what kinds of thing exist, how one is identified, and what links them |
| `knowledge_graph/` | 2 | Rows become nodes and bitemporal edges; the graph can be rewound |
| `semantic/` | 3 | Proposes the metrics the columns support, compiles them to SQL |
| `context/` | 4 | Packs cited evidence under a hard budget, with what was dropped |

## The one idea that matters

**A guess must never read as a fact.** A declared foreign key is `measured`; a
link inferred from column names is `derived` and shown as a guess in the tables,
the diagram and the final answer.

## What else is here

- [START_HERE.md](START_HERE.md) — connect data and see output (one page).
- [SETUP.md](SETUP.md) — install, multi-source, review, API/MCP, troubleshooting.
- [docs/API.md](docs/API.md) — local HTTP API and MCP tools.
- [docs/benchmark/](docs/benchmark/README.md) — measured baselines (lake100, Olist).
- [docs/strategy/](docs/strategy/README.md) — research, positioning, scorecard
  (for the internal pitch, not needed to run the tool).
- [STATUS.txt](STATUS.txt) — what is done and what is next.

## Limits, stated plainly

It reads structure (tables, keys, types, dates), not business names; a rename
is a stored decision, not a code change. There is no Streamlit review screen
yet, no cloud connectors (Snowflake/Databricks) and no wired-in LLM — the
context pack is deterministic. See [STATUS.txt](STATUS.txt).
