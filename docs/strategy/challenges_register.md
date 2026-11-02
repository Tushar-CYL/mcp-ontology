# Challenges register — better middle layer

Living document. Every challenge has an owner, an impact, and a mitigation that
is either already in the plan or an explicit decision. Review at Gate 1 and
Gate 2; do not let a challenge live only in conversation.

**Status key:** `open`, `mitigating`, `closed`, `accepted` (we knowingly live
with it and say so in the deck).

## A. Research and evidence

| ID | Challenge | Impact | Likelihood | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R1 | Vendor marketing treated as fact | Research becomes a sales deck; senior buyers discount it | High | Every claim graded A–D (A = measured by us, B = vendor docs, C = independent, D = inference); quote + URL + date; "documented vs measured" column | Lead | mitigating |
| R2 | Category blur: catalog vs ontology vs semantic vs context | Apples-to-oranges comparisons; "everyone does that" | High | Fixed definitions in [definitions.md](definitions.md); overlap column in the matrix | Lead | mitigating |
| R3 | Paid tools are not accessible for hands-on testing | Our "measured" claims only cover the free/local side | High | Mark market side as documented; optional free trials only with approval; never present documented as measured | Lead / manager | open |
| R4 | Fast-moving market (Neo4j Context Engine, MCP, GraphRAG are recent) | Findings date quickly | Medium | Date-stamp every claim; 2-week timebox; refresh list at Gate 1 | Lead | mitigating |
| R5 | Research never becomes product | Deck without capability, or capability without story | Medium | Gate 1 decision; every differentiator maps to a demo test + metric | Lead / Arin | mitigating |
| R6 | "Best in market" overclaim | One overclaim discredits the whole story | High | Weighted scorecard with explicit losses; claims limited to named criteria and job; no number without `BENCHMARK.md` | Lead | mitigating |
| R7 | Studies from vendor case studies are self-selected | Outcomes look better than reality | Medium | Label vendor case studies; seek independent evidence; state selection bias | Lead | open |

## B. Product and engineering

