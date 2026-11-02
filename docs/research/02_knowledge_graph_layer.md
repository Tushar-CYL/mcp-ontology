# Layer 2 — Knowledge graph: how the market builds instance graphs, and where it stops

*Research round 2026-10-29. All sources accessed 2026-10-29. Grades: A = measured by us; B = primary vendor docs; C = independent article/analyst; D = our inference. Vendor case studies are B at best, labelled "vendor-reported", never "measured".*

## Executive summary

1. The market splits into **graph engines** (Neo4j, Neptune Analytics, TigerGraph, Memgraph, Kùzu) and **graph-ish compute inside a data platform** (Databricks GraphFrames, Snowflake recursive SQL). Engines give traversal but make *you* build the graph; platforms give scale but not a graph you can serve.
2. **Nobody sells the instance graph as a derived artifact.** Every engine's documented entry is "model your schema, load data, write queries". The nearest automation is Neo4j's LLM Knowledge Graph Builder for *documents* (B) and Bedrock's managed GraphRAG — which explicitly **cannot customise the graph build** (B).
3. **Time validity is not first-class anywhere we looked.** Engines store current state; versioning is left to the customer (named graphs, transaction logs, manual valid-from columns). No documented as-of primitive.
4. **Provenance is thin.** GraphRAG returns retrieved chunks/subgraphs, not per-edge evidence; nothing tells you whether an edge was measured from a foreign key or guessed from a name match.
5. **The free-tool lesson is real:** Kùzu, the best-known embedded Cypher engine, is **archived** (GitHub API: `archived: true`, last push 2025-10-10, MIT, 4,018 stars) and its site no longer resolves (2026-10-29). A buyer who built on it has no upstream. Durability is a differentiator, not a footnote.

## Comparison table (Layer 2)

| Tool | Public price anchor (2026-10-29) | How the graph is built | Time / versioning | Agent path | Grade |
|---|---|---|---|---|---|
| Neo4j (AuraDB, GraphRAG, Context Engine, Aura Agent, Virtual Graph) | Page with Aura tiers + free start; **rates not captured → unknown**; self-managed Enterprise quote | Hand-modelled Cypher property graph; LLM KG Builder for documents; vector index; resolvers | Transactions; no documented bitemporal edges (D) | GraphRAG retrievers, Context Engine, Aura Agent, MCP | B |
| Amazon Neptune Analytics | Per m-NCU-hour + storage; **rates not captured → unknown** | Load from S3/Neptune snapshot; algorithms; vector search in traversal. Bedrock GraphRAG builds a graph from docs with **no customisation** | Not documented (D) | Bedrock Knowledge Bases → FMs | B |
| Stardog virtual graphs | Enterprise quote; Free lacks full connectors | Declarative mappings or R2RML direct mapping; SPARQL→SQL pushdown; optional materialisation | Point-in-time recovery; named graphs (D) | Voicebox, GraphQL, SQL/BI | B |
| TigerGraph | Savanna trial **$0/GB-month** (24×7, US Tier 1); paid quote; Community free | GSQL schema + loading jobs + installed queries; GraphStudio | Not documented (D) | GraphRAG/agentic marketing; REST endpoints | B |
| Memgraph | Community free/OSS; Enterprise **quote by memory**; 30-day trial | Cypher modelling; stream connectors; vector; MAGE algorithms | Not documented (D) | GraphRAG / AI memory marketing | B |
| Databricks GraphFrames | Free, Apache-2.0; pushed 2026-10-28 | Vertex/edge DataFrames; algorithms + Pregel; **library, not a store** | None | None (Spark SQL only) | A / B |
| Snowflake SQL-only | Warehouse credits; no graph SKU | Hand-written `WITH RECURSIVE` / `CONNECT BY`; restricted recursive clause | Time Travel for tables (not verified); no bitemporal edges (D) | SQL only | B |
| Kùzu | Free, MIT — **archived** | Embedded Cypher graph; no server | None documented | None upstream | A |

## Tool sections

### Neo4j — the reference engine, now selling "context"

