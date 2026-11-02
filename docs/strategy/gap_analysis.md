# Gap analysis — where the market is weak enough for us to win

Inputs: the 48 buyer problems recorded in `docs/research/01..04` (12 per layer),
each with an evidence grade. This page clusters them, scores where we can be
best, and states where we will lose. It is the bridge from research to the
better-version blueprint.

## 1. Clustering: 48 layer problems → 10 cross-layer problems

| # | Buyer problem (market words) | Layer(s) | Served today? | Who serves it | Evidence |
|---|---|---|---|---|---|
| P1 | "What exists here, and what identifies one?" | L1 | **Under-served for messy/local sources** | Palantir/Stardog/GraphDB by hand; Databricks sees tables only | 01 §problems 1–2 |
| P2 | "Is this statement given or guessed?" | L1, L2, L4 | **Under-served** | GraphDB inference provenance; Stardog reasoning explanation; citations ≠ confidence | 01 §4, 02 §5, 04 §2 |
| P3 | "What was true on 1 March?" | L1, L2, L3, L4 | **Greenfield** | Nobody documents bitemporal model/edges/metrics; Zep is temporal for memory only | 01 §12, 02 §3, 03 §11, 04 §4 |
| P4 | "Same metric, different number" | L3 | **Served** | dbt, Cube, AtScale, Databricks, Snowflake, LookML | 03 §problems 1–5 |
| P5 | "Onboarding a new source takes weeks of modelling" | L1, L2, L3 | **Under-served** | All manual; AI assists authoring only (Genie Code, Autopilot, Cube agent) | 01 §10, 02 §1, 03 §6 |
| P6 | "Where is the source of truth / which table?" | L1, L3 | **Partly** | Catalog lineage; semantic layers assume it | 01 §6, 03 §3 |
| P7 | "Too much context missing evidence / context rot" | L4 | **Under-served** | Vendors ship retrieval/query APIs; no hard-budget packer | 04 §1, §7 |
| P8 | "Who approved this for the agent?" | L4, L3 | **Rare** | Palantir staged writes; Snowflake verified queries; dbt PR review | 04 §8, 03 §2 |
| P9 | "Agent re-derives logic every prompt; no delivery contract" | L3, L4 | **Partly** | MCP servers everywhere (dbt/Cube/Snowflake/Glean/Zep) | 03 §8, 04 §3 |
| P10 | "Cost/latency per question is invisible; platform lock-in" | L1–L4 | **Under-served** | Enterprise/credit pricing; Kùzu shows free-tool fragility | 01 §10, 03 §12, 04 §10, 02 Kùzu |

**Served-well list (do not compete head-on):** cross-tool metric consistency at
scale (P4), enterprise governance/permissions (P6), graph traversal throughput
(Neo4j/TigerGraph), catalog breadth (Atlan/Databricks), formal OWL/SPARQL
semantics (Stardog/GraphDB), BI modelling (LookML/Power BI).

**Under-served list (our hunting ground):** P1, P2, P3, P5, P7, P8, P10.

## 2. Opportunity scoring

Scores 1–5. "Advantage" = how much our existing code/design already does or can
do cheaply; "Demo" = can we show it live in under 10 minutes; "Buyer value" =
what a senior buyer will pay attention to; "Evidence" = how strong the research
case is (grade and number of sources).

| Bet | Under-served | Our advantage | Demo | Buyer value | Evidence | Total /25 |
|---|---|---|---|---|---|---|
| **B1 Auto-authoring with confidence grades** (P1/P5) | 5 | 5 (already auto-discovers) | 5 (connect → graph in minutes) | 5 ("can it do 100 tables?") | 5 | **25** |
| **B2 Provenance + approval gate for semantic/context** (P2/P8) | 5 | 4 (tags exist, approvals missing) | 4 (approve/reject live) | 5 ("can I trust it?") | 4 | **22** |
| **B3 Bitemporal answers** (P3) | 5 | 4 (edges already bitemporal) | 4 (same question, two dates) | 4 | 5 | **22** |
| **B4 Agent Context Builder + MCP/API** (P7/P9) | 5 | 3 (budget exists, API missing) | 5 (agent asks, answer has citations + budget) | 5 | 4 | **22** |
| **B5 Multi-source + cross-source source-of-truth** (P1/P6) | 4 | 2 (single-source today) | 5 (same product in 3 sources) | 5 (the Hindi insight) | 4 | **20** |
| **B6 Local/$0/durable/portable** (P10) | 4 | 5 (already local, $0) | 3 (no live cost comparison) | 4 | 4 | **20** |
| B7 Formal OWL/SHACL export | 3 | 2 | 2 | 3 | 3 | 13 |
| B8 Graph algorithms (PageRank, communities) | 2 | 1 | 2 | 2 | 2 | 9 |
| B9 BI-tool connectors / dashboards | 2 | 1 | 2 | 3 | 2 | 10 |

