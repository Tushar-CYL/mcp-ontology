# Sources — consolidated evidence index

All sources were accessed **2026-10-29** unless stated. Grades: **A** measured
by us, **B** primary vendor docs, **C** independent/analyst, **D** inference.
Full per-tool citations live at the end of each layer document; this page is
the index the deck uses.

Rules: quote the source, keep the date, never present a vendor claim as a
measured outcome, never cite a price the source does not publish.

## Layer 1 — ontology / semantic model

| Source | Grade | Used for |
|---|---|---|
| [Palantir OSDK Maker README](https://raw.githubusercontent.com/palantir/osdk-ts/main/packages/maker/README.md) | B | object/link/interface/value-type/action primitives; migrations |
| [Palantir Ontology core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts) | B | ontology as an operating layer |
| [Palantir pricing](https://www.palantir.com/pricing/) | B (absence) | no public list price |
| [Databricks Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) | B | catalog scope and namespace |
| [Databricks lineage](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) | B | table/column lineage, retention, gaps |
| [Databricks metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/basic-modeling) | B | semantic layer on UC |
| [Atlan context layer](https://atlan.com/context-layer/) | B | context-layer positioning |
| [Atlan: catalog vs semantic vs context](https://atlan.com/know/ai-agent/semantic-layer/context-layer-vs-data-catalog-vs-semantic-layer/) | B | terminology collision |
| [Dawiso — Atlan pricing](https://dawiso.com/glossary/atlan-pricing) | C | $120k/yr marketplace anchor |
| [Stardog pricing](https://www.stardog.com/pricing/) | B | Free vs Enterprise, exclusions |
| [Stardog virtual graphs](https://docs.stardog.com/virtual-graphs/) | B | mappings, pushdown, limits |
| [GraphDB licensing](https://graphdb.ontotext.com/documentation/10.8/licensing.html) | B | free 2 queries; per-core EE |
| [GraphDB reasoning](https://graphdb.ontotext.com/documentation/10.8/reasoning.html) | B | rulesets, provenance plugin |
| [metaphactory](https://metaphactory.com/) | B | virtual KG over warehouses |
| [W3C OWL 2 overview](https://www.w3.org/TR/owl2-overview/) | B | formal ontology standard |
| [W3C SHACL](https://www.w3.org/TR/shacl/) | B | validation standard |

## Layer 2 — knowledge graph

| Source | Grade | Used for |
|---|---|---|
| [Neo4j GraphRAG for Python](https://neo4j.com/docs/neo4j-graphrag-python/current/) | B | KG builder, resolvers, ANN limit |
| [Neo4j Context Engine coverage](https://www.storagereview.com/news/neo4j-context-engine-ai-agents-knowledge-layer-ontology-graph-native-memory) | C | context engine launch |
| [Amazon Neptune Analytics](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html) | B | managed graph analytics |
| [Bedrock GraphRAG with Neptune](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html) | B | S3-only, no build customisation |
| [TigerGraph pricing](https://www.tigergraph.com/pricing/) | B | trial and paid tiers |
| [Memgraph pricing](https://memgraph.com/pricing) | B | community vs enterprise |
| [GraphFrames](https://github.com/graphframes/graphframes) | B | DataFrame graphs, algorithms |
| [GitHub API — kuzudb/kuzu](https://api.github.com/repos/kuzudb/kuzu) | A | archived=true, last push 2025-10-10 |
| [Snowflake CTE docs](https://docs.snowflake.com/en/user-guide/queries-cte) | B | recursive SQL limits |

## Layer 3 — semantic layer

| Source | Grade | Used for |
|---|---|---|
| [dbt MetricFlow](https://docs.getdbt.com/docs/build/about-metricflow) | B | metrics as code |
| [dbt Semantic Layer architecture](https://docs.getdbt.com/docs/use-dbt-semantic-layer/sl-architecture) | B | licences, APIs |
| [dbt pricing](https://www.getdbt.com/pricing) | B | Starter $100/user/mo |
| [Cube pricing](https://cube.dev/pricing) | B | $40/$80 tiers |
| [Cube AI context layer](https://cube.dev/product/ai-context-layer) | B | semantic layer renamed for AI |
| [AtScale semantic layer](https://www.atscale.com/use-cases/universal-semantic-layer/) | C | capabilities (title-only pages) |
| [Snowflake semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/overview) | B | semantic objects + Analyst |
| [Snowflake verified queries](https://docs.snowflake.com/en/release-notes/2026/other/2026-04-05-semantic-views-verified-queries) | B | human approval mechanism |
| [Snowflake AI pricing](https://docs.snowflake.com/en/user-guide/snowflake-cortex/pricing) | B | credit pricing |
| [Looker LookML](https://docs.cloud.google.com/looker/docs/what-is-lookml) | B | BI modelling language |
| [Power BI pricing](https://www.microsoft.com/en-us/power-platform/products/power-bi/pricing) | B | seat pricing |

## Layer 4 — context / agent delivery

| Source | Grade | Used for |
|---|---|---|
| [Atlan Context Engineering Studio](https://atlan.com/context-engineering-studio/) | B | versioned context repo, evals |
| [Neo4j Context Engine](https://neo4j.com/product/context-engine/) | C | graph context + memory |
| [Palantir AIP](https://www.palantir.com/docs/foundry/aip/overview/) | B | agents on the Ontology; staged writes |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | B | entity/claim extraction, community summaries |
| [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28/index) | B | delivery protocol, consent |
| [Glean pricing docs](https://docs.glean.com/glean-core-suite-pricing) | B | seat + model usage |
| [Zep pricing](https://www.getzep.com/pricing/) | B | $125/$375 plans, MCP |
| [Graphiti licence](https://raw.githubusercontent.com/getzep/graphiti/main/LICENSE) | B | Apache-2.0 temporal graph |
| [Letta Code README](https://raw.githubusercontent.com/letta-ai/letta-code/main/README.md) | B | self-managed memory harness |
| [Pinecone pricing](https://www.pinecone.io/pricing/) | B | storage tiers |

## Internal evidence (A)

| Source | Note |
|---|---|
| `docs/benchmark/README.md` + `baseline/*_after_core.*` | measured current code |
| `python -m pytest` | 281 pass, ~177 s |
| `docs/CURRENT_VERSION.md` | environment and capability audit |

## Known gaps in the evidence

- No public list prices for Palantir, Stardog, GraphDB, AtScale, Looker,
  Databricks DBU rates, Neo4j Aura, Neptune, TigerGraph paid tiers.
- AtScale capability rows grade C (title-only pages).
- Neo4j Context Engine is new; claims unverified.
- Kùzu acquisition unverified; the archive itself is measured.
- Paid platforms were documented, not trialled hands-on.
- No customer interviews yet; problem statements must be validated with Arin.