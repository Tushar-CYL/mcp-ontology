# Layer 3 — Semantic Layer: market research

Research note for the "better middle layer" programme. Prices are public list prices seen on the
vendor page on **2026-10-29**; "unknown" means no public list price was found. Evidence grades:
**A** = we measured, **B** = primary vendor docs, **C** = independent/analyst, **D** = our inference.
Vendor marketing is labelled *(documented — vendor)*. No outcome here is measured by us.

## Executive summary

1. Every mainstream L3 vendor sells the same promise — define a metric once, let the engine write the SQL — and every one of them is **manual, human-modelled**; none documents inferring metrics from a raw schema.
2. List pricing is visible at the low end (dbt Starter $100/user/mo, 5,000 queried metrics; Cube Starter $40/dev/mo) and opaque at the enterprise end (AtScale, Looker, Databricks and Snowflake feature SKUs are quote- or consumption-based).
3. The AI story has converged on **MCP**: dbt, Cube, Snowflake and Databricks all expose governed metrics to agents, but what arrives is a *query API*, not task-conditioned evidence with provenance or a size budget.
4. The unsolved problems are ownership/approval of definitions, bitemporal semantics, per-claim evidence grading and zero-modelling onboarding of a new source.
5. Our opening is not another semantic layer; it is a **bootstrap-and-grade** layer that infers candidate metrics, marks stated vs guessed, and hands BI and agents one evidence-tagged artifact.

## Comparison table

| Tool | Category | Licence / public list price (2026-10-29) | How built | Human review | Agent path | Grade |
|---|---|---|---|---|---|---|
| dbt Semantic Layer / MetricFlow | Semantic layer inside a transformation platform | MetricFlow + semantic-interfaces Apache-2.0; service/APIs proprietary. Developer free; **Starter $100/user/mo** (5,000 queried metrics/mo); Enterprise custom | Code-first YAML semantic models; SQL/joins generated at query time | Author + PR review, RBAC | dbt MCP server; GraphQL/JDBC/ADBC | B |
| Cube | Universal semantic layer, marketed as "AI Context Layer" | Core open source; Cloud **Free / $40 dev/mo / $80 Premium**; Enterprise custom; dedicated deploy $0.60/h | Manual JS/YAML model + dbt integration + modelling agent | Authoring, access rules, evals | MCP server for any MCP agent | B |
| AtScale | Enterprise universal semantic layer | Proprietary; **no public list price** (consumption-based, quote-only) | Manual modelling; "one-click modeling" claimed 2025 | Enterprise modelling team | Semantic-layer integration (e.g. Bedrock AgentCore) | C |
| Databricks UC metric views | Metrics as catalog objects | Proprietary feature; no separate SKU documented; platform DBUs apply | UI / YAML / `CREATE VIEW … WITH METRICS`; Genie Code assist | Author + catalog owner + tags | Genie Agents, AI/BI, external BI via SQL | B |
| Snowflake Semantic Views + Cortex Analyst | Semantic objects + managed NL-to-SQL | Views are metadata; AI billed in **AI Credits $2.00** global / $2.20 regional; Analyst API per 1,000 messages | YAML/DDL, Semantic Studio, **Autopilot**, verified queries | Author + verified queries + evals | Cortex Agents read the view and generate SQL; REST; managed MCP | B |
| Looker / LookML | BI semantic model | Proprietary; pricing page exposed no list price in this fetch (quote-based; unknown) | Hand-written LookML in git | Developer + content certification | No verified MCP contract in this pass | B / C |
| Power BI semantic models | BI semantic model (DAX) | **Pro $14/user/mo**; **PPU $24/user/mo**; Fabric capacity extra | Manual model + DAX; Copilot assists authoring | Model owner, pipelines | Copilot in Fabric; no open MCP documented | B |

## Per-tool findings

### dbt Semantic Layer / MetricFlow

**Licence and price.** MetricFlow and `dbt-semantic-interfaces` are Apache-2.0; the hosted service
layer and Semantic Layer APIs are proprietary and need a paid plan. 2026-10-29: Developer free (1
seat, no hosted layer), **Starter $100/user/month** with metrics and "5,000 queried metrics per
month", Enterprise custom at 20,000/month.

**Entry and build.** A dbt project on a supported warehouse; docs require Starter or Enterprise for
the hosted layer. Definitions are hand-written YAML: semantic models declare entities, dimensions and
measures, metrics compose them; the platform generates SQL "including performing joins". The
intellectual work — which entities exist, which measures are correct — is entirely human. No
documented schema inference.

**Artifacts, time, lineage.** Versioned YAML in git; GraphQL/JDBC/ADBC APIs; exports; caching; dbt
Catalog lineage (column-level on Enterprise); a **dbt MCP server**. Versioning is git history plus
incremental builds; no documented bitemporal metric semantics.

**What an agent receives.** Metric query results and metadata over MCP or APIs — no packed evidence
bundle, no per-fact provenance, no budget logic. The agent still decomposes the question and
assembles the answer.

