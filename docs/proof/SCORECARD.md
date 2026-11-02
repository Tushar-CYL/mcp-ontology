# Scorecard — current vs better vs market

**Status:** skeleton. "Better version" columns are filled only from
`docs/benchmark/BENCHMARK.md` after Phase 2. "Market" columns are documented
research (`docs/research/`), never measured. No cell may be filled from memory.

**Claim rule:** "best in market" means best on the weighted criteria for the
defined job (`docs/strategy/better_version_blueprint.md` §3), with the losses
shown. A blanket "we are best" is not allowed.

## Criteria and weights (proposed; confirm at Gate 1)

| # | Criterion | Weight | Why it matters |
|---|---|---|---|
| C1 | Auto-authoring coverage + time (100-table lake) | 25% | the manager's first question |
| C2 | Provenance + approval gate (trust) | 20% | why an agent's answer can be trusted |
| C3 | Multi-source + cross-source source-of-truth | 15% | real enterprises have many systems |
| C4 | Bitemporal / as-of answers | 10% | nobody else documents it |
| C5 | Agent-native consumption (MCP/API, budget, citations) | 15% | the consumption angle |
| C6 | Local / $0 / private / durable / portable | 15% | our structural difference |
| — | Enterprise governance / connectors / scale / support | — | we do not claim these |

## Current version — measured baseline

| Criterion | Current version | Evidence |
|---|---|---|
| C1 auto-authoring | lake100: 100 tables → 100 classes, 141 relations, 4,864 nodes, 0 dangling, **15.67 s total**; Olist 121 MB/1.55M rows → 1,550,922 nodes / 640,501 edges, 0 dangling, **23.90 s**; p95 query 0.88 ms (lake100) / 3.78 ms (Olist). No coverage ground truth scored yet. | `docs/benchmark/README.md` |
| C2 trust | **gate exists** (`review/`): proposals, approve/reject, audit, publish refuses pending items; semantic/context can be gated. Persisted business renames and the review UI are still missing | `test_review.py`, `review/cli.py` |
| C3 multi-source | **works (core)**: N sources in one graph, per-source ids/counts/rebuild; **cross-source identity candidates with confidence** (`resolve.py`), never auto-merged; attribute precedence/merged view still missing | `test_multi_source.py`, `test_resolve.py` |
| C4 bitemporal | **present** in schema and in `graph.neighbours`/`context.build` via `as_of`; not in the UI | `store.py`, `api/service.py` |
| C5 agent-native | **API + MCP implemented** (`api/`): ontology, describe, neighbours, metric, context, provenance; context has budget/citations/dropped. Golden-question 5/5 not yet measured | `test_api.py` |
| C6 local/$0 | verified by construction; no cost benchmark | `requirements.txt`, local run |
| Warm reopen | **fixed** (was a crash for database sources); second process answers warm | `*_after_core.md`, `TestWarmReopen` |
| Tests | **281 pass** (165 app + 7 fixture + 24 multi-source/robustness + 10 resolution + 16 review + 12 context + 21 API + 13 RDF/URL + 7 triple-store + 3 connection-reuse + 3 labels), measured 177.3 s | this session |

## Better version — to be filled (targets)

| Criterion | Target | Actual | Status |
|---|---|---|---|
| C1 | 100-table lake: 100% tables→classes, relation recall/precision ≥90%, key accuracy ≥95%, ≤10 min, deterministic | 100 classes, 141 relations derived; recall/precision vs ground truth not yet scored; 15.67 s | partial |
| C2 | 100% facts tagged; gate blocks unapproved; audit rows; live demo | facts tagged + cited; gate blocks publish; audit rows; review UI pending | core done |
| C3 | 3-source product scenario: chosen source + alternatives + reason | 3-source candidates + confidence + alternatives demonstrated; precedence choice pending | partial |
| C4 | same question two dates → two correct answers, p95 < 200 ms | as-of in graph/API; two-date acceptance not yet scripted | partial |
| C5 | 5/5 golden questions via API/MCP; budget never exceeded; p95 assembly < 1 s | API/MCP + envelope built; context assembly measured ~3–20 ms; 5/5 not yet scored | partial |
| C6 | install → first graph < 5 min; $0; export fidelity test | local $0 verified; install timing/export test pending | partial |

## Market — documented (grade, not measured)

| Criterion | Market state | Evidence |
|---|---|---|
| C1 | every vendor requires a modelling step; AI assists authoring only | research 01 §1–2, 02 §1, 03 §6 |
| C2 | citations/lineage exist; per-fact grades do not; only Palantir documents an approval gate (staged writes) | research 01 §4, 04 §8 |
| C3 | entity resolution available in graph engines, but requires modelling/Spark; no source-of-truth decision layer | research 02 §4 |
| C4 | no bitemporal edge/model documentation found; Kùzu lesson on time | research 01 §12, 02 §3 |
| C5 | MCP everywhere; no hard-budget packer with dropped-facts record | research 04 §1, §7 |
| C6 | platform/cloud-bound; quote-only or seat/credit pricing; free tools can be archived | research 01 pricing, 03 pricing, 02 Kùzu |

## Wins and losses to present

**We expect to lead:** C1, C2, C4, C5, C6.
**We expect to trail:** enterprise governance, connector breadth, graph
throughput at scale, formal OWL reasoning, BI ecosystem, vendor support/brand.
**The deck shows the trailing list before the audience asks.**

## Sign-off

- [ ] Weights confirmed at Gate 1
- [ ] Better-version numbers filled from `BENCHMARK.md`
- [ ] Market cells carry grade + URL
- [ ] Losses slide reviewed by Arin
- [ ] Every spoken number traceable
