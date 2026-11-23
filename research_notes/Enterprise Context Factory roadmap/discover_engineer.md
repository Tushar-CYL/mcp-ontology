# Discover and Engineer: automated context discovery and canonical modeling (state as of Nov 2026)

Scope: how vendors and startups find business context automatically (from tables, query history, BI files, documents, MDM) and turn it into a canonical model or "context graph". Written for the Strata team. Strata already builds an AI ontology from tables, checks it against data, and builds a virtual KG.

Research budget note: about 17 searches and fetches. Snowflake, Databricks, Fabric IQ, Atlan and Foundation Capital were checked against primary pages. Palantir, Collibra, Alation, data.world and the hierarchy questions got thin results and are marked as gaps. Most figures are vendor-reported unless the note says otherwise.

## 1. How the major platforms discover context, and which sources they mine

### Takeaway
The leaders have converged on one pattern. They bootstrap a draft model from schema plus usage signals: query history, BI files (DAX, Tableau calculated fields), dashboards and dbt runs. They score or rank the candidates by how reliable the source is, then send everything through human review or certification. Documents and wikis (Confluence, Drive, Jira) are mostly indexed for retrieval. They are rarely mined into structured rules. Only Databricks (Genie Ontology) and Atlan go clearly beyond schema plus BI.

### Cited Findings

