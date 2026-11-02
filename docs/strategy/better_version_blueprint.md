# Better-version blueprint

The research says the market is model-first, manual, enterprise-priced and weak
on derivation, time and per-fact provenance (`docs/research/`). The better
version keeps the four-layer shape and attacks exactly those weak points. This
is the build contract; the status at the bottom says what has landed.

## 1. Product statement

> **Authoring:** connect any source; in minutes get a derived ontology, a
> time-aware knowledge graph, candidate metrics and an agent-ready context pack —
> with confidence on every element and a human approval gate where judgment is
> required.
>
> **Consumption:** expose the approved artifacts through an API and an MCP
> server so any agent gets cited, time-stamped, provenance-graded evidence
> inside a hard size budget — locally, with no platform contract.

```
AUTHORING ANGLE                                          CONSUMPTION ANGLE
any source ─▶ derive ─▶ confidence ─▶ review gate ─▶ publish ─▶ API / MCP ─▶ agents, BI, apps
              layers      labels      (semantic,                envelope:
                                     context)                 facts + sources + as-of + budget
```

## 2. The bets (from `gap_analysis.md`)

| # | Bet | What "better" means | Proof metric |
|---|---|---|---|
| B1 | Auto-authoring with confidence | 100-table lake: all tables→classes, keys, relations, time, measures derived with no per-dataset code | coverage %, relation recall/precision ≥90%, key accuracy ≥95%, build ≤10 min, deterministic |
| B2 | Provenance + approval gate | every element tagged `measured`/`derived`/`external` + confidence; semantic/context require approval; audit persisted | 100% tagged; gate blocks live; audit rows; review time measured |
| B3 | Bitemporal answers | same question at two dates returns two correct, different answers | as-of test on a changing fixture; p95 query time |
| B4 | Agent Context Builder + MCP/API | agent asks; gets a hard-budget pack with citations, provenance, as-of and what was dropped | 5/5 ground-truth questions; budget never exceeded; p95 assembly ≤1 s |
| B5 | Multi-source + cross-source source-of-truth | connect N sources; same product in 3 sources resolved with chosen source + alternatives + reason | 3-source scenario answers correctly; no silent merge |
| B6 | Local/$0/durable/portable | laptop, no Docker/account, data stays local, export paths | $0 licence; install→first graph <5 min; export test |

## 3. Capability matrix — the answer to "how automatic is it?"

| Capability | Automatic | Auto + confidence | Human approval | Impossible from data |
|---|---|---|---|---|
| tables → classes | ✅ | | | |
| identity/key discovery | ✅ (unique+non-null) | ✅ ambiguous | rename/confirm | which column is *the* business key |
| relations | ✅ declared FKs | ✅ name/profile inference | ✅ inferred/ambiguous | true meaning of a link |
| time validity | ✅ date column | ✅ candidate dates | ✅ semantics | "valid from" vs "updated" |
| business names | | | ✅ stored rename | names not in the data |
| measures/dimensions | ✅ type-based | | ✅ metric definition | whether a number is a KPI |
| business metrics | proposals | ✅ candidate SQL | ✅ definition + owner | targets/policy |
| cross-source identity | blocking + rules | ✅ fuzzy with confidence | ✅ low confidence | "same entity" with no shared keys |
| context answer | deterministic assembly | | ✅ answer policy | business context outside the data |
| ownership | if in metadata | | ✅ otherwise | org chart not in data |

**Rule:** ontology/KG auto-publish with findings; **semantic + context are
gated** until approved.

## 4. Target architecture (implemented)

```
 SOURCES (read-only, local)                         STORAGE (boring, portable)
 SQLite/DuckDB · CSV/Parquet/JSON/Excel             DuckDB graph file
 Postgres/MySQL · Snowflake*/Databricks* (planned)  + vector/BM25 index (retrieval only)
        │
        ▼
 ┌────────────────────────────────────────────────────────────────────────────┐
 │ THE MIDDLE LAYER                                                           │
 │  connect_many ─▶ Schema(s) ─▶ derive ─▶ Ontology + confidence              │
 │                                      │                                     │
 │                          Knowledge graph (nodes, bitemporal edges,        │
 │                          source, findings)                                │
 │                                      │                                     │
 │                          cross-source resolution (same_as, confidence)    │
 │                                      │                                     │
 │                    ┌────────── REVIEW GATE ──────────┐                    │
 │                    │ proposals: names, inferred      │                    │
 │                    │ relations, metrics, policies    │                    │
 │                    │ approve / edit / reject + audit │                    │
 │                    └───────────────┬─────────────────┘                    │
 │                                    │ approved                              │
 │                                    ▼                                       │
 │              Semantic layer (metric catalogue, owners, definitions)       │
 │                                    │                                       │
 │                                    ▼                                       │
 │              Agent Context Builder (task → evidence → budget → citations) │
 └──────────────────────────────┬─────────────────────────────────────────────┘
                                │  API / MCP
                                ▼
                  AGENTS · BI · APPS   (trust envelope in every answer)
```

