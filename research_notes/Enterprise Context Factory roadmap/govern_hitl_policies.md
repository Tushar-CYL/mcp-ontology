# Govern step: human-in-the-loop validation, ownership, certification, lifecycle, KPI governance, machine-readable policies

Scope: how leading platforms (2025-2026) keep humans in control of AI-generated metadata, ontologies and metrics, and what a small team building "Strata" should build next. Strata already has an AI ontology with data checks and a % confirmed, user notes, ontology versions, and certified metrics with owner and drift alerts.

Vendor bias warning: almost every number below comes from the vendor that sells the feature (Atlan, Alation, Informatica, Snowflake). I found no independent benchmark of reviewer effort saved. Treat the numbers as rough guides, not results anyone has checked.

## 1. Risk-based / confidence-based human review (triage, thresholds, review by exception)

### Takeaway
The pattern everyone uses is "AI suggests, a steward accepts / edits / rejects, and the change is stamped as AI-made." Only Informatica documents a real confidence-threshold auto-accept band (80-100%). Atlan reports 60-70% acceptance of AI descriptions. No vendor publishes reviewer-hours saved with a method behind it.

### Cited Findings
- **Informatica CDGC (CLAIRE):** an admin sets an auto-accept threshold for glossary-term associations "from 80 to 100 inclusive". When auto-accept is on, a second, lower threshold (between 80 and the auto-accept value) sends matches to a manual accept/reject queue. Below that, nothing is suggested. The result is three bands: auto-apply / human review / drop. — [Informatica MCC Glossary association](https://onlinehelp.informatica.com/IICS/prod/MCC/en/metadata-command-center-administration/Glossary_association.html)
- CDGC gives a confidence score to every possible asset-to-term match. Abbreviation and synonym lookup tables raise scores and cut false positives. The setup example uses a 92% threshold. — [Informatica CDGC slides](https://www.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/How%20to%20Effectively%20Classify%20Assets%20and%20Associate%20Glossary%20Terms%20in%20CDGC.pdf); [Informatica success accelerator](https://success.informatica.com/success-accelerators/how-to-enable-claire-ai-for-data-classification-and-glossary-ass.html)
- **Atlan:** reported a 60% acceptance rate for AI description suggestions after 6 months of closed preview (2023). — [Atlan 2023 product roundup](https://humansofdata.atlan.com/2024/03/2023-product-roundup/). A later undated marketing page says 70% acceptance for first drafts of descriptions and READMEs. — [atlan.com/ai](https://atlan.com/ai.md)
- Atlan users accept, reject or edit suggestions. Each accepted change shows in the activity log with an "Updated using Atlan AI" stamp, the user and a timestamp. You need edit-metadata permission to use it. Bulk column-description runs write **without** a review step, are attributed to "Context Agent", and cannot be stopped once started. — [Atlan docs: use Atlan AI for documentation](https://docs.atlan.com/product/capabilities/atlan-ai/how-tos/use-atlan-ai-for-documentation)
- Atlan has a blog post on a feedback loop for improving context quality for humans and AI (usage signals fed back into curation). — [Atlan blog: The Feedback Loop](https://blog.atlan.com/community/metadata-feedback-loop-context-layer/)
- **Collibra:** AI-suggested semantic-layer entities and attributes carry an AI icon and a "Ready for review" tag that stays until every suggestion is approved or rejected. Rejecting an entity also rejects its attributes. Stewards can drop all unapproved suggestions at once. — [Collibra semantic layer docs](https://productresources.collibra.com/docs/collibra/latest/Content/Catalog/GuidedStewardship/SemanticLayer/ta_semantic-layer.htm)
- Collibra column descriptions: the steward runs "Create Descriptions" on a table, then checks and edits each one. Saving a description is how it gets accepted. Existing descriptions are not overwritten unless the user chooses to. — [Collibra: create descriptions with Collibra AI](https://docs.collibra.com/Content/CollibraAI/ta_auto-desc-bulk.htm)
- Collibra "Governance by design" smart checks (e.g. a minimum description length) are rules an admin sets, and the AI writing assistant helps stewards meet them. — [Collibra blog](https://www.collibra.com/blog/governance-by-design-automatically-enforce-standards-with-the-ai-powered-writing-assistant-smart); [Collibra toolkit docs](https://productresources.collibra.com/docs/collibra/latest/Content/Assets/LifecycleMgmt/co_gov-by-design-toolkit.htm)
- **Alation:** ALLIE AI Suggested Descriptions, built from table metadata only. Stewards approve, regenerate or edit, and can leave feedback on a suggestion. On by default since 2024.1.4. — [Alation docs](https://docs.alation.com/en/latest/steward/AISuggestedDescriptions/AISuggestedDescriptions.html). Alation marketing claims "six weeks of manual curation in 15 minutes", with no method given. — [Alation agentic governance page](https://www.alation.com/DGQ3)
- **Palantir Foundry:** ontology changes go through "proposals" (like pull requests) on branches. Reviewers approve or reject each resource or all of them, and can comment with reasons. Protected branches need at least one approval. A merged proposal cannot be reverted automatically. Proposals are off by default. — [Palantir: review ontology proposals](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/); [Palantir: ontology proposals](https://palantir.com/docs/foundry/ontologies/ontologies-proposals)
- **Snowflake:** Cortex Analyst suggests relationships and "verified queries" from the query history. Evaluations treat the verified queries as ground truth and report "regressions" (questions that used to be correct and now fail). Semantic View Autopilot builds semantic views automatically from existing queries and BI assets. — [Snowflake optimization release note Dec 2025](https://docs.snowflake.com/release-notes/2025/other/2025-12-02-cortex-analyst-optimization); [Cortex Analyst evaluations](https://docs.snowflake.com/ja/user-guide/snowflake-cortex/cortex-analyst-evaluations); [Semantic View Autopilot blog](https://www.snowflake.com/en/blog/semantic-view-autopilot/)
- **Databricks Unity Catalog:** bulk certification/deprecation automations (beta) can, for example, deprecate tables with no reads or writes in 30 days and email the owners. — [Databricks certify/deprecate docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-discovery)
- **Research:** arXiv 2506.08422 reports LLM F1 0.97 against 0.68 for human annotators on an ontology-classification task. Where they disagreed, the LLM often caught human mistakes. The authors propose auto-accepting high-confidence predictions and flagging the unclear ones for experts. — [arXiv 2506.08422](https://arxiv.org/pdf/2506.08422)
- OE-Assist (arXiv 2507.14552): 1,393 competency questions checked by two ontology engineers with LLM help. Human performance **dropped when the LLM gave wrong guidance** (automation bias). — [arXiv 2507.14552](https://arxiv.org/html/2507.14552v1)
- A systematic review (Semantic Web Journal) names hybrid LLM+human workflows and standard benchmarks as the main open problems in LLM ontology engineering. — [SWJ systematic review](https://semantic-web-journal.net/node/4039)

### Inferences
- The best-documented design to copy is Informatica's three-band triage: auto-apply above X, a review queue between Y and X, drop below Y. Strata's "% confirmed" could then be split into "auto-confirmed by checks" and "human-confirmed".
- Automation bias (OE-Assist) means a review screen should not show the AI answer as the default without its evidence. Show the data check result (row counts, sample values, the % of rows that match) next to every suggestion, so the reviewer is checking evidence and not just the model's answer.
- Busy Finance users should review exceptions only: items with low confidence, failing data checks, high impact (used by a certified metric or many downstream objects), or conflicts with an existing confirmed item. The usual review styles are Atlan's per-item accept/edit/reject and Collibra's "reject the parent, reject the children". Palantir's batch proposal approval lets one reviewer approve many changes at once. All of these keep the number of clicks low.
- Every AI write should carry provenance (who or what wrote it, when, from which run), as Atlan stamps it. Bulk writes without review (Atlan Context Agent) are a known risk. They need an undo.
- Snowflake's "verified queries + regression count" is an ongoing check: once a human confirms a question/answer pair, every later ontology or metric version is re-tested against it.

### Gaps
- No independent or peer-reviewed numbers on reviewer hours saved, or on acceptance rates broken down by confidence band. The Atlan 60/70% figures are vendor-reported and don't say what counts as "accepted".
- I found no paper that sweeps calibrated confidence thresholds for routing LLM ontology output to human review.
- I didn't research Purview's and Unity Catalog's AI-suggested description approval flows in detail. Atlan and Collibra both document per-item accept/reject.
- No active-learning implementations (where reviewer decisions retrain the suggester) are documented by these vendors, apart from Alation's feedback capture and Informatica's synonym tables.

## 2. Ownership, certification/endorsement, versioning, lifecycle and approval workflows

### Takeaway
The usual model is two or three trust badges (promoted/endorsed, certified, deprecated, sometimes "master data"). Anyone can request a badge, but only named domain reviewers can grant it. Approval is "any one" or "all" approvers. Lifecycle uses deprecation dates that warn first and break later. Change control is done as branches and proposals (Palantir) or contracts and versions (dbt).

### Cited Findings
- **Unity Catalog:** the governed tag `system.certification_status` has the values `certified` and `deprecated`. Deprecated assets show a restricted icon. Applying the tag needs ASSIGN permission on it. It is supported on catalogs, schemas, tables, views, volumes, functions, models, dashboards and notebooks. Metric views are **not listed**. — [Databricks: certify/deprecate](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-discovery). An Azure page marked Beta uses the different names `system.Certified` / `system.Deprecated`, so the two sources conflict. — [Microsoft Learn: certify/deprecate](https://learn.microsoft.com/azure/databricks/data-governance/unity-catalog/certify-deprecate-data)
- **Fabric/Power BI:** three endorsement badges: Promoted (anyone with write access), Certified (anyone can request, only reviewers named by an admin can certify, with reviewers set per domain), and Master data (data items only, authorized reviewers only). **Copilot prefers certified and promoted semantic models** when answering, and there is also an "Approved for Copilot" setting on semantic models. — [Fabric endorsement overview](https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview); [Endorse Fabric items](https://learn.microsoft.com/en-us/fabric/fundamentals/endorsement-promote-certify)
- **Microsoft Purview Unified Catalog:** publish workflows for data products and glossary terms with "Pending on all" or "Pending on any" approval. A business domain must be published before its data products can be. Critical data elements are added automatically from the product's assets. Approval workflows for CDE and OKR publishing appear on a roadmap as "In planning" (not confirmed shipped). — [Purview workflows](https://learn.microsoft.com/is-is/Purview/unified-catalog-workflows); [Purview publish data products](https://learn.microsoft.com/zh-tw/purview/section3-publish-data-products); [Purview roadmap PDF](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/final/en-us/microsoft-brand/documents/MS-Purview-Data-Governance-Roadmap.pdf)
- **Palantir:** the reviewer list is for tracking and does not restrict who can approve. Editors and owners can approve, including their own changes. A community thread says there was no first-class way to require proposals for all ontology changes. — [Palantir review proposals](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/); [Palantir community](https://community.palantir.com/t/requiring-proposals-for-all-ontology-changes/950)
- **dbt model governance:** contracts (enforced column names, types and constraints, checked before build), model versions, access levels, and `deprecation_date`. Referencing a deprecated or past-date model gives a warning that can be turned into an error. The usual migration is to publish v2 next to v1, set a deprecation date on v1, and remove v1 once consumers have moved. — [dbt model governance docs](https://docs.getdbt.com/docs/mesh/govern/about-model-governance?version=1.12); [Xebia deprecation_date tip](https://xebia.com/blog/dbt-quicktip-using-deprecation-date-to-improve-your-model-governance/); [dbt 1.6 upgrade notes](https://docs.getdbt.com/docs/dbt-versions/core-upgrade/Older%20versions/upgrading-to-v1.6)
- **ODCS (Bitol, Linux Foundation) v3:** a contract has 11 sections: fundamentals, schema, data quality, pricing, team, roles/security, SLA, infrastructure, support, business rules (authoritative definitions) and custom properties. v3.1.0 adds relationships, predefined quality rules (nullValues, missingValues, invalidValues, duplicateValues, rowCount) and scheduled SLA checks (cron). — [Bitol v3 announcement](https://bitol.io/odcs-version-3-transforming-data-contracts-with-enhanced-flexibility-integration-and-global-collaboration/); [Bitol v3.1.0](https://bitol.io/?p=302); [datacontract.com ODCS](https://docs.datacontract.com/open-data-contract-standard)
- Tools that import ODCS do not always enforce it. In OpenMetadata and Collate, a contract run does **not** check SLA values, only quality and schema. — [OpenMetadata ODCS](https://docs.open-metadata.org/v2.0.x/how-to-guides/data-contracts/odcs); [Collate spec](https://docs.getcollate.io/ai-2-0/how-to-guides/data-contracts/spec)

### Inferences
- Strata already has owner + certified + drift alerts on metrics. What's missing compared with the market: (a) a separate lighter "endorsed/promoted" tier so the gap between draft and certified isn't so big; (b) a "deprecated" state with a replacement pointer and a deprecation date; (c) request → reviewer approval with "any/all" rules; (d) one reviewer group per domain (Finance, R2R, P2P).
- Fabric's "Copilot prefers certified models" is the key link between governance and agents. Strata's agents and context packer should rank or limit sources by certification state and say which state they used in every answer.
- Semantic versioning can follow dbt's contract logic: a breaking change (removed or renamed property, changed metric formula or grain) gives a new major version with a deprecation window. Adding things is a minor change. Text/description edits are a patch. A contract check (like dbt's) can sort the change type automatically.
- ODCS is a good exchange format for import and export, but don't promise that its SLAs are enforced unless Strata runs the checks itself.

### Gaps
- No vendor documents fixed deprecation-window lengths (e.g. 30/90 days) as a standard. It's a policy choice.
- I did not check Atlan's certificate states (Verified/Draft/Deprecated) or Alation's trust flags (Endorsed/Warning/Deprecated) in primary docs this session. They are widely known but not cited here.

## 3. KPI & metric governance (certification, calculation lineage, conflicting definitions)

### Takeaway
Metric governance runs on the same badges and permissions as tables (UC metric views as securable objects, Fabric certified semantic models, Snowflake semantic views under RBAC), plus Git-based definitions (dbt MetricFlow YAML) and "verified question → SQL" sets used as regression tests. I found no platform that automatically settles conflicting KPI definitions. Conflicts are prevented by having one governed definition per name and an owner, not by tooling.

### Cited Findings
- Databricks metric views are "reusable SQL objects that define and govern business KPIs" and are Unity Catalog securable objects governed by standard privileges. — [Unity Catalog semantics](https://docs.databricks.com/aws/en/uc-semantics)
- Snowflake semantic views sit on top of physical tables and are governed by role-based access and masking. Verified queries pair a natural-language question with the expected SQL, and the optimizer mines them to improve the semantic view. Evaluations report regressions. — [Snowflake semantic views (Snowsight)](https://docs.snowflake.com/en/user-guide/views-semantic/ui); [Snowflake optimization](https://docs.snowflake.com/en/ja/user-guide/snowflake-cortex/cortex-analyst/analyst-optimization); [AtScale glossary (third party)](https://snowflake.atscale.com/glossary/snowflake-semantic-views/)
- dbt metrics moved to MetricFlow YAML in v1.6. Governance (contracts, versions, deprecation) applies to models, and search results did not show versioning or deprecation for metrics themselves. — [dbt 1.6 upgrade](https://docs.getdbt.com/docs/dbt-versions/core-upgrade/Older%20versions/upgrading-to-v1.6)
- Fabric: certified semantic models (where measures live) get priority from Copilot, with per-domain certifiers. — [Fabric endorsement](https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview)
- Purview lists OKR / metric approval workflows only as planned. — [Purview roadmap](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/final/en-us/microsoft-brand/documents/MS-Purview-Data-Governance-Roadmap.pdf)

### Inferences
- Strata's "certified metric + owner + drift" already matches the core of the market. Next steps: (1) attach verified question/answer pairs to each certified metric and re-run them on every ontology or metric version (Snowflake-style regression count); (2) show the calculation lineage as metric → formula → ontology properties → source columns → data checks; (3) detect conflicts: when the AI proposes a metric whose name or synonym matches a certified one but whose formula or filter differs, send it to the owner as "variant of X" and don't create a second "Revenue".
- Metric versioning should follow the dbt pattern (a formula change is a new version, with the old one deprecated by a date), because dbt doesn't version metrics itself.

### Gaps
- Not researched this session (call budget): Cube, AtScale, and Looker (LookML certification / Git-PR workflow) mechanisms, and the dbt Semantic Layer / dbt Catalog's own "certified" metadata. These still need primary sources.
- No source found that quantifies how often conflicting KPI definitions occur, or how much it costs.

## 4. Policies & business rules in machine-readable form (SHACL, ODRL, OPA, DMN, contracts, checks)

### Takeaway
2025-2026 research shows LLMs can turn natural-language rules into SHACL shapes that are close to complete, but with expert editing (the remaining errors mostly come from vague wording). Products put rules either in the ontology as condition→action (Fabric IQ + Activator) or in data contracts and checks (ODCS quality rules). The practical path is: natural-language rule → LLM drafts an executable check → run it on real data → a human confirms the rule text, the code and the evidence → rule versioned with an owner.

### Cited Findings
- AutomationML study (arXiv 2506.10678): GPT-4 turned text constraints into SHACL shapes that were "near-complete" and needed only minor expert edits, mostly because the natural-language rules were underspecified. — [arXiv 2506.10678](https://arxiv.org/html/2506.10678v1)
- Text2SHACL (Leuphana master's thesis, 2025): LLM-generated SHACL for social-benefit eligibility rules, motivated by the manual effort of converting rules by hand. — [Leuphana thesis](https://pubdata.leuphana.de/entities/publication/05d20e2a-6e2a-49df-a73f-0612831f0b05)
- PolicyKG (listed as arXiv 2608.09028, Aug 2026): sorts each policy sentence into obligation / permission / prohibition (86.9% accuracy) and generates SHACL (F1 0.866 on 69 shapes). Only seen on an aggregator. Check it on arXiv before relying on it. — [opentrain.ai listing](https://www.opentrain.ai/papers/policykg-an-agentic-llm-pipeline-for-translating-institutional-policies-into-sha--arxiv-2608.09028/)
- LLM4ODRL (arXiv 2506.03301): generates ODRL usage policies from natural-language instructions, using SHACL shapes as context or validators. — [arXiv 2506.03301](https://www.arxiv.org/pdf/2506.03301)
- Fabric IQ ontology: entity types, relationships, properties, and condition→action rules through Fabric Activator. Business rules and constraints live in the ontology so agents can take "safe, auditable actions". Fabric IQ became GA in June 2026, with Ontology still in preview. — [Fabric IQ overview](https://learn.microsoft.com/fabric/iq/overview); [Fabric blog: what's next for Fabric IQ Ontology](https://community.fabric.microsoft.com/t5/Fabric-Updates-Blog/What-s-next-for-Fabric-IQ-Ontology-The-operational-context-that/ba-p/5172145)
- ODCS v3.1 predefined quality rules (nullValues, invalidValues, duplicateValues, rowCount…) are described by Bitol as runnable by any compliant tool. Contracts also have a business-rules / authoritative-definitions section. — [Bitol v3.1.0](https://bitol.io/?p=302)
- Collibra smart checks are admin-defined rules on metadata quality (e.g. description length). — [Collibra governance by design](https://productresources.collibra.com/docs/collibra/latest/Content/Assets/LifecycleMgmt/co_gov-by-design-toolkit.htm)

### Inferences
- For "cancelled orders are not revenue", store three linked artifacts: (1) the natural-language rule with an owner, a version and a status; (2) an executable form. For Strata's DuckDB stack the simplest is a SQL predicate / check ("count of revenue rows where status='Cancelled' = 0") or a filter baked into the metric definition. SHACL is useful if the ontology is exported as RDF; (3) evidence, meaning the last check run (pass/fail, violating row count, sample rows). The human confirms all three together, not just the text.
- Use the deontic split (obligation / permission / prohibition) from PolicyKG as a simple type field on rules. It maps to check types: must-exist, may, must-not.
- For agents, expose rules as context ("business rules as context") **and** as guardrails checked after generation: before an answer goes out, check that the SQL or metric used respects the rules that apply (e.g. the cancelled filter is present). Fabric's framing (rules in the ontology so agent actions are auditable) supports this.
- Heavy standards (SWRL, Drools, DMN, OPA/Rego) only make sense when Strata needs access policy (OPA) or decision tables (DMN). For a small team, SQL checks plus optional SHACL/ODCS export cover most of the value.

### Gaps
- Not researched this session: OPA/Rego, DMN/Drools, Great Expectations/Soda as rule targets, and Palantir AIP Logic. I have no cited mechanism details for these.
- No production numbers on the accuracy of turning natural-language rules into executable checks in finance domains.

## 5. Business hierarchies governance (chart of accounts, cost centres, product hierarchy)

### Takeaway
Finance hierarchies are governed as versioned trees, changed through multi-step change requests with approval policies per dimension, then published to downstream systems (Oracle EDM pattern). This is stricter than metadata governance because a hierarchy change moves reported numbers.

### Cited Findings
- Oracle EDM: complex changes that need several inputs and approval before commit go through change requests. — [Oracle EDM docs](https://docs.oracle.com/en/cloud/saas/enterprise-data-management-cloud/dmcaa/fcgl_edm_edmuser_steps_100x2d572d48.html)
- Account hierarchies are trees with one or more versions, used to track change over time. — [Oracle Financials maintenance hierarchies](https://docs.oracle.com/en/cloud/saas/financials/24b/faigl/maintenance-hierarchies.html); [Oracle ERP blog](https://blogs.oracle.com/erp-ace/post/structure-your-account-hierarchies-for-optimal-processing-and-reporting)
- Approval policies can be set per dimension. One customer had separate policies for BS, PL and STAT accounts on the GL_ACCOUNT dimension. — [Oracle community](https://community.oracle.com/customerconnect/discussions/tagged/213-request-changes/p4)
- Steps to push to the GL: import the modified chart of accounts → check the tree versions → publish. — [Oracle EDM GL steps](https://docs.oracle.com/en/cloud/saas/enterprise-data-management-cloud/dmcaa/fcgl_edm_fcgluser_steps_100x2dcef6c2.html)
- Oracle DRM (the older product) has a formal version lifecycle. — [Oracle DRM version life cycle](https://docs.oracle.com/en/applications/enterprise-performance-management/11.2/drmuy/mdmserver_version_life_cycle.html)

### Inferences
- Strata should treat a hierarchy as a versioned object with an effective-from date. A change request shows the diff (moved nodes, new or removed leaves) plus its **impact on certified metrics**, i.e. how much each KPI moves when the new version is applied to current data. The request then goes to an approver per dimension (e.g. the controller for P&L accounts).
- Approval routing by sub-tree (BS vs PL) is a cheap way to avoid sending everything to one busy person.

### Gaps
- SAP MDG, Informatica MDM hierarchy workflows, and cost-centre / product-hierarchy specifics were not researched. There are no numbers on hierarchy change frequency.

## 6. Concrete recommendations for a small team (Strata)

### Takeaway
Build "review by exception" on top of what exists: confidence bands plus data-check evidence feed one review queue, ranked by impact. Add trust tiers and deprecation. Make rules first-class objects (text + check + evidence). Put verified question sets as regression tests on certified metrics. Have agents prefer certified context.

### Cited Findings (basis)
- Three-band auto-accept / review / drop — [Informatica](https://onlinehelp.informatica.com/IICS/prod/MCC/en/metadata-command-center-administration/Glossary_association.html)
- AI provenance stamp and accept/edit/reject — [Atlan](https://docs.atlan.com/product/capabilities/atlan-ai/how-tos/use-atlan-ai-for-documentation)
- "Ready for review" until resolved, and cascading reject — [Collibra](https://productresources.collibra.com/docs/collibra/latest/Content/Catalog/GuidedStewardship/SemanticLayer/ta_semantic-layer.htm)
- Batch proposals with per-resource approval — [Palantir](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/)
- Certified content preferred by AI, with per-domain certifiers — [Fabric](https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview)
- Verified queries as regression tests — [Snowflake](https://docs.snowflake.com/ja/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- deprecation_date warns, then errors — [dbt](https://docs.getdbt.com/docs/mesh/govern/about-model-governance?version=1.12)
- Automation bias in LLM-assisted review — [OE-Assist](https://arxiv.org/html/2507.14552v1)

### Inferences (suggested build order)
1. **Review queue by exception.** Every AI item gets a score = model confidence × data-check pass rate. Auto-confirm above a threshold the admin sets (start strict, e.g. only if every data check passes and confidence ≥ 0.9). Queue the middle band. Hide or drop the bottom band. Rank the queue by impact (used by a certified metric, number of downstream objects, row volume). Show "N items need you; M were auto-confirmed by checks" in place of a raw % confirmed. Keep auto-confirmed items reversible and sample-audited: send a random ~5% to reviewers to measure the false auto-accept rate. The 5% is a design suggestion, not from a source.
2. **Evidence-first review card.** Show the check evidence (sample rows, % match, failing rows) before the AI's claim. Offer one-click accept / edit / reject with a reason, plus "reject parent → reject children". Log reviewer decisions as labels. This builds an acceptance-rate dataset per item type and confidence band, which gives Strata its own numbers (none of the vendors publish real ones).
3. **Trust tiers and lifecycle.** Draft (AI) → Confirmed (human or checks) → Endorsed (domain user) → Certified (named owner). Add Deprecated, with a replacement pointer and a sunset date. Warn before the date and block after. Use semver on ontology and metric versions: a changed formula or grain, or a removed property, is a major version.
4. **Domain owners and approvers.** Owners per domain or sub-tree (Finance/R2R/P2P, BS vs PL). Requests use "any" or "all" approval. Self-approval only where the role allows it.
5. **Rules as first-class objects.** Natural-language rule → LLM-drafted SQL check (optional SHACL/ODCS export) → run on data → human confirms text + check + evidence → owner, version, schedule. Agents receive the rules as context and are checked against them after generation.
6. **Metric regression set.** Each certified metric gets 3-10 verified question→answer pairs, re-run on every new ontology, metric or hierarchy version. Show regressions next to drift alerts.
7. **Conflict detector.** A new metric or term whose name or synonym matches a certified one but whose formula differs is sent to the owner as a "variant", not created as a duplicate.
8. **Hierarchy change requests** with a diff and the impact on KPIs before approval.
9. **Agents prefer certified context** and name the trust tier of each source in their answers (Fabric Copilot pattern).

### Gaps
- Threshold values, sampling rate and number of tiers are design choices. No benchmark supports specific numbers. Strata should measure them from its own review logs.