**Outcomes.** Vendor case studies only *(documented — vendor)*. **Measured: none.**

**Limits.** Needs dbt and modelling skill; per-plan metric caps; warehouse-only; no ownership object
beyond PR review; no provenance grades.

**Gap for us.** Bootstrap metrics from any schema with no dbt project, grade stated vs guessed, and
deliver a budgeted evidence pack rather than only a query endpoint.

### Cube

**Licence and price.** Core open source, Cloud paid. 2026-10-29: Free (includes semantic model IDE,
chat and MCP server), **Starter $40/dev/month**, **Premium $80** (Explorer $40, Viewer $20),
Enterprise custom; dedicated deployment $0.60/hour; caching $0.15/hour per small worker.

**Build and automation.** A human JS/YAML model over a warehouse, dbt integration on Premium+, model
sync, and an in-product semantic-model agent to assist. Cube now sells the same layer as an **"AI
Context Layer"**: semantic core + business rules/glossary + lineage and external context over **MCP
Connectors** (docs, tickets, incidents). It is the closest L3 competitor to our L4 story, but context
is still assembled per agent turn, not pre-packed to a size limit.

**Artifacts and exit.** REST/GraphQL/SQL APIs, MCP server, workbooks, access rules, and **Cube Evals**
(question plus known-correct answer, scored per case). Answers trace to named definitions.

**What an agent receives.** Governed metrics, joins and access rules as MCP tools, then query
results. Cube's own pitch: point an LLM at raw tables and "it re-derives joins and metric logic on
every prompt".

**Outcomes.** Vendor case studies (Brex says it chose Cube over dbt Semantic Layer and LookML);
vendor-published, not measured.

**Limits.** Model per source before agents work; no discovery from files; no per-fact grade; no
answer-size budget; key features gated to Premium+.

**Gap for us.** Auto-model bootstrap, explicit provenance, deterministic packing on files and
warehouses alike.

### AtScale

Proprietary with **no public list price** (a consumption-pricing blog plus quote-only sales; price
unknown). Manual semantic modelling; the 2025 launch blog title claims "GenAI, One-Click Modeling &
More" *(documented — title only; details unverified)*. An AWS blog documents an AtScale + Bedrock
AgentCore agentic pattern. Primary pages returned title-only HTML in this pass, so capability cells
are **unverified (D)** and this row is **grade C**. Gap for us: be transparent, self-serve and locally
reproducible.

### Databricks Unity Catalog metric views

Proprietary platform feature; the metric-view docs publish no separate SKU, so cost is platform
compute (DBU); feature list price **unknown**. Entry needs `SELECT` on the source, `CREATE TABLE` and
`USE SCHEMA`, `USE CATALOG`, and a warehouse on DBR 16.4+ (17.3+ for agent metadata). Build is manual
via Catalog Explorer, YAML or `CREATE VIEW … WITH METRICS`; **Genie Code** writes definitions from
natural language, and agent metadata adds display names, up to 10 synonyms per field, formats and
governed tags. Artifacts: a catalog object queryable from SQL, notebooks, dashboards, Genie Agents and
external BI, with optional materialization. Agent metadata is names/synonyms/formats only — no
evidence grade, freshness or budget. Databricks-only; ownership workflow not documented.

### Snowflake Semantic Views + Cortex Analyst

Semantic views are metadata; AI usage is billed in **AI Credits ($2.00 global / $2.20 regional)**,
with the standalone Analyst API billed per 1,000 messages and SQL execution on warehouse compute. Entry:
`CORTEX_ANALYST_USER`/`CORTEX_USER` role, `SELECT` on tables, a semantic view (or legacy YAML). Build:
DDL/YAML, Snowsight wizard, **Semantic Studio** (GA 2026-09-30), **Semantic View Autopilot** (ingests
YAML, Tableau or Power BI files), **verified queries** (2026-04-05) and custom instructions
(2026-01-12) — the clearest human-approval mechanism here — plus evaluations. Cortex Agents read the
view and generate SQL against physical tables; a managed MCP server exposes them. Documented limits:
no access to prior query results, SQL-only questions, long-conversation degradation. Vendor claims
accuracy improvement; **measured: none**.

### Looker / LookML and Power BI (brief)

LookML is a hand-written modelling language (views, dimensions, measures, Explores) in git, validated
in the IDE, SQL generated at query time; pricing is quote-based in this fetch. Power BI semantic
models are manual models plus DAX, list-priced at **Pro $14/user/month** and **PPU $24**; Copilot
assists authoring but does not infer a metric catalogue, and no open MCP contract is documented.
Both are BI-bound with no packed-context or provenance path. Grades B.

## Problems solved / under-served

Twelve buyer problems; "served" means a mainstream tool documents it as a first-class feature.

