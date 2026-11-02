# Industry map — who does what in the four layers, and why everyone is converging on "context"

*Synthesis of `docs/research/01..04`. All claims graded A–D there; this page only
uses the graded findings and names the pattern. Accessed 2026-10-29.*

## 1. The map in one picture

```
                         WHAT BUYERS ARE TRYING TO SOLVE
        meaning &        trust &         one metric,       multi-hop       AI grounding &      operational
        discovery        governance      everywhere        relationships   agent context       action
        ─────────────────────────────────────────────────────────────────────────────────────────────
L1      Atlan            Databricks      Databricks UC      Stardog         Palantir            Palantir
ONTOLOGY  (metadata)     Unity Catalog   Metric Views      GraphDB         Foundry Ontology    Foundry
        Protégé/OWL      Atlan           (semantic)        (virtual KG)    metaphactory        (actions)
                                            │
L2      —                Neo4j           —                 Neo4j           Neo4j               Palantir
KNOWLEDGE                (lineage)                          Neptune        Neptune GraphRAG    AIP
GRAPH                                                       TigerGraph     (Bedrock)
                                                            Memgraph
                                                            GraphFrames
                                            │
L3      Atlan            Databricks      dbt MetricFlow     —               Snowflake Cortex    —
SEMANTIC (glossary)     Unity Catalog   Cube / AtScale                     Cube MCP
                                            │
L4      Atlan Context    Atlan Context   Cube "AI Context   GraphRAG        MCP (delivery)      Palantir AIP
CONTEXT   Layer          policies        Layer"             (retrieval)     Glean / Zep /       (staged writes)
        (metadata)       (governance)                                        Letta (memory)
                                            │
                                            ▼
                              EVERYONE IS MOVING RIGHT AND DOWN:
                    catalog → semantics/context; graph DB → GraphRAG/context;
                    BI/semantic → MCP; platform → ontology + agents.
```

**Pattern:** no vendor owns a clean four-layer stack. Each starts from its own
center of gravity and stretches toward "context for AI":

| Started as | Vendor | Stretch move (documented) |
|---|---|---|
| Operational platform | Palantir | Ontology → AIP agents; typed OSDK APIs |
| Governance catalog | Databricks | Unity Catalog → metric views → Genie agents / MCP |
| Data catalog | Atlan | Active metadata → "Context Layer for AI"; Context Agents/Studio |
| Graph engine | Neo4j | Property graph → GraphRAG → Context Engine → Aura Agent |
| Warehouse | Snowflake | Semantic Views → Cortex Analyst → managed MCP; Horizon Context preview |
| Semantic layer | dbt, Cube | Metric APIs → MCP servers; Cube calls itself "AI Context Layer" |
| Retrieval / memory | GraphRAG, Zep, Letta, Glean | RAG → agent memory / enterprise graph; MCP endpoints |
| Integration protocol | MCP | De-facto delivery contract for all of the above |

## 2. What each layer actually is in the market