## 5. Data model v2 (DuckDB graph)

`classes`, `relations`, `nodes`, `edges`, `build_info`, `findings` now carry a
`source_id`; the graph also stores `sources`, `review_items`,
`review_decisions`, `publish_state`, `entity_links`, `attribute_rules`.
Node id = md5(source + class + key); class/relation codes are hashed from
source+name. A graph from the old schema is dropped and rebuilt (derived
artifacts only).

## 6. Review gate

- Auto-publish: classes, keys with high confidence, declared relations,
  measures, graph build, findings.
- Proposals: business names, inferred/ambiguous relations, time-column choice,
  metric definitions, context policy, low-confidence entity matches.
- States: `proposed → approved | rejected | edited`; every decision audited.
- Gate: semantic/context artifacts cannot be served until their publish state
  is approved; a pending item blocks `publish`.

## 7. Agent Context Builder

```
task ─▶ intent/entity ─▶ evidence: props · direct links · indirect links ·
        cross-source matches · findings · review state
     ─▶ rank measured > derived > external · pack whole facts under budget ·
        record drops
     ─▶ envelope {focus, answer, facts[{text, provenance, citation, as_of}],
                  dropped[], sources[], review_pending, budget_chars, chars,
                  latency_ms}
```

Deterministic; no LLM required. Every fact carries a citation. A vector/BM25
index is storage for retrieval, not a layer.

## 8. API / MCP contract

| Tool | Returns |
|---|---|
| `ontology.list` / `ontology.describe` | classes, relations, key, time, measures |
| `graph.neighbours` | links with edge provenance |
| `metric.get` | definition + SQL + rows |
| `context.build` | the envelope above |
| `provenance.explain` | what a citation refers to + pending review counts |

HTTP mirrors these at `/ontology`, `/describe`, `/neighbours`, `/metric`,
`/context`, plus `/health`, `/sources`, `/resolve`.

## 9. Multi-source and cross-source identity

- `connect_many` + `build_many`; one bad source never aborts the others.
- Per-source rebuild; ambiguity refused rather than guessed.
- `resolve()` proposes `same_as` candidates when class names match (or share a
  meaningful stem) and keys overlap, with confidence lowered by low overlap.
- Nodes are never merged; approval changes the link status only.
- Attribute precedence (`attribute_rules`) is modelled but not enforced yet.

## 10. Proof plan

- Before/after on the same fixtures: `data/example.db`, `data/hospital.db`,
  Olist CSVs and the 100-table lake with tracked ground truth.
- Metrics: timings, node/edge counts, dangling edges, relation/key accuracy vs
  ground truth, review items, budget compliance, answer correctness, file size.
- Outputs: `docs/benchmark/BENCHMARK.md` + `docs/proof/SCORECARD.md`.
- Acceptance: B1 thresholds; B2 gate live; B3 as-of test; B4 5/5; B5 3-source
  scenario; `python -m pytest` green.

## 11. Non-goals

Production RBAC/SSO/multi-tenancy, BI dashboards, graph algorithms, full
connector catalogue, cloud requirement, paid dependency for the demo, or
replacing Databricks/Atlan/Neo4j. We complement them and beat them on the
onboarding + trust + context-packing job.

## 12. Build order and status (2026-10-30)

1. Warm-reopen defect — **fixed** (materialise every source table).
2. Foundation (requirements, docs, benchmark harness, lake100) — **done**.
3. Multi-source registry + schema v2 + safe rebuild — **done**.
4. Cross-source identity candidates — **done** (precedence next).
5. Review gate (store + CLI) — **done** (UI next).
6. Agent Context Builder — **done** (document search next).
7. API + MCP — **done**.
8. Review UI, golden-question score, source precedence, connectors — **next**.

Every step keeps the suite green (281 tests) and adds tests; no step ships
without a benchmark or a test.