# Definitions and terms — our four layers vs the market

**Purpose.** The manager's concern was exact: *"ontology, context — these words
have different meanings outside this space."* This document fixes the words we
use internally, the words the market uses for the same-looking things, and the
words we are allowed to say in front of a customer. It is the first thing to
sign off before any deck is written.

Rule for every external document: **define a term on first use, and never say
"context layer" without a qualifier.** The market already uses that phrase for
something different from ours.

## 1. The four layers, defined for us

| # | Layer | Our definition | Artifact | Consumer |
|---|---|---|---|---|
| 1 | **Ontology** | The domain's rules derived from the source: what kinds of thing exist, how one is identified, which links are allowed, what time a row became true, what can be measured. | `Ontology` object + stored codes/provenance in the graph DB | Layer 2, layer 3, review UI |
| 2 | **Knowledge graph** | The instances: one node per real thing, one edge per real link, every edge with a validity interval, so the graph can be rewound. | `nodes`, `edges`, `findings` tables | Layer 3/4 queries, graph UI, API |
| 3 | **Semantic layer** | The numbers, defined once: metric name, owner, definition, aggregation, dimensions, time grain, source precedence — compiled to SQL by every caller. | Metric catalogue + compiled SQL | Dashboards, API, agent tools |
| 4 | **Context (answer bundle)** | The evidence for one question, selected from the three layers, packed under a hard size limit, with provenance/citations on every line. | ordered `Fact` list / answer envelope | LLM prompt, agent, report |

**Vector DB:** storage used by retrieval inside layer 4 (or a future search
feature). It is **not** a fifth layer and must not appear as one in the
architecture diagram.

**Two product angles (both use the same engine):**

- **Authoring angle** — a platform a data team uses to *create* the four
  artifacts from their sources: connect → auto-author → review → publish.
- **Consumption angle** — a platform agents, BI tools and apps use to *consume*
  the published artifacts through API/MCP, with provenance and confidence.

## 2. What the market means by the same words

