# Codebase walkthrough — from code terms to business terms

**Audience:** the manager, Arin, and anyone joining the pitch. After this
document and a 30-minute walkthrough you should be able to explain what each
layer does, what the code guarantees, and where it still stops.

The code is deliberately small: the engine is dataset-agnostic, and every new
dataset must work without a code change. If this page ever needs a per-dataset
special case, the product claim is false.

## 1. The one-sentence version

`connect()` reads any source into a neutral `Schema`; `discover()` turns that
into an `Ontology`; `build()` (one or many sources) writes nodes and bitemporal
edges; `discover_metrics()` + `compile_metric()` turn columns into governed
SQL; `resolve()` proposes cross-source identities; `context/assemble.py` packs
cited evidence under a budget; `review/` gates what a human must approve; and
`api/` serves all of it to agents, HTTP clients and the UI.

## 2. Data flow

```
  any source (SQLite/DuckDB, CSV/Parquet/JSON/Excel, Postgres/MySQL URL)
        │  ontology/connect.py  (bad files are skipped with a warning)
        ▼
  Schema (tables, columns, types, declared keys, row counts, readers)
        │  ontology/discover.py
        ▼
  Ontology (classes, keys, relations, time columns, measures,
            dimensions, stable codes, provenance measured|derived)
        │
        ├─ knowledge_graph/build.py ──▶ DuckDB:
        │     sources, classes, relations, nodes, edges,
        │     findings, entity_links, review_*, publish_state
        │
        ├─ knowledge_graph/resolve.py ─▶ cross-source same_as candidates
        │
        ├─ semantic/discover.py + compile.py ─▶ metrics + SQL
        │
        ├─ context/assemble.py ─▶ cited, budgeted evidence pack
        │
        └─ review/store.py ─▶ proposals, decisions, publish gate
        │
        ▼
  api/service.py ─▶ api/http.py (local HTTP)
                  ─▶ api/mcp_server.py (agent tools)
  app.py/ui.py    ─▶ four tabs
```

## 3. Reading order

1. [run.py](../run.py) — the whole product in one main, one section per layer.
2. [ontology/schema.py](../ontology/schema.py) — the neutral vocabulary.
3. [ontology/connect.py](../ontology/connect.py) — the only file that knows
   what a source looks like (and how to skip a bad file).
4. [ontology/keys.py](../ontology/keys.py) — identity when nobody declared one.
5. [ontology/discover.py](../ontology/discover.py) — schema → ontology.
6. [knowledge_graph/store.py](../knowledge_graph/store.py) — schema v2,
   source-aware queries, safe rebuild on an old graph.
7. [knowledge_graph/build.py](../knowledge_graph/build.py) — copy, nodes, edges,
   findings, per-source isolation.
8. [knowledge_graph/resolve.py](../knowledge_graph/resolve.py) — cross-source
   candidates and explanations (never a silent merge).
9. [semantic/](../semantic/) — metric catalogue and SQL compiler.
10. [context/budget.py](../context/budget.py) +
    [context/assemble.py](../context/assemble.py) — the evidence pack.
11. [review/](../review/) — the human gate, CLI in `review/cli.py`.
12. [api/](../api/) — the consumption surface.
13. [tests/](../tests/) — the living specification (281 tests).

## 4. Module map in business language

