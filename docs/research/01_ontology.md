# Ontology Layer for Enterprise Data and AI Agents (2025-2026 state of the art)

Note: these notes were meant for `C:/Users/tusha/AppData/Local/Temp/claude/2e81386eb977b160/f3643104-2f23-4ceb-a2ba-205b24e80fe3/scratchpad/research_notes/Strata four layers and agents/01_ontology.md`. Plan mode was on, so this plan file was the only one I could write to. Copy this file to that path.
Research date: 2026-11-03. Vendor-authored sources are marked [VENDOR]. Competitor commentary is marked [COMPETITOR]. Lines marked "(standard reference)" are well-established facts from the canonical spec URL; I did not re-fetch those pages this session.

## Q1. Plain-language definitions: ontology vs schema vs semantic layer vs knowledge graph

### Takeaway
A schema says how data is stored (tables, columns, keys). An ontology says what the business things are and how they relate, independent of storage. A knowledge graph is the ontology filled in with real instances and links. A semantic layer is the set of governed calculations (metrics, dimensions) on top. The vendors now merge these: Microsoft's ontology holds entities, relationships, metrics, rules and bindings in one item.

### Cited Findings
- Microsoft defines its ontology as "a shared, machine-understandable representation of your business": concepts (customers, products, assets, orders, locations), their properties, how they relate, and "the rules and metrics that give them business meaning". These definitions are bound to enterprise data so that people, apps and AI agents share one vocabulary. [VENDOR] — [Microsoft Learn, Ontology overview (updated 2026-10-16)](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Microsoft says the ontology bridges "the gap between how data is physically stored and how your business understands it". Without it, every consumer has to interpret "tables, columns, measures, and joins independently". It is "not itself a general-purpose data-query engine": it stores definitions and bindings, and consumers query the bound sources. [VENDOR] — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Palantir: "An Ontology is a categorization of the world". In Foundry it is "the digital twin of an organization". An object type is "the schema definition of a real-world entity or event", and a link type is "the schema definition of a relationship between two object types". [VENDOR] — [Palantir core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts)
- Microsoft keeps the "schema graph" (ontology) separate from the instance graph. "An ontology-derived schema graph doesn't load instance data by default." Graph materialization is opt-in, for multi-hop, reachability and shortest-path questions. Routine lookups and aggregations stay on the source systems. Microsoft says this "replaces the earlier framing" in which every ontology automatically had a materialized instance graph. [VENDOR] — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- NVIDIA describes its ontology as a "context layer" that tells agents "where data lives, what it means, whether to use it, and where it came from". [VENDOR, open source] — [NVIDIA/auto-ontology README](https://github.com/NVIDIA/auto-ontology)

### Inferences
- Analogy for non-experts. The schema is the warehouse's shelf layout (bin numbers, aisle codes). The ontology is the product catalogue: what a "Customer" or an "Order" is, and that a customer places orders. The knowledge graph is the catalogue with every actual customer and order filled in and connected. The semantic layer is the agreed accounting rulebook ("revenue = this formula, excluding returns"). The context layer is the evidence folder handed to someone answering a question.
- Industry framing is converging on the ontology as a virtual layer of definitions plus bindings over live sources, not a copy of the data. Strata's deterministic schema-derived ontology fits this model.

### Gaps
- No neutral standards body defines "semantic layer" vs "ontology" for agent products. The boundaries are set by vendor marketing.

## Q2. How vendors model ontology and expose it to agents

### Takeaway
Palantir is the reference design: objects, links, actions and functions, with agents reaching them through typed tools. Microsoft Fabric IQ (preview) is the closest analogue to Strata: it generates an ontology from existing semantic models, binds it to live sources, adds metrics and natural-language rules, uses proposal-first agent edits, and supports named versions and RDF/OWL import and export. Databricks and Snowflake are semantic-layer-first: their join relationships are explicit, and Snowflake requires them before it will join. Vendors that started on RDF (Stardog, Timbr, data.world) stress OWL inference and virtual graphs.

### Cited Findings

**Palantir Foundry Ontology and AIP [VENDOR]**
- The Ontology has "semantic elements (objects, properties, links) and kinetic elements (actions, functions, dynamic security)". Object definitions carry "granular security and governance for all changes". — [Palantir Ontology overview](https://www.palantir.com/docs/foundry/ontology/overview)
- Core types: object type, property, shared property, link type, action type ("a set of changes or edits to objects, property values, and links", including side effects), function ("code-based logic that takes in input parameters and returns an output", which can take objects and object sets as input), interface ("the shape of an object type and its capabilities"), roles ("the central permissioning model"), and Object Views. — [Palantir core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts)
- AIP Agent Studio tools:
  - The **Action tool** lets an agent "execute an ontology edit", either automatically or after user confirmation.
  - The **Object query tool** supports filtering, aggregation, inspection and link traversal over configured objects. Limiting the exposed properties makes it more token-efficient.
  - The English docs list six tool types in total. The search snippet named Update application variable, Command and Request clarification as others, and the application-state page also mentions a Function tool. The Chinese translation lists five, so the two versions conflict.
  — [Palantir Agent Studio tools](https://palantir.com/docs/foundry/agent-studio/tools)
- Application state (formerly "parameters"): variables of string or object-set type can update deterministically from Object query outputs, function-backed context or Ontology context. Action and Function tools can take inputs from these variables "instead of generating inputs dynamically through the LLM". — [Palantir application state](https://palantir.com/docs/foundry/agent-studio/application-state)

**Microsoft Fabric IQ ontology (PREVIEW) [VENDOR]**
- Status: the ontology item is still in preview (doc updated 2026-10-16). The old ontology experience retires on 31 January 2027. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Status conflict: one vendor blog says Fabric IQ went GA at Build 2026 while the ontology item stayed in preview. Microsoft's pages say preview. — [Atlan explainer](https://atlan.com/know/microsoft-fabric/what-is-fabric-iq/), [Microsoft Learn IQ overview](https://learn.microsoft.com/fabric/iq/overview)
- Modelling concepts:
  - Entity type (name, description, properties, identifiers, metrics, rules, relationships), entity instance, property (typed, mappable to fields in one or more sources), relationship ("Customer places Order"), metric, rule, namespace and data binding.
  - The new model supports "keyless entity types, relationships without dedicated join tables, namespaces, entity hierarchies, and reuse through inheritance", plus shared properties.
  — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Generation: an ontology can be generated from Power BI semantic models, carrying over tables, columns, relationships, calculated columns and DAX measures. Measures become **metrics**. "The source semantic model remains the owner of the DAX expression", so agents reuse the defined calculations instead of recreating them. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Bindings: sources include semantic models, lakehouses, eventhouses, warehouses, SQL databases, mirrored databases, shortcuts, views and materialized views. Data stays in the owning system, so the ontology is a "virtual semantic and context layer". — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Rules: business logic in natural language, linked to entities, properties and relationships, so it is not duplicated across prompts. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Ontology agent: generates definitions and bindings from connected sources, answers questions, and proposes changes. "Changes follow a proposal-first model so users can review them before applying them." — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Governance:
  - Named versions are created manually and record date, time, creator, name and description. Restoring a version replaces the current definition.
  - The ontology can import RDF, Turtle and OWL into an empty item and export RDF or Turtle. Import reports flag "preserved, automatically adjusted, and unsupported elements".
  - Access respects OneLake security and source-enforced RLS, OLS and CLS.
  — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Foundry IQ can use a Fabric ontology as a knowledge source (public preview, June 2026). These calls run synchronously, subject to the tool-call timeout. — [M365 message AZ563416](https://mc.merill.net/message/AZ563416), [Microsoft Learn Foundry Fabric IQ tool](https://learn.microsoft.com/en-my/Azure/foundry/agents/how-to/tools/fabric-iq)
- CLI authoring constraint: properties with the same name on different entity types must share a valueType. — [Fabric IQ ontology authoring CLI skill](https://mcpservers.org/agent-skills/microsoft/skills-for-fabric/fabriciq-ontology-authoring-cli)

**Databricks (Genie Ontology / Unity Catalog), mostly from secondary sources**
- Genie Ontology reportedly draws on two inputs: governed definitions in Unity Catalog, and knowledge snippets Genie infers from tables, dashboards, queries and usage. It was reportedly announced at Data + AI Summit (June 2026) and is in Public Preview. Unity Catalog permissions gate each snippet, and citation icons show which sources were used. — [Kanerika (secondary)](https://kanerika.com/blogs/databricks-genie-ontology/), [besthub (secondary)](https://www.besthub.dev/articles/databricks-genie-ontology-mining-business-context-from-sql-and-usage-patterns-cc7038d77ec0), [Atlan [COMPETITOR-adjacent]](https://atlan.com/know/ai-agent/databricks/unity-catalog-metrics/)
- Metric views define measures and dimensions once in Unity Catalog. "Unity Catalog Metrics" (Data + AI Summit 2026) reportedly adds multi-fact relationships, level-of-detail calculations and parameterized metrics, and is in public preview. — [Atlan](https://atlan.com/know/ai-agent/semantic-layer/unity-catalog-semantic-layer/)
- The official URL `docs.databricks.com/aws/en/genie/ontology` returned 404, so the claims above are unverified against primary docs.

**Snowflake**
- Semantic views are a schema-level object that stores semantic model information natively, replacing the Cortex Analyst YAML file in a stage. [VENDOR] — [Snowflake engineering blog](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/)
- Cortex Analyst will not join tables unless the semantic view explicitly defines the relationship. Many-to-many relationships are not directly supported. [VENDOR] — [Snowflake best-practices guide](https://www.snowflake.com/en/developers/guides/best-practices-semantic-views-cortex-analyst/)
- Snowsight's Semantic View Autopilot suggests definitions from query history. A third party warns that with several tables, Cortex likely did not add any relationships. — [Snowflake docs, Autopilot](https://docs.snowflake.com/user-guide/views-semantic/ui), [The Data School (secondary)](https://thedataschool.co.uk/jules-claeys/cortex-1-0-1-semantic-views/)
- I found no Snowflake product branded "ontology".

**Timbr.ai [VENDOR]**
- Timbr is an ontology-based semantic layer. Its FAQ says it "fully complies with OWL DL" and that its SQL rewrite engine acts as an inference engine. It is a virtual SQL knowledge graph over existing databases. — [Timbr FAQ](https://timbr.ai/timbr-faqs/), [Timbr docs intro](https://docs.timbr.ai/doc/docs/getting-started/intro-timbr)
- Modelling: multiple inheritance and transitive IS-A reasoning. Relationships map to OWL object properties, appear as columns, and are "created by SQL foreign keys". Agents connect via JDBC/ODBC, REST, a Data Agent, or an MCP server (Copilot Studio). — [Timbr FAQ](https://timbr.ai/timbr-faqs/), [Atlan on Timbr](https://atlan.com/know/ai-agent/semantic-layer/timbr-semantic-layer/)

**Stardog [VENDOR]**
- Full W3C stack (OWL, RDF, SPARQL, SHACL), virtual graphs (federated, no ETL), and the Voicebox LLM agent. Stardog claims answers come from the knowledge graph, which it says removes hallucination. [COMPETITOR] Atlan disputes this, saying Stardog's own docs exempt two Voicebox agents. — [Stardog Voicebox FAQ](https://www.stardog.com/blog/stardog-voicebox-faq-how-llm-generative-ai-and-knowledge-graphs-are-the-future-of-data-management/), [Atlan vs Stardog](https://atlan.com/know/ai-agent/knowledge-graph/stardog-vs-atlan/)
- An AWS blog (July 2026) shows Stardog as the semantic layer for Bedrock AgentCore agents across Aurora and Redshift. — [aws-news summary](https://aws-news.com/article/2026-07-10-build-a-semantic-layer-for-agentic-ai-on-aws-with-stardog-and-amazon-bedrock-agentcore)

**data.world (now ServiceNow)**
- ServiceNow announced the acquisition of data.world in May 2025. The knowledge-graph-based catalog was the main asset. — [TechCrunch 2025-05-07](https://techcrunch.com/2025/05/07/servicenow-acquires-data-world-two-months-after-acquiring-moveworks), [The New Stack](https://thenewstack.io/servicenow-acquires-data-world-to-expand-its-ai-data-strategy/)
- Its benchmarks are the most-cited evidence that ontologies help LLMs (see Q7). [VENDOR]

**TopQuadrant / TopBraid EDG, Google**
- The searches returned nothing usable on TopBraid EDG's 2025-2026 agent features or on a Google "ontology" product (Dataplex, Spanner Graph, Looker). These are gaps.

**NVIDIA auto-ontology (open source, Apache-2.0) [VENDOR]**
- Pipeline (README):
  - **Discover**: generate ontologies from metadata, connect existing ontologies and semantic models, build knowledge graphs.
  - **Ground**: business meaning for metrics, entities and relationships, including resolving inconsistent definitions.
  - **Validate**: check generated queries against certified definitions and lineage, and "return provenance with every answer".
  - **Expose**: serve context via MCP, CLI and API.
  - **Learn**: feed certified corrections and usage back into the ontology.
  — [README](https://github.com/NVIDIA/auto-ontology)
- Sources: Databricks, Postgres, Snowflake and DuckDB. Stack: Postgres/pgvector, a Next.js web UI, Docker Compose or Helm. Credentials added in the UI are stored in plaintext in Postgres unless Vault is configured. The project does not accept external contributions. — [README](https://github.com/NVIDIA/auto-ontology)
- MCP tools (all read-only): `ask_question` (answer plus SQL plus rows), `check_answerable`, `check_readiness`, `search_terms`, `get_term`, `get_term_columns`, `get_term_sql_attributes`, `get_sql_attribute` and `describe_table`. — [docs/mcp.md](https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/docs/mcp.md)
- Design split: the MCP server is read-only, and all writes go through the Next.js `/api` surface.
  - The model is built from glossary **terms** mapped to physical columns, plus **SQL attributes** (named expressions) and semantic relationships.
  - Modelling references cover concepts, mappings, relationships, measures, units, grain and policies.
  - The lifecycle is install/connect/readiness, then inspect/model, then staged apply and readback, then query validation, then governed publication (apply, verify, certify, publish, roll back).
  — [AGENTS.md](https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/AGENTS.md)
- The README gives no accuracy numbers. It points to BIRD text-to-SQL evaluation in a separate repo. — [README](https://github.com/NVIDIA/auto-ontology)

### Inferences
- Patterns that recur across vendors and that Strata should keep or add:
  1. A virtual ontology with bindings to sources (Microsoft, Timbr, Stardog, Strata).
  2. Metrics owned by the semantic layer and referenced, not copied, from the ontology (Microsoft).
  3. Explicit, allowed join relationships, never inferred at query time (Snowflake refuses to join without them).
  4. Proposal-first or certified changes (Microsoft proposals; NVIDIA certify/publish/rollback).
  5. Read-only agent tools kept separate from write paths (NVIDIA). Actions require confirmation (Palantir).
  6. Natural-language rules attached to entities (Microsoft).
  7. Named versions (Microsoft).
- Strata's "derived" vs "measured" link labels have no direct equivalent in the docs I read. Microsoft and Snowflake suggest relationships but do not show a per-link provenance badge. This looks like a differentiator worth keeping.
- Strata's three-letter verbs are close to NVIDIA's Ground/Validate/Learn cycle. NVIDIA validates SQL against certified definitions, which supports a "validate SQL against allowed joins" feature.

### Gaps
- Primary Databricks Genie Ontology docs could not be reached (404).
- No 2025-2026 information was found on TopQuadrant or on a Google ontology offering.
- NVIDIA's key and relationship inference algorithm is not documented in the README or AGENTS.md. It would need a source-code read.

## Q3. Open-source repos

### Takeaway
The mature open stack is rdflib (Python RDF), Ontop (virtual KGs over SQL), LinkML (YAML schema language that compiles to OWL, JSON Schema, SQL and more), Protégé (desktop editor), and RML tools (Morph-KGC, RMLMapper). NVIDIA auto-ontology is the only agent-native one and is very active. All are actively maintained as of October/November 2026.

### Cited Findings (GitHub API, fetched 2026-11-03)
| Repo | Stars | Licence | Last push | Archived | What it does |
|---|---|---|---|---|---|
| NVIDIA/auto-ontology | 2,267 | Apache-2.0 | 2026-11-03 | no | Agent context layer: Discover/Ground/Validate/Expose/Learn, MCP |
| RDFLib/rdflib | 2,546 | BSD-3-Clause | 2026-11-02 | no | Python RDF graphs, SPARQL, Turtle/JSON-LD I/O |
| protegeproject/protege | 1,627 | NOASSERTION (BSD-2 per project, standard reference) | 2026-10-01 | no | Desktop OWL editor with reasoners (HermiT etc.) |
| monarch-initiative/ontogpt | 1,085 | BSD-3-Clause | 2026-09-10 | no | LLM extraction into LinkML schemas (SPIRES method) |
| ontop/ontop | 1,009 | Apache-2.0 | 2026-10-15 | no | Virtual knowledge graphs / OBDA: SPARQL rewritten to SQL via R2RML mappings |
| linkml/linkml | 682 | Apache-2.0 | 2026-11-03 | no | YAML modelling language compiling to OWL, SHACL, JSON Schema, SQL DDL, Pydantic |
| morph-kgc/morph-kgc | 300 | Apache-2.0 | 2026-10-15 | no | R2RML/RML materialization in Python |
| RMLio/rmlmapper-java | 205 | MIT | 2026-02-17 | no | Reference RML processor |
| schemaorg/schemaorg | 6,297 | Apache-2.0 | 2026-11-02 | no | Shared web vocabulary (Person, Organization, Product, Order...) |
- Source for the table: GitHub REST API `api.github.com/repos/{owner}/{repo}` — e.g. [NVIDIA/auto-ontology](https://github.com/NVIDIA/auto-ontology), [rdflib](https://github.com/RDFLib/rdflib), [protege](https://github.com/protegeproject/protege), [ontogpt](https://github.com/monarch-initiative/ontogpt), [ontop](https://github.com/ontop/ontop), [linkml](https://github.com/linkml/linkml), [morph-kgc](https://github.com/morph-kgc/morph-kgc), [rmlmapper-java](https://github.com/RMLio/rmlmapper-java), [schemaorg](https://github.com/schemaorg/schemaorg)
- owlready2: the latest PyPI version is 0.51. The PyPI metadata licence field is empty (the project is LGPL per its docs; standard reference, not re-verified). It is hosted outside GitHub. Owlready2 loads OWL ontologies as Python objects and runs the HermiT/Pellet reasoners. — [PyPI owlready2](https://pypi.org/project/owlready2/)
- RIGOR's evaluation used Protégé for OWL 2 DL syntax checks, HermiT for consistency and OOPS! for pitfalls. That is the de facto open quality toolchain for generated ontologies. — [RIGOR arXiv 2506.01232](https://arxiv.org/html/2506.01232v1)

### Inferences
- Lessons for Strata:
  - **LinkML**: a single YAML source of truth that emits OWL, SHACL, JSON Schema and SQL. This argues for Strata storing its ontology in one neutral format and exporting RDF/Turtle (as Microsoft does) instead of building an RDF engine.
  - **Ontop**: the reference for "ontology as mappings over SQL", i.e. the virtual KG Strata already approximates.
  - **rdflib**: a cheap way to add Turtle/OWL export.
  - **OOPS!/HermiT**: ready-made checks for an automatic ontology quality score.
  - **OntoGPT/SPIRES**: shows LLMs filling a fixed schema (constrained extraction) instead of inventing one.
  - **schema.org**: a ready vocabulary for naming common entity types (Person, Organization, Order).
- NVIDIA's repo does not accept outside contributions and stores credentials in plaintext by default. Treat it as a pattern source, not a dependency.

### Gaps
- Protégé's licence shows as NOASSERTION in the GitHub API. Confirm on the repo.
- The owlready2 licence was not verified this session.
- Commit cadence beyond the last-push date was not measured.

## Q4. Research on automatic ontology generation from relational schemas

### Takeaway
On the 2025-2026 evidence, **simple rule-based mapping (direct mapping or schema rules) still beats LLM-based ontology learning from relational databases**, according to the Burr benchmark (SIGMOD). LLM pipelines such as RIGOR improve on naive LLM prompting but are evaluated mostly by LLM judges on two medical databases. This supports Strata's deterministic-first approach, with LLMs used only for naming, descriptions and suggested enrichments under human review.

### Cited Findings
- **Burr** (Laskowski, Hladik, Portisch, Panse, Naumann; HPI) is a benchmark for ontology learning from relational DBs. It has 54 scenarios from real-world DB-ontology mappings (including industry data), a micro-benchmark, and a new mapping-based metric. The authors report "the current strengths of simple rule-based approaches compared to LLM-based systems, while also pointing to research potential for LLMs". It was accepted at SIGMOD 2026; one repository lists it as PACMMOD 3(6), Article 305, Dec 2025, DOI 10.1145/3769770, so the year is inconsistent. — [HPI announcement](https://hpi.de/naumann/news/paper-accepted-at-sigmod-2026.html), [dbscholar entry](https://rmarcus.info/dbscholar/papers/h709f0bd7ecb74f00), [Uni Augsburg repository PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/132308/132308.pdf)
- **RIGOR** (arXiv 2506.01232, June 2025, under review; Nayyeri et al.):
  - Method: iterative retrieval-augmented generation of OWL. It processes the schema table by table following FKs, retrieves the table schema, documentation and parts of the growing core ontology, and has an LLM write "delta ontology" fragments that a judge-LLM refines before merging. — [arXiv abs](https://arxiv.org/abs/2506.01232v1)
  - Data: a liver-cancer registry (18 tables, 350 columns, 15 FKs) and the PhysioNet ICU database (32 tables, 559 columns, 30 FKs).
  - Competency-question score (0-5, LLM judge): baseline 1.4-1.6, non-iterative 3.3-3.7, RIGOR 4.2-4.6 across Llama-3.1-70B, Mistral-Small-3.1-24B and DeepSeek-67B.
  - All RIGOR outputs passed OWL 2 DL syntax and HermiT consistency checks.
  - Semantic coverage on one delta ontology was 72.4% (21 of 29 classes matched to columns).
  — [arXiv HTML](https://arxiv.org/html/2506.01232v1)
  - Weaknesses:
    - The judge is Llama-3.1-8B, from the same family as one generator.
    - Only two databases were tested.
    - Human review is not quantified, and the "minimal human effort" claim is not measured.
    - Tables 2 and 6/7 give slightly different scores (4.5 vs 4.4).
    - Baseline outputs were often invalid Turtle or returned SQL instead.
    - Frequent OOPS! pitfalls: P19 "multiple domains/ranges" (up to 54 cases, DeepSeek on ICU) and P34 "untyped class" (up to 21).
    - Hallucination was not measured directly. The authors only argue that selective retrieval reduces it.
    — [arXiv HTML](https://arxiv.org/html/2506.01232v1)
  - Direct Mapping and R2RML appear only in RIGOR's related work. They were not run as baselines. — [arXiv HTML](https://arxiv.org/html/2506.01232v1)
- A Nov 2025 comparison of ontology-learning and KG-construction approaches for RAG (arXiv 2511.05991) adapted RIGOR to take raw DDL with PK/FK constraints and drop table-level documentation. — [arXiv 2511.05991](https://arxiv.org/pdf/2511.05991)
- data.world "Benchmark II" (June 2024, older): an Ontology-based Query Check (OBQC) plus LLM Repair raised accuracy to 4.2x the baseline without a KG. [VENDOR] — [data.world blog](https://data.world/blog/genai-benchmark-ii-increased-llm-accuracy-with-ontology-based-query-checks-and-llm-repair)
- ERBench (2024, older) uses FK constraints to build verifiable hallucination questions. It is a template for testing whether an LLM invents relationships. — [arXiv 2403.05266](https://arxiv.org/html/2403.05266v1)
- SchemaAgent (arXiv 2503.23886, March 2025) is multi-agent relational schema generation with error detection and correction, plus the RSchema benchmark. It is adjacent (schema design, not ontology). — [arXiv 2503.23886](https://export.arxiv.org/abs/2503.23886)

### Inferences
- Known LLM failure modes when generating ontologies from schemas:
  - Invalid syntax.
  - Multiple domains or ranges on one property (P19).
  - Untyped classes.
  - Classes with no backing column (about 28% unmatched in RIGOR's coverage test).
  - Output in the wrong artefact (SQL instead of OWL).
  These argue for a deterministic skeleton (PK becomes identity, FK becomes link) with LLM output limited to labels, descriptions, synonyms and candidate links, always marked "derived" until confirmed.
- Burr's mapping-based metric could become a Strata regression test if its dataset is public (not verified).

### Gaps
- Burr's numeric results and the exact systems compared were not read; only the abstract-level claim is cited.
- No 2025-2026 paper was found that measures LLM foreign-key inference precision and recall on undeclared FKs. This matters for CSV sources with no declared keys.
- Classic undeclared-FK and inclusion-dependency discovery work (profiling-based) was not covered this session.

## Q5. Standards: which matter in practice

### Takeaway
For agent products, standards matter mainly at the edges: RDF/Turtle (and OWL) export and import for interoperability, SKOS-style glossaries (prefLabel/altLabel/synonyms), and SHACL-style constraints for validation. Full OWL reasoning and R2RML authoring are used mostly by RDF-native vendors and academia. Microsoft supports RDF/Turtle/OWL import and export but models natively in its own format.

### Cited Findings
- Microsoft Fabric IQ imports RDF, Turtle and OWL and exports RDF and Turtle, with a report of adjusted or unsupported elements. This shows a large vendor treating OWL/RDF as an exchange format, not the internal model. [VENDOR] — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Stardog advertises the full stack: OWL, RDF, SPARQL, SHACL. Timbr claims OWL DL compliance over SQL. [VENDOR] — [Stardog product page](https://www.stardog.com/product/), [Timbr FAQ](https://timbr.ai/timbr-faqs/)
- W3C **Direct Mapping** (Recommendation, Sept 2012): each table becomes a class, each row an IRI built from the PK (blank node if there is no PK), each column a data property, and each FK an object property. This is essentially Strata's rule set. (standard reference) — [W3C RDB Direct Mapping](https://www.w3.org/TR/rdb-direct-mapping/)
- W3C **R2RML** (Recommendation, Sept 2012): a customizable mapping language from relational data to RDF. It is used by Ontop and Morph-KGC. RML generalizes it to CSV and JSON. (standard reference) — [W3C R2RML](https://www.w3.org/TR/r2rml/), [Ontop repo](https://github.com/ontop/ontop)
- **SHACL** (Recommendation, 2017) is shape constraints for validating graphs, such as cardinality, datatype and required properties. (standard reference) — [W3C SHACL](https://www.w3.org/TR/shacl/)
- **SKOS** (Recommendation, 2009) is for thesauri and glossaries: prefLabel, altLabel, broader and narrower. (standard reference) — [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/)
- **OWL 2** (Recommendation, 2012) and **RDF 1.1 / RDFS** (2014) are the class/property semantics and the data model. (standard reference) — [W3C OWL 2 Overview](https://www.w3.org/TR/owl2-overview/), [W3C RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/), [W3C RDF Schema](https://www.w3.org/TR/rdf-schema/)
- LinkML compiles one schema to OWL, SHACL, JSON Schema and SQL DDL, bridging standards without hand-writing RDF. — [linkml repo](https://github.com/linkml/linkml)

### Inferences
- Practical priority for Strata:
  1. Keep the internal model native, and align it with W3C Direct Mapping semantics (and cite them as precedent).
  2. Add Turtle/OWL export (rdflib), which costs little and answers buyers' "standards?" question.
  3. Use SKOS concepts for the glossary and synonyms.
  4. Express validation rules as SHACL-like shapes, even if they are only exported.
  5. Skip OWL reasoning and SPARQL endpoints unless customers ask for them.
- Note that Direct Mapping is a formal W3C standard, so Strata's "derived from schema" ontology is defensible as standards-aligned.

### Gaps
- No adoption statistics were found showing how many agent products use SHACL or OWL in production.

## Q6. Best practices and failure modes

### Takeaway
Best practice in 2025-2026:
- Generate a draft automatically.
- Keep metrics owned by the semantic layer.
- Require explicit relationships for joins.
- Route all changes through review (proposal-first or certification).
- Keep named versions.
- Attach provenance to every answer.

The main failure modes are wrong or missing joins, stale models, duplicated definitions, and over-modelling.

### Cited Findings
- Identity: Microsoft entity types carry "identifiers" but now also allow "keyless entity types". Palantir objects have primary keys (standard reference; the core-concepts page does not define PK). Direct Mapping uses blank nodes for tables without a PK. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview), [W3C Direct Mapping](https://www.w3.org/TR/rdb-direct-mapping/)
- Relationships:
  - Snowflake will not join tables without explicit relationships, and many-to-many is not directly supported. [VENDOR] — [Snowflake guide](https://www.snowflake.com/en/developers/guides/best-practices-semantic-views-cortex-analyst/)
  - Clear relationships prevent "incorrect joins or assumptions". — [ClearPeaks](https://www.clearpeaks.com/building-an-ai-ready-semantic-layer-with-snowflake-semantic-views/)
  - Microsoft supports "relationships without dedicated join tables". — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Relationship inference from usage: Snowflake Autopilot uses query history, and Databricks Genie mines queries and dashboards (secondary). A third party says autopilot often adds no relationships on multi-table views. — [Snowflake Autopilot docs](https://docs.snowflake.com/user-guide/views-semantic/ui), [The Data School](https://thedataschool.co.uk/jules-claeys/cortex-1-0-1-semantic-views/), [Kanerika](https://kanerika.com/blogs/databricks-genie-ontology/)
- Naming: properties with the same name on different entity types must share a type in Fabric. Microsoft uses namespaces to scope names, and shared properties and inheritance to avoid duplicates. — [Fabric CLI skill](https://mcpservers.org/agent-skills/microsoft/skills-for-fabric/fabriciq-ontology-authoring-cli), [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Human review and certification:
  - Microsoft's ontology agent is "proposal-first". — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
  - NVIDIA uses staged apply, readback, certify, publish and rollback, and learns from "certified corrections". — [AGENTS.md](https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/AGENTS.md), [README](https://github.com/NVIDIA/auto-ontology)
  - Palantir actions can require user confirmation. — [Palantir tools](https://palantir.com/docs/foundry/agent-studio/tools)
- Versioning: Microsoft keeps manual named versions with creator, timestamp and description, and restore replaces the whole definition. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Provenance: NVIDIA's Validate step returns "provenance with every answer". Databricks Genie shows citation icons per knowledge source (secondary). — [NVIDIA README](https://github.com/NVIDIA/auto-ontology), [Kanerika](https://kanerika.com/blogs/databricks-genie-ontology/)
- Single ownership of calculations: Microsoft metrics keep the source model as owner of the DAX expression, so definitions do not drift. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- Failure modes:
  - Over-modelling and modelling errors in generated ontologies (multiple domains or ranges, untyped classes, classes with no data) are documented in RIGOR. — [RIGOR](https://arxiv.org/html/2506.01232v1)
  - Stale models: Microsoft's migration doc warns that copying to the new experience requires reconnecting agents and dashboards and recreating rules manually. This is a concrete example of ontology drift and migration cost. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
  - Security leaks: Microsoft enforces source RLS, OLS and CLS. NVIDIA stores credentials in plaintext unless Vault is used. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview), [NVIDIA README](https://github.com/NVIDIA/auto-ontology)

### Inferences
- Strata's derived/measured labels map onto the industry's proposal-to-certified flow. Suggested states: derived (schema rule), suggested (LLM or usage), measured (verified by data profiling, e.g. FK inclusion checked on rows), and certified (human). Only certified or measured links should be allowed joins for agents by default, as in Snowflake's strictness.
- Over-modelling risk for Strata: turning every table (including staging, log and junction tables) into an entity type. Microsoft's keyless entities and "relationships without join tables" suggest collapsing junction tables into many-to-many links.

### Gaps
- No quantitative study was found on how fast enterprise ontologies go stale or on wrong-join rates in production agents.

## Q7. What makes an ontology useful to an AI agent

### Takeaway
Agents need entity descriptions and synonyms (to map words to tables), allowed join paths with cardinality (so they do not invent joins), governed metrics (so they do not reinvent formulas), natural-language rules, permission-aware access, typed read tools, and separately governed actions. Vendor benchmarks claim large accuracy gains from an ontology or knowledge graph. That evidence is vendor-produced and dates from 2023-2024.

### Cited Findings
- Palantir exposes the ontology to agents as typed tools:
  - an object query tool (filter, aggregate, traverse links, with a limited property set for token efficiency);
  - an action tool for edits, optionally with confirmation;
  - deterministic application variables that keep the LLM from generating inputs.
  [VENDOR] — [Palantir tools](https://palantir.com/docs/foundry/agent-studio/tools), [Palantir application state](https://palantir.com/docs/foundry/agent-studio/application-state)
- Microsoft says agents grounded in the ontology work with "governed entities, relationships, definitions, rules, metrics, and source mappings" instead of "raw schemas or prompts". [VENDOR] — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
- NVIDIA's agent tool surface: glossary search, term-to-column mapping, SQL attributes, table description, an answerability pre-check, a readiness check, and question answering that returns SQL plus rows. All are read-only. [VENDOR] — [docs/mcp.md](https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/docs/mcp.md)
- data.world benchmark (Nov 2023, older): 43 insurance questions over the OMG P&C schema. A knowledge-graph representation improved LLM accuracy about 3x. A secondary summary reports 16% (GPT-4 zero-shot SQL) vs 54% (over KG), which I did not confirm in the primary page. [VENDOR] — [data.world blog](https://data.world/blog/generative-ai-benchmark-increasing-the-accuracy-of-llms-in-the-enterprise-with-a-knowledge-graph), [BigDATAwire](https://www.bigdatawire.com/2023/12/13/new-data-world-report-finds-a-technique-for-making-llms-3x-more-accurate-in-answering-business-questions)
- Follow-up (June 2024): ontology-based query checks plus LLM repair gave 4.2x. [VENDOR] — [data.world Benchmark II](https://data.world/blog/genai-benchmark-ii-increased-llm-accuracy-with-ontology-based-query-checks-and-llm-repair)
- Snowflake requires relationships before it will join. The ontology's relationship list is effectively the agent's join allow-list. [VENDOR] — [Snowflake guide](https://www.snowflake.com/en/developers/guides/best-practices-semantic-views-cortex-analyst/)

### Inferences
- An agent-useful ontology for Strata would expose, per entity type:
  - a plain-language description, synonyms and an example value;
  - identity (key) and grain;
  - allowed links with cardinality and provenance label (derived, measured, certified);
  - time columns;
  - attached certified metrics (pointer to the semantic layer);
  - rules;
  - permissions.
- Tools should come in two classes: read and describe tools (like NVIDIA's MCP set) and validation tools (check SQL joins against allowed links, as in data.world's OBQC). Actions should stay out of scope unless they are behind confirmation.
- Strata could drop or deprioritize OWL reasoning, a full SPARQL engine, and automatic materialization of an instance graph. Microsoft made graph materialization opt-in, which shows the instance graph is not essential for most agent questions.

### Gaps
- No independent (non-vendor) 2025-2026 benchmark was found that quantifies ontology-grounded agent accuracy against schema-only prompting on enterprise data.
- Palantir's "Ontology augmented generation" docs were not read.