| Our word | Market usage (documented) | Where it differs from ours | External wording we should use |
|---|---|---|---|
| Ontology | **Palantir Foundry Ontology**: object types, link types and actions that model the operational business and back applications/AI ([object/link types](https://www.palantir.com/docs/foundry/object-link-types), [core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts)). **W3C OWL/RDF/SHACL**: a formal logic vocabulary with reasoners and constraint validation. **Databricks Unity Catalog**: metadata (tables, tags, lineage) rather than an inferred domain model ([metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/basic-modeling)). | Ours is *derived from physical schema* and deliberately not a formal logic; it carries confidence and provenance. It is closer to an "operational semantic model" than to OWL. | "Ontology **derived from your schema**" or "semantic model"; if we mean OWL/RDF, say "RDF/OWL ontology" explicitly. |
| Knowledge graph | **Neo4j**: property graph + Cypher + GraphRAG ([Aura Agent](https://go.neo4j.com/rs/710-RRC-335/images/Neo4j-Aura-Agent-datasheet.pdf), [Context Engine coverage](https://www.storagereview.com/news/neo4j-context-engine-ai-agents-knowledge-layer-ontology-graph-native-memory)). **Amazon Neptune Analytics**: managed property/RDF graph, GraphRAG with Bedrock ([AWS example](https://builder.aws.com/content/2uYGXLDH0lH3Y1VGS90xhy71YOl/building-graphrag-solutions-using-amazon-bedrock-knowledge-bases-and-amazon-neptune-analytics)). **Stardog**: virtual graphs + reasoning ([docs](https://docs.stardog.com/virtual-graphs/)). | Ours is a property graph with **bitemporal edges** (`valid_from`/`valid_to`) and a hard provenance tag, built automatically from any source. Time travel is first-class, not an add-on. | "time-aware knowledge graph" — this is our catchphrase and it is accurate. |
| Semantic layer | **dbt Semantic Layer / MetricFlow**: metrics defined as code, served to BI/AI ([docs](https://docs.getdbt.com/docs/build/about-metricflow)). **Cube** semantic layer API. **AtScale**. **Databricks UC Metric Views**. **Snowflake Semantic Views + Cortex Analyst** for natural language over governed metrics ([release notes](https://docs.snowflake.com/en/release-notes/2026/other/2026-04-05-semantic-views-verified-queries)). | Ours is auto-proposed from columns, then gated by human approval; it is not a full modelling language and currently has no dbt/Cube export. | "semantic/metrics layer" is safe. Do not claim to be "a dbt replacement". |
| Context layer | **Atlan** markets a "Context Layer for AI" — governed metadata/glossary/lineage context for agents ([Atlan](https://atlan.com/), [catalog vs semantic vs context](https://atlan.com/know/ai-agent/semantic-layer/context-layer-vs-data-catalog-vs-semantic-layer/)). **Neo4j Context Engine** — graph-native shared knowledge/memory for agents ([coverage](https://www.storagereview.com/news/neo4j-context-engine-ai-agents-knowledge-layer-ontology-graph-native-memory)). **"Context engineering"** in AI engineering = selecting/compacting what goes into an LLM's window. **MCP** = the protocol by which an agent fetches tools/context ([spec](https://modelcontextprotocol.io/specification/2026-07-28/index)). **GraphRAG** = graph-based retrieval for LLMs. | Ours is the **last mile**: given a question, pack the right facts from the graph/metrics under a budget with citations. It is *not* a metadata catalogue and *not* agent memory. | **"Agent Context Builder"** or "context packer". Reserve the bare phrase "context layer" for the market category, and explain the difference. |

## 3. Consequences for the pitch

1. **Never** open with "we build ontology, knowledge graph, semantic and context
   layers" alone. That sentence is true of half the market and invites
   "everyone does that".
2. Open with the **differentiated sentence**:
   *"We derive a time-aware, provenance-tagged middle layer from any data
   source with no per-dataset code — and we show every guess to the human who
   approves it, before an agent consumes it."*
3. Then use the market words one at a time, each defined:
   - "ontology — the rules we derive from your schema",
   - "knowledge graph — the instances, rewound to any moment",
   - "semantic layer — the numbers defined once and approved",
   - "Agent Context Builder — the evidence bundle the agent actually reads".
4. When a customer says "we have Unity Catalog / Atlan / Neo4j", agree and
   **position as complementary**: we consume the catalog/graph where it exists,
   and add the auto-derived, approved, agent-ready layer it does not produce.
   (This is the "co-existence" slide; it is more credible than a head-on claim.)

## 4. Terms we will not use loosely

| Don't say | Say instead | Why |
|---|---|---|
| "fully automatic ontology" | "automatically derived, with confidence and a review path" | the manager's own question; overclaiming loses the room |
| "context layer" (bare) | "Agent Context Builder" | collision with Atlan/Neo4j |
| "AI-ready data" | "facts with provenance an agent can cite" | measurable |
| "graph database" | "knowledge graph on an embedded engine" | we use DuckDB; Neo4j is the graph-DB comparison |
| "semantic layer" for generated counts | "metric proposals" until approved | definitions need a human owner |
| "best in market" | "best on {named criteria} for {named job}; here is where we lose" | only claim what the scorecard measures |

## 5. References (seed set; full evidence in `docs/research/`)

- Palantir — [object and link types](https://www.palantir.com/docs/foundry/object-link-types), [Ontology core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts)
- Databricks — [Unity Catalog metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/basic-modeling)
- Stardog — [virtual graphs](https://docs.stardog.com/virtual-graphs/)
- Ontotext — [GraphDB + Ontopic virtualization](https://www.ontotext.com/knowledgehub/webinars/graphdb-virtualization-enabled-by-ontopic-studio/)
- Neo4j — [Aura Agent datasheet](https://go.neo4j.com/rs/710-RRC-335/images/Neo4j-Aura-Agent-datasheet.pdf), [Context Engine coverage](https://www.storagereview.com/news/neo4j-context-engine-ai-agents-knowledge-layer-ontology-graph-native-memory)
- Amazon — [Neptune Analytics + Bedrock GraphRAG](https://builder.aws.com/content/2uYGXLDH0lH3Y1VGS90xhy71YOl/building-graphrag-solutions-using-amazon-bedrock-knowledge-bases-and-amazon-neptune-analytics)
- dbt — [MetricFlow](https://docs.getdbt.com/docs/build/about-metricflow)
- Snowflake — [semantic views release notes](https://docs.snowflake.com/en/release-notes/2026/other/2026-04-05-semantic-views-verified-queries)
- Atlan — [Context Layer for AI](https://atlan.com/), [catalog vs semantic vs context](https://atlan.com/know/ai-agent/semantic-layer/context-layer-vs-data-catalog-vs-semantic-layer/)
- GraphRAG — [Microsoft GraphRAG discussion](https://learn.microsoft.com/en-ca/answers/questions/5968687/microsoft-graphrag-com-fonte-de-dados-rdf-externa)
- MCP — [specification](https://modelcontextprotocol.io/specification/2026-07-28/index)