| Field | Finding |
|---|---|
| Category / licence | Graph intelligence platform: AuraDB, Virtual Graph, Aura Graph Analytics, **Aura Agent**, **Context Engine**, GraphRAG, MCP dev path. Pricing page publishes Aura tiers and a free start; rates not captured → **unknown**; self-managed Enterprise quote |
| Entry / inputs | Cypher skill; GraphRAG needs an LLM key, embedding model and vector index (Neo4j ≥5.18.1, Aura ≥5.18.0, 2026.01+ for in-index `SEARCH`; Python 3.10–3.14) |
| How built | (a) hand-modelled property graph; (b) LLM **Knowledge Graph Builder** in `neo4j-graphrag` extracts entities/relations from documents with resolvers (`SpaCySemanticMatchResolver`, `FuzzyMatchResolver`) and vector indexes (`create_vector_index`, `upsert_vectors`). Relational/CSV→graph remains human modelling (D) |
| Automation / HITL | High for document extraction, low for source-to-graph; pipelines configurable, no approval UI documented |
| Artifacts / time / provenance | Graph, vector index, retrieval pipelines, agent context. ACID transactions, **no valid-from/valid-to edge model** (D). GraphRAG returns chunks/subgraph; no per-edge provenance; vector search is approximate (ANN) |
| Agent path | Strongest in set: GraphRAG retrievers, Context Engine, Aura Agent, MCP, agent memory |
| Problems / outcomes / limits | Fraud/AML, recommendations, MDM/identity, supply chain, GraphRAG accuracy, agent memory. Outcomes vendor-commissioned (IDC study, TfL story). Limits: property graph ≠ ontology; optional schema → drift; extraction quality drives quality; ANN approximate; cluster cost |
| Gap for us | Sells engine + modelling labour. We sell the derived graph (instances, links, time, provenance), and can export to Neo4j when traversal/ecosystem is wanted |

### Amazon Neptune Analytics (+ Bedrock GraphRAG)

| Field | Finding |
|---|---|
| Category / licence | Memory-optimized graph analytics engine: fast in-memory processing, algorithm library, low-latency queries, vector search within traversals; loads from S3 or a Neptune Database snapshot. AWS-managed, per m-NCU-hour + storage (rates not captured → **unknown**) |
| Entry / inputs | IAM + graph. GraphRAG: Bedrock Knowledge Base, **S3 only**, up to **1,000 files** per data source (raisable to 10,000 by request), a foundation model for graph construction; 7 regions |
| How built | Algorithms on loaded data; GraphRAG = managed LLM extraction + enrichment, then vector search followed by graph expansion. Documented: **"configuration options to customize the graph build are not supported"** |
| Automation / HITL | High automation, not tunable; no human review path documented |
| Artifacts / time / provenance | Graph + vector index + KB retrieval + grounded answers. No temporal model. Retrieval returns used chunks/nodes; no per-edge evidence; deleting the KB does **not** delete the graph and charges continue |
| Agent path | Bedrock Knowledge Bases + FMs (Bedrock Agents) |
| Problems / outcomes / limits | Cross-document reasoning, GraphRAG over corpora, fraud/identity analytics. Vendor marketing only. Limits: S3-only, 1,000-file default, no build customisation, no autoscaling for Neptune Analytics graphs, region limits, cost trap |
| Gap for us | A black-box document graph. Our opening: deterministic, inspectable graph from structured sources, explainable entity types, per-edge provenance |

### Stardog virtual graphs (instance graph without copying)

| Field | Finding |
|---|---|
| Category / licence | Virtual graph: data stays in RDBMS/NoSQL; SPARQL is rewritten to SQL and pushed down; optional materialisation. Free lacks HA/backups/LDAP/full connectors; Enterprise quote-only |
| Entry / inputs | SPARQL/OWL skill, JDBC sources (customer-supplied drivers), SMS/R2RML/SMS2 mapping or R2RML direct mapping |
| How built / automation | Declarative mappings, human-authored; direct mapping is table-level; virtual transparency merges virtual + local graphs; `virtual import` materialises when latency demands |
| Artifacts / time / provenance | KG, registered virtual graphs, materialized copies, SPARQL/GraphQL/SQL/BI/Voicebox. Point-in-time recovery; named graphs (D); reasoning explanation = inference provenance, not source provenance |
| Problems / limits | Data fabric without ETL, analytics modernization, operational risk, supply chain. Documented SPARQL→SQL gaps (duplicate solutions, `MINUS` untranslated, datatype comparison, R2RML named graphs); pushdown-dependent performance; skills scarcity; connectors paywalled |
| Gap for us | No-copy is right; delivery needs specialists. We do no-copy for files/small DBs with an auto-derived model and no SPARQL |

