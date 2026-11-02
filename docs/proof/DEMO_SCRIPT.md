# Demo script — 10 minutes, three scenarios

Rehearsed twice with Arin. Every number spoken must come from
`docs/benchmark/BENCHMARK.md` (better version) or
`docs/benchmark/baseline/` (current version). The script below uses the
scenario names from `docs/strategy/problem_statements.md` §5.

## Before the room (setup checklist)

```powershell
.\.venv\Scripts\python.exe benchmarks\fixture_lake100.py --out data\fixtures\lake100
.\.venv\Scripts\python.exe run.py data\fixtures\lake100      # prebuild, then stop
.\.venv\Scripts\python.exe ui.py                             # open the four tabs
```

- Pre-build every graph the demo touches. A cold build is fine to *talk about*,
  not to wait for.
- Have a recording of the same flow as fallback.
- Do not run two copies of the app (Streamlit stale-copy trap; `ui.py` kills it).
- The old warm-reuse crash is fixed: a database source reopened without a
  rebuild now answers normally (verified in `docs/benchmark/baseline/*_after_core.md`).
- Additional sources can be built into the same graph: `python run.py srcA srcB`.

## Minute-by-minute

**0:00 — The pain (no screen).**
"At 3am, an on-call engineer gets a page. Today it takes forty minutes because
the answer is split across a dashboard that knows numbers, a tracing tool that
knows one request, a wiki that is out of date, and nobody knows who owns what.
And by the time you look, the system has already changed."
Thirty seconds. No slides.

**0:40 — Scenario A, authoring.**
Show `python run.py data/fixtures/lake100` output (prebuilt).
Point at: 100 tables → 100 classes, 141 relations, 0 dangling links, the time,
the three product masters, the `derived` relations.
Say: "No code was written for this dataset. The structure is derived; the
guesses are labelled."

**2:00 — Scenario B, consumption.**
Ask the agent: *"How much A-pack did we sell in the EU last quarter?"*
Show the answer envelope: facts, citations, as-of, chosen source, alternatives,
latency, dropped facts.
Say: "The agent did not guess. It got an evidence pack with receipts."

**4:00 — Scenario C, trust.**
- Open a `derived` link; show the method and confidence.
- Open the review queue; approve one metric live.
- Show the API refusing an unapproved metric (`review_pending`).
Say: "Ontology and graph publish themselves. Semantic and context wait for a
human — that is the line we drew."

**6:00 — The scorecard.**
Show the weighted table: current vs better vs documented market. Read two wins
and one loss out loud.
Say: "We are not the best at enterprise catalogs or graph throughput. We are
best at the onboarding-plus-trust-plus-context job — and here is the evidence."

**7:30 — Where paying wins.**
List the loss slide before anyone asks. Then: "If you are already standardised
on Databricks, use it; we make the layer it does not derive."

**8:30 — Market evidence in one breath.**
"Every vendor we studied requires a modelling step first; none labels a guessed
link as a guess; none documents as-of answers on the model; none packs context
under a budget. That is the gap we are in."

**9:30 — The ask.**
One pilot schema/data set, one review session with their data team, a date for
Gate 2. End on the request, not a summary.

## If they ask the hard questions

- "Is this real data?" — the 100-table lake is synthetic and deterministic; the
  real-data evidence is Olist/hospital; state which is which.
- "What about our data?" — connect their schema live (read-only); show the first
  model; do not promise coverage.
- "Why not Databricks/Atlan/Neo4j?" — they are model-first/platform-bound; we
  derive and pack; complementary where they already exist.
- "How is this not another context layer?" — Agent Context Builder: budget,
  provenance, dropped-facts record; define it once.
- "Can I trust the auto model?" — show confidence + review gate; say what is
  impossible from data (ownership, intent).
- "What is missing?" — say it: RBAC at scale, connectors, graph throughput,
  support; all documented in the scorecard's loss column.

## Post-demo

- Leave the one-page positioning (`docs/strategy/positioning.md`).
- Offer the research pack (`docs/research/`) and the benchmark reproduction.
- Collect the client's schema/questions for the pilot.