| # | Buyer problem | Status | Evidence |
|---|---|---|---|
| 1 | Same metric, different numbers in BI, reports and chat | **Served** | All six tools exist for this |
| 2 | Who owns and approves a definition | **Partly** | dbt PR review; Snowflake verified queries; no ownership object elsewhere |
| 3 | Which table is the source of truth | **Partly** | Catalog/lineage answers it; semantic layers assume it |
| 4 | Cryptic physical names vs business terms | **Served** | Snowflake's own example (`amt_ttl_pre_dsc`); Databricks synonyms |
| 5 | Join correctness, fan-out, chasm traps | **Served** | Engines derive joins from declared entities |
| 6 | New dataset onboarding takes weeks of modelling | **Under-served** | All are manual; AI assists authoring only (Genie Code, Autopilot, Cube agent) |
| 7 | Metric drift when upstream changes | **Partly** | dbt tests/CI, Cube Evals, Snowflake evals; not semantics-aware |
| 8 | Agents re-derive logic per prompt | **Partly** | MCP endpoints help; agents still choose and assemble |
| 9 | Permissions/row-level security applied consistently | **Served** | dbt RBAC, Cube access rules, UC/Snowflake grants |
| 10 | "Why did this number change?" | **Partly** | Lineage exists; per-answer provenance does not |
| 11 | "What did this metric mean on 1 March?" | **Under-served** | No vendor documents as-of-date metric semantics |
| 12 | Predictable cost/latency per question | **Under-served** | Credit/DBU models hide marginal cost; caps are blunt |

## What a better version must do

1. **Start from the source.** Infer candidate tables, keys, measures and dimensions from schema plus
   profiling, with confidence; humans only name and approve.
2. **Grade evidence per claim.** A declared foreign key is not a name-matched guess; carry the grade
   into every answer.
3. **Make definitions temporal.** Valid-from/valid-to on definitions so "revenue as at Q1" is
   answerable.
4. **Serve one artifact to BI and AI.** Compile to SQL *and* to a bounded, labelled evidence pack.
5. **Refuse rather than guess.** Fail when asked to group by a column the metric's table lacks (our
   compiler already raises here).
6. **Attach ownership as data,** not as git etiquette.
7. **Prove adoption cheaply:** local run on a CSV or SQLite file, no licence, no warehouse.
8. **Expose MCP** so existing agents consume us instead of changing framework.

## Candidate differentiators

1. **Zero-modelling bootstrap** — metrics proposed from actual columns and profiling, not from a
   pre-built dbt/LookML project.
2. **Per-claim evidence grade** — stated (declared key) vs guessed (name match) carried into every
   answer, visible to humans and agents.
3. **Bitemporal metrics** — the number *and* what the metric meant at the time.
4. **One artifact for BI and AI** — the same definition compiles to SQL and to a size-budgeted pack.
5. **Local and free by default** — runs on a laptop against files; no warehouse, licence or catalog.

## Terminology

No settled definition exists. dbt and Snowflake define metrics inside their platform; Cube sells "the
semantic layer" but brands it an **"AI Context Layer"**; Databricks says "Unity Catalog semantics";
Looker says LookML; Power BI says semantic model. "Metrics layer" is used loosely for all of them. For
our external story, use **"semantic layer"** with data teams — it is what they search for — and always
add **"inferred from your actual schema, evidence-graded"** to separate us from manual-modelling
incumbents. Reserve "context layer" for Layer 4; see `04_context_layer.md` for that collision and the
recommended external name.

## Sources (all accessed 2026-10-29)

- dbt pricing — https://www.getdbt.com/pricing
- dbt Semantic Layer — https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl
- dbt SL architecture (licences, APIs) — https://docs.getdbt.com/docs/use-dbt-semantic-layer/sl-architecture
- Cube pricing — https://cube.dev/pricing
- Cube AI Context Layer — https://cube.dev/product/ai-context-layer
- AtScale universal semantic layer — https://www.atscale.com/use-cases/universal-semantic-layer/
- AtScale 2025 launch — https://www.atscale.com/blog/atscale-2025-product-announcements/
- AtScale consumption pricing — https://www.atscale.com/blog/flexible-consumption-based-pricing-explained/
- AWS + AtScale agentic pattern — https://aws.amazon.com/blogs/machine-learning/build-a-semantic-layer-for-agentic-ai-on-aws-with-atscale-and-amazon-bedrock-agentcore/
- Databricks metric views — https://docs.databricks.com/gcp/en/uc-semantics/metric-views
- Databricks create metric view — https://docs.databricks.com/gcp/en/uc-semantics/metric-views/create
- Databricks agent metadata — https://docs.databricks.com/gcp/en/uc-semantics/agent-metadata
- Snowflake semantic views — https://docs.snowflake.com/en/user-guide/views-semantic/overview
- Snowflake Cortex Analyst — https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst
- Snowflake AI pricing — https://docs.snowflake.com/en/user-guide/snowflake-cortex/pricing
- Snowflake verified queries — https://docs.snowflake.com/en/release-notes/2026/other/2026-04-05-semantic-views-verified-queries
- LookML introduction — https://docs.cloud.google.com/looker/docs/what-is-lookml
- Looker pricing — https://cloud.google.com/looker/pricing
- Power BI pricing — https://www.microsoft.com/en-us/power-platform/products/power-bi/pricing