| Layer | Market names | Reference products | How the layer is built | What the buyer gets | Where it stops |
|---|---|---|---|---|---|
| L1 Ontology | Ontology (Palantir), Unity Catalog semantics, active metadata/context (Atlan), semantic knowledge graph (Stardog, GraphDB) | Palantir, Databricks UC, Atlan, Stardog, GraphDB, metaphactory | Human modelling, OWL/SPARQL, metadata + curation; Databricks automates lineage/classification; **no vendor documents auto-deriving classes/keys/relations from an arbitrary source** | A model, catalog, glossary, governed semantics | Enterprise cost/skills; no uncertainty labels; no bitemporal relations (documented absence); platform-bound |
| L2 Knowledge graph | Knowledge graph, graph database, GraphRAG, virtual graph | Neo4j, Neptune Analytics, TigerGraph, Memgraph, GraphFrames, Stardog | Hand-modelled schema + load + queries; docs extraction for GraphRAG | A graph you can traverse (if you built it) | You must build the graph; time validity not first-class; per-edge provenance thin/absent |
| L3 Semantic layer | Semantic layer, metrics layer, semantic views, LookML | dbt/MetricFlow, Cube, AtScale, Databricks metric views, Snowflake Semantic Views + Cortex Analyst, LookML, Power BI | Manual YAML/JS/LookML; AI assists authoring only | One definition of a metric, compiled to SQL, served to BI/agents | Manual onboarding weeks; no auto-inference; no as-of metric semantics; per-claim provenance absent |
| L4 Context | Context layer / context engine / agent memory / GraphRAG / MCP | Atlan, Neo4j Context Engine, Cube, Palantir AIP, GraphRAG, MCP, Glean, Zep, Letta, vector DBs | Metadata+governance (Atlan), graph+memory (Neo4j), retrieval (GraphRAG), memory (Zep/Letta), delivery (MCP) | Governance-filtered knowledge, retrieved chunks, memory, tool access | Nobody documents **task-conditioned evidence packing under a hard budget with per-fact grades**; permission and "as-at" answers are rare; silent truncation is the norm |

## 3. The five things the whole market lacks (and we can own)

1. **Auto-derivation from an arbitrary source.** Every Layer-1/2/3 tool begins
   with a human modelling step; AI only assists authoring. No competitor
   documents deriving classes, keys, relations, time validity and candidate
   metrics from a raw schema/CSV and labelling the uncertainty.
2. **Per-fact evidence grades.** GraphDB has inference provenance; Databricks
   has table/column lineage; citations exist in AI answers. None labels each
   statement **measured vs derived vs external** and carries it into the answer.
3. **Bitemporal facts/relations.** No Layer-1/2 vendor documents valid-from/
   valid-to on model elements or edges; Layer-3 has no as-of metric semantics.
   "What was true then" is daily in operations and nearly unserved.
4. **Hard-budget context packing.** Vendors ship retrieval/query APIs. Nobody
   guarantees a size limit, drops a fact whole rather than half, or reports what
   was dropped. Silent truncation is the default failure mode.
5. **Local, boring, portable delivery.** The category is platform/cloud-bound
   (enterprise contracts, DBU/credit/AI-credit billing, quote-only pricing).
   Free embedded tools are not durable (Kùzu archived). A local, $0,
   export-friendly implementation is unserved.

## 4. What this means for our position

We are not competing with Palantir, Atlan, Databricks or Neo4j on their terms
(governance breadth, connectors, scale, ecosystem). We compete on **the
onboarding step they all skip**: derive a trustworthy, time-aware, agent-ready
middle layer from any source, locally, with the human approving only the parts
that need judgment, and prove it with numbers.

**Category sentence for the deck:**
*"An auto-authoring, provenance-first middle layer that turns any data source
into ontology, a time-aware knowledge graph, governed metrics and agent-ready
context — local, free, and honest about what it guessed."*

## 5. Where the map is thin (research gaps to close before Gate 1)

- AtScale capabilities/pricing pages returned title-only HTML (grade C).
- Looker list price not captured; Power BI Fabric capacity not quantified.
- Neo4j Aura / Neptune Analytics / TigerGraph paid rates not captured.
- Palantir, Atlan, Stardog, GraphDB per-seat/core prices quote-only.
- Neo4j Context Engine is 9 days old at this writing; claims unverified.
- Kùzu acquisition unverified (repo archive + site DNS measured).
- No hands-on market trial this round (documented, not measured).

## 6. Detailed evidence

- L1: [01_ontology_layer.md](../research/01_ontology_layer.md)
- L2: [02_knowledge_graph_layer.md](../research/02_knowledge_graph_layer.md)
- L3: [03_semantic_layer.md](../research/03_semantic_layer.md)
- L4: [04_context_layer.md](../research/04_context_layer.md)
- Gap analysis: [gap_analysis.md](gap_analysis.md)
- Better-version blueprint: [better_version_blueprint.md](better_version_blueprint.md)