**Chosen for the better version (Gate 1 proposal): B1, B2, B3, B4, B5, with B6
as the always-on context.** B7 is a cheap interoperability add; B8/B9 are
explicit non-goals for now.

## 3. The job we can be best at (definition)

> **Job:** give a data team a trustworthy, time-aware middle layer from any
> source — with the boring parts automatic, the judgment parts gated by a human,
> and the output ready for an AI agent to consume — locally, with no platform
> contract.

**"Best in market" therefore means:** best on the weighted scorecard for *this
job*, on criteria we can measure, with the losses published beside the wins.
It does **not** mean best at enterprise catalogs, graph throughput or BI.

## 4. Where incumbents beat us (say it before the buyer does)

| Capability | Who wins | Why we do not chase it now |
|---|---|---|
| Governance, RBAC, audit at enterprise scale | Databricks, Atlan, Palantir | Years of platform work; our review gate is deliberately small and local |
| Connector breadth | Atlan, Glean, Databricks | We support DuckDB-attached sources + Snowflake/Databricks adapters; the long tail is not the differentiator |
| Graph traversal throughput / scale | Neo4j, TigerGraph, Neptune | We target small/medium data and seconds-to-build, not billion-edge clusters |
| Formal ontology/reasoning | Stardog, GraphDB | OWL/SHACL export is enough for interoperability; a reasoner is not the product |
| BI ecosystem | Looker, Power BI, dbt | We serve metrics to agents/BI via API/MCP instead of rebuilding dashboards |
| Support, brand, procurement | Everyone enterprise | We lead with measurable capability and a local trial, not procurement |
| Price at scale | Cloud incumbents | At very large scale, platform economics can win; we say so |

## 5. Risks to the differentiation (and response)

| Risk | Signal | Response |
|---|---|---|
| Incumbents add auto-inference | Databricks "Genie Code", Snowflake Autopilot, Cube model agent already assist authoring | Our depth is *derivation + uncertainty + time*, not autocomplete; move fast and publish measurements |
| MCP commoditises delivery | dbt/Cube/Snowflake/Glean/Zep all ship MCP | MCP is table stakes; our moat is the pack (budget + provenance + approval), not the endpoint |
| Free/local tools disappear | Kùzu archived 2025; KuzuDB site DNS dead | Own boring portable formats (DuckDB/Parquet/CSV) + export (OWL/SHACL/Neo4j); keep provenance independent of engine |
| "Everyone builds ontology" buyer fatigue | Manager's own observation | Open with the derivation/approval/proof demo, not the layer list |
| Our benchmark is self-built | Buyers may discount it | Real datasets + reproducible command + published losses; invite a customer schema |
| Heavy multi-source work slips | Cross-source resolution is the hardest item | Gate 1 may cut B5 to "detect and flag duplicates" if time is short; still demoable |

## 6. Gate 1 recommendation

Proceed to build **B1–B5** (B6 always on), with the proof plan in
[better_version_blueprint.md](better_version_blueprint.md). Keep B7 (OWL/SHACL
export) as a stretch; explicitly drop B8/B9. If the manager wants a thinner
first cut, drop B5 from the demo and keep it in the roadmap — B1, B2, B4 alone
already answer the three questions asked in the room.

## 7. Evidence map

- P1/P5: [01 §problems 1–3, 10](../research/01_ontology_layer.md), [02 §1](../research/02_knowledge_graph_layer.md), [03 §6](../research/03_semantic_layer.md)
- P2: [01 §4](../research/01_ontology_layer.md), [02 §5](../research/02_knowledge_graph_layer.md), [04 §2](../research/04_context_layer.md)
- P3: [01 §12](../research/01_ontology_layer.md), [02 §3](../research/02_knowledge_graph_layer.md), [03 §11](../research/03_semantic_layer.md), [04 §4](../research/04_context_layer.md)
- P7/P8: [04 §1, §7, §8](../research/04_context_layer.md), [03 §2](../research/03_semantic_layer.md)
- P9/P10: [03 §8, §12](../research/03_semantic_layer.md), [04 §3, §10](../research/04_context_layer.md), [02 Kùzu](../research/02_knowledge_graph_layer.md)
