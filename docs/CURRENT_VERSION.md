# Current version — audit and baseline

**Status:** verified 2026-10-30 on this machine. This file keeps the honest
"before" picture and the current measured state separate. Every number is
labelled **verified** (we ran it), **reported** (inherited, not re-measured) or
**unknown**. No pitch may upgrade "reported" to "verified" without a benchmark
line.

## 1. What this is

A local Python "middle layer": any source in, four derived artifacts (ontology,
knowledge graph, semantic metrics, agent context) out, with a UI, a local HTTP
API and an MCP server. No per-dataset code. No server, no Docker, no account.

- Repository (per STATUS): `https://github.com/Tushar-CYL/mcp-ontology`
- Earlier path: `D:\tushar\ontology` (the venv and legacy docs still point
  there); this copy is `D:\tushar\new_latest\ontology`.
- Built by the internal team. **No external users; no deployed instance.**
- Earlier generations (the Alibaba four-arm R&D and the `domains/` engine) are
  no longer part of the repo; the current engine is source-agnostic.

## 2. Verified environment

| Item | Value |
|---|---|
| OS | Windows 11 |
| Interpreter | Python 3.14.7 (`.venv\Scripts\python.exe`) |
| DuckDB | 2.0.0 |
| Streamlit | 1.66.1 |
| pytest | 9.2.0 |
| pandas (optional app fallback) | 3.1.0 |
| Tests | **281 pass** (165 application + 7 fixture + 24 multi-source/robustness + 10 resolution + 16 review + 12 context + 21 API + 13 RDF/URL + 7 triple-store + 3 connection-reuse + 3 labels); ~81 s |

## 3. Measured baselines (after the core build, same machine)

Every source table is now materialised into the graph, so a warm reopen is a
pure read. The cost is a slower cold build; the benefit is that the second
process works.

| Source | connect | cold build | warm reopen | total | nodes / edges | dangling |
|---|---:|---:|---:|---:|---|---:|
| lake100 (100 tables, 4,864 rows) | 2.18 s | 8.13 s | 0.08 s | **15.67 s** | 4,864 / 6,347 | 0 |
| Olist (9 CSV, 121 MB, 1.55M rows) | 2.18 s | 20.50 s | 0.14 s | **23.90 s** | 1,550,922 / 640,501 | 0 |
| example.db | 0.18 s | 0.28 s | 0.07 s | **0.79 s** | 21 / 21 | 0 |
| hospital.db | 0.22 s | 0.28 s | 0.07 s | **0.79 s** | 13 / 13 | 0 |

Query latency: p50 0.70 ms / p95 0.88 ms on lake100; p50 2.08 ms / p95 3.78 ms
on Olist (one representative metric, 20 runs after warm-up). Full runs and
reproduction: [docs/benchmark/README.md](benchmark/README.md) and
`docs/benchmark/baseline/*_after_core.*`.

The pre-core baseline (single-source attach, warm reopen broken) is kept as
`*_current.*` for an honest before/after; do not mix the two tables.

## 4. Capability now

| Area | State | Evidence |
|---|---|---|
| Ontology | works: classes, keys, relations, time, measures, stable codes, provenance | `ontology/discover.py`, tests |
| Knowledge graph | works: bitemporal edges, findings, traversal, per-source rows | `knowledge_graph/`, tests |
| Semantic | works but shallow: auto-proposed counts + 6 aggregates, SQL compiler | `semantic/`, tests |
| Context | works: cited, budgeted evidence pack with dropped list | `context/assemble.py`, tests |
| Multi-source | works: N sources, source_id everywhere, per-source rebuild, ambiguity refused | `test_multi_source.py` |
| Source robustness | works: bad file skipped with warning, duplicate stems, empty file | `test_sources_robust.py` |
| Cross-source identity | works: candidates + confidence + explanation; **not merged silently** | `knowledge_graph/resolve.py`, `test_resolve.py` |
| Review gate | works: propose/approve/reject, audit, publish refusal; CLI | `review/`, `test_review.py` |
| API / MCP | works: local HTTP + MCP stdio; 6 tools; trust envelope | `api/`, `test_api.py` |
| UI | works: 4 tabs; Context tab uses the real pack builder | `app.py`, AppTest |
| Review UI | **not built** | next |
| Source-of-truth precedence / merged view | **not built** | next |
| Search over documents | **not built** | roadmap |
| Cloud connectors | **not built** | roadmap |
| Time travel in the UI | API/graph support it; no control | roadmap |
| Wired-in LLM | **deliberately absent** (facts are deterministic) | design |

## 5. Claims that must NOT be reused as-is

From the earlier Alibaba generation, **reported** not verified here: 1.27M
things / 1.52M links; 1,550,922 things in 14 s; blast radius 2,591 vs 2,055;
34,594 wrong-kind links and 10,969 dangling ids; 5,878 hash collisions.
Re-measure on the current benchmark before any slide uses them.

## 6. Defects: fixed and remaining

Fixed: dead `db.py` deleted; requirements now include streamlit+pytest; SETUP
and STATUS rewritten; legacy docs moved; warm reopen crash fixed; invisible
U+001F separator replaced by an escaped constant; a bad file no longer aborts a
folder; `is_current` is per source.

Remaining: review/multi-source screens; attribute precedence; golden-question
acceptance score; connector interfaces; document search.

## 7. What the better version must preserve

The four-layer shape, the provenance rule ("a guess must never read as a
fact"), citations on every packed fact, local/$0/no-Docker, one engine for any
source, and a one-command demo a non-engineer can run.

## 8. What "better" is measured against

1. This baseline (same fixtures, before/after).
2. Documented market capability in `docs/research/` with evidence grades.
3. The five bets in `docs/strategy/better_version_blueprint.md` — measured by
   `docs/benchmark/` and summarised in `docs/proof/SCORECARD.md`.