**Snowflake: Semantic View Autopilot (SVA). GA Feb 3, 2026, per Snowflake's blog as reported in search results.**
- Wizard inputs: name and description, one or more tables or views, chosen columns, and optional context. The context can be example SQL with natural-language questions, a 2-column CSV of question/SQL pairs, a Tableau file, a Power BI file, or YAML. Optional toggles add sample values and AI-generated table and column descriptions. — [Snowflake docs: Semantic View Autopilot](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
- Relationships are inferred from example SQL and from query history. Primary and unique keys come from metadata or distinct-value counts, which set cardinality and relationship type. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
- Verified queries: valid example queries become verified queries. Historical queries that fit the chosen tables and columns are offered as suggestions. Only the query history visible to the creating role is used. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
- Tableau import (TWB/TWBX/TDS/TDSX) pulls tables, columns, relationships, calculated fields, parameters, filters and Custom SQL. Custom SQL is parsed into a regular view and needs CREATE VIEW. Power BI import (.pbit/.pbix) pulls DAX measures, relationships and column definitions. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
- Guidance on size: fewer than 10 tables or views for a first semantic view (a recommendation, not a hard limit) and no more than 50 columns. Suggestions arrive several minutes after creation. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
- Snowflake blog claims, as summarized in search results (the blog page returned 403 to direct fetch): SVA proposes metrics and filters learned from query history and trusted BI assets. It weights signals by how reliable the source is, so a curated Tableau workbook ranks above a one-off ad-hoc query, and it says frequency alone is a poor proxy for correctness. It uses clustering over query patterns and natural-language questions to find "consensus business logic". — [Snowflake blog: SVA](https://www.snowflake.com/en/blog/semantic-view-autopilot/); [Snowflake docs UI page](https://docs.snowflake.com/user-guide/views-semantic/ui)
- Third-party view: every Autopilot output needs human review before production. — [datalakehousehub.com](https://datalakehousehub.com/blog/snowflake-semantic-view-autopilot-business-logic)

**Databricks: Genie Ontology, knowledge store, AI comments. Docs page last updated Nov 16, 2026.**
- Genie Ontology is described as a "unified context layer that gives AI agents a business-aware map of your organization". It is used by Genie One and Genie Code, and external agents reach it through the Genie One MCP server under Unity Catalog permissions. — [Databricks docs: Genie Ontology](https://docs.databricks.com/en/genie/genie-ontology)
- It holds two kinds of knowledge:
  - **Modeled knowledge** is defined and certified: metric views, domains, Pages and certification. Genie treats it as more authoritative.
  - **Learned knowledge** is "snippets" that Genie extracts and maintains automatically.
  — [Databricks docs](https://docs.databricks.com/en/genie/genie-ontology)
- Snippets are learned from metric views, dashboards, SQL queries (including dbt and other external-tool runs that land in query history), Genie Agents, and external knowledge sources (Beta) such as Power BI. A snippet can hold a metric definition, guidance on the authoritative source, or a business rule. Each snippet gets an **authority score** from its origin, how often it is used and how fresh it is. The page gives no numeric ranges. — [Databricks docs](https://docs.databricks.com/en/genie/genie-ontology)
- Conflicts: modeled knowledge, certified assets and curated Genie Agents win. If Genie cannot resolve a conflict, it may ask the user to clarify. Snippets are filtered by Unity Catalog permissions, except snippets from external sources, which all users in the account can see. — [Databricks docs](https://docs.databricks.com/en/genie/genie-ontology)
- Unstructured sources: Genie Search indexes Google Drive, Jira and Confluence, for Genie One only. Workday can be connected as a people source. — [Databricks docs](https://docs.databricks.com/en/genie/genie-ontology)
- The per-agent knowledge store holds table and column descriptions, synonyms, join relationships, SQL expressions and prompt matching. Edits there do not change Unity Catalog metadata. "Knowledge mining" uses UC lineage and query history to suggest instructions or recurring patterns. — [Databricks Genie docs (Azure)](https://learn.microsoft.com/en/azure/databricks/genie); [Databricks Genie concepts](https://docs.databricks.com/aws/en/genie/concepts)
- Catalog Explorer drafts an AI-generated comment for each table or column, and Databricks recommends a person check it for inaccuracies. On views and metric views, only the owner can generate and save comments. A Genie space that contains metric views cannot also contain other tables. — [Databricks: Generate metadata with AI comments](https://docs.databricks.com/aws/en/getting-started/starter-journey/genie-ontology/metadata-generation); [Databricks Genie set-up](https://docs.databricks.com/aws/genie/set-up)
- Naming: the product was renamed from "Genie Space" to "Genie Agent". One third-party page dates this to July 2026, which could not be verified. — [Atlan guide on Genie](https://atlan.com/know/ai-agent/databricks/databricks-genie-context-requirements/)

**Microsoft Fabric IQ (ontology). Public preview at Ignite 2025. GA at Build 2026 per one third-party source, not verified.**
- A "Generate Ontology" button on a published semantic model turns tables into entity types, columns into properties, and relationships into relationship types. Microsoft calls this a starting point: "You still need to review names, keys, and relationship direction." — [Microsoft Learn: Decide when to extend a semantic model with Fabric IQ (Aug 2026)](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology)
- Data bindings, which let the ontology answer from live data, need Direct Lake mode with inbound public access on the lakehouse. Import and DirectQuery give definitions only. — [Microsoft Learn](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology); [Fabric IQ tutorial](https://learn.microsoft.com/en-us/Fabric/iq/ontology/tutorial-1-create-ontology)
- Design rule from Microsoft: an entity goes into the ontology only when its definition is stable, it has a clear owner, and other teams need it. Measures, report filters and calculated columns stay in the semantic model. — [Microsoft Learn](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology)
- Third-party write-ups say generation takes entity types from dimension tables and relationships from foreign keys, that it fails silently if tables are hidden or relationships are missing, and that it does not work in "My workspace". — [team400.ai](https://team400.ai/blog/2026-05-fabric-iq-ontology-from-semantic-model); [kanerika](https://kanerika.com/blogs/microsoft-fabric-iq/)
- Fabric IQ mines no query logs or documents. The only input is an existing, curated semantic model. — inferred from the [Learn description](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology)

**Atlan: Context Engineering Studio (launched at Activate, Apr 29, 2026) and Context Repos.**
- Bootstraps from Snowflake, Confluence, Looker, dbt, Slack, Tableau, BigQuery and Notion: systems of record, SQL queries, BI dashboards and chat threads. It drafts a semantic layer that domain experts then refine. — [Atlan: Context Engineering Studio](https://atlan.com/context-engineering-studio.md)
- Evals come from the same usage signals. Dashboards and SQL history are turned into "hundreds" of test questions with expected answers. When a test fails, the Studio names the missing piece (a relationship, synonym or default filter) and suggests a context fix for a human to verify. Evals persist across versions. — [Atlan](https://atlan.com/context-engineering-studio.md)
- **Context Repos** are versioned, bounded, portable YAML with git-like history, branching, A/B tests, staged rollout and rollback. Conflicting definitions, for example two teams' "revenue", are kept in separate domain repos rather than forced into one universal ontology. Production traces (question, retrieved context, answer) and user corrections become suggested updates, and confirmed answers become regression tests. Delivery is through MCP. — [Atlan](https://atlan.com/context-engineering-studio.md)
- Vendor claim: AI teams at Workday and Fox saw "5x improvement in AI accuracy". No method was published. — [Atlan About](https://atlan.com/about.md)
- Later in 2026: Context Agents at Snowflake Summit 2026, then Atlan Trident, an open "AI Registry" spec, and an open-source Forward Deployed Playbook at Context Conference (Oct 28, 2026). — [Atlan Summit 2026](https://atlan.com/snowflake-summit-2026-announcements/); [Context Conference recap](https://atlan.com/know/context-conference-2026-recap/)
- SI offer: phData sells a 6–8 week "Context Layer Pilot" for one domain, which is a signal of how much services work these projects need. — [phData](https://www.phdata.io/blog/why-enterprise-ai-fails-the-context-gap/)

**Informatica CLAIRE**
- CLAIRE GPT in MDM generates glossary descriptions and aliases. The catalog (CDGC) links technical columns to Business Glossary terms using synonyms and abbreviations. Its example maps a cryptic column name to a business name. — [Informatica TechTuesdays slides: AI for the Catalog](https://success.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/AI%20for%20the%20Catalog,%20Catalog%20for%20the%20AI.pdf); [Informatica Spring 2025 release PR](https://www.informatica.com/about-us/news/news-releases/2025/04/20250402-informatica-introduces-new-ai-powered-cloud-integration-and-master-data-management-capabilities)
- CLAIRE Agents include Discovery & Exploration, Data Integration and DQ. An analyst note says the fall 2026 release made CLAIRE GPT agentic, with planning and reasoning. A2A support is planned for Fall 2026. — [Informatica CLAIRE Agents slides](https://www.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/Informatica%20CLAIRE%20Innovations%20Agentic%20CLAIRE%20GPT%20and%20CLAIRE%20Agents%20Unleashed.pdf); [SoftwareReviews](https://www.softwarereviews.com/vendor-technology-notes/informatica-introduces-ai-agents-but-does-not-become-an-agentic-ai-platform-yet)

**Palantir Foundry/AIP**
- AI proposes rather than ingests. Palantir announcements say a user can ask **Pilot** to "propose the object types, relationships, and actions" for a new workflow. **HyperAuto** creates object types and links for a list of SAP tables, per a community user rather than docs. The standard route is still manual: datasets mapped to object types through backing pipelines in Ontology Manager. AIP Analyst searches existing object types and does not generate them. — [Palantir announcements](https://palantir.com/docs/foundry/announcements/); [Palantir community: create object types with code](https://community.palantir.com/t/how-do-i-create-object-types-with-code/6676); [AIP Analyst docs](https://www.palantir.com/docs/foundry/aip-analyst)

**Glean**
- Glean's **Enterprise Graph** (Sept 2025) maps people, content, workflows and applications. It combines a company-wide knowledge graph with a **personal graph** per employee (tasks, projects, collaborators). Glean now calls itself "the trusted context and intelligence layer". — [BusinessWire Sept 2025](https://www.businesswire.com/news/home/20250925784461/en); [Glean blog](https://www.glean.com/blog)
- Gartner abstract (27 Apr 2026) names Glean the front-runner in the "enterprise context graph" race. ARR was $200M per Futurum, and $300M+ per a later Glean press release. Glean self-reports that its results are preferred about 2x over ChatGPT company knowledge and 1.6x over Claude. — [Gartner](https://www.gartner.com/en/documents/7773753); [Futurum](https://futurumgroup.com/insights/glean-doubles-arr-to-200m-can-its-knowledge-graph-beat-copilot/); [Glean press](https://glean.com/press/glean-surpasses-300m-arr-unrivaled-enterprise-context-fuels-ai-adoption); [Glean eval blog](https://www.glean.com/blog/enterprise-search-evaluation-2026)
- Glean's graph is built from documents, people and activity, not from warehouse schemas or metrics. It covers the opposite side from Snowflake and Databricks. — inferred from the above sources

### Inferences
- The table-stakes pipeline in 2026 has four steps:
  1. Schema and keys, with profiling for PK/FK.
  2. Query history mining for joins, verified queries and common filters.
  3. BI file import for measures and filters (DAX, Tableau calculated fields, LookML).
  4. Human review or certification.
  Strata has step 1 and a data check. Steps 2 and 3 are the biggest gaps that every peer covers.
- Two ideas worth copying directly:
  - Databricks' authority score (origin × usage × freshness) with modeled beating learned when they conflict.
  - Atlan's "turn SQL history and dashboards into eval questions, then fix context on failure" loop.
- Fabric IQ is the closest analogue to Strata (semantic model → ontology, plus bindings). Microsoft still ships it as "starting point, review names, keys, and direction", so a strong review UX is a real differentiator, not a cosmetic one.

### Gaps
- Collibra, Alation and data.world (ServiceNow) AI discovery features for 2025–2026 were not found in this session's searches, so nothing is claimed about them. They need a follow-up search per vendor.
- No vendor publishes accuracy for auto-generated semantic models. Snowflake, Databricks and Microsoft give none. Atlan's "5x" has no method behind it.
- Snowflake Horizon specifics (AI classification, auto-tagging) were not researched.
- Looker/LookML harvesting: Atlan lists Looker as a source, but no vendor doc on parsing LookML into a semantic model was retrieved.
- Palantir: no official doc describes fully automatic ontology generation from raw sources.

## 2. Concrete techniques: query-log mining, BI harvesting, document extraction, reconciliation; published accuracy

### Takeaway
Query-log mining for joins and metrics is the best-evidenced technique, in both academic work and products. The best recent number is 78–100% precision for LLM-adjudicated join inference on well-structured schemas. Document and policy rule extraction into canonical models is mostly marketing or retrieval. No good accuracy figures were found for it.

### Cited Findings
- **Join inference with stats plus LLM (Tursio, arXiv 2603.04176, Mar 2026):**
  - Method: statistical pruning picks primary-key candidates, then an LLM adjudicates. The same two stages detect inclusion dependencies (FK candidates). Query history refines the joins as workloads change.
  - Result: **78–100% precision** on well-structured schemas (TPC-DS, TPC-H, BIRD-Dev, production workloads). It is harder on poorly normalized schemas, but no numbers are given for that case and no recall is reported.
  — [arXiv:2603.04176 "Scalable Join Inference for Large Context Graphs"](https://arxiv.org/abs/2603.04176)
- **Automatic Metadata Extraction for Text-to-SQL (arXiv 2505.19988, May 2025):** combines database profiling, query-log analysis and LLM SQL-to-text generation to produce metadata. Evaluated on BIRD. — [arXiv:2505.19988](https://arxiv.org/abs/2505.19988)
- **TailorSQL (2025):** an NL2SQL system that uses historical query logs for workload-informed schema enhancement, log mining, fine-tuning and RAG. — [TailorSQL summary](https://newx.sg/paper/detail/7a6bd5d5-f823-11f0-b84c-00163e10baa7)
- **Semantic-layer-mediated NL2SQL (arXiv 2606.31041):** reports that the quality of the semantic layer, including join declarations, drives accuracy. The source's date looked odd, so verify before citing. — [emergentmind](https://www.emergentmind.com/papers/2606.31041)
- **TEMPLAR (2019, older):** the foundational query-log join-path inference work, reporting up to 138% top-1 accuracy improvement for NLIDBs. — [arXiv:1902.00031](https://arxiv.org/pdf/1902.00031)
- **Product mechanisms:**
  - Snowflake infers relationships from query history plus distinct-count key detection, and weights signals by source reliability with clustering for consensus logic. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
  - Databricks gives each snippet an authority score (origin, usage, freshness). — [Databricks](https://docs.databricks.com/en/genie/genie-ontology)
  - Atlan does eval-driven gap detection, naming the missing relationship, synonym or default filter. — [Atlan](https://atlan.com/context-engineering-studio.md)
- **BI harvesting:** Snowflake parses Tableau calculated fields, filters and parameters, and Power BI DAX measures and relationships, from the files themselves. Tableau Custom SQL is parsed into views. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)
- **Glossary from MDM:** Informatica generates glossary descriptions and aliases and links columns to terms by synonym and abbreviation. — [Informatica slides](https://success.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/AI%20for%20the%20Catalog,%20Catalog%20for%20the%20AI.pdf)
- **SQL parsing for lineage:** DataHub uses sqlglot for column-level lineage (pure Python, around 20 dialects at the time of their write-up) and chose it after comparing parsers. — [DataHub: Extracting column-level lineage from SQL](https://datahub.com/?p=4506); [DataHub SQL lineage](https://datahub.com/?p=11072)

### Inferences
- A cheap, high-value path for Strata:
  1. Parse warehouse or DuckDB query logs with sqlglot.
  2. Count join pairs, GROUP BY dimensions, aggregate expressions (candidate metrics) and repeated WHERE predicates (candidate default filters).
  3. Weight them by source: saved or BI queries above ad-hoc ones.
  4. Show them as "suggested from usage" next to the existing data-checked ontology.
  This lines up with Strata's "suggestions from the real data" rule.
- Strata can already check joins against the data (inclusion dependencies). Adding the Tursio-style LLM adjudication step and reporting precision on a test set would give a publishable number, which competitors do not have.
- Reconciliation in practice is precedence rules (certified > modeled > learned; curated BI > ad hoc) plus asking a human. No vendor documents an automatic merge algorithm.

### Gaps
- No published accuracy for LLM extraction of business rules or glossary terms from PDFs or policies in enterprise settings.
- No vendor documentation on LookML parsing, or on how dbt semantic models or MetricFlow get imported into these tools.
- How Snowflake's clustering works (algorithm, thresholds) is not documented.

## 3. "Context graph" vs data catalog vs knowledge graph: who uses the term

### Takeaway
"Context graph" was popularized by Foundation Capital's essay "AI's trillion-dollar opportunity: Context graphs" (Garg and Gupta). In that essay it means a record of **decision traces**: how inputs, policies, exceptions and approvals turned into action. That is not a schema or metadata graph. Atlan, Glean, Databricks ("unified context layer") and Gartner have taken up "context graph" or "context layer" to mean a governed, versioned semantic and knowledge layer for agents. That meaning sits closer to a catalog plus semantic layer plus evals.

### Cited Findings
- Foundation Capital defines a context graph as "a living record of decision traces" linked across entities (accounts, tickets, policies, approvers, agent runs) and over time, so precedent becomes searchable. It is "not the model's chain-of-thought".
  - Contrast with systems of record: those store current state, not the reasoning or the state of the world at decision time.
  - Contrast with warehouses: those get data through ETL after the fact. Agents "in the execution path" can capture context at decision time.
  - Examples named: Regie, Maximor, PlayerZero, Arize.
  — [Foundation Capital essay](https://foundationcapital.com/context-graphs-ais-trillion-dollar-opportunity/); [Ashu Garg substack](https://ashugarg.substack.com/p/ais-trillion-dollar-opportunity-context)
- Date conflict: secondary sources say the essay was published in December 2025, and FC published "Context graphs, one month in" afterwards. The fetched page's metadata showed Nov 12, 2026, which is probably an update timestamp. — [FC: one month in](https://foundationcapital.com/context-graphs-one-month-in/); [Chris Fenster critique](https://chrisfenster.substack.com/p/the-context-graph-opportunity-everyones)
- FC put money behind the thesis by backing Fulcrum, a context graph for insurance. It frames the market as the $4.6T spent on salaries and services, not software budgets. — [FC on Fulcrum](https://foundationcapital.com/ideas/building-the-context-graph-for-insurance-why-we’re-doubling-down-on-fulcrum)
- Atlan's response argues for open, federated context platforms that any agent reads and humans govern, rather than each app building its own graph. — [Atlan: context graphs are a trillion dollar opportunity, but who captures it](https://atlan.com/context-and-chaos/issue/context-graphs-are-a-trillion-dollar-opportunity-but-who-captures-it.md)
- Gupta (Apr 2026): sales context is harder to capture because the reasoning is less codified and more intuition-based. — [Ramp interview](https://ramp.com/leading-indicators/how-ai-gets-built-jaya-gupta)
- Arize treats agent traces as the raw material of a context graph. — [Arize](https://arize.com/blog/how-context-graphs-turn-agent-traces-into-durable-business-assets.md)
- The Tursio paper uses "context graph" for a schema and join graph. — [arXiv:2603.04176](https://arxiv.org/abs/2603.04176)
- Gartner uses "enterprise context graph" for Glean. — [Gartner](https://www.gartner.com/en/documents/7773753)
- Databricks says "unified context layer" (Genie Ontology). — [Databricks](https://docs.databricks.com/en/genie/genie-ontology)
- Atlan says "context layer", "context repos" and the "SDLC for context". — [Atlan](https://atlan.com/context-engineering-studio.md)
- What separates a context layer from a catalog, as Atlan positions it: versioned (git-like), tested with evals, scoped by domain, served to agents over MCP, and updated from production traces and corrections. — [Atlan](https://atlan.com/context-engineering-studio.md)

### Inferences
- The term means three different things:
  - FC: decision traces, i.e. "why" events.
  - Atlan, Databricks, Gartner: a governed semantic and knowledge layer.
  - Tursio: a schema and join graph.
  Strata should pick one meaning and define it explicitly. Its existing virtual KG plus ontology matches the second meaning. Logging each answer's question, context used, result and user confirmation would add a light first version of FC-style decision traces.
- Versioning plus evals is the concrete feature that marketing uses to set a "context layer" apart from a "catalog". Strata already has confirmed shares and drift checks, which would make this a short step.

### Gaps
- No neutral or analyst definition was found that formally separates a context graph from a knowledge graph. The distinction is mostly vendor positioning.

## 4. Business hierarchies (org, product, geography, CoA, cost centre)

### Takeaway
In 2025–2026 AI ontology and semantic products (Fabric IQ, Snowflake semantic views, Genie), no documented feature for discovering or managing hierarchies was found. Hierarchies are still modeled the classic way: level-based hierarchies (balanced), or parent-child for ragged and unbalanced structures such as cost centres and CoA. SAP has the richest native support, and its Datasphere still trails S/4HANA.

### Cited Findings
- A ragged hierarchy is one where a parent skips a level. Parent-child modeling handles it, but some engines allow only one parent-child hierarchy per dimension. — [Kyvos](https://www.kyvosinsights.com/blog/handling-ragged-and-unbalanced-hierarchies-in-kyvos/)
- Oracle: parent-child hierarchies are unbalanced by nature, which suits uneven structures. Level-based hierarchies suit fixed levels. — [Oracle docs](https://docs.oracle.com/en/middleware/bi/analytics-server/datamodel-oas/create-and-manage-level-based-hierarchies-semantic-model.html)
- SAP Datasphere supports parent-child hierarchy attributes and a "hierarchy with directory" that holds several parent-child hierarchies (for example S/4HANA set hierarchies by controlling area). It is called a far easier way to bring S/4HANA hierarchies across. — [SAP Community: hierarchy with directory](https://community.sap.com/t5/technology-blog-posts-by-sap/an-introduction-to-hierarchy-with-directory-in-sap-datasphere/ba-p/13575573); [SAP Community: build parent-child from S/4HANA](https://community.sap.com/t5/technology-blog-posts-by-sap/build-an-sap-datasphere-parent-child-hierarchy-based-on-s-4hana-hierarchies/ba-p/13497286)
- Older limits, 2023–2024 and possibly fixed since: Datasphere hierarchy features did not match S/4HANA or ECC richness, and there is no "Unassigned nodes" bucket as in BW. — [SAP Community](https://community.sap.com/t5/technology-blog-posts-by-sap/modeling-a-basic-hierarchy-with-directory-in-sap-datasphere/ba-p/13575652)
- SAP Seamless Planning and SAC parent-child planning hierarchies need workarounds to reuse in Datasphere. Level-based ones need little extra modeling. — [zpartner](https://www.zpartner.eu/?p=13996); [Mindset Consulting](https://www.mindsetconsulting.com/modeling-customer-hierarchies-in-sap-bdc-datasphere-for-analytics/)
- Classic SSAS handles ragged hierarchies with HideMemberIf (older material). — [Microsoft Learn (SQL 2012)](https://learn.microsoft.com/pl-pl/previous-versions/sql/sql-server-2012/ms365406(v=sql.110))

### Inferences
- Finding hierarchies from data is open ground. Two cheap mechanisms Strata could add:
  1. Detect self-referencing FK columns (parent_id → id) as parent-child. Check for cycles, orphans, depth, and raggedness (leaf depths that differ).
  2. Detect level chains among columns through functional dependencies (city → region → country, sku → category), which are testable on the data.
  Both fit Strata's "check against the data" strength. None of the vendors checked document either.
- An effective-dated (SCD2) hierarchy plus several alternate hierarchies per dimension (SAP's "directory") is the pattern needed for CoA and cost centres.

### Gaps
- Nothing was found on hierarchies in Fabric IQ ontology, Snowflake semantic views, Databricks metric views, or Palantir ontology. Hierarchy support in MDM tools (Informatica, Reltio, Profisee) was also not researched.

## 5. Open-source building blocks (licence, activity)

### Takeaway
A Python-only stack (which fits Strata's "no Docker" rule) is available: sqlglot for query-log parsing, docling for PDFs and policies, and LlamaIndex PropertyGraphIndex or docling-graph for document-to-graph extraction. OpenMetadata and DataHub are heavy, server-based catalogs. They are useful as references or connectors, not as embedded parts.

### Cited Findings
- **sqlglot**: MIT. About 9.5k stars per an aggregator (check GitHub). Pure Python, multi-dialect. DataHub picked it for column-level lineage. — [openapps.pro](https://openapps.pro/packages/sqlglot); [DataHub](https://datahub.com/?p=4506)
- **sqllineage** (reata): MIT, about 1.7k stars. A lighter lineage tool. — [dev.co](https://dev.co/databases/open-source/sqllineage)
- **docling** (IBM / docling-project): MIT, reported past 65k stars. Converts PDF and DOCX to structured output for RAG. — [AlphaSignal](https://alphasignal.ai/news/ibm-s-docling-hits-65k-stars-fixing-the-pdf-problem-that-breaks-rag)
- **docling-graph**: MIT, about 756 stars, listed in the LinkML registry. Extracts knowledge graphs from documents into a schema, using Pydantic or LinkML templates. — [GitHub docling-graph](https://github.com/docling-project/docling-graph); [LinkML registry](https://linkml.io/linkml-registry/details/docling-project_docling-graph/)
- **LlamaIndex PropertyGraphIndex**: MIT. A pluggable, extractor-based property graph with an in-memory default. The repo is about 52k stars (Sept 2026). — [aiwiki LlamaIndex](https://www.aiwiki.ai/wiki/llamaindex/raw); [Atlan comparison of Neo4j GraphRAG, LlamaIndex and LangChain](https://atlan.com/know/ai-agent/knowledge-graph/neo4j-graphrag-vs-llamaindex-vs-langchain/)
- **DataHub**: open-source catalog with a SQL-parsing lineage pipeline based on sqlglot. — [DataHub](https://datahub.com/?p=11072)

### Inferences
- For Strata, sqlglot is the clear first add. It is pure Python, MIT and dialect-aware, and it already powers DataHub lineage. It parses DuckDB, Snowflake, Postgres and other logs into ASTs, from which joins, aggregates and predicates can be counted.
- For "Discover from documents", the pairing is docling for parsing plus a schema-guided extractor (docling-graph templates, or LlamaIndex's schema-constrained extraction). The schema should be Strata's own ontology, so extracted rules and terms attach to existing entities instead of making a parallel graph.

### Gaps
- Licence and activity for OpenMetadata, DataHub (current stars), Unstructured (open-source core vs. paid API split) and LlamaIndex SchemaLLMPathExtractor were not verified this session. Check their GitHub pages before deciding.
- Star counts above come from aggregators, not GitHub directly.