| ID | Challenge | Impact | Likelihood | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| E1 | Execution environment was blocked (sandbox could not grant ACLs on `D:\`) | No tests, no measured baseline | Was certain | **Closed for this session:** the approved danger-full-access policy runs `.venv\Scripts\python.exe`; baseline captured. Re-verify on any new machine. | Lead | closed |
| E2 | Single-source design: ids/classes collide if two sources are merged naively | Multi-source feature would corrupt data | Certain if unhandled | **Closed 2026-10-29:** schema v2 with source registry, source in class/relation/node identity, namespaced codes, per-source rebuild; tests in `tests/integration/test_multi_source.py` | engineering | closed |
| E3 | Cross-source entity resolution false merges | Wrong answers, lost trust | Medium | Confidence tiers; `same_as` links never silent collapse; human confirm for low confidence; precedence + freshness explained. `entity_links`/`attribute_rules` tables exist; resolver is next | engineering | open |
| E4 | Human-in-the-loop becomes a rubber stamp | Approval adds latency without trust | Medium | Small review queue sorted by confidence; bulk approve; audit; measure review time and edit rate | engineering | open |
| E5 | Scale/timeouts on 100 tables (profiling every column) | Demo fails or takes minutes | Medium | Sampled profiling option; incremental rebuild; per-source isolation; hidden timing budget in benchmark | engineering | open |
| E6 | Benchmark is ours and could be gamed | "Best" claim fragile | Medium | Ground truth tracked; real datasets (Olist, hospital) also tested; reproduce command published; adversarial cases from the existing torture suite | Lead | mitigating |
| E7 | Our 100-table lake is synthetic | Results may not transfer to customer data | Medium | Real-dataset acceptance alongside the fixture; publish both; invite the manager to bring a real schema | Lead | open |
| E8 | Connectors (Snowflake/Databricks) need accounts and approvals | Cannot demo live ingestion | High | Adapter interfaces + documented semantics; credential-gated tests; no cloud upload without approval | Lead / manager | open |
| E9 | LLM nondeterminism if we wire one in | Demo answers drift | Medium | Deterministic assembler first; optional local model; fixed prompt + temperature 0; cached answers for rehearsal | engineering | open |
| E10 | Context layer has no task planner/retrieval today | Agent answers are shallow | Certain | Context v2: question → evidence selection → citations → budget; API returns envelope | engineering | open |
| E11 | Legacy docs/code mislead users (SETUP, STATUS, db.py, ARCHITECTURE/STORY) | Lost afternoons; manager distrust | Certain | Foundation task: rewrite SETUP/STATUS, delete db.py, move legacy docs with banner | engineering | mitigating |
| E12 | requirements.txt misses streamlit/pytest | Fresh install cannot run UI/tests | Certain | Add both; mark future deps clearly as optional | engineering | mitigating |
| E13 | Invisible U+001F separator in build.py | Composite keys could silently corrupt after an edit | Low | Replace raw control chars with the escaped `\u001f` everywhere; test one composite key round-trip | engineering | open |
| E14 | 7.99 GB Alibaba DB and old artifacts may bias runs/disk | Slow tests or accidental dependency on old data | Medium | Keep old data out of the acceptance path; use example/Olist/lake100; document which files are legacy | Lead | open |
| E15 | Warm reopen of a database source crashes (`s.<table>` missing on the second process) | A live demo that restarts the app fails; `run.py` twice fails | Was certain | **Closed 2026-10-29:** every source table is materialised during the build; warm reopen verified by `TestWarmReopen` and `*_after_core` benchmarks (`sample query runs=True`). Cost: build 6.0s→8.1s on lake100 | engineering | closed |
| E16 | Graph file is 38.8 MiB for 4,864 rows (copies + page overhead) | Multi-source graph may get large/slow | Medium | Keep the copy-based model for correctness in this phase; measure three sources; optimise/attach instead of copy only if the benchmark demands it | engineering | accepted for now |

## C. Product story and company pitch

| ID | Challenge | Impact | Likelihood | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| P1 | Audience is 20–25-year experienced buyers | Basic claims get challenged hard | Certain | FAQ bank (15 questions), scorecard with losses, live demo, every number traceable | Arin / Lead | open |
| P2 | "Everyone is building ontology" | Differentiation is not heard | Certain | Open with the derived/approved/agent-ready sentence, not the layer list; show the demo beat where a rule fails | Arin | open |
| P3 | Two angles (authoring vs consumption) confuse the story | Buyers don't know what is being sold | High | One narrative with two acts; same demo, two views; explicit "what you get today" vs roadmap | Arin / Lead | open |
| P4 | The company may want "best in market" as a blanket claim | Credibility risk | Medium | Agreed phrasing: best on named criteria for a named job; losses slide kept | Lead / manager | open |
| P5 | Demo fragility (live build, live agent) | A crash in front of the room ends the meeting | Medium | Prebuild the graph in the demo script; deterministic agent; fallback recording; "live system, not a recording" rule from the legacy STORY | Lead | open |
| P6 | Terminology mismatch with manager/Manoj's definition | Rebuild work, misalignment | High | Definitions doc at Gate 1; walkthrough session; confirm OWL/RDF expectations | Lead / manager | open |
| P7 | Data licensing for demo datasets | Legal/optics risk | Low | Public datasets only (Olist, Alibaba, flights, hospital synthetic); no customer data; local execution | Lead | open |
| P8 | Team bandwidth (Arin story, Pooja infographic, Manoj definitions, Tushar code) | Slipped gates | High | Gate reviews, disjoint workstreams, 2-week research timebox, build only approved scope | Lead | mitigating |

## D. Decisions we must take (not risks, but unmade choices)

| ID | Decision | Default if nobody decides | Deadline |
|---|---|---|---|
| D1 | First vertical/account to tailor the story to | Retail/e-commerce (Olist) | Gate 1 |
| D2 | Cloud trials / uploading public data to Snowflake or Databricks | No upload; documented only | Gate 1 |
| D3 | External name for layer 4 | "Agent Context Builder" | Gate 1 |
| D4 | Is "best in market" acceptable as "best on named criteria"? | Yes, with losses slide | Gate 1 |
| D5 | Hands-on scope for Phase 2 (which connectors, LLM or not) | CSV/Parquet/SQLite/Postgres + optional local LLM | Gate 1 |
| D6 | Target hardware for benchmark comparisons | This machine, documented | M0 |
