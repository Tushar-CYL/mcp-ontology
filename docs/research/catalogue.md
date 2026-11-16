# Catalogue: repos, tools and companies per layer

Extracted from [REPORT.md](REPORT.md) (November 2026 deep research). Licences and activity were checked during the research; re-check before reuse.


Star counts and licences below are snapshots from the research notes (about November 2026). Unverified items are labelled.

### Ontology

| Repo or tool | Licence | Activity | What to learn |
|---|---|---|---|
| [NVIDIA/auto-ontology](https://github.com/NVIDIA/auto-ontology) | Apache-2.0 | 2,267 stars, pushed 2026-11-03 | Discover/Ground/Validate/Expose/Learn loop; read-only MCP; certify/publish/rollback. No outside contributions; plaintext credentials by default |
| [RDFLib/rdflib](https://github.com/RDFLib/rdflib) | BSD-3-Clause | 2,546 stars, pushed 2026-11-02 | Cheap Turtle/OWL/JSON-LD export |
| [linkml/linkml](https://github.com/linkml/linkml) | Apache-2.0 | 682 stars, pushed 2026-11-03 | One YAML source compiling to OWL, SHACL, JSON Schema, SQL |
| [ontop/ontop](https://github.com/ontop/ontop) | Apache-2.0 | 1,009 stars, pushed 2026-10-15 | Reference for ontology-as-mappings over SQL (virtual KG) |
| [protegeproject/protege](https://github.com/protegeproject/protege) | Shown as NOASSERTION on GitHub; confirm | 1,627 stars | Desktop OWL editor with reasoners |
| [monarch-initiative/ontogpt](https://github.com/monarch-initiative/ontogpt) | BSD-3-Clause | 1,085 stars | LLMs filling a fixed schema instead of inventing one |
| [morph-kgc/morph-kgc](https://github.com/morph-kgc/morph-kgc), [RMLio/rmlmapper-java](https://github.com/RMLio/rmlmapper-java) | Apache-2.0, MIT | 300 and 205 stars | R2RML/RML materialization |
| [schemaorg/schemaorg](https://github.com/schemaorg/schemaorg) | Apache-2.0 | 6,297 stars | Ready names for common entity types |

Companies: Palantir Foundry/AIP (reference design), Microsoft Fabric IQ (closest analogue, preview), Timbr (OWL over SQL), Stardog (full W3C stack, Voicebox agent), data.world (now ServiceNow), TextQL (ontology as version-controlled `.tql` files), Databricks Genie Ontology (reported public preview, unverified).

### Knowledge graph

| Repo or tool | Licence | Activity | What to learn |
|---|---|---|---|
| [getzep/graphiti](https://github.com/getzep/graphiti) | Apache-2.0 | ~32.5k stars | Bitemporal fact invalidation; hybrid retrieval. Reference MCP server lacks auth |
| [topoteretes/cognee](https://github.com/topoteretes/cognee) | Apache-2.0 | ~33k stars, v1.6.1 Sep 2026 | Remember/recall/improve/forget; feedback into the graph; runs on Postgres |
| [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | MIT | ~40.5k stars, active | Graph plus vector RAG; default storage not for production |
| [microsoft/graphrag](https://github.com/microsoft/graphrag) | MIT | ~36.5k stars, maintenance mode | Global sensemaking over documents; expensive indexing |
| [neo4j-contrib/mcp-neo4j](https://docsearch.algolia.com/mcp/docs/repo/neo4j-contrib/mcp-neo4j) | Not checked | Labs collection | NL-to-Cypher and memory MCP servers |
| Kuzu | Archived Oct 2025 | Dead | Avoid |

Companies: Neo4j (Aura Agent, hosted MCP in every Aura instance), AWS (Bedrock GraphRAG on Neptune Analytics, GA Mar 2025), Glean (Enterprise Graph plus personal graphs), Senzing (entity resolution with MCP), RelationalAI (Relational Knowledge Graph on Spider 2.0). Splink and Zingg (entity resolution) were not verified this round.

### Semantic layer

| Repo or tool | Licence | Activity | What to learn |
|---|---|---|---|
| [dbt-labs/metricflow](https://github.com/dbt-labs/metricflow) | Apache-2.0 since 0.209.0 (earlier AGPL, then BSL) | ~1.9k stars | Richest metric typing and filter grammar; Ossie reference |
| [dbt-labs/dbt-mcp](https://github.com/dbt-labs/dbt-mcp) | Apache-2.0 | ~616 stars | Discover-then-query tool decomposition; write tools isolated |
| [cube-js/cube](https://github.com/cube-js/cube) | MIT client, Apache-2.0 backend | ~21.2k stars | RLS at query time, caching, branch-gated writes; MCP in Cloud on all plans |
| [malloydata/malloy](https://github.com/malloydata/malloy) | MIT | ~2.6k stars | Symmetric aggregates against fan-out; Publisher serves REST and MCP |
| [Canner/WrenAI](https://github.com/Canner/WrenAI) | Mixed: Apache-2.0 core plus AGPL-3.0 and CC-BY files | ~18.1k stars | MDL plus `instructions.md` and `queries.yml` next to the model |
| [boringdata/boring-semantic-layer](https://github.com/boringdata/boring-semantic-layer) | MIT | ~487 stars | Tiny Ibis-based layer with MCP extra |
| [apache/ossie](https://github.com/apache/ossie) | Apache-2.0 | Incubating since 2026-06-22 | The interchange format to import and export |
| [microsoft/powerbi-modeling-mcp](https://github.com/microsoft/powerbi-modeling-mcp) | Not checked | Preview | Local authoring MCP |

Companies: dbt Labs, Cube, AtScale (MCP server Dec 2025), Snowflake semantic views and Cortex Analyst, Databricks Unity Catalog metric views, Google Looker, Microsoft Power BI.

### Context

| Repo or tool | Licence | Activity | What to learn |
|---|---|---|---|
| [mcp-server-datahub](https://pypi.org/project/mcp-server-datahub/0.8.0/) | Not checked | Official | Per-client tokens, no server-wide token; filtered, paginated search; lineage |
| [RAGAS](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) | Not verified this round | Active | Context precision/recall, faithfulness, tool-call accuracy |
| Google sufficient-context code ([blog](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)) | Not checked | Research | Ready-made "is this answerable?" autorater |
| MCP spec and SDKs ([versioning](https://modelcontextprotocol.io/specification/versioning)) | Not verified this round | Active | `outputSchema`, `structuredContent`, annotations, security rules |

Companies: Atlan (29-tool MCP, metadata only, OAuth), Microsoft Foundry IQ (cited answers under caller identity), Glean (MCP Gateway with OAuth 2.1), Databricks Genie knowledge store. Licences for Mem0, Letta, LangGraph and the MCP SDKs were not verified this round.

### Agents

| Repo or tool | Licence | Activity | What to learn |
|---|---|---|---|
| [vanna-ai/vanna](https://github.com/vanna-ai/vanna) | MIT | Archived 29 Mar 2026, ~23.8k stars | Tool registry with `access_groups`, `UserResolver`, admin-only SQL |
| LangGraph supervisor ([LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)) | Not verified this round | Active | Telephone-effect fixes: strip handoffs, forward replies verbatim |
| [HKUSTDial/awesome-data-agents](https://github.com/HKUSTDial/awesome-data-agents) | List | Active | Paper index behind the L0-L5 survey |
| [xlang-ai/Spider2](https://github.com/xlang-ai/Spider2) | Benchmark | Active | Enterprise text-to-SQL tasks (with known annotation noise) |

Companies: Snowflake Cortex Agents, Microsoft Fabric data agent (GA, read-only, 5 sources, 25x25 cap), Databricks Agent Bricks (supervisor now legacy), Palantir AIP Agent Studio, Google Looker Conversational Analytics. ThoughtSpot Spotter, Amazon Q and Bedrock agents, and Copilot Studio were not researched.

