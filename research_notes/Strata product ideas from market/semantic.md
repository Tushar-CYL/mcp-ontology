# Semantic layer (governed metrics): market features, UX patterns and ideas for Strata (2025-2026)

Research date: 2026-11-20. Most sources are vendor docs or blogs, which are biased toward their own products. Practitioner complaints were hard to find; see the Gaps sections. Strata baseline already in place: AI-proposed metrics, certification with an owner, a receipt (formula, joins, no double counting), drift warnings, synonyms, verified questions, defining a metric in words, and export to dbt MetricFlow and SQL views.

## 1. What leading products offer, and which UX patterns stand out

### Takeaway
By 2026 every major vendor has the same core loop: a governed model (semantic view, metric view, LookML, DAX model), plus plain-text instructions, plus verified or golden question-to-query pairs, plus an AI that drafts the model from existing assets. The differences are in automation. Snowflake mines query history and turns verified queries into an evaluation suite. Omni and Lightdash turn user feedback into proposed model edits. Tableau keeps the LLM out of the math altogether.

### Cited Findings
**Snowflake (semantic views + Cortex Analyst)**
- Semantic View Autopilot (SVA) proposes candidate metrics and filters learned from query history and trusted BI assets. Tableau is the first BI source supported, with more planned through OSI partners. SVA became GA on Feb 3, 2026. — [Snowflake blog](https://www.snowflake.com/en/blog/semantic-view-autopilot/)
- In the Autopilot wizard, example SQL is validated, invalid entries are dropped, and the remaining queries are used to pre-select tables and columns. They are then added to the semantic view as verified queries. — [Snowflake docs: Autopilot](https://docs.snowflake.com/user-guide/views-semantic/autopilot)
- "Optimize with verified queries" (Preview, Dec 2, 2025) analyzes verified queries and pushes what it learns back into the semantic layer. Example: a verified "active users" query leads to a suggested `is_active` filter on the customer table that uses the exact same definition. Limits: it needs at least one verified query, more than 20 verified queries slows it down, and each verified query may be executed up to 4 times. — [Release note](https://docs.snowflake.com/release-notes/2025/other/2025-12-02-cortex-analyst-optimization); [Docs](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/analyst-optimization)
- Cortex Analyst Evaluations use verified queries as ground truth. Generated SQL is executed and its results are compared with the verified query's results. The selected queries are held out of the semantic view during the run so the model cannot copy known answers. The results page shows accuracy (% judged correct) and a regression count per run, with an "improve the semantic view" action. The evaluation is also exposed as SQL (`EXECUTE_AI_EVALUATION`, `GET_ANALYST_AI_EVALUATION_DATA`). — [Snowflake docs: evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)

**Databricks (Unity Catalog metric views + Genie)**
- Metric views define a KPI once, keep measures separate from dimensions, and are Unity Catalog securables. They are created with SQL DDL or in Catalog Explorer. — [Databricks docs: metric views](https://docs.databricks.com/en/metric-views); [UC semantics](https://docs.databricks.com/aws/en/uc-semantics)
- "Unity Catalog semantics" (page updated Nov 9, 2026) adds Domains, governed Pages that define business concepts, Wikis (Beta), and certification and deprecation marks. Certified assets steer Genie One toward the assets the organization vouches for. Databricks calls this "modeled knowledge" and combines it with "learned knowledge" extracted from assets and usage. — [UC semantics](https://docs.databricks.com/aws/en/uc-semantics)
- Genie spaces (now "Genie Agents") are built from UC data, example SQL, plain-text instructions and trusted assets. Instructions and example SQL live under Configure > Context. There is a limit of 50 tables or views, and a space that uses metric views cannot mix in other table types. — [Genie set-up/trusted assets](https://docs.databricks.com/genie/trusted-assets)
- Trusted assets are parameterized example queries or UC SQL functions. An answer produced by one is labelled "Trusted". A third-party blog says metric-view answers are also marked Trusted, which conflicts with the official docs. — [Databricks docs](https://docs.databricks.com/genie/trusted-assets); contradicted by [element61](https://element61.be/en/node/44551)

**Power BI / Fabric**
- "Prep data for AI" has three tools. AI data schema chooses which tables and columns the AI can see. AI instructions are free-text business context. Verified answers are human-approved visuals triggered by phrases and can carry filters. After all three, the model can be marked "Approved for Copilot". Q&A must be turned on first. — [MS Learn: prep data for AI](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai); [verified answers](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai-verified-answers); [instructions](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-prepare-data-ai-instructions)
- AI instructions cannot disable Copilot features or force which features it calls. Microsoft's docs disagree on whether authoring is Desktop-only; newer pages say both Desktop and the service. — [MS Learn FAQ](https://learn.microsoft.com/en-gb/power-BI/create-reports/copilot-prepare-data-ai-faq)

**ThoughtSpot (Spotter)**
- There are two coaching tools. Reference questions are a sample question plus a verified answer in search-token syntax. They guide reasoning but are not deterministic. Business terms are a global word-to-definition mapping, the most rigid form of coaching, and ThoughtSpot recommends them only as a "last resort". The docs warn against coaching date terms globally because "this quarter" may need a different date column depending on context. — [ThoughtSpot docs: coaching options](https://docs.thoughtspot.com/cloud/latest/spotter-coaching-options); [business terms](https://docs.thoughtspot.com/cloud/26.5.0.cl/spotter-business-terms); [coach/not coach](https://docs.thoughtspot.com/cloud/26.2.0.cl/spotter-coach-not-coach)

**Looker (LookML + Gemini Conversational Analytics)**
- The agent picks fields, filters, sorts and limits, and Looker compiles the SQL from LookML. Admins can add custom instructions, golden queries, business glossaries and persona frameworks. Google's own tests claim the semantic layer cuts gen-AI query data errors by up to two thirds (vendor claim). An upgraded agent was announced in Preview at Next '26 and can be published into Gemini Enterprise. — [Looker docs](https://docs.cloud.google.com/looker/docs/2610/conversational-analytics-overview); [Google blog](https://cloud.google.com/blog/products/data-analytics/grounding-analytical-ai-agents-with-lookers-trusted-metrics); [Next '26](https://cloud.google.com/blog/products/business-intelligence/looker-updates-for-agentic-bi-at-next26)

**Tableau Pulse / Tableau Agent**
- A metric definition holds the core metadata. A metric is a definition with filter and time choices applied. Users follow metrics, not definitions. Only Creator or Explorer-publish roles can create definitions; Viewers follow metrics and see insights. Insights are generated automatically, ranked by usefulness, and grouped into configurable bundles. — [Tableau help: create metrics](https://help.tableau.com/current/online/en-us/pulse_create_metrics.htm); [Pulse intro](https://help.tableau.com/current/online/en-gb/pulse_intro.htm)
- Tableau Agent in Pulse (June 2026) never asks the LLM to compute or query. A deterministic Pulse Insight Service computes over the governed definitions, and the LLM only explains the result (vendor description). Since Nov 20, 2025, metrics link to their data source. — [Tableau blog](https://www.tableau.com/es-es/blog/tableau-pulse-enhanced-qa); [Release notes](https://help.tableau.com/current/online/en-us/pulse_intro.htm)

**dbt Semantic Layer**
- Saved queries are MetricFlow nodes in the DAG and can be exported to tables. The dbt MCP server exposes semantic-layer tools including `list_saved_queries`, which lists and searches saved queries along with their metrics, dimensions and filters. — [dbt saved queries](https://docs.getdbt.com/docs/build/saved-queries); [dbt MCP tools](https://docs.getdbt.com/docs/dbt-ai/mcp-available-tools)
- dbt open-sourced MetricFlow under Apache 2.0 as the reference implementation for OSI. — [dbt blog](https://www.getdbt.com/blog/the-osi-spec-updates)
- dbt (a vendor) claims accuracy approaches 100% for questions the semantic layer covers. When a question needs too many entity hops, the semantic layer says so instead of guessing. — [dbt blog 2026](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)

**Cube**
- D3 launched June 2, 2025 as agentic analytics on the Cube semantic layer, with agents querying through "Semantic SQL". In Oct 2025 the D3 name was dropped and the product was merged into Cube Agentic Analytics (GA). — [Cube blog](https://cube.dev/blog/announcing-cube-d3); [SiliconANGLE](https://siliconangle.com/2025/06/02/semantic-data-layer-startup-cube-automates-analytics-ai-agents); [Cube blog](https://cube.dev/blog/cube-agentic-analytics)

**Omni**
- "Learn from conversation" reads a chat where a user explained business rules and proposes YAML model edits (descriptions, synonyms, `ai_context`). The user accepts, edits or rejects them in a review modal. Auto-learn is on by default. — [Omni docs](https://docs.omni.co/ai/learn-from-conversation)
- "Suggestions" turns thumbs-down feedback into a prioritized (P1/P2) list of model improvements. Each suggestion links to the chats that caused it, and a Modeling Agent drafts the YAML. An AI usage dashboard shows the negative-feedback queries. `ai_context` can be set at model, topic, view and field level. Omni's advice is to start from real questions and save them as `sample_query`, and to mine Slack threads for answers already given. — [Omni suggestions](https://docs.omni.co/ai/suggestions.md); [improve AI quality](https://docs.omni.co/guides/ai/improve-ai-answer-quality); [Omni blog](https://omni.co/blog/tuning-for-smarter-ai-in-omni)

**Lightdash**
- Verified answers save a good agent response so recurring questions get the same answer. "Reviews" (Beta) scans agent turns for likely-wrong answers and proposes one-click fixes to the semantic layer or project context. The Metrics Catalog is searchable and shares its curation with agents, so approved metrics are what agents retrieve. "Spotlight" visibility is set in `lightdash.config.yml` (default hide, then show selected metrics). It controls display only and is not access control. — [Lightdash conversational analytics](https://www.lightdash.com/conversational-analytics); [AI agents docs](https://docs.lightdash.com/guides/ai-agents); [Metrics catalog](https://www.lightdash.com/metrics-catalog)

**Metric trees**
- Mixpanel metric trees are a visual "five whys". Deterministic trees are built from formulas such as Revenue = Users x ARPU and support precise root-cause analysis and forecasting. — [Mixpanel blog](https://mixpanel.com/blog/metric-trees-benefits-guide/); [Mixpanel docs](https://docs.mixpanel.com/guides/guides-by-use-case/empower-your-team/close-strategy-execution-gap.md)
- An Amazon Science paper extends metric decomposition into a recursive metric-tree framework for multi-level root cause analysis. — [Amazon Science PDF](https://cdn.amazon.science/bc/dd/f39d8aaf426db95869d76eb2f52b/scipub-approval152134-47263635-a-unified-approach-to-interpretable-causal-root-cause-attribution.pdf)

### Inferences
- The standout UX patterns are: (a) **verified queries doubling as an eval suite**, with accuracy and regression count shown per run (Snowflake); (b) **feedback turned into a proposed model diff** that a human reviews (Omni, Lightdash Reviews, Snowflake optimize); (c) **definition vs. instance**, where people follow a filtered metric and do not edit the definition (Tableau); (d) **deterministic compute, LLM narrates** (Tableau, Looker, Cube Semantic SQL); (e) **a certified/trusted label on the answer itself**, not only on the asset (Genie "Trusted").
- Strata already has receipts and drift warnings. No vendor found here shows a per-metric "receipt" that is as explicit about double counting, so that looks like a real differentiator worth keeping visible.

### Gaps
- I did not research Hex (semantic models, threads), Zenlytic, GoodData, Honeydew or AtScale within the tool budget. No sourced findings for them.
- I found no sourced vendor feature for a "metric diff on change" or "impact preview" (dependent dashboards and questions affected) beyond lineage. It may exist in dbt or Looker (content validator) but this research did not verify it.
- Snowflake "suggested verified queries" from query history is covered here only through Autopilot's example-SQL ingestion. Any standalone suggestion feature was not verified.

## 2. How business users teach and correct metrics

### Takeaway
Teaching happens on four levels, from most rigid to softest. Global term mappings (business terms, synonyms) come first, then verified/golden question-to-query pairs, then free-text instructions, then implicit learning from usage and feedback. The 2026 trend is that feedback becomes proposed model edits that a modeler approves, rather than silent self-learning.

### Cited Findings
- Rigid vs. soft coaching: ThoughtSpot treats business terms as rigid and "last resort", and reference questions as reasoning examples that are not deterministic. — [ThoughtSpot](https://docs.thoughtspot.com/cloud/latest/spotter-coaching-options)
- Verified/golden pairs exist in every product: Snowflake verified queries, Genie trusted assets and example SQL, Power BI verified answers (trigger phrases + visual + filters), Looker golden queries, Lightdash verified answers. — sources in section 1
- Free-text instructions: Genie instructions, Power BI AI instructions, Looker agent instructions, Omni `ai_context`. — sources in section 1
- Feedback to model edits: Omni Suggestions (thumbs-down to P1/P2 edits, linked to chats), Omni Learn from conversation, Lightdash Reviews (one-click fixes), Snowflake optimize (verified queries to new filters and definitions). — [Omni](https://docs.omni.co/ai/suggestions.md); [Lightdash](https://docs.lightdash.com/guides/ai-agents); [Snowflake](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/analyst-optimization)
- Query-history mining: Snowflake SVA learns metrics and filters from query history and Tableau assets. Databricks Genie One blends "learned knowledge" from assets and usage. — [Snowflake blog](https://www.snowflake.com/en/blog/semantic-view-autopilot/); [UC semantics](https://docs.databricks.com/aws/en/uc-semantics)

### Inferences
- Human review of every learned change is now standard (Omni review modal, Modeling Agent draft "may differ from the proposal"). This fits Strata's certify-with-owner model: learned changes should arrive as proposals on a metric, not as silent edits.
- ThoughtSpot's warning about global date terms suggests synonyms should be scoped to a context (per metric or per entity) and not applied globally by default.

### Gaps
- I found no sourced usage stats on how often business users, as opposed to analysts, actually coach these systems.

## 3. How trust is shown

### Takeaway
Trust signals cluster around certification or deprecation marks on assets, a "Trusted" or "verified" label on individual answers, the owner, a link to the source, and (rarely) a measured accuracy score. Freshness and usage counts were not prominent in the sources found.

### Cited Findings
- Certification and deprecation in Unity Catalog steer Genie toward vouched-for assets. — [UC semantics](https://docs.databricks.com/aws/en/uc-semantics)
- Genie labels an answer "Trusted" when it comes from a trusted asset. — [Databricks](https://docs.databricks.com/genie/trusted-assets)
- Power BI "Approved for Copilot" is a model-level mark. — [MS Learn](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai)
- Lightdash catalog curation equals what agents retrieve. Spotlight is display-only. — [Lightdash](https://www.lightdash.com/metrics-catalog)
- Tableau metrics link to their data source (Nov 2025). Computation is deterministic and the LLM only explains. — [Tableau release notes](https://help.tableau.com/current/online/en-us/pulse_intro.htm); [Tableau blog](https://www.tableau.com/es-es/blog/tableau-pulse-enhanced-qa)
- Snowflake shows a measured accuracy % and regression count per evaluation run. — [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- A whitepaper argues that governed definitions plus version history and lineage are needed to tell a change in meaning apart from a change in performance. — [Colrows](https://colrows.com/whitepapers/definitions-foundation-causality-payload/) (vendor whitepaper)

### Inferences
- A per-metric "tested accuracy" badge (x of y verified questions pass) is something only Snowflake surfaces, and only at the semantic-view level. Showing it per metric would be a visible differentiator.
- Version history on a definition, shown next to a drift warning, answers the question "did the number move or did the meaning move?"

### Gaps
- I found no sourced vendor screens showing usage counts or freshness on metric cards (Atlan, Lightdash and others may have them; not verified).

## 4. User and analyst complaints

### Takeaway
The recurring problems are: definitions disagree across tools, setup is hard with a steep learning curve, lock-in and migration costs are high, pricing is per-seat, and LLMs invent business logic. Most evidence comes from vendor blogs and a few practitioner posts. Direct Reddit and HN complaint threads were not found.

### Cited Findings
- A practitioner defined net revenue in dbt MetricFlow, Cube, LookML and DataJunction over the same tables, and 3 of the 4 disagreed. — [HackerNoon](https://hackernoon.com/i-defined-the-same-business-metric-in-4-semantic-layers-3-of-them-disagreed)
- dbt Labs admits that a poorly implemented semantic layer can worsen the consistency problems it is meant to solve, and that migration cost and complexity cause lock-in. — [dbt blog: pitfalls](https://www.getdbt.com/blog/semantic-layer-pitfalls)
- Cost: the dbt Semantic Layer needs the dbt platform Starter plan at $100/user/month, while Cube has a free tier (comparison by Atlan, a third party). — [Atlan](https://atlan.com/know/ai-agent/semantic-layer/dbt-semantic-layer-vs-cube/)
- Kyvos G2 reviews: about 35 mention the learning curve and about 34 mention setup complexity. Cube's AWS Marketplace reviews also mention a learning curve. — [G2 Kyvos](https://www.g2.com/products/kyvos-semantic-layer/reviews); [AWS Marketplace Cube](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-i3zig43yuaytu)
- An HN commenter called having an LLM own business logic "madness" because a hallucinated filter can end up in revenue figures. Another argued that straight text-to-SQL does not scale. — [HN thread](https://news.ycombinator.com/threads?id=tillvz)
- Omni lists text-to-SQL failure modes as domain metrics the LLM cannot interpret, non-determinism, and wrong joins. — [Omni blog](https://omni.co/blog/why-text-to-sql-fails) (vendor)
- Academic: curated semantic-layer documentation boosted first-shot accuracy by 17-23% across LLMs, and with a semantic layer the models' performance became statistically indistinguishable. — [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
- Fragmentation is widely recognized: 17 vendors signed OSI in 2025. — [Atlan](https://atlan.com/know/ai-agent/semantic-layer/dbt-semantic-layer-vs-cube/); [Snowflake OSI](https://www.snowflake.com/en/blog/open-semantic-interchanges-specs-finalized/)
- Product limits that frustrate users: a Genie space with metric views cannot mix in other tables, and the limit is 50 assets. — [Databricks](https://docs.databricks.com/genie/trusted-assets)

### Inferences
- The finding that the same metric gives different numbers in different tools is exactly what Strata's receipt plus export should address. A "cross-check" that runs Strata's SQL against the exported MetricFlow or SQL-view output would prove the export is faithful.
- The arXiv result (model choice matters less once a semantic layer exists) supports Strata running on cheap or local models.

### Gaps
- No primary Reddit r/dataengineering or r/BusinessIntelligence threads were retrieved. No Gartner or Forrester text was accessed (paywalled). There were no G2 reviews for LookML or AtScale.

## 5. Open source to borrow from

### Takeaway
MetricFlow (Apache 2.0, the OSI reference implementation) and Wren AI's MDL engine are the most directly reusable. OSI/Apache Ossie is the interchange format to target.

### Cited Findings
- OSI was launched in Sep 2025 by Snowflake, Salesforce and dbt. The v1 spec was published under Apache 2.0 on GitHub on Jan 27, 2026, covering datasets, metrics, dimensions, relationships and contexts. It has since moved to the Apache Foundation as Apache Ossie (Incubating). Version labels differ across sources (v0.1 vs v1.0). — [Snowflake](https://www.snowflake.com/en/blog/open-semantic-interchanges-specs-finalized/); [Tableau](https://www.tableau.com/blog/ending-semantic-drift-unified-business-logic-foundation); [Ossie updates](https://ossie.apache.org/updates/)
- Wren AI: MDL is a Git-friendly semantic layer (models, columns, relationships, views, cubes, metrics) on a Rust/DataFusion engine. The open core is Apache-2.0 and includes the MCP server and CLI. Row- and column-level security and the GenBI UI are commercial. The engine was merged into the main repo on 2026-05-07. — [Wren README](https://raw.githubusercontent.com/Canner/WrenAI/HEAD/README.md); [PyPI](https://pypi.org/project/WrenAI/)
- dbt MCP server (pip package `dbt-mcp`) shows how to expose semantic-layer tools to agents. — [PyPI dbt-mcp](https://pypi.org/project/dbt-mcp)

### Inferences
- Python-friendly options: MetricFlow is pip-installable and could serve as a second compiler to cross-check Strata's SQL. The dbt-mcp tool shapes (list metrics, dimensions, saved queries, query) are a good template for a Strata MCP server.

### Gaps
- Malloy, Cube core and Lightdash OSS internals were not researched in this pass.

## Ranked feature ideas for Strata's Semantic layer

1. **Verified questions as an eval suite with an accuracy badge** (borrowed from Snowflake Evaluations). Hold out each verified question, regenerate its SQL from the metric layer, compare result sets, and show "9/10 pass, 1 regression" per metric and per ontology. Re-run on every metric edit. *Who:* analyst/owner. *Why:* turns "trust me" into a measured number and catches regressions. **M**
2. **Feedback-to-proposal inbox** (Omni Suggestions, Lightdash Reviews). Thumbs-down, or a user saying "no, revenue excludes refunds", creates a proposed YAML/metric diff linked to the conversation. The owner accepts, edits or rejects, and accepting re-certifies. *Who:* business user teaches, owner approves. *Why:* teaching by business users without silent drift. **M**
3. **Learn metrics from query history and existing SQL** (Snowflake SVA, optimize). Paste or upload SQL (or a DuckDB query log). Strata extracts repeated aggregates and filters as candidate metrics, and adds valid queries as verified questions. *Who:* AI drafts, analyst confirms. *Why:* faster setup, a top complaint. **M**
4. **"Trusted" label on each answer, with the receipt one click away** (Genie Trusted). Every answer shows whether it came from a certified metric or verified question, or was improvised, and the improvised ones get a warning style. *Who:* business user. *Why:* trust at the point of use. **S**
5. **Metric versions and "meaning vs. number" diff**. Each certify stores a version. When a definition changes, show a before/after result on the same data (impact preview) and list the dependent verified questions and agents. Link this to the drift warnings. *Who:* owner. *Why:* stops silent redefinition, one of the conflicting-definitions complaints. **M**
6. **Deterministic metric tree with "explain this change"** (Mixpanel, Tableau Pulse). Decompose a metric by formula (Revenue = Orders x AOV) and by dimension, compute contributions in SQL, and let the LLM narrate only. *Who:* business user. *Why:* the most-requested "why did it move" question, without hallucinated math. **L**
7. **Scoped synonyms and term rigidity levels** (ThoughtSpot). Mark a synonym as global, per-entity or per-metric, and separate rigid "business terms" from soft "examples". Warn when a global term (like a date phrase) is ambiguous across columns. *Who:* analyst. *Why:* avoids the global-term trap. **S**
8. **Definition vs. followed instance** (Tableau Pulse). Users "follow" a certified metric with their own filters and time grain without forking the definition. Show "12 followers" as a usage and trust signal. *Who:* business user. *Why:* cuts metric sprawl because people stop copying metrics. **M**
9. **Export fidelity cross-check** (HackerNoon finding: 3 of 4 layers disagreed). After exporting to MetricFlow or SQL views, run both and compare outputs, then stamp the export "matches Strata". *Who:* analyst. *Why:* proves portability and reduces lock-in fear. **S-M**
10. **OSI/Apache Ossie import and export**. Read and write the OSI YAML so metrics move to and from Snowflake, dbt, Tableau and others. *Who:* platform/analyst. *Why:* lock-in is a top complaint and OSI has 17+ vendor backers. **M**
11. **Strata semantic MCP server** (dbt-mcp shape). Tools for list_metrics, get_receipt, query_metric and list_verified_questions, so outside agents answer through governed metrics. *Who:* developers and agents. *Why:* agents are the new consumers, and this is cheap to build in Python. **S-M**
12. **AI-visibility schema** (Power BI AI data schema, Lightdash Spotlight). Toggle which columns and metrics the AI may use, separately from access control, and show "Approved for AI" per ontology. *Who:* analyst. *Why:* cuts AI noise and wrong-column picks. **S**