### TigerGraph

| Field | Finding |
|---|---|
| Category / licence | Distributed MPP graph DB with GSQL, GraphStudio, Savanna managed cloud, Community Edition, GraphRAG/vector marketing. Savanna free trial **$0/GB-month** (24×7, US Tier 1); paid Savanna and self-managed DB contact sales; Community free single server |
| Entry / inputs | You must design a schema (vertices/edges/types), write a loading job and install GSQL queries. Connectors/Kafka feed it |
| How built / automation | Code-first manual: schema + load + compiled queries exposed as REST; GraphStudio for exploration; no source auto-inference. Automation is execution parallelism, not modelling |
| Artifacts / time / provenance | Loaded graph, installed queries via REST, GraphStudio visuals. Time/versioning and provenance not documented (unknown) |
| Agent path | Vendor markets GraphRAG, vector and agentic AI; specifics not verified |
| Problems / outcomes / limits | Fraud/AML, customer 360, entity resolution, recommendations, supply chain, cybersecurity, deep-link analytics. Named customers (Ford, Intuit, JLR, Xbox) — vendor marketing. Limits: schema-first, GSQL curve, heavy ops, enterprise pricing |
| Gap for us | Their buyers buy throughput; ours want no schema authoring, no new query language, instant graph for small/medium data |

### Memgraph

| Field | Finding |
|---|---|
| Category / licence | In-memory graph DB, Cypher-compatible, real-time streams, vector search, MAGE algorithms. **Community free forever, open source**; Enterprise/AI Platform **priced by memory** (quote-only); 30-day trial; Cloud 1–32 GB, AWS 6 regions; AWS Marketplace; OEM/SaaS |
| Entry / inputs | Cypher + memory sizing; Kafka/Pulsar/Redpanda streams; ZeroETL marketed; vector index |
| How built / automation | Hand-modelled property graph + Cypher; streams for updates; no documented source auto-modelling |
| Artifacts / time / provenance | In-memory graph, algorithms, vector search, Bolt/REST. Time/versioning and provenance not documented (D) |
| Problems / limits | Real-time fraud/risk, 360° network exploration, logistics, GraphRAG/AI memory. Limits: memory-bound cost, in-memory ops, no semantic/ontology layer, no temporal model documented |
| Gap for us | An engine waiting for a modeller; our auto-derived time-aware graph is a different product, not a worse engine |

### Databricks GraphFrames (Spark graph)

Open-source Spark package, community-maintained under `graphframes/graphframes` (GitHub API: `archived: false`, Apache-2.0, pushed 2026-10-28, 1,212 stars; README: "maintained by a group of individual contributors" — no vendor SLA). Input = vertex DataFrame (`id`) + edge DataFrame (`src`, `dst`); algorithms include PageRank, connected components ("entity resolution on billions or even trillions of records"), motif finding, Pregel/aggregate messages, label propagation, shortest paths. It is an **analytics library, not a store**: the "graph" is the DataFrame pair, output is DataFrames, no persistence, no traversal API for apps, no ontology, no lineage, no agent path. Problems: entity resolution at scale, fraud cycle detection, compliance shortest paths, graph ML. **Gap:** proves demand for graph algorithms on existing tables but leaves the graph unbuilt — we produce the graph and time bounds; algorithms are a thin add-on.

### Snowflake SQL-only / recursive SQL

No native property-graph type appears in the query docs reviewed (D for absence). Hierarchies use `WITH RECURSIVE` or `CONNECT BY`. Snowflake documents the evaluation model (anchor + working table iterations) and the restrictions clearly: the recursive clause **cannot** use aggregate/window functions, `GROUP BY`, `ORDER BY`, `LIMIT` or `DISTINCT`; bad construction **loops until statement timeout**; non-contiguous hierarchies need extra handling. No graph algorithms, centrality, shortest path or identity resolution; output is result sets only — nothing reusable, no graph object, no API, no as-of semantics. Problems: org charts, BOM rollups, simple multi-hop chains. **Gap:** our largest addressable segment — teams already doing "graph" in SQL who would try a derived graph with as-of queries if it cost nothing.

