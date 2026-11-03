# Knowledge Graph Layer for Enterprise Data and AI Agents (2025-2026)

NOTE: Plan mode blocked the write to the requested path:
C:/Users/tusha/AppData/Local/Temp/claude/2e81386eb977b160/f3643104-2f23-4ceb-a2ba-205b24e80fe3/scratchpad/research_notes/Strata four layers and agents/02_knowledge_graph.md
Copy this file there once plan mode is off. Research date: 2026-11-03.

## 1. Definition: knowledge graph vs graph database vs ontology

### Takeaway
A knowledge graph (KG) is data about real things (customers, orders, products) stored as nodes, with typed links between them. The ontology is the schema of meaning: which kinds of thing exist and how they may relate. A graph database is just one place to store a KG. Timbr and Stardog virtual graphs show that a KG can sit over SQL without a graph database at all.

### Cited Findings
- Timbr builds a "virtual knowledge graph over existing data sources using SQL-native ontologies" (concepts, properties, relationships, inheritance). It does not store the data and is queried in SQL. So a KG does not need a graph DB. — [Timbr docs](https://docs.timbr.ai/doc/docs/platform/); third-party view: "a semantic layer whose implementation is ontology and knowledge-graph shaped", not a stored graph — [Atlan](https://atlan.com/know/ai-agent/semantic-layer/timbr-semantic-layer/)
- Stardog is an RDF/OWL platform. It uses SPARQL natively, offers GraphQL and SQL access for BI, OWL reasoning, and "Virtual Graphs" that federate over sources (description written by a competitor, Timbr) — [Timbr vs Stardog (vendor, biased)](https://timbr.ai/timbr-vs-stardog/)
- Practitioner framing: KGs built without entity resolution end up with duplicate nodes (synonyms) — [KGC 2024 talk](https://www.knowledgegraph.tech/blog/kgc-2024-knowledge-graph-named-entity-resolution/)

### Inferences
- Analogy: the ontology is the map legend, the KG is the map with every real place and road drawn in, and the graph database is the filing cabinet the map is kept in. Strata's DuckDB-backed KG is a legitimate "KG without a graph DB", the same pattern as Timbr and virtual KGs.

### Gaps
- No single authoritative standards-body definition was fetched. The W3C RDF/OWL and R2RML specs were not fetched in this session.

## 2. Approaches: structured-data KGs vs LLM-extracted (GraphRAG) vs temporal agent-memory graphs

### Takeaway
There are three families. (a) Structured/relational to KG (R2RML, virtual KGs, data.world, Stardog, Timbr). This one is deterministic and cheap, and it carries the strongest accuracy evidence for enterprise question answering. (b) LLM extraction from documents (GraphRAG, LightRAG, Neo4j LLM Graph Builder). It costs a lot to index and its claimed gains have been disputed. (c) Temporal memory graphs (Graphiti/Zep, Cognee, Mem0). These target chat and agent memory, and their main idea worth taking is bitemporal fact invalidation. Strata's structured data fits (a) best. It should borrow temporal ideas from (c) and use (b) only for unstructured sources.

### Cited Findings
**(a) Structured/relational**
- data.world benchmark (Sequeda, Allemang, Jacob; arXiv 13 Nov 2023): GPT-4 zero-shot on SQL databases reached 16% accuracy. Asking over a KG representation of the same enterprise SQL database raised it to 54% — [arXiv 2311.07509](https://arxiv.org/abs/2311.07509). The paper gives exact figures of 16.7% and 54.2% — [arXiv 2405.11706](https://arxiv.org/pdf/2405.11706)
- Follow-up (Allemang and Sequeda, May 2024): adding an Ontology-based Query Check (deterministic, no LLM, validates generated SPARQL against the ontology) plus LLM repair (up to 3 iterations, otherwise "I don't know") gave 72.55% accuracy, about 8% "unknown" and about 20% error. data.world markets this as "4.2x" — [arXiv 2405.11706](https://arxiv.org/pdf/2405.11706); [data.world blog (vendor)](https://data.world/blog/genai-benchmark-ii-increased-llm-accuracy-with-ontology-based-query-checks-and-llm-repair). FLAG: vendor-run, on the vendor's own benchmark (insurance-domain schema), with no independent replication found.
- Timbr positions the same ontology as serving SQL users and agents through its "GenAI NL2SQL engine and GraphRAG SDK". It also has a governed Knowledge Base for Data Agents with draft, approved and deprecated entries — [Timbr (vendor)](https://atlan.com/know/ai-agent/semantic-layer/timbr-semantic-layer/)

**(b) LLM-extracted from text**
- Microsoft GraphRAG (Edge et al.): targets "global sensemaking" questions over corpora "in the 1 million token range". It claims gains over a conventional RAG baseline on comprehensiveness and diversity. v1 was 24 Apr 2024, v2 19 Feb 2025 — [arXiv 2404.16130](https://arxiv.org/abs/2404.16130)
- The repo is in MAINTENANCE MODE: no new PRs or features, only bug fixes, dependency updates and CVE fixes. It is "a demonstration", "not an officially supported Microsoft offering", and warns "GraphRAG indexing can be an expensive operation". MIT licence, about 36.5k stars — [microsoft/graphrag](https://github.com/microsoft/graphrag)
- LightRAG (HKUDS): a dual-layer KG plus vector RAG framework. MIT, about 40.5k stars, active (news item 2026.07). Default storage is in-memory/NetworkX and "not for production"; PostgreSQL is recommended for production, with Neo4j or Memgraph as graph options — [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG). The README's own win-rate table (LLM-judged, author-run) shows narrow margins of about 52-55% on comprehensiveness and overall. GraphRAG wins the "Mix" domain (50.4% vs 49.6% overall), which contradicts the "consistently outperforms" claim — [same](https://github.com/HKUDS/LightRAG)
- Amazon Bedrock Knowledge Bases GraphRAG on Neptune Analytics: preview Dec 2024, GA Mar 2025. It auto-extracts entities and relations, stores embeddings and graph in Neptune Analytics, and combines vector search with traversal — [AWS preview](https://aws.amazon.com/about-aws/whats-new/2024/12/amazon-bedrock-knowledge-bases-graphrag-preview); [AWS GA](https://aws.amazon.com/about-aws/whats-new/2025/03/amazon-bedrock-knowledge-bases-graphrag-generally-available)

**(c) Temporal agent-memory graphs**
- Zep/Graphiti paper (Rasmussen et al., 20 Jan 2025): a temporally aware KG combining conversations with structured business data. DMR 94.8% vs MemGPT 93.4%; LongMemEval up to +18.5% accuracy and 90% lower latency vs baselines — [arXiv 2501.13956](https://arxiv.org/abs/2501.13956). FLAG: vendor-authored (Zep).
- Graphiti repo: Apache-2.0, about 32.5k stars. "Explicit bi-temporal tracking with automatic fact invalidation": superseded facts are invalidated, not deleted. Hybrid retrieval (embeddings + BM25 + graph traversal). Backends are Neo4j 5.26, FalkorDB, Amazon Neptune, and Kuzu (deprecated, removal planned). Its reference MCP server has no auth or prompt-injection protection and is not for production — [getzep/graphiti](https://github.com/getzep/graphiti)
- Cognee: Apache-2.0, about 33k stars, very active (v1.6.1, 24 Sep 2026). A self-hosted memory KG from documents, code and chats, with operations remember, recall, improve (feedback into the graph) and forget. Runs locally with no API key. It can run on a single Postgres — [topoteretes/cognee](https://github.com/topoteretes/cognee)

### Inferences
- Strata's approach (rows become nodes, foreign keys become edges, with provenance and valid-from time) belongs to family (a). That family has the only published enterprise text-to-query accuracy evidence (16% to 54% to 72%). Strata should keep it as the core.
- Cognee's "improve" (feedback into the graph) and Timbr's draft, approved and deprecated lifecycle are both governance and feedback loops. They map onto Strata's semantic/feedback.py and glossary work.

### Gaps
- Not fetched this session: neo4j-labs/llm-graph-builder, LlamaIndex PropertyGraphIndex and Mem0 graph memory (licence, stars, status). Mem0's graph-memory benchmark claims were not checked.
- No published accuracy numbers for R2RML or Stardog virtual graphs on enterprise QA were found.

## 3. Vendors: features and dates

### Takeaway
In 2025-2026, every graph vendor shipped an "agents plus MCP" story. Neo4j has the broadest set: Aura Agent, a hosted MCP server in every Aura instance, and both official and Labs MCP servers. AWS ships managed GraphRAG. Glean ships an enterprise graph plus a per-user personal graph. Kuzu was bought by Apple and its repo archived in Oct 2025, so it is a dead dependency.

### Cited Findings
- Neo4j Aura Agent: builds and deploys agents from AuraDB KGs, with "agentic GraphRAG" (vector + graph queries) and one-click deployment to a hosted REST or MCP endpoint. Free to build and test; usage billing from 1 Mar 2026 — [Neo4j community (vendor)](https://community.neo4j.com/t/new-release-aura-agent-ai-agents-from-your-auradb-knowledge-graphs/76481)
- MCP for Aura: a hosted MCP server built into every Aura instance at no extra cost (Free, Pro, Business Critical tiers) — [Neo4j blog (vendor)](https://neo4j.com/blog/genai/introducing-mcp-for-aura/)
- The official Neo4j MCP server (neo4j/mcp) was GA at v1.0.1 by Dec 2025 — [This Week in Neo4j (vendor)](https://neo4j.com/blog/twin4j/this-week-in-neo4j-mcp-deployment-vector-graphrag-and-more/). The Labs collection neo4j-contrib/mcp-neo4j includes mcp-neo4j-cypher (NL to Cypher), mcp-neo4j-memory (KG memory), an aura-manager and data-modeling servers — [mcp-neo4j index](https://docsearch.algolia.com/mcp/docs/repo/neo4j-contrib/mcp-neo4j); [neo4j-field/mcp-neo4j-graphrag](https://github.com/neo4j-field/mcp-neo4j-graphrag)
- Amazon Neptune Analytics plus Bedrock GraphRAG: GA Mar 2025, with no extra charge beyond the underlying services. An AWS walkthrough puts the example Neptune Analytics cost at about $0.48/hr — [AWS GA](https://aws.amazon.com/about-aws/whats-new/2025/03/amazon-bedrock-knowledge-bases-graphrag-generally-available); [AWS ML blog](https://aws.amazon.com/blogs/machine-learning/announcing-general-availability-of-amazon-bedrock-knowledge-bases-graphrag-with-amazon-neptune-analytics/)
- Kuzu: GitHub repo archived 10 Oct 2025 with final release v0.11.3. FreshPorts gives 11 Oct. PyPI says no new releases are expected — [The Register](https://www.theregister.com/2025/10/14/kuzudb_abandoned/); [FreshPorts](https://freshports.org/databases/kuzu); [PyPI](https://pypi.org/project/kuzu/). Apple acquired it, per an EU filing reported Feb 2026 (deal dated Oct 2025) — [9to5Mac](https://9to5mac.com/2026/02/11/kuzu-database-company-joins-apples-list-of-recent-acquisitions/); [U Waterloo](https://cs.uwaterloo.ca/news/waterloo-based-graph-database-start-up-kuzu-acquired-apple). A community fork "LadybugDB" was reported in a forum post and is unverified — [Julia discourse](https://discourse.julialang.org/t/kuzudb-or-general-graphdbs/133139.md). Graphiti marks its Kuzu backend deprecated — [graphiti](https://github.com/getzep/graphiti)
- Glean Enterprise Graph: launched 25 Sep 2025 at Glean:LIVE. It extends the earlier people and knowledge Knowledge Graph to projects, processes and data, and adds a private per-user "personal graph". Agentic Engine 2 uses both graphs for planning and memory. Exposed via APIs and MCP. Built by ML inside a single-tenant environment — [Glean press (vendor)](https://www.glean.com/press/glean-introduces-third-generation-ai-assistant-new-enterprise-graph-to-enable-the-superintelligent-enterprise); [Reworked](https://www.reworked.co/knowledge-findability/glean-thinks-its-ai-understands-your-company-better-than-you-do/)
- Senzing offers an MCP server for agentic entity resolution and integrations into Neo4j and Neptune KGs — [Senzing (vendor)](https://senzing.com/graphrag-amazon-aws-neptune-bedrock/); [Neo4j ER tutorial](https://neo4j.com/blog/knowledge-graph/entity-resolved-knowledge-graphs/)

### Inferences
- MCP exposure of the graph is now table stakes. Strata's api/mcp_server.py is aligned with the market.
- Avoid Kuzu as an embedded graph engine. DuckDB (Strata's current choice) is the safer embedded option. DuckDB's own graph extensions were not researched here.

### Gaps
- Not researched this session (no citations): TigerGraph, Ontotext GraphDB, FalkorDB (licence is believed SSPL, unverified), Memgraph (licence and GraphRAG features), and Microsoft Graph (the M365 people and content graph). The Neo4j LLM Graph Builder status is also unchecked.

## 4. Evaluations and benchmarks

### Takeaway
The strongest positive evidence comes from vendor-run studies (data.world, Zep, LightRAG, Microsoft). An independent re-evaluation (arXiv 2506.06331) found GraphRAG gains "much more moderate than reported" once LLM-judge bias is removed. Plain vector RAG matches or beats GraphRAG on single-hop fact lookup.

### Cited Findings
- Zeng et al., "How Significant Are the Real Performance Gains? An Unbiased Evaluation Framework for GraphRAG" (v1 31 May 2025, v2 Aug 2026). Existing evaluations suffer from unrelated questions and LLM-judge biases. On 3 representative GraphRAG methods, gains were "much more moderate than reported previously" — [arXiv 2506.06331](https://arxiv.org/abs/2506.06331). Secondary reports cite position bias shifting win rates by more than 30% — [beancount research log](https://beancount.io/bean-labs/research-logs/2026/06/04/graphrag-local-to-global-query-focused-summarization) (secondary, not verified against the paper text)
- A secondary report says vector RAG narrowly beat the best graph method on single-hop Natural Questions (F1 64.8 vs 63.0) in a 2025 Michigan State / Meta comparison — [Groundy](https://groundy.com/articles/graphrag-vs-vectorrag-does-the-graph-index-earn-its-cost/) (secondary; primary paper not fetched)
- Cost: a claim that indexing 5 GB of legal data fell from about $33,000 (early 2024) to about $33 (mid-2025), largely due to LazyGraphRAG — [Medium/Graph Praxis](https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4). UNVERIFIED, sources unclear, and dates for LazyGraphRAG conflict across blogs.
- The vendor-run benchmarks are data.world 16% to 54% to 72% ([2311.07509](https://arxiv.org/abs/2311.07509), [2405.11706](https://arxiv.org/pdf/2405.11706)), Zep DMR 94.8% ([2501.13956](https://arxiv.org/abs/2501.13956)), and LightRAG win rates ([repo](https://github.com/HKUDS/LightRAG)). All are self-reported.
- Text2Cypher (Neo4j, Dec 2024): 44,387 NL-to-Cypher pairs (39,554 train / 4,833 test). Execution-based evaluation favoured GPT-4o and a fine-tuned tomasonjo model — [arXiv 2412.10064](https://arxiv.org/html/2412.10064v1); [Neo4j benchmark blog (vendor)](https://neo4j.com/blog/developer/benchmarking-neo4j-text2cypher-dataset/). "Mind the Query" (IBM): 27,529 NL-to-Cypher pairs over 11 graphs — [IBM Research](https://researcher.ibm.com/publications/mind-the-query-a-benchmark-dataset-towards-text2cypher-task) (attribution partly unconfirmed)

### Inferences
- For Strata, the data.world result is the relevant one: structured data, enterprise questions, ontology checks. Its key mechanism is a deterministic ontology validation of generated queries, which Strata's semantic/validate.py already mirrors. Treat the 72% as an upper-bound vendor figure.
- Strata should not claim "GraphRAG-level" gains. It should run its own held-out evaluation with blind or position-swapped judging.

### Gaps
- Exact GraphRAG paper win-rate numbers were not on the abstract page. Commonly cited figures (about 72-83% comprehensiveness) are unverified here.
- No 2025-2026 independent text2cypher accuracy leaderboard was found.

## 5. Entity resolution / identity across sources

### Takeaway
Entity resolution (ER), meaning working out which records in different systems are the same customer or company, is a precondition for a useful cross-source KG. Without it, agents see duplicate entities and give split or contradictory answers. Senzing (commercial SDK, real-time, now Spark and MCP) is the most KG-integrated option. Splink and Zingg are open-source batch options but were not verified this session.

### Cited Findings
- KGs without ER suffer from duplicate (synonym) nodes. The recommended pattern keeps multiple levels of detail: raw records linked to resolved entities — [KGC 2024](https://www.knowledgegraph.tech/blog/kgc-2024-knowledge-graph-named-entity-resolution/); [Neo4j + Senzing tutorial](https://neo4j.com/blog/knowledge-graph/entity-resolved-knowledge-graphs/)
- Senzing: real-time explainable ER SDK (people, organisations, relationships). Has a Spark beta (batch, transactional with SQL, or hybrid) and an MCP server for agentic workflows; it pushes the entity graph into KGs, Elasticsearch or lakes — [Senzing (vendor)](https://senzing.com/?p=45386)

### Inferences
- Strata's cross-source identity resolution plus measured-vs-derived provenance matches the "records linked to resolved entity" pattern. Keep same-as edges explicit and reversible, marked derived with a confidence score, and never merge source rows.

### Gaps
- Splink (UK Ministry of Justice, MIT, Fellegi-Sunter probabilistic model, runs on DuckDB/Spark) and Zingg (AGPL, ML-based) were not confirmed with fetched sources this session. Splink's DuckDB backend would fit Strata naturally, but this needs verification.

## 6. Temporal graphs: "what was true on date X"

### Takeaway
Bitemporal modelling records two times: when a fact was true in the world (valid time) and when the system learned it (transaction or ingest time). Graphiti/Zep is the most visible agent-graph implementation: it invalidates rather than deletes facts. Strata's valid-from per edge is half of this, and adding a valid-to field and an ingest time would make it fully bitemporal.

### Cited Findings
- Graphiti: "explicit bi-temporal tracking with automatic fact invalidation". Superseded facts get validity windows closed, not deleted — [getzep/graphiti](https://github.com/getzep/graphiti)
- The Zep paper describes a temporally aware KG that maintains historical relationships, combining conversations and business data — [arXiv 2501.13956](https://arxiv.org/abs/2501.13956)

### Inferences
- With only valid-from, "as-of" queries must infer an edge's end from the next version. Storing valid_to and recorded_at allows audit questions like "what did the agent believe on date X", which matters for cited evidence packs.

### Gaps
- Bitemporal support in Stardog, Neo4j (no native bitemporality as far as known), XTDB and TerminusDB was not researched this session.

## 7. How agents query graphs, and failure modes

### Takeaway
There are three patterns. (1) The LLM generates Cypher or SPARQL (text2cypher, mcp-neo4j-cypher). This is flexible but hallucination-prone, so it needs schema grounding plus deterministic validation and repair. (2) Predefined graph tools such as neighbours, path or as-of queries, exposed via MCP. These are safer. (3) Hybrid neighbourhood retrieval (vector or BM25 seed, then traversal), as in Graphiti, LightRAG and Aura Agent. The recurring failures are hallucinated queries, judge-inflated evals, extraction cost, duplicate entities, stale facts and insecure MCP servers.

### Cited Findings
- Text-to-query: mcp-neo4j-cypher exposes NL-to-Cypher to agents — [mcp-neo4j](https://docsearch.algolia.com/mcp/docs/repo/neo4j-contrib/mcp-neo4j). Neo4j's failure analysis of text2cypher models proposes parse-tree-based evaluation — [Neo4j blog (vendor)](https://neo4j.com/blog/developer/text2cypher-model-struggles-dataset-improvements/)
- Validate-and-repair cuts errors: an ontology check plus LLM repair raised accuracy from 54% to 72%, and returning "I don't know" after 3 failed repairs turned about 8% of would-be errors into abstentions — [arXiv 2405.11706](https://arxiv.org/pdf/2405.11706)
- Hybrid retrieval: Graphiti combines embeddings, BM25 and traversal ([graphiti](https://github.com/getzep/graphiti)). Aura Agent combines vector and graph queries ([Neo4j](https://community.neo4j.com/t/new-release-aura-agent-ai-agents-from-your-auradb-knowledge-graphs/76481)). Bedrock GraphRAG does vector plus traversal ([AWS](https://aws.amazon.com/about-aws/whats-new/2025/03/amazon-bedrock-knowledge-bases-graphrag-generally-available))
- Failure modes found in sources:
  - indexing cost — [graphrag repo](https://github.com/microsoft/graphrag)
  - abandoned upstream: GraphRAG maintenance mode, Kuzu archived — [graphrag](https://github.com/microsoft/graphrag), [The Register](https://www.theregister.com/2025/10/14/kuzudb_abandoned/)
  - non-production defaults (LightRAG NetworkX/JSON storage) — [LightRAG](https://github.com/HKUDS/LightRAG)
  - MCP servers without auth or prompt-injection protection — [graphiti](https://github.com/getzep/graphiti)
  - duplicate nodes without ER — [KGC 2024](https://www.knowledgegraph.tech/blog/kgc-2024-knowledge-graph-named-entity-resolution/)
  - inflated LLM-judge evaluations — [arXiv 2506.06331](https://arxiv.org/abs/2506.06331)

### Inferences
- Super-nodes are a risk specific to Strata's design. Turning every FK value into an edge makes high-fan-in nodes (e.g., country = "US", status = "active") that blow up multi-hop reach. Mitigations: model low-cardinality lookup columns as properties rather than edges, cap fan-out per hop, and rank neighbours by provenance and recency.
- Graph bloat: a node for every row duplicates the warehouse. Consider materialising nodes only for entity tables and treating fact rows as edges or properties. This is unsourced design judgement.
- Strata's predefined tools (neighbours, reach, as-of) are the safer pattern. Keep free-form Cypher/SQL generation behind validate.py-style deterministic checks with an "I don't know" fallback.

### Gaps
- No sourced quantitative study of super-node or stale-edge impact on agent accuracy was found.
- No independent comparison of "predefined graph tools" vs "text2cypher" accuracy for agents was found.

## Keep / build / drop summary (inference, for the report writer)
- KEEP: building the KG deterministically from structured data (family a); the measured-vs-derived provenance; DuckDB storage (avoid Kuzu); predefined MCP graph tools; cross-source identity as explicit derived edges.
- BUILD: full bitemporality (valid_to, recorded_at); super-node and fan-out guards; ontology-based query validation with repair and abstain (data.world pattern); an unbiased evaluation harness (position-swapped, held-out questions); optional hybrid seed retrieval (BM25/vector, then traversal); an MCP server with auth.
- DROP / DEFER: LLM extraction from documents as the core KG (costly, gains disputed, upstream GraphRAG frozen). Use it only as an optional connector for unstructured sources, with LightRAG or Cognee as reference designs.
