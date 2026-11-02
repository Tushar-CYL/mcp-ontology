# Deck outline — 12–15 slides

Audience: 20–25-year-experienced buyers and the internal manager. Rule: every
number is traceable to `docs/benchmark/` or a graded research row; no invented
figures; losses shown before the audience asks.

## Slide 1 — Title
**The Middle Layer.** Ontology · knowledge graph · semantic · context — derived
from any source, approved by your people, consumed by any agent.
*Local. $0 licence. Honest about what it guessed.*

## Slide 2 — The question in the room
"Can a platform create ontology/KG from our 100-table lake? To what extent?
What human support is needed? Same for semantic and context."
Answer up front: **structure automatic, meaning reviewed, consumption via
API/MCP** — here is the measured proof.

## Slide 3 — What the market does today (one slide, evidence)
Four layers, four tool families, one shared pattern: **a human models first.**
Palantir by hand · Databricks metadata + authored metric views · Atlan curation
programme · Neo4j Cypher · dbt/LookML YAML · Palantir/Atlan approval exists only
at the platform level. (Sources: `docs/research/`, graded.)

## Slide 4 — Five things the market does not do
1. derive the first model from an arbitrary source;
2. label every relation measured vs guessed;
3. answer "what was true on 3 March" on graph/metrics;
4. pack evidence under a hard budget and say what was dropped;
5. run locally with no platform contract.
(This is the whole thesis.)

## Slide 5 — Our answer (architecture diagram)
sources → ontology → graph → review gate → semantic → Agent Context Builder →
API/MCP → agents. One picture, from `docs/diagrams/target_architecture.mmd`.

## Slide 6 — Authoring angle: the lake
- 100 tables, 4,864 rows, mixed CSV/Parquet/JSON.
- Current version baseline: 100 classes, 141 relations, 6,347 edges, 0 dangling,
  11.4 s total, 742 metrics — **measured today** (`docs/benchmark/`).
- Better version target: coverage scored against ground truth, approval queue,
  multi-source.
- Message: "the model exists before the meeting ends."

## Slide 7 — The review gate (HITL)
What is automatic, what needs a human (the coverage map). Ontology/KG auto-
publish with findings; semantic + context wait for approval. Audit trail.
Message: "we automate the structure, you own the meaning."

## Slide 8 — Consumption angle: what an agent receives
The trust envelope: `{answer, facts[], sources[], as_of, dropped[], latency_ms}`.
Every line measured/derived/external + citation. MCP + FastAPI.
Message: "not a pile of search results — a receipted evidence pack."

## Slide 9 — The cross-source scenario
Same product in ERP/PIM/marketplace. Layers discover it, resolve it, choose the
source of truth, explain alternatives. (The manager's Hindi insight, made real.)

## Slide 10 — Proof scorecard
Current vs better vs documented market, weighted criteria, **wins and losses**.
Load the numbers only from `docs/proof/SCORECARD.md`.

## Slide 11 — Where paying wins
Governance/RBAC at scale, graph throughput, connector breadth, support/procurement,
companies standardised on Databricks/Snowflake. (Credibility slide.)

## Slide 12 — The two angles and the product shape
Authoring (create) + consumption (serve) on one engine. What a customer gets
today vs roadmap.

## Slide 13 — What we ask for
Pilot schema/data from one client, approval to run a paid-platform trial if
needed, Arin's client-question input, Gate 2 date.

## Slide 14 — Appendix: method
Evidence grades A–D, sources, benchmark reproduction commands, definitions.

## Slide 15 — Appendix: definitions
Our four layers vs market meanings; why "Agent Context Builder"; why we do not
say "context layer" bare.

## Speaking rules (from the legacy story, kept)
- Never say "as you can see".
- Never apologise for what is missing; state it flatly or leave it out.
- If something breaks: "that is the live system, not a recording" and move on.
- Every number you say out loud must be in the scorecard or benchmark.
- One invented number loses the room.