### Kùzu — the archived-free-tool lesson

Embedded property graph DB (Cypher, vector + full-text search), MIT. **Measured 2026-10-29 via GitHub API:** `archived: true`, `pushed_at: 2025-10-10`, MIT, 4,018 stars, 329 open issues still listed; `kuzudb.com` returned DNS `ENOTFOUND`. The reported acquisition is discussed in the market but we **could not verify it from a primary source** (D — do not state as fact).

**Why it matters:** Kùzu was the closest thing to what we build (embedded, Cypher, zero-ops). Once archived there are no patches, no CVE fixes, no support, and a migration burden; third-party ADRs already document replacements ("RyuGraph replaces Kùzu", commits replacing Kùzu with SQLite). **Lesson:** a free embedded graph is not a durable platform. Durability comes from owning data in boring portable formats (DuckDB/Parquet/CSV), export paths (OWL/SHACL/Neo4j/CSV), a model + provenance record that survives an engine swap, and a clear licence/support story. "Free" is distribution, not a moat.

## Problems solved / under-served

| # | Buyer problem | Served well by | Under-served |
|---|---|---|---|
| 1 | Instance graph without a modelling project | Nobody fully; Neo4j (docs only), Bedrock (generic doc graph) | **Auto-derived graph from structured sources** (keys, FKs, CSV heuristics) |
| 2 | Multi-hop traversal at interactive latency | Neo4j, TigerGraph, Neptune Analytics, Memgraph | Cheap local no-cluster traversal for small/medium data |
| 3 | What was true on date X | — | **Time-valid edges derived from date columns: greenfield** |
| 4 | Entity identity/resolution across sources | GraphFrames connected components; Neo4j resolvers; TigerGraph ER | Resolution without Spark/cluster; confidence-labelled merges |
| 5 | Provenance per edge | Partial: GraphRAG chunks; Stardog inference explanation | **Measured vs inferred vs guessed per edge, exposed downstream** |
| 6 | Agent consumption with citations | Neo4j stack, AWS Bedrock GraphRAG | Agent context from a *small local* graph, token-budgeted, with evidence |
| 7 | Scale without cost surprise | Neptune, TigerGraph, Aura | Cost-transparent local option |
| 8 | Query without learning Cypher/GSQL/SPARQL | Only Snowflake SQL ("no new language") | Ask in SQL/NL over a derived graph |
| 9 | Keeping the graph fresh | Memgraph/Neo4j streams; Stardog virtual graphs | Incremental refresh on local files/DBs without pipelines |
| 10 | Model change without rebuild | — | Versioned graph builds + diffable model |
| 11 | Governance/permissions on graph data | Neo4j/Stardog/TigerGraph RBAC | Small-team governance; per-fact sensitivity tagging |
| 12 | Vendor durability / exit | Commercial vendors; RDF standards | **Portable graph + model export**; Kùzu shows the risk |

**Served well:** raw traversal at scale (Neo4j, TigerGraph), managed analytics (Neptune), batch algorithms (GraphFrames), no-copy federation (Stardog). **Under-served:** deriving the graph; time; provenance; local/no-ops; agent context from small graphs; durability.

## What a better version must do

1. **Build the graph from the source, not a schema document.** Rows→nodes, FKs→edges, CSV header/type/name evidence→candidate keys/edges with confidence; zero per-dataset code.
2. **Make time a property of every edge and node.** valid_from/valid_to derived from source timestamps; as-of traversal; never silently overwrite history.
3. **Attach provenance to every fact.** Source, method (stated FK / inferred / heuristic), confidence, build id; surface it in traversal results and agent context.
4. **Be embedded and boring.** DuckDB-class footprint, no cluster; rebuild in seconds for millions of rows. Our internal measured benchmark (`STATUS.txt`, 2026-10-29): **1.5M nodes built in 14 s** — grade A internal, not independently reproduced here; present as our measurement, not market evidence.
5. **Expose the graph to agents cheaply.** Pack subgraphs + evidence into token-budgeted context; no GraphRAG infrastructure required.
6. **Keep an exit.** CSV/Parquet, Neo4j, RDF/OWL export; model and provenance independent of the engine (Kùzu lesson).
7. **Version and diff builds.** Added/removed nodes, changed edges, confidence drift.

