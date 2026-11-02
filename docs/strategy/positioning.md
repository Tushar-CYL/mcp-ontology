# Positioning — what we sell, to whom, and how we prove it

Derived from `docs/research/`, `gap_analysis.md` and `better_version_blueprint.md`.
Audience: manager, Arin (story), and the eventual company pitch.

## 1. One sentence

> **The auto-authoring, provenance-first middle layer:** turn any data source
> into an ontology, a time-aware knowledge graph, governed metrics and an
> agent-ready context pack — locally, with a human approving only what needs
> judgment, and every fact labelled as measured or guessed.

## 2. The two angles (same engine, two products)

| Angle | Who buys | What they get | Why now |
|---|---|---|---|
| **Authoring** | data platform lead, analytics engineer, CDO team | connect → auto-derive → review → publish; coverage report; audit | every incumbent starts with a modelling project; onboarding is the bottleneck |
| **Consumption** | AI product owner, agent builder, BI owner | API/MCP trust envelope: cited, graded, time-stamped facts under a budget | MCP has made delivery easy; the missing piece is *trustworthy, sized evidence* |

Do not present them as two companies. One narrative, two acts: "we build it with
you" then "your agents consume it".

## 3. The pitch in three acts (4 minutes spoken)

1. **The gap.** "Everyone is building ontology, semantic layers and context.
   Look at how they do it: a human models first — Palantir by hand, dbt in YAML,
   Neo4j in Cypher, Atlan with a governance programme. The first two weeks are
   always the same modelling project. And almost nobody labels a guessed link as
   a guess, or can answer 'what was true on 3 March'."
2. **What we do differently.** "We derive the first model from the data, label
   every element with confidence, let your people approve only the business
   judgments, and pack the answer an agent actually needs inside a hard budget."
3. **Proof.** "Here is the 100-table lake, built in X minutes with no per-dataset
   code; here is the same product in three sources resolved with a reason; here
   is an agent answer with citations and a dropped-facts list. Here is the
   scorecard — including where Databricks, Atlan and Neo4j still beat us."

## 4. Competitive frame

**We are not:** a catalog (Atlan/Databricks UC), a graph engine (Neo4j/Neptune),
a semantic-layer platform (dbt/Cube/AtScale), a context/memory platform (Atlan,
Neo4j Context Engine, Zep), or a BI tool.

**We are:** the layer before those. In a customer with a catalog or graph
already, we are complementary: consume their metadata/definitions where they
exist, derive and package where they do not.

| Their strength | Our response |
|---|---|
| Enterprise governance, RBAC, catalog breadth | "Use your catalog for governance; we produce the derived, approved, agent-ready layer it does not." |
| Graph traversal at scale | "Run our export in Neo4j when you need scale; our job is to build the graph and its time bounds in the first place." |
| Manual semantic modelling correctness | "We propose and you approve; your definitions stay the source of truth." |
| MCP delivery | "We ship MCP too — plus the budget, provenance and approval behind it." |

## 5. Where paying still wins (say it out loud)

- Regulated enterprises needing SSO/RBAC/lineage/audit at catalog scale.
- Very large graphs where a dedicated engine's throughput matters.
- Teams without any data engineering capacity who want a managed service.
- Companies already standardised on Databricks/Snowflake where the platform's
  semantics are "good enough".
- Cases needing 24×7 vendor support and procurement.

A comparison where free wins everything reads like a sales deck; this list is
what makes the rest believable. (This is the legacy STORY rule, kept.)

## 6. Public price anchors (for the cost slide; documented, not measured)

| Product | Public anchor (2026-10-29) | Grade |
|---|---|---|
| Atlan | third-party reading of a Microsoft Marketplace listing: **$120k/yr** for 5 admins + 5 members | C |
| dbt Semantic Layer | **$100/user/month** (Starter; 5,000 queried metrics) | B |
| Cube | **$40/dev/month** Starter; $80 Premium; dedicated $0.60/h | B |
| Power BI | **$14/user/month** Pro; $24 PPU | B |
| Snowflake Cortex | AI credits **$2.00** global / $2.20 regional; Analyst API per 1,000 messages | B |
| Zep | **$125/month** Flex; $375 Flex Plus | B |
| Pinecone | $20/month Builder; $50/month Standard minimum | B |
| Palantir, Stardog, GraphDB, AtScale, Looker, Databricks DBU rates | **not public / quote-only** | B for absence |

**Our cost:** $0 licence, local compute, no account. Caveat for the slide: these
are different units and products; the comparison is an anchor, not an
apples-to-apples bill. The honest claim is *"zero licence cost and no data
leaves the machine"*, not *"we are 1,000× cheaper"*.

## 7. How we claim "best in market" without losing the room

Weighted scorecard, agreed at Gate 1, e.g.:

| Criterion | Weight | Us | Current version | Market |
|---|---|---|---|---|
| Auto-authoring coverage/time | 25% | measured | measured | documented |
| Provenance + approval/trust | 20% | measured | measured | documented |
| Multi-source + source-of-truth | 15% | measured | measured | documented |
| Bitemporal answers | 10% | measured | measured | documented |
| Agent-native (MCP/API, budget, citations) | 15% | measured | measured | documented |
| Local/$0/private/durable | 15% | measured | measured | list prices |
| Enterprise governance/connectors/scale | — | we lose | we lose | they win |

Rule: the deck shows the losses slide before the audience asks. Claim:
**"best on the weighted criteria for the auto-authoring + agent-context job;
not an enterprise catalog, graph engine or BI platform."**

## 8. Likely buyer questions (short answers)

1. *"How is this different from Databricks/Atlan?"* — They govern and model
   manually; we derive, label uncertainty, and pack for agents. Complementary.
2. *"Can it really build ontology from 100 tables?"* — Here is the measured
   coverage/time on a 100-table lake and on two real datasets; here is what still
   needs review.
3. *"How do I trust the graph?"* — Every edge has method + confidence + as-of;
   inferred links are visually distinct and reviewable; dangling links are
   counted, not hidden.
4. *"Is this another 'context layer'?"* — We call it Agent Context Builder:
   task-conditioned evidence under a hard budget with what-was-dropped.
5. *"What about security/PII?"* — Local execution, no upload; the API exposes
   only published artifacts; production RBAC is documented, not built.
6. *"What if my data is huge?"* — We target small/medium operational data and
   local files; for billion-edge graphs, export to Neo4j/Parquet and use their
   engine.
7. *"Why not just use an LLM on the schema?"* — Because it would hallucinate
   keys and relations; we derive deterministically, grade the guesses and gate
   the business meaning.
8. *"What happens when the schema changes?"* — Rebuild signature, diff, findings,
   and the review queue shows what changed.
9. *"What's the commercial model?"* — Not decided; the demo proves the
   capability, not the pricing. (Do not invent pricing in the room.)
10. *"Is this free?"* — The stack we demo has $0 licence; support/enterprise
    packaging is a separate conversation.

## 9. Proof assets to bring

- Live demo (three scenarios in `problem_statements.md` §5).
- `docs/benchmark/BENCHMARK.md` (reproducible numbers).
- `docs/proof/SCORECARD.md` (current vs new vs market, wins and losses).
- `docs/research/` (evidence pack with grades and sources).
- This positioning page, one printed page.
