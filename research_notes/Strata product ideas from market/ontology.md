# Ontology layer: market features, UX patterns, complaints, and ideas for Strata (research as of 2026-11-20)

Scope note: this covers about 18 searches and fetches. Most sources are vendor docs and blogs, which are biased toward the vendor's own product. Independent user evidence (G2, PeerSpot, Gartner Peer Insights) exists for Palantir. I found little independent evidence for the other vendors. Reddit and Hacker News searches returned no usable threads.

## 1. What do the leading products offer, and which UX patterns stand out?

### Takeaway
The 2025-2026 market has settled on a small set of patterns: (a) generate a first draft automatically from what already exists (semantic models, tables, queries, dashboards), then ask humans to review it; (b) PR-style proposals or branches with per-change review and a preview on real data; (c) a split between a small set of "modeled", certified definitions that must be exact and a large set of "learned" ones that are ranked by authority; (d) an agent that edits the ontology from chat and shows its reasoning, plus a "test the ontology" step that writes sample questions and runs them against the bound data. Visual canvases still exist (metaphactory), but the newer products put the agent, review queues and test questions first.

### Cited Findings
**Palantir Foundry / AIP**
- Ontology proposals now run on Foundry Global Branching. Creating a branching proposal automatically creates an ontology proposal, and merging the branch triggers the ontology merge. Legacy "ontology branches" are being retired. — [Palantir: Test changes in the ontology](https://palantir.com/docs/foundry/ontologies/test-changes-in-ontology); [Ontology proposals legacy](https://palantir.com/docs/foundry/ontologies/ontology-branches-legacy/)
- Foundry Branching went to beta on all enrollments from the week of 12 May 2025, off by default. Ontology proposals are disabled by default and an admin turns them on in Control Panel. — [Palantir announcements 2025-04](https://palantir.com/docs/foundry/announcements/2025-04/); [Branching the ontology](https://palantir.com/docs/foundry/ontologies/branching-ontology/)
- Proposal review screen: the Proposals page has five tabs (My proposals / Assigned to me / In review / Merged / Closed). Inside a proposal there are four tabs. **Overview** shows changes grouped by author and task, plus reviewers. **Preview status** shows which object types are indexed on the branch, so their data can be tested before merge. **Review changes** lets reviewers approve or reject each task, one at a time or in bulk, with a comment on each. **Changelog** is a timeline of who changed what and when. Each task maps to one ontology resource. Approving usually requires editor or owner rights on that resource. With ontology roles, viewers can suggest changes on a branch. — [Palantir: Review ontology proposals](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/)
- The "kinetic" ontology has two parts. Action types define the set of changes users can make to objects, properties and links, and they capture operator input. Functions hold server-side business logic. Actions can be called from Object Explorer (search), Object Views (reusable 360 views in standard, full and panel forms), Workshop apps and the API. — [Palantir Ontology overview](https://palantir.com/docs/foundry/ontology/overview/); [Explore action types](https://palantir.com/docs/foundry/action-types/explore-action-types/); [Actions on interfaces](https://www.palantir.com/docs/foundry/action-types/actions-on-interfaces)
- On 2025-09-30, TypeScript v1 functions became usable on branches. Branching covers code repositories, Pipeline Builder, Ontology Manager and Workshop. — [Palantir announcements 2025-09](https://www.palantir.com/docs/foundry/announcements/2025-09); [Supported functionality](https://palantir.com/docs/foundry/foundry-branching/supported-functionality)

**Microsoft Fabric IQ Ontology (preview)**
- The building blocks are entity types, properties, relationships (typed and directional, with cardinality) and entity instances. Entity types carry data bindings. Static bindings must come from OneLake and are set before time-series bindings (eventhouse or lakehouse). Bindings can run data-quality checks for nulls, ranges and uniqueness. Rules run through Fabric Activator as condition-action rules. Public MCP endpoints are listed as "coming soon". — [Fabric IQ ontology overview](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview); [How to bind data](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-bind-data); [Create entity types](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-create-entity-types)
- "Generate Ontology" button on a Power BI semantic model. It creates entity types from tables, properties and bindings from columns, relationship types from model relationships, and **metrics from DAX measures**. The user must still do these by hand: bind time series, review entity keys (especially multi-key), bind relationship types to data, rename to friendly names, and review the whole ontology. — [MS Learn: Generate ontology from semantic models (updated 2026-11-17)](https://learn.microsoft.com/en-us/fabric/iq/ontology/concepts-generate)
- **Ontology agent with an "Act" mode**: the user asks in plain language to add a second semantic model. The agent reconciles overlapping tables (for example a shared customer table), avoids duplicate entities, and "summarizes what it did and exposes its reasoning steps, including how it resolved conflicts". A **"Test the ontology"** suggestion makes the agent write representative questions, run them as DAX against the bound data, and show results. The docs say: "If a result is blank or a query fails, verify the source data and bindings." — [same page](https://learn.microsoft.com/en-us/fabric/iq/ontology/concepts-generate)

**Databricks Genie Ontology (GA announced 11 Nov 2026)**
- **Modeled knowledge** is "the comparatively small set of definitions that must be exact": Unity Catalog Metric Views (certified KPIs), Domains and Pages. **Learned knowledge** is auto-generated "Ontology Snippets" from dashboards, SQL queries, notebooks and Power BI models. Snippets refresh as their sources change and inherit the source's permissions. — [Databricks: Announcing GA Genie Ontology](https://databricks.com/blog/announcing-ga-genie-ontology)
- **OntoRank** (inspired by PageRank) ranks knowledge on source authority, certification, the expertise of the people behind it, popularity and recency, and uses this to resolve conflicting definitions. Org directory and activity signals (who creates, shares and uses assets) add weight. — [same](https://databricks.com/blog/announcing-ga-genie-ontology)
- **Ontology Manager (beta, "coming soon")** is planned to offer: an ontology health score and major gaps; "high-impact opportunities" such as thin domain coverage or concepts that are asked about often but have no governed definition; promoting learned knowledge into authoritative Pages from a **review queue**; an interactive entity graph; and a per-domain hierarchy view. Each Page has a named owner. "Bulk import Pages" drafts them from Confluence, Slack, Google Docs or GitHub. Citations show a snippet's source, author and **why it was trusted**. — [same](https://databricks.com/blog/announcing-ga-genie-ontology)
- Conflict: one source says GA on 11 Nov 2026, while the Databricks docs reportedly still said Public Preview (Sept 2026). A practitioner argues it is "an authority-ranked enterprise context layer, not a formal ontology." Its benchmark (28 questions) is the vendor's own. — [Atlan on Genie Ontology](https://atlan.com/know/ai-agent/databricks/genie-ontology/); [letsdatascience news](https://letsdatascience.com/news/databricks-makes-genie-ontology-generally-available-with-new-97e18246) (Atlan is a competitor, so it is biased)

**Stardog (Voicebox / Designer)**
- Voicebox for Designer is an agent that guides users through creating an ontology, mapping sources and aligning the model to a use case. — [Stardog docs: guided ontology creation](https://docs.stardog.com/voicebox/guided-ontology-creation-and-mapping/)
- Designer added **competency-question evaluation** (v0.21.0, 2 Oct 2025) and **SPARQL generation for competency questions** (v0.22.0, 16 Oct 2025), so the model is tested against the business questions it must answer. Mapping generation was improved in v0.20.2 (Aug 2025). — [Stardog Voicebox release notes](https://docs.stardog.com/release-notes/stardog-voicebox)
- Provenance on answers: Voicebox labels whether an answer came from RAG, code execution, an external LLM or a direct KG query. "Hallucination-free" is a vendor claim. — [Stardog news Sept 2025](https://www.stardog.com/news/stardogs-hallucination-free-answer-engine-brings-ai-insights-to-high-stakes-industries/); [Stardog 2025.2](https://community.stardog.com/t/whats-new-in-stardog-2025-2-11-1/5385)

**Timbr (SQL ontology / virtual KG)**
- The ontology is exposed as a virtual SQL schema in which concepts are tables, over JDBC/ODBC, with no ETL. Relationships replace JOINs ("up to 90% shorter queries", a vendor claim). It offers runtime inference, governed measures with metric inheritance and OLAP-style cubes inside the ontology. Models can be built visually, in SQL DDL, or imported from catalogs, OWL or ERD tools. — [Timbr FAQ](https://timbr.ai/timbr/); [What are SQL ontologies](https://timbr.ai/what-are-sql-ontologies/); [Atlan on Timbr](https://atlan.com/know/ai-agent/semantic-layer/timbr-semantic-layer/)

**metaphactory (metaphacts)**
- A visual ontology editor for domain experts whose visual language maps to OWL and SHACL. It has Git-backed versioning, an Ontology Catalog (import, metadata, search), and a newer "modeling agent" that runs quality checks and recommends classes. Mostly pre-2025 material, so possibly dated. — [metaphactory 4.0](https://metaphacts.com/metaphactory-4-0); [Semantic knowledge modeling](https://metaphacts.com/product/semantic-knowledge-modeling)
- OntoInk (research, arXiv 2026): a form-based SHACL shape editor where you pick a target class and add constraints (path, cardinality, datatype, pattern). — [arXiv OntoInk](https://arxiv.org/pdf/2610.05945)

**Neo4j LLM Knowledge Graph Builder**
- The schema can be predefined, taken from an existing DB, or LLM-suggested from text (`POST /populate_graph_schema`). The neo4j-graphrag pipeline has an `EXTRACTED` mode (derive the schema once, then extract) and a `FREE` mode, followed by a pruner, an **entity resolver that merges similar entities**, and a writer. Neo4j itself says quality is higher when users configure the node and relationship types. — [neo4j-graphrag KG builder guide](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html); [llm-graph-builder GitHub](https://github.com/neo4j-labs/llm-graph-builder)

### Inferences
- "Generate, then show me what you couldn't do" is now standard. Fabric's explicit list of manual follow-ups (keys, relationship bindings, friendly names) is a good model for a Strata **post-build to-do list**.
- Strata's "% confirmed against data" goes further than any vendor feature I found. Fabric has binding data-quality checks and "test the ontology", but neither gives a per-claim verdict. Strata should lead with this.
- Palantir's per-task review with "preview on branch data" is the most mature correction UX. It is heavy, and Palantir turns it off by default.

### Gaps
- Collibra, TopBraid EDG, data.world/ServiceNow, Atlan's ontology features, Graphwise/Ontotext, WebProtégé, Cognee and the Neo4j Data Importer were not researched in this pass because of the tool budget. From background knowledge, not verified: WebProtégé has threaded comments on entities and a change history; TopBraid EDG has working copies with workflows. Verify both before citing.
- The details of the Palantir Pilot product were not found.
- There are no independent screenshots or reviews of the Databricks Ontology Manager, which is not yet shipped.

## 2. How do business users teach and correct the ontology?

### Takeaway
There are three mechanisms: (1) **formal proposals** with per-change approve or reject and comments (Palantir); (2) **promotion queues**, where machine-learned knowledge is promoted to an owned, authoritative definition (Databricks); (3) **chat agents in act mode** that make the edits and explain their reasoning (Fabric, Stardog). Learning from usage shows up mostly as ranking signals (Databricks) and gap detection ("asked often, not defined").

### Cited Findings
- Palantir: viewers with ontology roles can suggest changes on a branch. Reviewers approve or reject per task and comment per task. — [Palantir review proposals](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/)
- Databricks: domain owners (Finance, Marketing) curate their own definitions. Stewards promote learned snippets into Pages from a review queue. The system "continuously learns and improves through usage". Snippets update when their source dashboards or queries change. The blog describes no direct end-user "this is wrong" button. — [Databricks GA blog](https://databricks.com/blog/announcing-ga-genie-ontology)
- Fabric: users correct through the ontology agent in Act mode, which shows its reasoning steps. — [MS Learn generate](https://learn.microsoft.com/en-us/fabric/iq/ontology/concepts-generate)
- Stardog: competency questions are a test harness the business writes and the model is checked against. — [Stardog release notes](https://docs.stardog.com/release-notes/stardog-voicebox)
- Thoughtworks (June 2026): use LLM pipelines to draft from schemas, APIs and wikis "so experts review rather than write from scratch". Require **competency questions as a funding gate**, tied to a decision or cost, and drop any concept that doesn't serve one. — [Thoughtworks: Why ontologies matter, fail, build anyway](https://www.thoughtworks.com/insights/blog/data-strategy/why-ontologies-matter-fail-build-anyway)
- Graphiti supports a "prescribed" ontology (Pydantic types defined upfront) and a "learned" one (structure comes from the data). Contradicting facts are invalidated, not deleted (bi-temporal `t_valid`/`t_invalid`). — [Graphiti custom entity types](https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types); [Graphiti GitHub](https://github.com/getzep/graphiti)

### Inferences
- Strata's plain-English notes are close to Fabric's Act-mode agent. The difference worth adding is showing the **diff and reasoning before applying**, and attaching each note to the claim it changed.
- "Contradiction invalidates but keeps history" (Graphiti) suits Strata's "data disagrees" flags. Keep the old claim with an end date instead of overwriting it.

### Gaps
- I found no vendor evidence of learning corrections from failed NL queries (thumbs-down feedback feeding the ontology), apart from Databricks' general "usage" claim.

## 3. How do they show trust?

### Takeaway
Trust is shown through **certification states** (Verified, Draft, Deprecated), **named owners**, **citations that explain why something was trusted**, **answer provenance labels**, **data-quality checks on bindings**, and **usage or popularity**. Nobody I found shows a per-claim "data confirms this" percentage the way Strata does.

### Cited Findings
- Atlan has four certificate states: Verified, Draft, Deprecated, none. Each can carry a message. A deprecation flags downstream assets for owner review, and dependents should never inherit Verified without an owner approving. Deprecated status moves to the top of the sidebar with its own icon. — [Atlan docs: add certificates](https://docs.atlan.com/product/capabilities/discovery/how-tos/add-certificates); [Atlan: what is data certification](https://atlan.com/know/ai-agent/ai-agent-governance/what-is-data-certification/); [Atlan release note](https://shipped.atlan.com/date/2025/4)
- Databricks Unity Catalog lets users flag tables as certified or deprecated, which feeds OntoRank. Genie citations show source, author and why it was trusted. — [Databricks certify/deprecate](https://docs.databricks.com/aws/en/data-governance/unity-catalog/certify-deprecate-data); [Databricks GA blog](https://databricks.com/blog/announcing-ga-genie-ontology)
- Stardog labels whether an answer came from the KG, RAG, code or an external LLM. — [Stardog 2025.2](https://community.stardog.com/t/whats-new-in-stardog-2025-2-11-1/5385)
- Fabric bindings check nulls, ranges and uniqueness. — [MS Learn bind data](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-bind-data)
- Palantir proposal changelog: who, what, when, linked to each resource. — [Palantir review proposals](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/)

### Inferences
- Strata could combine its "% confirmed" with an owner-set certificate. "AI-confirmed 94%" and "Certified by Finance" are separate signals and should be shown as two badges.
- Deprecation should **propagate** to the metrics, agents and KG queries that use the thing, so their owners review them (the Atlan pattern).

### Gaps
- I did not research how Collibra or data.world show trust scores or usage counts.

## 4. What do users and analysts complain about?

### Takeaway
The complaints are consistent: steep learning curve and vendor-specific vocabulary, high and opaque cost (Palantir), scope creep ("model everything first"), and above all **maintenance and drift**: the model goes stale once the business changes and nobody owns reconciliation. ROI is hard to show.

### Cited Findings
- Palantir: reviewers report a steep learning curve and Foundry-specific concepts even for SQL/Spark users, outdated docs, high startup cost, and opaque licensing. An AWS Marketplace listing shows a $100k/month subscription unit. Few reviews target the ontology itself, and some praise it as easy. These are anecdotal, individual reviews. — [PeerSpot: what needs improvement](https://peerspot.com/questions/what-needs-improvement-with-palantir-foundry); [G2 Foundry reviews](https://www.g2.com/products/palantir-foundry/reviews); [Gartner Peer Insights](https://www.gartner.com/reviews/product/palantir-foundry-2024460406); [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-a5m5xespbqyci)
- Thoughtworks (June 2026) names three failure modes: (1) a translation gap between ontology engineers and SMEs; (2) scope creep, where projects that model the whole business stall within a year; (3) maintenance neglect, "the one that actually kills the program", when every update takes weeks of debate. Without a steward and regular reconciliation, the model goes stale "within two quarters". — [Thoughtworks](https://www.thoughtworks.com/insights/blog/data-strategy/why-ontologies-matter-fail-build-anyway)
- Atlan calls drift "the silent technical failure mode" because nothing triggers re-validation. It cites "<15% of enterprises beyond pilot" and "67% of abandoned projects cite lack of graph expertise". Both numbers are secondhand and unverified, and Atlan is a vendor. — [Atlan: enterprise KG pitfalls](https://atlan.com/know/ai-agent/knowledge-graph/enterprise-knowledge-graph-pitfalls/)
- Stardog: "the business changes, the data changes, and the definitions drift." — [Stardog: 25 years in semantics](https://www.stardog.com/blog/25-years-in-semantics/)
- Academic (2026; 28 interviews plus 76 surveyed, agriculture domain): ROI is "uncertain or unquantifiable". — [White Rose eprints: Agrisemantics adoption](https://eprints.whiterose.ac.uk/id/eprint/240285/1/Agrisemantics%20%20The%20Current%20State%20of%20Adoption.pdf)
- Neo4j's own docs concede that LLM-derived schemas are lower quality than user-configured ones. — [neo4j-graphrag guide](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html)
- Zep Cloud caps custom ontologies at 10 entity types, 10 edge types and 10 fields per type (plan-dependent). — [Zep entity types](https://help.getzep.com/entity-types)

### Inferences
- Strata's checks against live data are an automatic re-validation trigger, which is the missing piece Atlan describes. A scheduled **drift re-check**, with a "what changed since last version" view, answers the top complaint directly.
- Time-to-value argues for competency questions plus a small first ontology, not a full-schema build.

### Gaps
- No Reddit or HN threads came up. G2 and TrustRadius reviews for Stardog, Timbr and metaphactory were not pulled.

## 5. Open-source tools worth borrowing UX from

### Takeaway
Graphiti (prescribed vs learned types, bi-temporal invalidation), OntoGPT/SPIRES (schema-driven extraction with LinkML as the schema language), and the Neo4j LLM Graph Builder (choose schema source, entity resolution step) are the most relevant to borrow from. WebProtégé and Cognee were not checked in this pass.

### Cited Findings
- OntoGPT uses LLM extraction grounded in an ontology. SPIRES is zero-shot extraction of nested structures, driven by a LinkML schema. OWL can be converted to LinkML with schema-automator. — [OntoGPT docs](https://docsearch.algolia.com/mcp/docs/repo/monarch-initiative/ontogpt)
- Graphiti uses Pydantic entity and edge types. Its pipeline is extraction, then validation against the model, then attribute population, then storage. — [Graphiti custom types](https://help.getzep.com/graphiti/graphiti/custom-entity-types)
- Neo4j builder: three schema sources (predefined, existing DB, LLM-suggested) and a merge-similar-entities resolver. — [llm-graph-builder](https://github.com/neo4j-labs/llm-graph-builder)

### Inferences
- LinkML is a cheap extra export and import format for a Python team (YAML, and it generates Pydantic, JSON Schema and SHACL).
- A Pydantic-typed internal model, like Graphiti's, would give Strata validation for free.

### Gaps
- WebProtégé (collaboration, comments), Cognee ontology grounding, and LinkML tooling details were not verified in this pass.

---

## Ranked feature ideas for Strata's Ontology layer

Each idea gives what it is, who uses it, why it matters, and the effort for a small Python/React team.

1. **Competency questions as the build input and the test suite** (M). The business user writes, or picks from AI suggestions based on the data, 5-15 questions the ontology must answer. Strata builds only the things those questions need, then runs each question against live tables and shows pass or fail. This copies Stardog Designer's CQ evaluation, Fabric's "Test the ontology" and Thoughtworks' funding gate, and it tackles the scope-creep and time-to-value complaints.
2. **Scheduled drift re-check with a "what changed" diff** (M). Strata re-runs its claim checks nightly or on demand. It shows the claims whose % confirmed dropped, the new columns or tables, and links that broke, then opens items in the review queue automatically. It is for stewards. This answers the top complaint (drift, staleness within two quarters, no re-validation trigger). Strata already has the checking engine and versions.
3. **Two-badge trust: AI-confirmed % plus a human certificate (Verified / Draft / Deprecated, with owner and message)** (S). The owner sets the certificate, and the data sets the %. Deprecating something flags the metrics, agents and KG queries that use it (Atlan pattern). This separates "the data agrees" from "the business signed off", and no competitor has the data half.
4. **Proposal-style change review for notes and AI edits** (M). Each plain-English note or AI edit becomes a proposal with a per-change diff, approve or reject per item, a comment per item, a changelog, and a "preview on live data" sample before merge. Business users suggest and an owner approves. This is the Palantir model, simplified: one page, no branching infrastructure.
5. **Post-build "what I could not do" to-do list** (S). After the AI build, Strata lists what it is unsure of: missing or multi-column keys, links with no join evidence, cryptic names it could not translate, and many-to-many tables. Each item is a one-click fix. This is the same as Fabric's manual follow-up list, made interactive, and it sets honest expectations.
6. **Agent edits show their reasoning and a diff before applying** (S-M). When a note says "merge Client and Customer", Strata shows the plan, the evidence (overlapping keys, % of shared values), and the diff, and the user confirms. This matches Fabric's Act-mode transparency and builds trust in AI edits.
7. **Gap finder from usage** (M). Strata logs the questions asked in KG, Context and Agents that hit concepts with no or weak definitions, and ranks them by how often they are asked (Databricks "frequently asked concepts without governed definitions"). Stewards then know what to model next. This turns adoption into upkeep of the ontology.
8. **Keep history on contradictions instead of overwriting** (S). When the data disagrees or a note overrides a claim, Strata closes the old claim with valid-from and valid-to dates and its reason (Graphiti bi-temporal pattern). Anyone can audit "why did this change?". It fits Strata's versions.
9. **Object 360 page per business thing** (M). One screen per entity instance: fields, linked things, the claims and their confirmation status, the owner, and recent changes. This is Palantir Object Views and Explorer at small scale, for business users. It makes the virtual KG tangible without a canvas. Keep it to one page, per the simple-screens rule.
10. **Entity resolution suggestions across tables** (M). Strata detects that `client`, `customer` and `account_holder` look like the same thing (shared key values, similar names) and proposes a merge with evidence. This copies Neo4j's resolver and Fabric's multi-model reconciliation, and it solves a common source of messy ontologies.
11. **LinkML export and import** (S). Add LinkML YAML to the OWL, RDF and Ossie exports. It plugs into OntoGPT, Pydantic and SHACL tooling with no extra effort, and is cheap reach into open-source users.
12. **Owner per domain plus delegated review** (S). Each group of business things has a named owner, and the review queue routes items to that owner (Databricks domain owners, Palantir resource-level approvals). This answers the stewardship gap that Thoughtworks calls fatal.

Bias note: the Palantir, Microsoft, Databricks, Stardog, Timbr and metaphacts material is vendor-authored. Atlan's pieces about Genie and Timbr come from a competitor. The only independent sources are the reviews on PeerSpot, G2 and Gartner, the Thoughtworks piece and the academic study.