## Candidate differentiators (Layer 2)

| # | Differentiator | Why it wins | Proof |
|---|---|---|---|
| K1 | Auto-derived instance graph from any source (FKs, keys, CSV heuristics) | Every engine requires a modelling step; nobody derives | Unseen-source suite: 0 per-dataset code; links graded stated/guessed |
| K2 | Bitemporal edges (valid_from/valid_to from date columns) | No competitor documents it; as-of questions are daily | As-of query test on a changing source vs hand SQL |
| K3 | Per-fact provenance + confidence in traversal/agent output | GraphRAG gives chunks, not evidence; catalogs give metadata lineage | Agent answers carry edge-level evidence; wrong answers trace to a row |
| K4 | Local, no-cluster, seconds-to-build | Engines are infra purchases; GraphFrames needs Spark | 1.5M nodes/14 s internal + laptop demo on 121 MB CSV |
| K5 | Durable + portable (boring storage, export to Neo4j/RDF) | Kùzu shows free-tool risk; buyers fear lock-in | Export/re-import fidelity; model + provenance survive engine swap |

## Sources

All accessed **2026-10-29**; grade in brackets.

1. [Neo4j pricing](https://neo4j.com/pricing/) — Aura tiers, free start, Enterprise quote; body truncated, **rates not captured**. [B-limited]
2. [Neo4j GraphRAG for Python](https://neo4j.com/docs/neo4j-graphrag-python/current/) — KG Builder, resolvers, vector index requirements, ANN limitation. [B]
3. [Neo4j navigation](https://neo4j.com/pricing/) — AuraDB, Virtual Graph, Aura Graph Analytics, Aura Agent, Context Engine, GraphRAG, MCP, agent memory. [B]
4. [Neptune Analytics — What is it?](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html). [B]
5. [Bedrock — GraphRAG with Neptune Analytics](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html) — regions, S3-only, 1,000 files, no build customisation, no autoscaling, deletion trap. [B]
6. [Stardog — Virtual Graphs](https://docs.stardog.com/virtual-graphs/) — mappings, pushdown, translation limits. [B]
7. [Stardog — Pricing](https://www.stardog.com/pricing/). [B]
8. [TigerGraph — Pricing](https://www.tigergraph.com/pricing/) — Savanna trial $0/GB-month; paid contact-sales. [B]
9. [TigerGraph — Compare editions](https://www.tigergraph.com/comparison-of-tigergraph-editions/). [B]
10. [Memgraph — Pricing](https://memgraph.com/pricing) — Community OSS; Enterprise by memory; Cloud sizes. [B]
11. [GraphFrames README](https://github.com/graphframes/graphframes) — DataFrame graphs, algorithms, maintainers. [B]
12. [GitHub API — graphframes/graphframes](https://api.github.com/repos/graphframes/graphframes) — archived=false, Apache-2.0, pushed 2026-10-28. [A]
13. [GitHub API — kuzudb/kuzu](https://api.github.com/repos/kuzudb/kuzu) — archived=true, pushed 2025-10-10, MIT, 4,018 stars. [A]
14. [Snowflake — Working with CTEs](https://docs.snowflake.com/en/user-guide/queries-cte) — recursive syntax, clause restrictions, loop risk, CONNECT BY. [B]
15. [Databricks — What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) — open-source UC, object model (host platform context). [B]
16. `STATUS.txt` (repo, 2026-10-29) — our own "1.5M things built in 14s". [A internal]

### Could not verify

- **Kùzu acquisition** (market-reported; no primary announcement fetched). Measured: repo archived, last push 2025-10-10, site DNS failure. The lesson stands; the deal is unverified.
- **Neo4j AuraDB / Neptune Analytics / TigerGraph paid list rates** (truncated, dynamic or quote-only).
- **Any vendor's bitemporal edge support** — absence of docs is not proof (D).
- **Outcome numbers** for Neo4j/Neptune/TigerGraph — vendor-reported only.
- Whether Neptune Analytics supports **RDF** as well as property graphs (user brief says yes; not verified in fetched pages — do not claim).