| File | Business meaning | Produces | Stops at |
|---|---|---|---|
| [run.py](../run.py) | "Show me all four layers" | terminal report, optionally several sources in one graph | no agent answer |
| [ui.py](../ui.py) / [app.py](../app.py) | "The screens a customer sees" | 4 tabs; the Context tab uses the real pack builder | no review screen, no multi-source UI yet |
| [ontology/connect.py](../ontology/connect.py) | "Connect anything" | `Schema` + warnings | no Snowflake/Databricks connectors yet |
| [ontology/keys.py](../ontology/keys.py) | "Find the identity nobody declared" | key or an honest "no key" | ambiguous cases need review |
| [ontology/discover.py](../ontology/discover.py) | "Derive the rules" | classes, relations, time, measures, stable codes | business names still need a human |
| [knowledge_graph/store.py](../knowledge_graph/store.py) | "Things and links, rewindable" | source-aware graph + traversal | no merged entity view |
| [knowledge_graph/build.py](../knowledge_graph/build.py) | "Build it from the data" | nodes/edges/findings for N sources | does not decide identity across sources |
| [knowledge_graph/resolve.py](../knowledge_graph/resolve.py) | "Same thing in two systems?" | candidates + confidence + explanation | does not choose source-of-truth automatically |
| [semantic/](../semantic/) | "One number, everywhere" | metric catalogue + SQL | no dbt/Cube import/export |
| [context/budget.py](../context/budget.py) | "Keep only what fits" | kept/dropped facts, drop-whole rule | — |
| [context/assemble.py](../context/assemble.py) | "The answer an agent can cite" | envelope: facts, citations, dropped, review state | no document search yet |
| [review/store.py](../review/store.py) | "Who approved this?" | proposals, decisions, audit, publish gate | Streamlit review screen next |
| [api/service.py](../api/service.py) | "One service, three transports" | ontology/describe/neighbours/metric/context | no auth/tenancy (out of scope) |
| [api/http.py](../api/http.py) | "Read-only local API" | JSON endpoints | binds to localhost by default |
| [api/mcp_server.py](../api/mcp_server.py) | "Let an agent ask" | 6 MCP tools over stdio | no write tools |
| [review/cli.py](../review/cli.py) | "Run the gate headless" | list/approve/reject/publish/audit | no UI |
| [tests/](../tests/) | "The spec that survives refactors" | 281 cases | golden-question score not measured yet |

## 5. Guarantees the code makes (say these out loud)

1. **Provenance:** every relation and every packed fact is `measured`,
   `derived` or `external`; the final answer keeps the label.
2. **Citations:** every fact in the Agent Context Builder envelope has a
   citation — table/column, edge id, node id, metric or entity link.
3. **No silent merging:** the same key in two sources is two nodes; resolution
   adds a candidate link with confidence, and a human can approve it.
4. **No silent data loss:** unreadable files/tables become warnings and
   findings; edges that point at nothing are counted, never dropped.
5. **Determinism:** class/relation codes are hashed from source+name; node ids
   are hashed from source+class+key; a rebuild does not renumber.
6. **Time, not just now:** every edge carries `valid_from`/`valid_to`;
   `-infinity` means "true with no start recorded".
7. **Idempotent rebuild:** a per-source signature decides whether to rebuild;
   rebuilding twice does not duplicate.
8. **Hard budget:** facts are dropped whole, never truncated; the dropped list
   is returned to the caller.
9. **Human gate:** semantic/context publishing is refused while a proposal of
   that kind is pending; every decision is audited.

## 6. Commands (verified 2026-10-30)

```powershell
python -m pip install -r requirements.txt
python run.py data\example.db
python run.py data\example.db data\hospital.db
python ui.py
python -m pytest -q                 # 281 tests
python benchmark.py --fixture lake100
python -m review.cli --graph <graph> list
python -m api.http --graph <graph>
python -m api.mcp_server --graph <graph>
```

## 7. Glossary for the pitch

| Code / term | Say this |
|---|---|
| class / relation | "a kind of thing / a kind of link" |
| `measured` | "the source declared it; it is a fact" |
| `derived` | "we inferred it; a strong hint, labelled everywhere" |
| synthetic key | "this table had no identity, so we numbered rows and said so" |
| `valid_from`/`valid_to` | "when the link was true — this lets us rewind" |
| metric | "one definition, compiled to SQL, same in UI/API/agent" |
| context envelope | "facts an AI may use, each with a citation and a budget" |
| `entity_links` | "a proposed cross-source identity; a human approves it" |
| review gate | "structure publishes itself; meaning waits for a person" |

## 8. What this walkthrough does not prove

- Recall/precision of discovery against ground truth (the lake100 ground truth
  exists; scoring is the next acceptance run).
- A 5/5 golden-question score through MCP.
- Attribute source-of-truth precedence or a merged entity view.
- Connectors beyond local files/databases.
- A review screen in the UI.

Those are the next items in [STATUS.txt](../STATUS.txt) and the progress note in
[PROGRESS_2026-10-30.md](proof/PROGRESS_2026-10-30.md).