# Quality & Risk and Impact & Lineage for an Enterprise Context Platform (2025-2026)

Vendor bias note: almost all vendor material below comes from the vendors' own docs or blogs (Atlan, Collibra, Microsoft, Snowflake, Databricks, Tobiko/SQLMesh, DataHub). No independent source shows that any vendor "AI readiness" score predicts better agent answers. Where a source is a third-party blog, it is marked as such.

## 1. How to score context quality and AI readiness

### Takeaway
No vendor publishes a fixed formula. They all use the same pattern: a set of yes/no checks or rule pass-rates, each given a configurable weight, combined as a weighted sum or weighted average on a 0-100 scale and stored on the asset. Atlan scores whether metadata is present. Collibra's AI Trust Score is a weighted average of "themes". Purview averages rules and dimensions and rolls them up to data products. Strata should copy this pattern but use signals from its own data (whether claims are confirmed, drift, conflicts), not only whether metadata is present.

### Cited Findings
- **Atlan Metadata Completeness workflow.** Each component adds its configured points when its condition is met and adds nothing otherwise. Components: Description, Owner, Tag (with a "number of tags" threshold, default 1), Verified/Draft certificate, Resource link, Readme (scored separately above and below a character threshold), linked glossary Term (physical assets only), Linked asset and Related term (glossary terms only), plus any custom-metadata attribute in the form `CM name@@@Attribute@@@Score`. In-scope types are a list such as Table, Column, View, AtlasGlossaryTerm. Results are saved as custom metadata on each asset: the score, the missing metadata, and what contributed to the score. No default point values are published; the doc's example values (Description 10, Owner 15, Verified 10) are only illustrations. — [Atlan docs: Metadata completeness](https://docs.atlan.com/product/capabilities/discovery/references/metadata-completeness)
- Atlan's "score assets for AI readiness" MCP recipe checks each table for a description, owner, certification and PII classification, then writes an "AI Readiness" score to a custom metadata field. The user supplies the rubric and weights. The recipe suggests running the scoring on a schedule, as a gate before data enters a pipeline. — [Atlan MCP Cookbook](https://atlan.com/mcp-cookbook/score-assets-for-ai-readiness/)
- Atlan also offers a lakehouse "metadata completeness tracking" query: a governance scorecard of enrichment gaps across descriptions, tags, certifications, owners and custom metadata. — [Atlan docs: completeness tracking](https://docs.atlan.com/platform/lakehouse/references/metadata-completeness-tracking)
- **Collibra AI Trust Score (2026.08 docs).** Score = Σ(factor score × weight) / Σ(weights). Each factor scores 0-100, and a factor with weight 0 is left out. Weights are set per asset type. There are seven factors:
  - Documentation: owner assigned, description present, linked to related assets.
  - Lifecycle progress.
  - Risk rating, from the Risks & Safeguards assessment (use cases only).
  - Data Assets: at least one link of type inference, training or output.
  - Linked Technology Assets: the average trust score of linked models and agents.
  - Data integrity: lineage to training, inference or output data, plus whether linked data is classified as PII.
  - Linked versions score: the average of the versions' scores (default weight 1).
  
  Default weights are published only for the last factor. — [Collibra: AI Trust Score contributing factors](https://productresources.collibra.com/docs/collibra/2026.08/Content/AICommandCenter/ref_aicc-trust-score-inputs.htm); [Edit AI Trust Score settings](https://productresources.collibra.com/docs/collibra/2026.08/Content/AICommandCenter/ta_aicc-edit-trust-score.htm)
- **Collibra Unified Data Quality.** Weighted DQ scores let each monitor's importance shape the asset score (0-100). Each monitor belongs to a default dimension. An older (2023.04) scorecard method started at 100 and subtracted per dimension. — [Collibra: weighted DQ scores](https://productresources.collibra.com/docs/release-notes/Content/UnifiedDataQuality/co_about-weighted-data-quality-scores.htm); [Collibra 2023.04 scoring](https://productresources.collibra.com/docs/collibra/2023.04/Content/DataQuality/DQScorecards/Overview/Scoring.htm); [Collibra: 6 dimensions](https://www.collibra.com/blog/the-6-dimensions-of-data-quality)
- **Microsoft Purview.**
  - A column's DQ score is the average of the scores of its rules.
  - A data product's DQ score is the arithmetic mean of the scores of its assets.
  - The health report's overall score is the average of the dimension scores, and blank dimensions are left out.
  - Separately, "metadata quality" health controls let stewards write low-code checks on metadata. Passing checks feed health-control scores, and failures create "health actions" with Low, Medium or High severity. Category scores combine their controls and are shown against an adjustable target.
  
  — [Purview: DQ scores](https://learn.microsoft.com/en-gb/Purview/unified-catalog-data-quality-scores); [Purview: metadata quality](https://learn.microsoft.com/en-us/purview/metadata-quality); [Purview: DQ health report](https://learn.microsoft.com/en-us/purview/data-quality-health-report); [Purview: DQ thresholds](https://learn.microsoft.com/en-us/purview/unified-catalog-data-quality-threshold)
- **Academic.** SciHorizon (arXiv 2503.13503, Mar 2025) assesses AI-ready scientific data on 4 dimensions (Quality, FAIRness, Explainability, Compliance) split into 15 sub-dimensions. — [arXiv 2503.13503](https://arxiv.org/abs/2503.13503v1). "Data Readiness for Scientific AI at Scale" (arXiv 2507.23018) uses a 2-D framework: Data Readiness Levels (raw to AI-ready) × processing stages. — [arXiv 2507.23018](https://arxiv.org/abs/2507.23018?context=cs). Majithia et al., "An actionable framework for AI-ready data" (AI Magazine, 2026) gives guidance to data publishers, not a numeric score. — reported via search result; DOI 10.1002/aaai.70054 (not opened)
- No search surfaced a published Alation, Informatica, Snowflake Horizon or Databricks "AI readiness" formula. (Gap: these were not searched in depth.)

### Inferences
- A practical model for Strata, per concept, metric or field, as a weighted average with configurable weights in the same style as Collibra and Atlan: `readiness = Σ w_i·s_i / Σ w_i`, where each s_i is 0-100. The signals, with candidate weights:
  - Documentation present: description, owner, synonyms. Weight 15.
  - Mapping coverage: the share of the concept's attributes mapped to real columns. Weight 15.
  - Evidence: the share of AI claims confirmed by data. Weight 25.
  - Consistency: 100 minus a penalty per open conflict. Weight 15.
  - Freshness: decays with days since last validation or profiling. Weight 10.
  - Certification: certified metric with no drift = 100, drifting = 50, none = 0. Weight 10.
  - Usage and answerability: the share of agent questions touching this concept that were answered. Weight 10.
  
  The weights are a suggestion, not taken from any source. Store the missing items and the contributors next to the score, as Atlan does, so the UI can show what would raise it.
- Roll up the way Purview does (field → concept → ontology/data product by arithmetic mean), and leave out blank dimensions instead of scoring them 0.

### Gaps
- Default weights are not published by Atlan, Collibra (except one factor) or Purview.
- No validation evidence links readiness scores to agent accuracy.
- Alation, Informatica CLAIRE and Databricks/Snowflake readiness scoring were not checked.

## 2. Conflict detection: duplicate or conflicting terms, metrics, and ontology vs data

### Takeaway
The most reliable approach has layers. First, normalise and compare metric formulas structurally (SQL AST diff with sqlglot, plus column lineage of each formula). Then run value-based checks (run both definitions on the same slice and compare results). Use embeddings and LLMs only to find candidate pairs and to explain them, because LLMs miss many inconsistencies. For ontology logic, use SHACL shapes (pySHACL) for closed-world data checks and an OWL reasoner (HermiT via Owlready2) for satisfiability.

### Cited Findings
- **sqlglot `diff`** gives an "edit script" of AST operations (Insert, Remove, Move, Update, Keep). Unlike a text diff, it does not depend on formatting and can see moves and updates. — [Tobiko: detecting breaking changes](https://tobikodata.com/blog/automatically-detecting-breaking-changes-in-sql-queries); [sqlglot sql_diff post](https://sources.debian.org/src/sqlglot/28.6.0-1/posts/sql_diff.md)
- **SQLMesh classification rules.** Any Remove, Move or Update is breaking. An Insert is breaking if it is a UDTF (e.g. `explode`, which changes row count) or if its parent is not a SELECT or another inserted node. The only non-breaking change is adding new projections. `SELECT *` is expanded before diffing. Users can override the category. Planned work: treat reordered AND predicates as non-breaking, and use column lineage to classify per downstream model. — [Tobiko blog](https://tobikodata.com/blog/automatically-detecting-breaking-changes-in-sql-queries)
- The sqlglot `lineage` module builds a lineage graph for one output column from a query plus a schema. DataHub uses sqlglot for column-level lineage across BigQuery, Snowflake and other warehouses. — [sqlglot lineage.py](https://sources.debian.org/src/sqlglot/27.7.0-1/sqlglot/lineage.py); [DataHub SQL parsing](https://docs.datahub.com/docs/lineage/sql_parsing.md)
- **LLM limits.** A Dec 2025 benchmark of inconsistency detection inside documents, including a metric-definitions task, found that the best models still miss almost half of the inconsistencies, and performance drops as documents get longer. — [arXiv 2512.18601](https://arxiv.org/pdf/2512.18601v1) (from search summary; not opened in full). LLMs are better at spotting mistakes in definitions than at confirming a definition is correct. — [arXiv 2607.06004](https://arxiv.org/pdf/2607.06004)
- **ContraGen** (arXiv 2510.03418) generates synthetic enterprise contradictions for evaluation and detects them with NLI models plus LLM reasoning, combined by confidence-weighted hybrid scoring. — [ContraGen](https://arxiv.org/html/2510.03418v1)
- A CEUR-WS paper proposes LLM-assisted harmonisation of conflicting definitions in ontology glossaries. — [CEUR-WS Vol-4177 paper2](https://ceur-ws.org/Vol-4177/paper2.pdf) (not opened)
- **Vendors.**
  - OvalEdge has a "Business Glossary Accelerator with conflict detection" recipe that flags formula conflicts for the same metric across reports. The page returned 404 when fetched, so this is a search snippet only. — [OvalEdge marketplace](https://marketplace.ovaledge.com/recipe/business-glossary-accelerator-with-conflict-detection-418e1765-1695-4622-a4d2-7e7e6e552897)
  - Atlan has a "glossary-metric link check" skill that audits glossary terms against the metrics that compute them. — [Atlan skill](https://atlan.com/skills/glossary-metric-link-check.md)
  - Atlan's marketing describes "Nexus", a Terms & Metrics Linkage agent that links columns to terms and aims to resolve conflicting metric definitions. — [Atlan data glossary](https://atlan.com/data-glossary)
  - Collibra positions certified business definitions as the trust control for agents. — [Collibra: business context definitions and trust](https://collibra.com/learn/context-governance-controls-for-ai-agents/business-context-definitions-and-trust)
- **Ontology consistency.** Owlready2 runs HermiT and Pellet (Java) from Python. HermiT gives a fast consistent/inconsistent answer, and Pellet gives explanations of the problem axioms. One toolchain notes these reasoners accept only RDF/XML. pySHACL (on rdflib) checks SHACL shape constraints, and some libraries combine both. — [pygraft-gen consistency checking](https://orange-opensource.github.io/pygraft-gen/concepts/consistency-checking); [Ontologies with Python, ch.7](https://www.oreilly.com/library/view/ontologies-with-python/9781484265529/html/502592_1_En_7_Chapter.xhtml); [Semantica validator (third-party summary)](https://instagit.com/semantica-agi/semantica/semantica-ontology-validator-shacl-enforcement/)

### Inferences
- A suggested pipeline for Strata's "two revenues" problem:
  1. **Candidate pairs.** Find pairs by name or synonym match, by embedding similarity of name plus description (for example cosine ≥ 0.85, a threshold to tune), or because the metrics share a concept link.
  2. **Structural compare.** Parse each formula with sqlglot, run `qualify` and `optimize` to normalise it (expand aliases, canonicalise predicates), then compare four things:
     - aggregate function
     - measure column lineage (the set of source columns)
     - filter predicates
     - grain and time column
     
     Label the result Identical, Equivalent (same after normalising), Variant (same measure, different filter or grain), or Different.
  3. **Value check.** Run both definitions on the same period and dimensions in DuckDB. Treat the pair as a match if the results agree within a tolerance (for example 0.5%). Otherwise record the gap and the breakdown by dimension where the difference sits.
  4. **LLM explanation.** Give the model the structural diff and the value gap, and ask for a one-line plain-English explanation and a recommendation: merge, rename one (e.g. "Gross revenue" vs "Net revenue"), certify one and deprecate the other, or keep both and add a scoping note. The LLM is a narrator here, not the detector, because of the benchmark results above.
- **Ontology vs data.** Express ontology claims (cardinality, keys, value ranges, required relationships) as SHACL shapes or plain SQL checks against the data. Strata's "data disagrees" flag already does this. Formalising it as shapes makes it reusable and exportable.
- **Resolution workflow.** Every conflict gets a status (open, accepted variant, merged, deprecated), an owner, and a link to the affected downstream items (section 4). Context packs keep conflicting fields out while the status is open.

### Gaps
- No vendor documents its conflict-detection algorithm in detail. OvalEdge and Atlan describe it only at the feature level.
- No published benchmark exists specifically for detecting duplicate or conflicting metric definitions.

## 3. Gap identification: undocumented fields, unmapped columns, unanswerable questions

### Takeaway
Gaps come from two places. The first is static coverage, i.e. what is missing from the metadata. Atlan stores a "missing metadata" list for each asset, and Purview raises "health actions" when checks fail. The second is runtime demand: questions that agents could not answer. Snowflake Cortex Analyst groups frequent questions that match no verified query and proposes them as suggestions for a human to review. That is the closest product version of a log of unanswerable questions.

### Cited Findings
- Atlan's completeness workflow stores "missing metadata" next to the score for each asset. — [Atlan docs](https://docs.atlan.com/product/capabilities/discovery/references/metadata-completeness)
- Purview metadata-quality checks that fail create health actions with a severity. — [Purview metadata quality](https://learn.microsoft.com/en-us/purview/metadata-quality)
- **Snowflake Cortex Analyst suggestions.**
  - Snowflake reviews recent SQL query history to find frequently used or missing elements of the semantic view.
  - Frequent questions that match no verified query are grouped and proposed, up to 10 suggestions.
  - Eligible questions must appear in the Cortex Analyst monitoring tables (which include Cortex Agents) and be asked often.
  - Users accept, edit or dismiss each suggestion; nothing is applied automatically.
  - Preview since 9 Oct 2025.
  
  — [Snowflake: verified query suggestions](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-suggestions); [release note](https://docs.snowflake.cn/release-notes/2025/other/2025-10-09-verified-query-suggestions); [VQR](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository)
- ABISS (arXiv 2607.23340, Jul 2026) gives an 8-category taxonomy of ambiguous and unanswerable questions. It separates schema-level from domain-level knowledge gaps and notes that most systems still generate SQL anyway. — [ABISS](https://arxiv.org/pdf/2607.23340)
- "Query Carefully" (arXiv 2512.21345) adds explicit no-answer rules and few-shot unanswerable examples. When the model detects an unanswerable question, it explains why and suggests how to improve. — [arXiv 2512.21345](https://arxiv.org/pdf/2512.21345)
- A practitioner report on a dbt semantic-layer benchmark: questions needing unmodelled joins scored 0% because the layer declined to answer, and the author argues a visible gap beats a silent wrong number. Modelling the schema alone raised text-to-SQL accuracy from 64.5% to 90.0%. (Third-party blog.) — [HackerNoon](https://hackernoon.com/why-better-schema-modeling-beats-better-text-to-sql-models)

### Inferences
- Strata coverage metrics, each computed from its own data:
  - Field documentation coverage = described fields / all fields.
  - Mapping coverage = mapped columns / profiled columns, plus a list of orphan columns (in the data, not in the ontology).
  - Concept grounding = concepts with at least one confirmed claim / all concepts.
  - Metric coverage = concepts with a certified metric / concepts that have numeric measures.
  - Answerability = answered agent questions / all agent questions.
- **Unanswerable-question log.** For each refusal or low-confidence answer, log the question, the concepts it was linked to, and an ABISS-style category for why it failed: missing concept, missing mapping, missing metric, ambiguous term, conflicting definition, or data absent. Group similar questions with embeddings, rank the groups by frequency, and show the top gaps as suggested fixes. This follows Snowflake's pattern: group, cap the list, and have a human accept it. It also fits the user's "suggestions from real data" rule.

### Gaps
- No vendor publishes a formula for an answerability or coverage metric. The ABISS taxonomy categories were not retrieved in full.

## 4. Impact analysis and end-to-end lineage

### Takeaway
The building blocks are standard. OpenLineage events, with a ColumnLineageDatasetFacet that maps each output column to the input columns it came from, flow into Marquez or DataHub. Column lineage parsed from SQL comes from sqlglot. dbt selectors (`state:modified+`, exposures) find what sits downstream in a dbt project. Unity Catalog keeps `system.access.table_lineage` and `column_lineage` for one year. Vendors (Atlan) now extend the impact "blast radius" to AI agents and show it inside PRs. For Strata, lineage must cover more steps than these tools: ontology concept → mapping → column → metric → report or context pack → agent answer. The same graph traversal then answers "what breaks if this changes".

### Cited Findings
- **OpenLineage.** OpenLineage added `ColumnLineageDatasetFacet` with OpenLineage 0.9.0, first in the Spark integration. For each output column it lists the input-dataset columns used to produce it. The current spec page is labelled 1.50.0. — [OL column lineage blog](https://openlineage.io/blog/column-lineage/); [OL facet spec](https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet/)
- **Marquez.** Marquez 0.27.0 exposes column lineage through its API, including as a graph. Spark support comes out of the box. — [Marquez column lineage demo](https://marquezproject.ai/blog/column-lineage-demo). A 2026 blog (secondary) says the OL dbt integration parses compiled SQL to get column lineage. — [datalakehousehub](https://datalakehousehub.com/blog/2026-05-openlineage-observability)
- **Unity Catalog.**
  - The system tables `system.access.table_lineage` and `system.access.column_lineage` keep a rolling one year of history.
  - Column lineage is captured "as much as possible", with known gaps, and information_schema tables are not captured.
  - UDF lineage appears in the UI only, not in the system tables.
  - Querying needs USE CATALOG on `system`, USE SCHEMA on `system.access`, and SELECT on the lineage tables.
  - Community advice for impact analysis: find downstream tables at table level first, then check column lineage, because `column_lineage` is most reliable for source-to-target derivation and less so for columns that are only referenced (e.g. in filters).
  
  — [Databricks lineage docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage.html); [Databricks community thread](https://community.databricks.com/t5/data-governance/incomplete-downstream-dependencies-in-system-access-column/td-p/162247)
- **dbt.**
  - `dbt build --select state:modified+` builds all downstream nodes, and `+N` limits the depth.
  - `dbt ls --select <node>+ --resource-type exposure` lists the dashboards (exposures) downstream of a node.
  - `dbt sl validate --select state:modified+` validates the semantic nodes affected by a change.
  
  These come from third-party guides and a dbt-labs agent-skill reference. — [dbt agent skill: evaluating impact](https://tessl.io/registry/dbt-labs/dbt-agent-skills/0.1.0/files/skills/using-dbt-for-analytics-engineering/references/evaluating-impact-of-a-dbt-model-change.md); [datachef](https://blog.datachef.co/the-missing-right-side-of-your-dbt-dag/). Whether exposures can depend directly on metrics was an open feature request. — [dbt-core #6057](https://github.com/dbt-labs/dbt-core/issues/6057)
- **Atlan (vendor claims).** Atlan calculates the blast radius of a schema change, including downstream AI agents, and shows it inside the GitHub or GitLab PR. Its MCP server lets agents query lineage before using data. Glossary updates propagate along lineage so that agents inherit the new definition. — [Atlan data lineage](https://atlan.com/data-lineage.md); [Atlan lineage impact analysis](https://atlan.com/know/data-lineage-impact-analysis/); [Atlan: lineage for AI answers](https://atlan.com/know/ai-agent/data-for-ai/data-lineage-for-ai/); [Atlan glossary](https://atlan.com/data-glossary)
- **Collibra.** Data integrity in the AI Trust Score depends on lineage links between agents or models and their training, inference and output data. For agent versions, lineage comes from the tools they call. — [Collibra trust score inputs](https://productresources.collibra.com/docs/collibra/2026.08/Content/AICommandCenter/ref_aicc-trust-score-inputs.htm)

### Inferences
- **Strata lineage graph.** Typed nodes: Concept, Attribute, Mapping, Column, Table, Metric (certified version), Report, ContextPack, Agent, Answer. Typed edges: maps_to, computes_from (from sqlglot lineage of the metric SQL), used_by, cites. For each agent answer, record which concepts, metrics and facts it cited. This fits Strata, because context packs already cite facts.
- **Impact query.** When something changes (a concept definition, a mapping, a metric formula, or source schema drift), run a BFS downstream and group the hits by type ("3 metrics, 2 packs, 1 agent, 14 past answers affected"). Then judge severity with SQLMesh-style rules on the metric SQL diff:
  - Breaking: Remove, Update or Move, or a change to cardinality or filters.
  - Non-breaking: a projection added.
  
  For a metric change, also run it on old data and report how much the value moves (Strata's drift detection already does this). Past answers that cited the changed metric get marked "may be stale".
- **OpenLineage export.** Emitting Strata's mapping and metric lineage as OpenLineage events (with the column lineage facet) would let Marquez, DataHub or OpenMetadata ingest it, with no Docker needed on Strata's side.

### Gaps
- No vendor documents how a change to a metric definition, rather than a schema change, triggers a downstream impact report.
- No independent check of Atlan's claims about impact on AI agents.
- Official dbt docs for exposures depending on metrics were not confirmed.

## 5. Open-source tools: licences and activity

### Takeaway
All the core pieces are permissively licensed Python or JVM tools that fit Strata's Python-only, pip-installable approach: sqlglot, pySHACL, Owlready2, and the OpenLineage client. The heavy catalog platforms (DataHub, OpenMetadata, Marquez) would only be export targets, not dependencies.

### Cited Findings
- **OpenMetadata.**
  - Licence: Apache-2.0.
  - Has native data contracts. 1.9.0 added metadata validations to contracts.
  - Latest release: one listing says 2.0.5 (8 Oct 2026); another says 2.0.2. The sources disagree.
  
  — [OpenMetadata GitHub](https://github.com/open-metadata/openmetadata); [OM releases](https://docs.open-metadata.org/latest/releases/all-releases); [OM 1.9.0](https://newreleases.io/project/github/open-metadata/OpenMetadata/release/1.9.0-release)
- **DataHub.**
  - Licence: Apache-2.0.
  - Contracts are supported through its governance features.
  - Column lineage is parsed with sqlglot.
  - Latest release: one source says v1.7.0.1 (Sep 2026), another says v1.6.0 (Apr 2026).
  
  — [modern-datatools comparison](https://www.modern-datatools.com/compare/datahub-vs-openmetadata); [DataHub SQL parsing](https://docs.datahub.com/docs/lineage/sql_parsing.md)
- **Marquez.** The reference backend for OpenLineage. One source lists v0.50.0 and says it still gets commits but no new tags as of September 2026. It has no first-party MCP server. — [decube comparison (third-party)](https://www.decube.io/post/open-source-data-catalog-comparison); [dev.to](https://dev.to/gowthampotureddi/openlineage-openmetadata-open-standards-for-lineage-and-cataloging-133n)
- Amundsen was reported archived on 10 Sep 2026. — [decube](https://www.decube.io/post/open-source-data-catalog-comparison) (third-party)
- sqlglot provides `diff` and `lineage`, and SQLMesh is built on it. — [Tobiko](https://tobikodata.com/blog/automatically-detecting-breaking-changes-in-sql-queries)

### Inferences
- Likely licences from general knowledge, to verify on PyPI or GitHub before relying on them: sqlglot MIT, pySHACL Apache-2.0, Owlready2 LGPL-3, SQLLineage MIT, OpenLineage Apache-2.0, Marquez Apache-2.0. The LGPL on Owlready2 matters when bundling, and HermiT needs a Java runtime, which may not fit the zip bundle. That makes pySHACL plus SQL checks the safer default.

### Gaps
- Licence files and current release tags for sqlglot, pySHACL, Owlready2, SQLLineage and Marquez were not confirmed this session.
- The sources disagree on release versions.

## 6. Recommendations for Strata

### Takeaway
Strata already has the strongest signal that vendors lack: whether claims are confirmed by the data. It should combine those confirmation results with metadata completeness, conflicts, drift and how often questions get answered, into a configurable readiness score that lists what is missing. It should add structural and value-based metric conflict detection, and a lineage graph that runs from concept to agent answer for impact analysis.

### Cited Findings
- Vendor pattern for scores (configurable weighted average, missing-items list stored per asset): [Collibra](https://productresources.collibra.com/docs/collibra/2026.08/Content/AICommandCenter/ref_aicc-trust-score-inputs.htm), [Atlan](https://docs.atlan.com/product/capabilities/discovery/references/metadata-completeness)
- Pattern for proposing gap fixes from logs, reviewed by a human: [Snowflake](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-suggestions)
- Pattern for classifying breaking changes: [Tobiko/SQLMesh](https://tobikodata.com/blog/automatically-detecting-breaking-changes-in-sql-queries)
- LLMs miss about half of inconsistencies, so they should not be the only detector: [arXiv 2512.18601](https://arxiv.org/pdf/2512.18601v1)

### Inferences
Each item should be built test-first and grounded in real data.
1. **Readiness score.** Compute a readiness score per concept, metric and ontology using the seven signals in section 1. Show the score and the top three missing items, each with a one-click fix. Leave out empty dimensions. Roll up by mean.
2. **Conflict engine.** Find candidate pairs by name, synonym or embedding. Compare them structurally with sqlglot (aggregate, lineage set, filters, grain), then run a DuckDB check on both values. Label each pair Identical, Equivalent, Variant or Different, and have the LLM write the explanation and the recommendation. Keep a conflict register with status and owner, and hold conflicting items out of context packs (this extends the current behaviour).
3. **Ontology checks.** Compile ontology constraints to SQL checks (already close to "data disagrees") with optional SHACL export. Use an OWL reasoner only if users bring OWL ontologies.
4. **Gap log.** Log every agent refusal or low-confidence answer with the concepts it linked to and a reason category. Group the log, rank by frequency, and show the gaps as suggested additions (concept, mapping, metric or synonym), each needing a human to accept it.
5. **Lineage and impact.** Keep typed edges from concept to agent answer. On any change, run a downstream BFS, give a breaking or non-breaking verdict with the size of the value change, and mark cited past answers as possibly stale. Optionally emit OpenLineage events for interoperability.
6. Weights and thresholds (0.85 cosine, 0.5% value tolerance, the weights in section 1) are proposals to tune on Strata's own data. They do not come from any source.

### Gaps
- No public evidence shows which weighting best predicts agent answer quality. Strata could measure this itself by correlating readiness with answer correctness in its benchmarks.
