# Semantic Layer (Governed Metrics) for BI and AI Agents, 2025-2026

NOTE: Plan mode was active, so these notes could not be written to the requested scratchpad path
(.../research_notes/Strata four layers and agents/03_semantic_layer.md). Copy this file there.
Research date: 2026-11-03.

## 1. What a semantic layer is (plain language) and how it differs from ontology / metrics store / BI model

### Takeaway
A semantic layer is a governed, code-defined dictionary of business metrics, dimensions and approved joins. A query engine compiles it into correct SQL, so every tool and agent asks for "revenue by region last quarter" and gets the same number. Industry specs (Ossie/OSI, MetricFlow, Databricks, Snowflake) now converge on one shape: datasets/semantic models, fields/dimensions, metrics, relationships, plus AI metadata (synonyms, descriptions, verified queries).

### Cited Findings
- Ossie (formerly OSI) core spec objects: Semantic Model (container), Datasets (logical business entities, fact/dimension tables), Fields (row-level attributes), Metrics (aggregates such as sums, averages and ratios that can span datasets), Dimensions, Relationships (foreign keys, including composite keys). Declarative YAML, Apache 2.0. — [ossie.apache.org](https://ossie.apache.org/)
- Databricks defines metric views as separating "measure definitions from the fields (dimensions) used to group, filter and aggregate". A metric is defined once and grouped by any field, and the engine generates the computation, unlike a standard view, which locks the aggregation in at creation. — [Databricks metric views](https://docs.databricks.com/aws/en/metric-views/)
- Cube describes Cube Core as a semantic layer that "models measures, dimensions, joins, and access rules, then serves governed queries over SQL, REST, GraphQL, and MCP" (vendor). — [Cube article](https://cube.dev/articles/open-source-semantic-layer)
- Ossie now calls itself "an open specification for both semantic layer and ontology", with three working groups: metric language, catalog and ontology. This means the standards body is merging the semantic-layer and ontology concepts. — [Dremio blog](https://www.dremio.com/blog/apache-ossie-the-open-semantic-interchange-joins-the-apache-incubator); [Snowflake blog](https://snowflake.com/en/blog/apache-ossie-open-semantic-interchange-incubator)
- Snowflake semantic views store synonyms, sample values and verified queries as metadata on a native schema object. This replaces the older Cortex Analyst YAML file kept in a stage. — [Snowflake engineering blog](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/)

### Inferences
- Analogy for users: the semantic layer is a "menu with recipes". Agents order dishes (metric + dimensions + filters + time window), and the kitchen (compiler) makes sure each dish is cooked the same way every time. The ontology is the "map of the business": what things exist and how they relate. A metrics store is the semantic layer minus joins/dimensions (older term, about 2021-22). A BI model (LookML, Power BI semantic model) is a semantic layer locked inside one BI tool.
- Strata's split (Ontology / KG / Semantic / Context) matches the field's direction, but Ossie is merging semantic layer and ontology into one spec. Strata should keep the two layers interoperable (shared entity IDs), not separate silos.

### Gaps
- No authoritative neutral definition document. Definitions come from vendors and spec pages.

## 2. How the major tools model metrics, dimensions, joins and time (status and dates)

### Takeaway
MetricFlow, which has been Apache 2.0 since Oct 2025, has the richest metric typing (simple, ratio, derived, cumulative, conversion, non-additive). Cube and Malloy are the strongest open-source engines. The warehouses (Snowflake semantic views, Databricks metric views) and BI tools (Looker, Power BI) have each made the semantic layer a native object with AI metadata and MCP access.

### Cited Findings
**dbt Semantic Layer / MetricFlow**
- Metric types: Simple (`agg` = sum/max/min/average/median/count_distinct/percentile/count/sum_boolean, `expr`, `non_additive_dimension`, `agg_time_dimension`, `join_to_timespine`, `fill_nulls_with`); Cumulative (`input_metric`, `window`, `grain_to_date`, `period_agg`); Derived (`expr`, `input_metrics`, `offset_window`/`offset_to_grain` for period comparison); Ratio (`numerator`, `denominator`, filters on either side); Conversion (`entity`, `base_metric`, `conversion_metric`, `window`, `constant_properties`). — [dbt metrics overview](https://docs.getdbt.com/docs/build/metrics-overview)
- New YAML spec (dbt v1.12+): the semantic model is declared on the model (`semantic_model: enabled`). Simple metrics live inside the model, and cross-model ratio/derived/cumulative/conversion metrics go at top level. Time columns declare a native `granularity`, and a time spine model is required for cumulative metrics. Filters use Jinja `{{ Dimension('customer__country') }}`, `{{ TimeDimension(...) }}`, `{{ Entity(...) }}`, `{{ Metric(...) }}`. — [dbt metrics overview](https://docs.getdbt.com/docs/build/metrics-overview)
- Licence: MetricFlow was open-sourced under Apache 2.0 at Coalesce 2025 (blog updated 15 Oct 2025), "including all of the code required to define metrics and calculate them in multi-dialect SQL". Licence history: v0-0.140.0 AGPL, 0.150.0-0.208.2 BSL, 0.209.0+ Apache 2.0. — [dbt blog](https://www.getdbt.com/blog/open-source-metricflow-governed-metrics); [GitHub metricflow](https://github.com/dbt-labs/metricflow). The README says it is "developed and maintained as part of the OSI initiative". About 1.9k stars. CONFLICT/NUANCE: the hosted dbt Semantic Layer APIs (JDBC/GraphQL) remain dbt Platform (commercial). Only the engine is open.
- Ossie's site carries the MetricFlow open-sourcing announcement, positioning it as a reference implementation. — [ossie.apache.org update](https://ossie.apache.org/updates/announcing-open-source-metricflow-governed-metrics-for-ai-and-agents/)

**Cube**
- Repo cube-js/cube: Cube Client MIT, Cube Backend Apache 2.0, about 21.2k stars, "open-source semantic layer for AI, BI and embedded analytics". Define "metrics, dimensions, joins, and access rules once in code", with a built-in caching engine (pre-aggregations). — [GitHub cube](https://github.com/cube-js/cube)
- Cube Cloud MCP server: hosted at `https://cubecloud.dev/mcp`, follows the 2026-07-28 MCP spec, stateless, OAuth PKCE. 30 tools: `listDeployments`, `chat`, `loadQueryResults`, `searchDataModel`, `runQuery` (Cube SQL API, Postgres dialect), dashboard/report authoring, data-model editing (`readDataModelFile`, `writeDataModelFile`, `commitDataModelChanges`, `mergeToDefaultBranch`, ...), pre-aggregation build. Every tool runs as the authenticated user with role-based permissions including row-level security. Writes go only to personal dev branches, and nine destructive tools prompt for confirmation. Documented caveats: `chat` is annotated read-only yet its agent can write, and `commitDataModelChanges` is not annotated destructive. — [Cube docs MCP server](https://docs.cube.dev/docs/integrations/mcp-server)
- CONFLICT: Cube docs say MCP is "available on all plans" ([docs](https://docs.cube.dev/docs/integrations/mcp-server)). Atlan said Premium/Enterprise only ([Atlan](https://atlan.com/know/ai-agent/semantic-layer/cube-semantic-layer/)). PricingSaaS logged MCP being added to the Free plan in late Sept 2026 ([PricingSaaS](https://pricingsaas.com/companies/cube/diffs/2026W40)). The current docs win: all plans, as of about Oct 2026. MCP is a Cube Cloud feature. The Core README doesn't mention MCP, although a Cube article says Core serves MCP ([Cube article](https://cube.dev/articles/open-source-semantic-layer)), which is unresolved.

**AtScale**
- MCP server announced 1 Dec 2025 and listed in the Databricks MCP Marketplace: "semantic layer available to agents as an action service". Existing customers attach semantic models directly. — [AtScale press](https://www.atscale.com/?p=28219); [BusinessWire](https://www.businesswire.com/news/home/20251201005442/en)
- Earlier: AtScale powered Databricks Genie (Mar 2025) — [BusinessWire](https://www.businesswire.com/news/home/20250310908691/en/AtScale-Powers-Databricks-Genie-with-Semantic-Layer-Delivering-Accurate-and-Trusted-Natural-Language-Querying). Its 2025 Summit announced GenAI features and an "open source standard" (SML) — [BusinessWire](https://www.businesswire.com/news/home/20250529075658/en/AtScale-Advances-Semantic-Layer-Leadership-with-Innovations-for-Generative-AI-and-Open-Source-Standard-at-2025-Summit)
- Nike usage: NOT VERIFIED. No source found in this search.

**Looker / LookML**
- Next '26: the Conversational Analytics agent (already GA) is upgraded with "semantic grounding" (preview), and Looker BI Agents trigger actions "grounded in the Looker semantic layer". — [Google Cloud blog Next26](https://cloud.google.com/blog/products/business-intelligence/looker-updates-for-agentic-bi-at-next26)
- Looker is reachable from MCP via the open-source MCP Toolbox, and can publish agents into Gemini Enterprise via A2A (Aug 2026). The LookML layer produces "deterministic SQL from version-controlled business logic". — [Looker MCP docs](https://docs.cloud.google.com/looker/docs/connect-ide-to-looker-using-mcp-toolbox); [Gemini Enterprise blog](https://cloud.google.com/blog/products/business-intelligence/connecting-looker-to-gemini-enterprise-with-mcp-toolbox-and-adk)
- Vendor claim: PayPal scaled conversational analytics to 3,000+ users via Claude Desktop + the Looker MCP server. — [Google blog](https://cloud.google.com/blog/products/business-intelligence/looker-in-2026-gartner-analytics-and-bi-platforms-mq)

**Snowflake semantic views / Cortex Analyst**
- Semantic views are a native schema object holding logical tables, relationships, facts, dimensions and metrics, plus synonyms, sample values and verified queries. They replace the stage-based YAML semantic model. — [Snowflake eng blog](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/); [Snowsight docs](https://docs.snowflake.com/en/user-guide/views-semantic/ui)
- GA announced at Summit 2025 (per phData, third party; I found no official GA post). Sample values may leak PII, so remove them or disable generation. The model excluding verified queries and sample values must stay under about 32K tokens. — [phData](https://www.phdata.io/?p=24102)

**Databricks Unity Catalog metric views**
- Defined in YAML (SQL DDL or Catalog Explorer). Sources, dimensions, measures, filters, multi-level joins (star/snowflake), window measures (trailing, period-over-period, cumulative). Relationships between metric views are in Beta and materialization is Experimental. "Agent metadata" adds synonyms, display names and format rules for agent accuracy. Consumed by Genie, dashboards, alerts, Power BI, Tableau and Sigma. Page updated 29 Oct 2026. — [Databricks metric views](https://docs.databricks.com/aws/en/metric-views/)

**Power BI / Fabric semantic models**
- Two MCP servers, both public preview: a remote one (`https://api.fabric.microsoft.com/v1/mcp/powerbi`) for natural-language query over semantic models using the user's permissions (admin must enable a tenant setting), and a local open-source `microsoft/powerbi-modeling-mcp` for authoring. Microsoft recommends "AI instructions and verified answers" to prepare models for AI. — [MS Learn overview](https://learn.microsoft.com/en-us/power-bi/developer/mcp/mcp-servers-overview); [remote get started](https://learn.microsoft.com/en-us/power-bi/developer/mcp/remote-mcp-server-get-started); [GitHub](https://github.com/microsoft/powerbi-modeling-mcp)

**Malloy**
- MIT licence, about 2.6k stars. Language for sources, measures, joins, nested results and symmetric aggregates (fan-out-safe). "Publisher" is the open-source semantic model server, serving `.malloy` models over REST and MCP for AI agents. — [GitHub malloy](https://github.com/malloydata/malloy)

**Boring Semantic Layer**
- MIT, about 487 stars, built on Ibis: `.with_dimensions(...)`, `.with_measures(...)`. Optional MCP extra (`MCPSemanticModel`). Lightweight Python, multi-backend via Ibis. — [GitHub BSL](https://github.com/boringdata/boring-semantic-layer); [author Substack](https://juhache.substack.com/p/boring-semantic-layer-mcp)

**Wren AI (MDL)**
- Canner/WrenAI: about 18.1k stars. Engine, SDK and skills are Apache-2.0 (the repo also contains AGPL-3.0 and CC-BY files, and the old Gitee mirror listed AGPL, so this is a licence CONFLICT across mirrors). RLS and the GenBI UI are commercial. MDL models columns, relationships, views, cubes and metrics. Context beyond the schema (enums, units, approved joins, definitions) lives in `instructions.md` and `queries.yml`. MCP server is included. On 2026-05-07 Wren Engine merged into `core/`, and the old Docker app was archived as "GenBI Classic". — [GitHub WrenAI](https://github.com/Canner/WrenAI); [Wren OSS page](https://www.getwren.ai/en/oss)

### Inferences
- Common AI metadata set across vendors: description, synonyms, sample/dimension values, verified queries, AI instructions, display format. Strata has description/format/caveats but should add synonyms, verified queries and sample-value retrieval with PII guarding.
- Strata lacks explicit metric typing. Ratio, derived, cumulative and non-additive (balances/snapshots) metrics are where hand-written SQL most often goes wrong. Its "value expression" and "base SQL" sit closer to Snowflake/Databricks than to MetricFlow.
- Writes via MCP (Cube) are gated by dev branches and confirmation. If Strata lets agents propose metric changes, that pattern (draft, review, approved) maps to Strata's status field.

### Gaps
- Nike/AtScale not verified. Snowflake official GA date not confirmed from Snowflake. Star counts are snapshots from about Nov 2026 page fetches.

## 3. Standards: OSI / Apache Ossie, MetricFlow spec

### Takeaway
OSI launched on 23 Sep 2025, led by Snowflake. It entered the Apache Incubator on 22 Jun 2026 as Apache Ossie (Incubating), and this is verified on incubator.apache.org. The format is YAML, with converters for MetricFlow, Snowflake semantic models and Polaris. No spec version number was found.

### Cited Findings
- Launched 23 Sep 2025, co-led by Snowflake, Salesforce, BlackRock, dbt Labs and RelationalAI. Partners include Alation, Atlan, Blue Yonder, Cube, Elementum AI, Hex, Honeydew, Mistral AI, Omni, Select Star, Sigma and ThoughtSpot. — [BusinessWire](https://www.businesswire.com/news/home/20250923902448/en/Snowflake-Salesforce-dbt-Labs-Revolutionize-Data-Readiness); [Snowflake blog](https://www.snowflake.com/blog/open-semantic-interchange-ai-standard/)
- Apache incubator page (VERIFIED): entered 2026-06-22. Champion JB Onofré. Mentors JB Onofré, Holden Karau, Zili Chen, Russell Spitzer. 14 initial committers (including Josh Klahr, Kurt Stirewalt, Will Pugh). Description: "vendor-neutral format for expressing business metrics, dimensions, and their relationships". — [incubator.apache.org/projects/ossie](https://incubator.apache.org/projects/ossie.html)
- GitHub announcement dated 22 Jun 2026: renamed to avoid clashing with the Open Source Initiative acronym, "core specification and its direction remain unchanged". Repo at github.com/apache/ossie, spec at core-spec/spec.md, converters at apache/ossie-converters. — [GitHub discussion 164](https://github.com/open-semantic-interchange/OSI/discussions/164); [ossie.apache.org](https://ossie.apache.org/)
- Snowflake and Dremio blogs date the rename announcement to July 2026. Converters exist for dbt MetricFlow, Polaris catalog and Snowflake semantic models. Roadmap: a standard semantic *query* spec and Polaris discovery. — [Dremio](https://www.dremio.com/blog/apache-ossie-the-open-semantic-interchange-joins-the-apache-incubator); [Snowflake](https://snowflake.com/en/blog/apache-ossie-open-semantic-interchange-incubator)
- Ecosystem growth: Denodo and Kyvos joined, and 14 new participants were added (28 Apr 2026). — [ossie.apache.org](https://ossie.apache.org/)
- Notable absences from the founder list: Databricks, Google/Looker, Microsoft. (Inference from the partner lists above; I did not verify later joins.)

### Inferences
- Strata should be able to import and export Ossie YAML (and therefore MetricFlow and Snowflake via converters). This is cheap interoperability and a credible "open" claim. Strata's metric fields map closely: name, description, expression, dimensions, relationships.

### Gaps
- No released spec version number found. Databricks/Google/Microsoft participation status as of Nov 2026 is unknown.

## 4. Evidence: semantic layer vs raw text-to-SQL

### Takeaway
Semantic layers consistently raise accuracy on in-scope questions (dbt: 100% vs 51-62%; arXiv 2604.25149: +17-23 pts). Their key property is failing loudly: they refuse what they can't model, where text-to-SQL returns plausible wrong numbers. All main studies are vendor-authored or vendor-linked. The gap is shrinking as models improve and as data is modeled better.

### Cited Findings
- **dbt Labs 2026 benchmark** (Ganz and Perigaud, 7 Apr 2026; VENDOR). ACME Insurance dataset (data.world, 15 tables, 3NF), 11 questions x 20 runs.
  - All questions: text-to-SQL 64.5% vs SL 72.7% (both Sonnet 4.6 and GPT-5.3 Codex). GPT-4 in 2023 scored 32.7% vs 60.5%.
  - Within SL scope: text-to-SQL 62.5% (Sonnet) and 51.2% (Codex) vs SL 100%.
  - Beyond SL scope (too many entity hops): SL 0%, because it declines to answer, while text-to-SQL scores 70-100%.
  - After 3 LLM-generated dbt models: Sonnet 90.0% vs 98.2%, Codex 84.1% vs 100%.
  - Reasoning sweep: SL 87-100% vs text-to-SQL 50-65%.
  - "Text-to-SQL fails silently" with plausible but incorrect answers, while the "Semantic Layer fails loudly". The 1-2 wrong-dimension errors seen in 2023 did not recur in 2026.
  - Caveat noted by the authors: text-to-SQL got the full schema in context, which doesn't scale.
  - [dbt blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- **arXiv 2604.25149** (VERIFIED exists). "Semantic Layers for Reliable LLM-Powered Data Analytics: A Paired Benchmark of Accuracy and Hallucination Across Three Frontier Models", Rumiantsau and Fokeev, 28 Apr 2026.
  - Setup: Contoso Retail in ClickHouse, 100 questions, Claude Opus 4.7 / Sonnet 4.6 / GPT-5.4, paired single-shot.
  - The semantic layer was a 4 KB hand-written markdown doc of measures, conventions and disambiguation rules.
  - Accuracy with the SL was 67.7-68.7% vs 45.5-50.5% without (+17-23 pts, p<0.01). Models within each condition were statistically indistinguishable, so "the semantic layer document accounts for essentially all significant variance".
  - [arXiv abs](https://arxiv.org/abs/2604.25149)
  - BIAS FLAG: the PDF links to github.com/cubedevinc/semantic-layer-benchmark, a Cube org repo ([arXiv PDF](https://arxiv.org/pdf/2604.25149)). This suggests a Cube connection. Author affiliations are not shown on the abstract page.
  - Note that this "semantic layer" is a prompt document, not a compiled metric engine.
  - The hallucination-rate numbers could not be extracted (PDF unreadable).
- **data.world KG study** (Sequeda, Allemang, Jacob, Nov 2023, VENDOR, older): GPT-4 zero-shot on SQL scored 16.7%, and over a knowledge-graph representation 54.2%. Insurance OMG P&C model. — [arXiv 2311.07509](https://arxiv.org/abs/2311.07509v1). A 2024 follow-up added an ontology-based query check plus LLM repair and reached 72.55%. — [arXiv 2405.11706](https://arxiv.org/html/2405.11706v1)
- **arXiv 2606.31041** (semantic-layer-mediated NL2SQL agent) reports 94.15% execution accuracy on Spider2-snow (per secondary summary, not verified). — [arXiv PDF](https://arxiv.org/pdf/2606.31041)
- AtScale advertises a "Tier 1 bank" case: the same five queries cost $17.93 on one path vs $0.0008 on another (VENDOR, cost not accuracy, unverified). — [AtScale press page](https://www.atscale.com/press/page/2/?hsLang=en)

### Inferences
- Strata's design (governed metrics plus an SQL validator that checks agent SQL against certified definitions) addresses both regimes in the dbt result: the SL path for in-scope questions, and validated text-to-SQL for out-of-scope ones. That is exactly dbt's recommendation: check the SL first, fall back to text-to-SQL.
- The arXiv result implies that even a plain-text semantic doc (definitions plus disambiguation rules) gives most of the gain. Strata's Context layer can ship metric definitions as compact prompt text, not only as tools.
- Refusal should be a product feature: return "not covered by certified metrics" plus the nearest metric, instead of guessing.

### Gaps
- No independent (non-vendor) head-to-head benchmark found. arXiv 2604.25149 hallucination and refusal figures and author affiliations were not extracted.

## 5. How agents use semantic layers (tool designs)

### Takeaway
The de facto agent tool pattern is discover, then inspect, then query: list metrics, get dimensions/entities for chosen metrics, get dimension values, compile (optional), query. Writes are branch-gated. Warehouse-native agents add synonyms, verified queries and sample values for retrieval.

### Cited Findings
- dbt-mcp (Apache-2.0, about 616 stars) Semantic Layer tools: `list_metrics`, `list_saved_queries`, `get_dimensions`, `get_entities`, `get_dimension_values`, `get_metrics_compiled_sql`, `query_metrics` (filter + group-by). Also `text_to_sql`, `execute_sql`, discovery (`get_model_health`, `get_lineage`, `get_related_models` semantic search), CLI (flagged as able to mutate warehouse, "trusted clients only"), Admin API, codegen. — [GitHub dbt-mcp](https://github.com/dbt-labs/dbt-mcp)
- Cube MCP: `searchDataModel` then `runQuery`, plus `chat`, which delegates to Cube's own agent. Runs under the user's RBAC/RLS. — [Cube docs](https://docs.cube.dev/docs/integrations/mcp-server)
- Snowflake Cortex Analyst uses verified queries (example question-to-SQL pairs), synonyms and sample values inside the semantic view to interpret questions. — [Snowsight docs](https://docs.snowflake.com/en/user-guide/views-semantic/ui); [Snowflake eng blog](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/)
- Databricks Genie consumes metric views plus agent metadata (synonyms, display names, formats). Declared relationships help AI choose the correct join path. — [Databricks](https://docs.databricks.com/aws/en/metric-views/)
- Power BI remote MCP queries semantic models under user permissions, with "AI instructions and verified answers". — [MS Learn](https://learn.microsoft.com/en-us/power-bi/developer/mcp/mcp-servers-overview)
- Looker guidance trade-off: built-in Conversational Analytics is less effort and less control, while MCP Toolbox custom agents are more effort and more control. — [Google webinar PDF](https://services.google.com/fh/files/misc/lookermcpserverwebinar.pdf)
- Wren keeps approved joins, enums, units and example queries in `instructions.md` and `queries.yml` next to the MDL. — [GitHub WrenAI](https://github.com/Canner/WrenAI)

### Inferences
- Minimum Strata MCP surface to match the field: `list_metrics` (with search/synonyms), `get_metric` (definition, caveats, owner, status), `get_dimensions`, `get_dimension_values` (PII-masked), `compile_metric_sql`, `query_metric` (filters, group-by, time window, compare-to-period), `validate_sql` (Strata's differentiator: no other vendor exposes "check my SQL against the certified definition" as a tool). Add `list_verified_queries`.
- Gate draft metrics: agents should only query approved metrics by default, and refuse or label drafts.

### Gaps
- Exact Snowflake Cortex Analyst MCP tool names not retrieved. AtScale MCP tool list not retrieved.

## 6. Best practices and failure modes

### Takeaway
Vendors converge on certified/approved status, rich descriptions plus synonyms for LLMs, verified query repositories, version control with dev branches, and role-based access and RLS enforced at query time. The known failure modes are metric sprawl, drift between definitions, join fan-out, PII in sample values, context-size limits, and silent wrong answers from ungoverned SQL.

### Cited Findings
- Version-controlled definitions produce deterministic SQL (Looker). — [Google blog](https://cloud.google.com/blog/products/business-intelligence/connecting-looker-to-gemini-enterprise-with-mcp-toolbox-and-adk)
- Branch-based editing: Cube writes only to dev branches, and merging to the deploy branch is permission-checked. — [Cube docs](https://docs.cube.dev/docs/integrations/mcp-server)
- PII risk: generated sample values may include sensitive data. Semantic models have size limits (about 32K tokens excluding verified queries and samples). — [phData](https://www.phdata.io/?p=24102)
- Join path ambiguity is fixed by declared relationships. — [Databricks](https://docs.databricks.com/aws/en/metric-views/). Malloy's "symmetric aggregates" exist to avoid fan-out double counting. — [GitHub malloy](https://github.com/malloydata/malloy)
- Non-additive metrics (balances) need `non_additive_dimension`, or naive sums give wrong results. Ratio metrics are computed as metric/metric, not as an average of ratios. — [dbt metrics overview](https://docs.getdbt.com/docs/build/metrics-overview)
- Scope limits: SLs scored 0% beyond modeled entity hops (they refuse), so coverage gaps must be closed by modeling. — [dbt blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- Text-to-SQL's silent failures include wrong joins, misread column meaning, and queries that run but return wrong results. — [dbt blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- MCP write risk: Cube's own docs list annotation gaps (a read-only-annotated `chat` can write). — [Cube docs](https://docs.cube.dev/docs/integrations/mcp-server)

### Inferences
- Keep: approved/draft status, owner, caveats, the health checks, the SQL validator.
- Add: synonyms, verified queries, explicit metric types (ratio/derived/cumulative/non-additive), relationship/join declarations with fan-out protection, versioning and change history, and Ossie import/export.
- Possibly drop or deprioritize: bespoke insight features (trend/contributor) if resources are tight. No surveyed vendor treats them as core semantic-layer features. They belong in the agent layer. (This is judgment, not sourced.)
- Metric sprawl and drift: use the health checks to flag duplicate or near-duplicate metrics and definitions that changed without a version bump.

### Gaps
- No quantified study of metric sprawl or drift found. "Testing metrics" practices (e.g. dbt saved-query tests) not researched in depth.

## 7. Open-source repos snapshot (fetched about Nov 2026)

| Repo | Licence | Stars | Note |
|---|---|---|---|
| [dbt-labs/metricflow](https://github.com/dbt-labs/metricflow) | Apache 2.0 (since 0.209.0; earlier AGPL/BSL) | ~1.9k | Richest metric types; Ossie reference |
| [dbt-labs/dbt-mcp](https://github.com/dbt-labs/dbt-mcp) | Apache 2.0 | ~616 | Canonical SL tool set |
| [cube-js/cube](https://github.com/cube-js/cube) | MIT client / Apache 2.0 backend | ~21.2k | Caching, RLS, SQL/REST/GraphQL; MCP is in Cloud |
| [malloydata/malloy](https://github.com/malloydata/malloy) | MIT | ~2.6k | Symmetric aggregates; Publisher serves REST+MCP |
| [Canner/WrenAI](https://github.com/Canner/WrenAI) | Apache 2.0 core (AGPL files also present) | ~18.1k | MDL + instructions.md + queries.yml; MCP |
| [boringdata/boring-semantic-layer](https://github.com/boringdata/boring-semantic-layer) | MIT | ~487 | Ibis-based, tiny, MCP extra |
| [microsoft/powerbi-modeling-mcp](https://github.com/microsoft/powerbi-modeling-mcp) | not checked | n/a | Local modeling MCP |
| [apache/ossie](https://github.com/apache/ossie) | Apache 2.0 | n/a | Spec + converters |

### Inferences
- What Strata can learn: MetricFlow's metric typing and filter grammar; Cube's RLS-at-query-time and branch-gated writes; Malloy's fan-out-safe aggregation; Wren's "instructions + verified queries next to the model"; dbt-mcp's discover-then-query tool decomposition.
