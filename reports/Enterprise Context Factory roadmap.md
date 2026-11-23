# Strata closes the Context Factory gaps

*Research report, 18 November 2026. Built from the five notes in `research_notes/Enterprise Context Factory roadmap/` and the earlier layer research in `docs/research/`. Where the two disagree, the newer notes win.*

## Summary for the manager

Strata already does most of what the "Enterprise Context Factory" slide asks for. It finds business things in the data. It checks each AI claim against the data. It certifies metrics. It sends cited facts to agents over MCP. That covers Engineer and Activate well, and Govern in part.

Three parts are missing. Discover reads only tables today. It does not read SQL logs, BI reports or documents. Quality has no single score per item and no check for two different "Revenue" definitions. Impact cannot yet say "if this changes, these metrics, packs and agents break."

The client's worries all have practical answers:

- **"Can we trust an ontology the AI made?"** Yes, if we do two things. We keep checking every AI claim against the data, which Strata already does. And we link each business thing to a world standard, such as schema.org, GS1 for products or FIBO for finance. The AI proposes, the standard supplies the name, the data shows whether it fits, and a person approves.
- **"Finance people have no time."** Then they should only see the hard cases. Items the data fully confirms are approved automatically. Items the data rejects are hidden. People review only the middle group, starting with the items that matter most.
- **"Can it really match our reports?"** We should prove it. We take three to five real Unilever or Kellogg's reports, turn each number into a question, and score Strata's answers against the report. This is how Databricks and Snowflake test their own tools.
- **"Do we need Neo4j?"** No. Strata's graph works on the live tables, with no copy and no licence. It loads 4.7 million records on a laptop in about 10 seconds. A graph database is worth buying only for very deep chains or graph algorithms, and the paid Neo4j edition has no public price.

**Next two weeks:** a report-accuracy test, a review-by-exception queue, a log of questions Strata could not answer, and better drill-down to child records in the graph.
**Next one to two months:** links to world standards, one quality score per item, a "two definitions disagree" check, an impact view, clearer trust levels with owners per domain, business rules that can be checked, and suggestions mined from SQL history.
**Later:** reading Power BI and Tableau files, reading policy documents, managing hierarchies with approvals, and logging decisions.

All of these fit inside the four layers and the agents. None needs a new main screen, Docker or a server.

## What the evidence says

Strata's main asset is one most vendors lack: **every AI claim is checked against the data**. Rivals mostly score whether metadata exists (Atlan, Collibra, Purview) or ship drafts with "please review" warnings (Fabric IQ, Snowflake Autopilot, Databricks AI comments). That matters for the meeting's first concern, because Microsoft still calls its generated ontology "a starting point" whose "names, keys, and relationship direction" need review ([Microsoft Learn](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology)). The gaps against the slide fall in three places. **Discover** reads only tables, while every peer also mines query history and BI files. **Quality** lacks a per-item readiness score and conflict detection. **Impact and lineage** do not exist yet. The roadmap below folds each gap into an existing layer and builds it from Python parts that are already proven: sqlglot for SQL parsing and lineage, DuckDB for value checks, pySHACL for optional shape export, and an LLM that writes explanations but does not decide. Nearly every accuracy and effort-saving number in this field comes from the vendor that sells the feature. Strata should quote none of them to clients and should produce its own numbers, starting with a test against real client reports.

## Strata already covers the core of the wheel

The slide's eight capabilities and five steps map onto Strata's four layers plus agents with little friction. The mapping table shows where each item belongs. Every new capability attaches to a layer that already exists, so the "simple screens" rule holds.

| Slide item | Strata layer it belongs to | Where it appears |
|---|---|---|
| 1 Discover (data, reports, SQL, BI, documents, policies, MDM) | Ontology (things, links, hierarchies); Semantic (metrics, filters from SQL and BI) | "Suggested from usage" next to the data-built suggestions |
| 2 Engineer (canonical structure, context graph) | Ontology + Knowledge graph | Existing build steps; standards mapping added to the ontology |
| 3 Govern (HITL, ownership, versioning, certification, lifecycle) | Shared across all layers; Ontology review queue; Semantic certification | One review queue shown inside each layer, not a new tab |
| 4 Quality (score, conflicts, impact, gaps) | Score as a badge on every item; conflicts in Semantic; gaps in Context | Trust Checker agent reads all of it |
| 5 Activate (APIs, MCP, context packs) | Context + Agents | Existing Context Pack v1 and MCP |
| Wheel: Discovery engine | Ontology | |
| Wheel: Context engineering | Ontology + Semantic + Context | |
| Wheel: Governance & lifecycle | Cross-layer (review queue, trust tiers) | |
| Wheel: Quality & risk | Cross-layer badge; Trust Checker agent | |
| Wheel: Context packs & APIs | Context + Agents | |
| Wheel: Impact & lineage | Semantic (metric lineage) + Context (packs, answers) | "Used by" panel on each item |
| Base: Context Graph (unified, connected, versioned) | Ontology + Knowledge graph + Semantic + notes, joined by shared IDs | Ontology versions already exist |
| Cap 1 Semantic layer management | Semantic | |
| Cap 2 Ontology & knowledge modelling | Ontology + Knowledge graph | |
| Cap 3 KPI & metric governance | Semantic | |
| Cap 4 Business hierarchies | Ontology (detect) + Semantic (roll-ups) | |
| Cap 5 Policies & rules | Semantic (rules beside metrics) | Exported to agents through Context |
| Cap 6 Context quality score | Cross-layer badge | |
| Cap 7 Conflict detection | Semantic (metrics, terms); Ontology (claims vs data) | |
| Cap 8 Impact analysis | Semantic + Context + Agents | |

### Gap analysis: have, partial, missing

| Capability | Status | What Strata has | What is missing |
|---|---|---|---|
| Discover from data | **Have** | AI proposes things, field meanings and links; data checks; field roles | — |
| Discover from SQL logs, BI files | **Missing** | — | Query-history mining; Power BI and Tableau import |
| Discover from documents, policies, MDM | **Missing** | Free-text "Add context" notes only | Document parsing; rule extraction; MDM read |
| Engineer: canonical model | **Have** | Ontology, versions, own-ontology import (Strata Model v1), OWL/RDF and Ossie export | — |
| Engineer: industry standards alignment | **Missing** | — | Mapping to schema.org, GS1, FIBO, gist |
| Engineer: hierarchies | **Missing** | — | Parent-child and level-chain detection |
| Context graph | **Have** | Virtual KG: 4.7M points, 11.7M lines on SALT in about 10 s; several relationship types; RDF export | Deep path queries; drill-down UX |
| Govern: human review | **Partial** | % confirmed, "data disagrees" flags, user notes that survive rebuilds | Triage bands, ranked queue, provenance stamp, audit sample |
| Govern: ownership, certification | **Partial** | Certified metrics with owner | Tiers below certified, deprecation, domain approvers, any/all approval |
| Govern: versioning, lifecycle | **Partial** | Ontology versions | Semver for breaking changes, sunset dates |
| KPI governance | **Have** | Certify, receipt (formula, joins, no double counting), drift, synonyms, verified questions, dbt MetricFlow export | Regression set per metric; formula lineage view |
| Policies & rules | **Missing** | Notes the AI applies | Rule object with check, evidence, owner, version |
| Quality score | **Partial** | % confirmed per ontology | One readiness number per item with "what would raise it" |
| Conflict detection | **Partial** | Context held back conflicting fields; data-disagrees flags | Metric-vs-metric conflicts; conflict register |
| Gap identification | **Partial** | AI rejects unsupported numbers | Unanswerable-question log; coverage metrics |
| Impact & lineage | **Missing** | Receipts list joins | Concept → column → metric → pack → agent → answer graph |
| Activate: MCP, packs | **Have** | Context Pack v1, MCP, scoped keys, usage log, agents built from the data | Current MCP spec features (see below) |
| Accuracy eval against client reports | **Missing** | Internal benchmarks | Golden set from reports; scoring protocol |

The slide's word "context graph" needs one defined meaning before Strata uses it in a pitch. Foundation Capital, which made the phrase popular, means "a living record of decision traces" (how inputs, policies and approvals turned into a decision) ([Foundation Capital](https://foundationcapital.com/context-graphs-ais-trillion-dollar-opportunity/)). Atlan, Databricks and Gartner use it for a governed semantic and knowledge layer ([Atlan](https://atlan.com/context-engineering-studio.md); [Databricks](https://docs.databricks.com/en/genie/genie-ontology); [Gartner](https://www.gartner.com/en/documents/7773753)). Strata's ontology plus virtual graph plus certified metrics matches the second meaning. Logging each answer's question, facts used, result and user confirmation later would add a light version of the first.

## Six meeting concerns, six concrete answers

### Trust in an AI-made ontology: anchor to standards, prove fit with data

The strongest answer combines what Strata already does with one new feature. Strata's deterministic core matches the W3C Direct Mapping recommendation (table to class, primary key to identity, foreign key to link) ([W3C](https://www.w3.org/TR/rdb-direct-mapping/)). A SIGMOD 2026 benchmark found simple rule-based methods still beat LLM systems at learning ontologies from relational databases ([HPI](https://hpi.de/naumann/news/paper-accepted-at-sigmod-2026.html)). So Strata's "AI proposes, data checks" design is defensible on its own. What it lacks is the vocabulary clients recognise.

Only a few standards are both open and machine-readable. **FIBO is MIT-licensed** ([FIBO guide](https://www.github.com/edmcouncil/fibo/blob/master/ONTOLOGY_GUIDE.md)). **GS1 Web Vocabulary is Apache 2.0** and covers CPG product master data, which is what Unilever and Kellogg's already use through GTIN ([GS1 WebVoc](https://github.com/gs1/WebVoc)). **gist is CC BY 4.0** ([Semantic Arts](https://semanticarts.com/gist)), and BFO is an ISO standard (ISO/IEC 21838-2) ([arXiv 2404.17758](https://arxiv.org/pdf/2404.17758v1)). Two licence traps matter. The **IFRS taxonomy needs a commercial licence** if embedded in a product ([IFRS](https://www.ifrs.org/products-and-services/ifrs-accounting-licensing/)). **ECLASS is paid** ([ECLASS](https://eclass.eu/en/eclass-standard/licenses)). The client must bring those. No standard models an SAP R2R, P2P or O2C transaction end to end, so a client extension layer will always exist. Customers map well (schema.org Organization, FIBO legal entity), sales documents map loosely (schema.org Order), and GL accounts, journal entries and cost centres map weakly.

The mapping method is well studied, and its accuracy is uneven. LLMs4OM retrieves the top 5 candidates with embeddings, has an LLM say yes or no, and keeps pairs above a confidence cut-off. It reached **F1 of about 0.89–0.94 on clean pairs but 0.26 on SNOMED-FMA** ([arXiv 2404.10317](https://arxiv.org/html/2404.10317v1)). LLMs also **confuse "is a kind of" with "is the same as"** and force a match when none exists ([CEUR Vol-4085](https://ceur-ws.org/Vol-4085/paper32.pdf)). RIGOR shows a better order of work: retrieve from domain ontologies *while* generating, so each new class is anchored at birth ([arXiv 2506.01232](https://arxiv.org/html/2506.01232v1)). Market leaders do not force standards either. Palantir and Fabric IQ let customers build their own types, and Gartner notes Fabric's RDF support "does not guarantee OWL-level semantic richness" ([Gartner](https://www.gartner.com/en/insights/gartner-first-takes/microsoft-fabric-iq)). "Standard names, proven fit, human sign-off" therefore beats the leaders rather than catching up with them. No benchmark exists for mapping SAP fields to FIBO, GS1 or schema.org, so Strata must build its own gold set before quoting any accuracy.

There is one licence warning about Strata itself. **SAP SALT is CC BY-NC-SA 4.0 and gated to non-commercial use** ([Hugging Face](https://huggingface.co/datasets/SAP/SALT)). It is fine for internal benchmarking. Using it in paid demos needs a licence check.

### Busy Finance users: review by exception, evidence first

Only Informatica documents a real three-band design: auto-accept between **80 and 100** confidence, a manual queue below that, and nothing suggested under the floor ([Informatica](https://onlinehelp.informatica.com/IICS/prod/MCC/en/metadata-command-center-administration/Glossary_association.html)). Collibra adds "reject a parent, reject its children" and a "Ready for review" tag that stays until resolved ([Collibra](https://productresources.collibra.com/docs/collibra/latest/Content/Catalog/GuidedStewardship/SemanticLayer/ta_semantic-layer.htm)). Palantir lets one reviewer approve a batch proposal at once ([Palantir](https://palantir.com/docs/foundry/ontologies/review-ontology-proposals/)). The key design risk is **automation bias**: in OE-Assist, ontology engineers did worse when the LLM gave wrong guidance ([arXiv 2507.14552](https://arxiv.org/html/2507.14552v1)). Strata's review card should therefore show the data evidence (match %, sample rows, failing rows) *before* the AI's claim. Strata's data checks give it a better triage signal than model confidence alone, because "every check passed" can be measured, while LLM confidence is not calibrated. Routing by sub-tree (balance sheet vs P&L, R2R vs P2P), which Oracle EDM does per dimension ([Oracle community](https://community.oracle.com/customerconnect/discussions/tagged/213-request-changes/p4)), keeps any one person's queue short. Vendor acceptance rates (Atlan's 60–70%) are self-reported and undefined ([Atlan](https://atlan.com/ai.md)), so Strata should log its own reviewer decisions and publish its own rates.

### KG navigation to child records and multiple relationship types

This is mostly done. Strata's record panel already shows linked records and separates sold-to, ship-to, bill-to and payer. The remaining work is presentation: expand a sales document into its items in place, filter by relationship type, show a path between two records, and cap fan-out so hub values (one country, one status) do not swamp the view. For true path queries, **DuckPGQ** adds ISO SQL:2023 SQL/PGQ pattern matching and path finding inside DuckDB ([DuckDB](https://duckdb.org/library/duckpgq)), so Strata gets multi-hop queries with no new engine.

### Class, type and object in plain words

A **class** (also called a type) is a kind of thing, such as "Sales Document". An **object** (instance) is one real thing of that kind, such as sales order 4711. **Attributes** describe an object (net amount, currency). **Relationships** link objects (sold-to → Customer). The same ideas have different names in each tool:

| Plain word | OWL/RDF | Palantir / Fabric / property graph | SAP example |
|---|---|---|---|
| Class / type | owl:Class | object type / entity type / node label | Sales Document |
| Object / instance | individual | object / node | Sales order 4711 |
| Attribute | datatype property | property | NetAmount |
| Relationship | object property | link / edge | soldTo → Customer |
| Sub-class | rdfs:subClassOf | often absent | Standard Order ⊂ Sales Document |
| Link to a standard | skos:exactMatch / closeMatch | none native | Sales Document closeMatch schema:Order |
| Rule check | SHACL shape | constraint | each order has one customer |

GS1's own example of a sub-class is FoodBeverageTobaccoProduct under Product ([GS1](https://gs1.org/voc/Product)). The UI should use the plain words and show the formal term on hover.

### Testing against real client reports: execution accuracy with tolerance

The industry measure is **execution accuracy**: compare the returned numbers with a trusted answer, ignoring row and column order, and allow for rounding. Databricks counts an answer "Good" if results match apart from extra columns, sort order, or **numbers equal to 4 significant digits** ([Databricks](https://docs.databricks.com/aws/en/genie/benchmarks)). Snowflake removes the test questions from the model's context before each run, so the test does not just measure memory ([Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)). Public benchmarks say little about enterprise data. On real private warehouses, agents on GPT-5.2 reached only **10.8%** on BEAVER ([arXiv 2409.02038](https://arxiv.org/pdf/2409.02038)), and the benchmarks themselves carry **52.8–62.8% annotation errors** ([arXiv 2601.08778](https://web3.arxiv.org/abs/2601.08778)). Grounding helps a lot. GPT-4 went from **16.7% to 54.2%** with a knowledge-graph representation ([arXiv 2311.07509](https://arxiv.org/pdf/2311.07509v1.pdf)), and dbt found that a semantic layer "fails loudly" by refusing, while text-to-SQL "will cheerfully give you a wrong number" ([dbt](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)).

The protocol for Unilever or Kellogg's follows from this. Take 3–5 internal reports, because published annual reports give only rounded group totals. List every number with its filters, period, currency and units. Write 2–4 phrasings of each question, including synonyms, fiscal vs calendar periods and questions that *should* be refused. Score by result matching with a tolerance set by the report's display precision, and check units separately, because a factor-of-1000 error is a common silent failure. Report execution accuracy, refusal correctness, agreement across phrasings and agreement across repeated runs. Report a "certified metric" score and an "ad-hoc" score separately. Use an LLM judge only for narrative answers, and spot-check it by hand. Suggested pass marks are judgement, not a standard: 95% or more on certified metrics, zero silent wrong numbers on the top 20 report KPIs, and every wrong answer accompanied by a visible warning. Atlan's idea of turning each failure into a named missing piece (relationship, synonym, default filter) ([Atlan](https://atlan.com/context-engineering-studio.md)) maps directly onto Strata's notes and Data Steward agent.

### Neo4j licence cost: virtual graph is the right default

Neo4j is the clear popularity leader on DB-Engines, which measures search interest and job ads, not market share ([DB-Engines](https://db-engines.com/en/ranking/graph+dbms)). **Community Edition is GPLv3, single-node, and gives every user full access** ([Neo4j manual](https://neo4j.com/docs/operations-manual/current/introduction/)). Clustering, role-based access and GDS need commercial licences whose self-hosted **prices are quote-only** ([Neo4j pricing](https://neo4j.com/pricing)). The cloud option AuraDB Business Critical lists about **$292/month for a 2 GB instance** ([Neo4j Aura](https://neo4j.com/cloud/aura/pricing/)). A "$75k–100k per month" figure on the Neo4j forum is an AI-generated estimate and should not be repeated ([Neo4j forum](https://community.neo4j.com/t/pricing-details-on-using-enterprise-edition/72957)).

| Option | Kind | Licence / cost | Fit for Strata |
|---|---|---|---|
| Strata virtual KG on DuckDB | Virtual | Own code, no licence | Default; 4.7M records in about 10 s (internal measurement) |
| DuckPGQ | Virtual, SQL/PGQ in DuckDB | Community extension | Add path queries without a new engine ([DuckDB](https://duckdb.org/library/duckpgq)) |
| Ontop | Virtual KG, SPARQL | Apache 2.0, v5.5.0 Feb 2026 | Reference design; Java ([GitHub](https://github.com/ontop/ontop)) |
| Timbr | Virtual SQL ontology | No public price; "$599/user/month" on TrustRadius is unverified | Closest commercial analogue ([Timbr](https://timbr.ai/sql-knowledge-graph/); [TrustRadius](https://www.trustradius.com/compare-products/timbr)) |
| Apache AGE | Graph on Postgres | Apache 2.0 | If a client already runs Postgres ([PostgreSQL](https://www.postgresql.org/about/news/apache-age-110-2504/)) |
| TigerGraph Community | Native graph | Free, proprietary, 200 GB cap, no HA | Deep traversal pilots ([TigerGraph](https://tigergraph.com/blog/tigergraph-db-community-edition-the-most-powerful-free-graph-vector-database-for-turbocharging-ai/)) |
| Memgraph | Native graph | BSL; Enterprise from $25k/year for 16 GB | Vendor price ([Memgraph](https://memgraph.com/enterprise)) |
| ArangoDB | Multi-model | Community licence, 100 GiB limit, commercial use restricted | Avoid ([ArangoDB](https://arango.ai/?p=2755)) |
| FalkorDB | Native graph | SSPLv1 | Avoid for bundling ([FalkorDB](https://docs.falkordb.com/license.html)) |
| Kuzu | Embedded graph | Archived Oct 2025 | Avoid ([The Register](https://www.theregister.com/2025/10/14/kuzudb_abandoned/)) |

A virtual graph wins when questions are BI-style (totals over facts with 1–3 joins), when the warehouse already enforces access, and when freshness matters. Copying into a graph database pays off only for deep variable-length chains (fraud rings, supply paths beyond 4–5 hops), graph algorithms such as PageRank, or sub-second traversal at high concurrency. Client finance questions rarely look like that.

## Roadmap: build the evidence first, then the governance

The order follows one rule: build first what lets Strata *prove* things to the client (accuracy, review effort, gaps), then what lets clients *govern* at scale, then what widens discovery. Sizes are rough team estimates (S = days, M = 1–2 weeks, L = 3+ weeks). Thresholds and weights below are starting proposals to tune on Strata's own data. No source supports specific values.

### Next 2 weeks

| # | Item | Layer | Recommended approach | Size |
|---|---|---|---|---|
| 1 | **Report check (accuracy test)** | Context + Agents | Golden-set file (question, phrasings, gold value, units, filters, precision). Runner asks Strata, scores by result match with a 4-significant-digit default and a units check, records refusals. Hold golden questions out of notes and verified questions. Show a scorecard (certified vs ad-hoc, refusal correctness, phrasing agreement). Pilot on Olist plus one real client report. | M |
| 2 | **Review by exception** | Ontology (shared queue) | Score each AI item from its data checks: all checks pass → auto-confirmed (reversible, stamped "confirmed by checks"); any check fails → hidden under "data disagrees"; rest → queue ranked by impact (used by a certified metric, number of links, row volume). Evidence shown before the claim. Reject parent rejects children. Send a random ~5% of auto-confirmed items to review to measure false accepts. Replace the raw "% confirmed" headline with "N need you, M confirmed by checks". | M |
| 3 | **Unanswerable-question log** | Context | Log every refusal and rejected number with linked concepts and a reason (missing thing, missing link, missing metric, unclear term, conflicting definition, data absent). Group similar questions, rank by frequency, show the top gaps as suggested fixes the Data Steward agent can draft. Follows Snowflake's group-and-suggest pattern ([Snowflake](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-suggestions)). | S |
| 4 | **Graph drill-down** | Knowledge graph | Expand child records in place (document → items), filter by relationship type, path between two records, fan-out cap with "show more". | S |
| 5 | **Plain-word glossary and Neo4j answer** | Ontology (help text) | Hover glossary from the table above; one-page Neo4j/alternatives note for the client. | S |

### Next 1–2 months

| # | Item | Layer | Recommended approach | Size |
|---|---|---|---|---|
| 6 | **Standards mapping** | Ontology | Bundle schema.org, GS1 WebVoc, FIBO and gist offline (client brings GPC, UNSPSC, ECLASS, IFRS). Per class and field: top-k embedding candidates, LLM verify, explicit match type (exact / close / broader / related / none), confidence, evidence. Pre-tick only exact matches with high confidence; below a floor, propose a marked client extension under the nearest standard parent. Export as skos matches in OWL. Measure precision and recall on a SALT gold set (internal use). | L |
| 7 | **Readiness score (one number per item)** | Badge in every layer; Trust Checker | Weighted average of 0–100 signals, Collibra style ([Collibra](https://productresources.collibra.com/docs/collibra/2026.08/Content/AICommandCenter/ref_aicc-trust-score-inputs.htm)): documentation, mapping coverage, share of claims confirmed by data, open conflicts, freshness, certification and drift, answerability from the gap log. Leave blank signals out. Store "what would raise it" with one-click fixes, as Atlan stores missing metadata ([Atlan](https://docs.atlan.com/product/capabilities/discovery/references/metadata-completeness)). Roll up by mean. Later, check whether the score predicts Report check accuracy. | M |
| 8 | **Metric conflict detection** | Semantic | Candidate pairs by name, synonym or shared concept. Parse both formulas with sqlglot, normalise, compare aggregate, source columns, filters and grain. Run both on the same slice in DuckDB within a tolerance. Label Identical / Equivalent / Variant / Different. LLM writes the one-line explanation and recommendation (merge, rename "Gross" vs "Net", deprecate one, keep both with a note). New AI metrics matching a certified one become "variant of X" sent to the owner. The LLM narrates and does not detect, because the best models miss almost half of inconsistencies ([arXiv 2512.18601](https://arxiv.org/pdf/2512.18601v1)). | M |
| 9 | **Lineage and impact** | Semantic + Context | Typed edges: concept → field → column → metric version → context pack → agent → answer (packs already cite facts). sqlglot `lineage` for metric SQL ([sqlglot](https://sources.debian.org/src/sqlglot/27.7.0-1/sqlglot/lineage.py)). On any change, walk downstream and show "3 metrics, 2 packs, 1 agent, 14 past answers affected". Rate breaking vs non-breaking with SQLMesh-style rules ([Tobiko](https://tobikodata.com/blog/automatically-detecting-breaking-changes-in-sql-queries)), show the value shift (reuse drift), mark cited past answers "may be stale". Shown as a "Used by" panel on each item. | M |
| 10 | **Trust tiers, owners, lifecycle** | Cross-layer | Draft (AI) → Confirmed (checks or person) → Endorsed (domain user) → Certified (named owner), plus Deprecated with replacement and sunset date (warn, then block, as dbt does ([dbt](https://docs.getdbt.com/docs/mesh/govern/about-model-governance?version=1.12))). Domain approver groups (Finance, R2R, P2P; BS vs P&L) with any/all approval. Formula, grain or removed property = major version. Agents and packs prefer certified sources and name the tier used, the pattern Fabric Copilot follows ([Microsoft Learn](https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview)). | M |
| 11 | **Rules and regression sets** | Semantic | A rule is three linked parts: plain-English text with owner and version; an executable DuckDB check or metric filter drafted by the LLM; evidence from the last run (pass/fail, violating rows). A person confirms all three together. Add a type (must / may / must-not). Agents get rules as context and are checked after generation. Each certified metric also gets 3–10 verified questions re-run on every new version, with regressions shown next to drift, as in Snowflake evaluations ([Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)). Optional SHACL export via pySHACL. Research shows LLMs draft near-complete SHACL from text constraints with minor expert edits ([arXiv 2506.10678](https://arxiv.org/html/2506.10678v1)). | M |
| 12 | **Suggestions from SQL history** | Ontology + Semantic | Read DuckDB or warehouse query logs (or a pasted SQL folder) with sqlglot. Count join pairs, GROUP BY fields, aggregates and repeated filters. Weight saved and BI queries above ad-hoc ones (Snowflake notes frequency alone is a poor proxy for correctness ([Snowflake](https://www.snowflake.com/en/blog/semantic-view-autopilot/))). Show as "suggested from usage" beside data-built suggestions, then data-check each join. LLM-adjudicated join inference reached 78–100% precision on well-structured schemas ([arXiv 2603.04176](https://arxiv.org/abs/2603.04176)). | M |
| 13 | **Hierarchy detection** | Ontology | Self-referencing keys (parent → id) become parent-child hierarchies, checked for cycles, orphans, depth and raggedness. Functional dependencies between columns (city → region → country) become level hierarchies, each verified on the data. The research found no hierarchy discovery in Fabric IQ, Snowflake semantic views or Databricks metric views, where hierarchies are still modelled by hand as level-based or parent-child ([Oracle](https://docs.oracle.com/en/middleware/bi/analytics-server/datamodel-oas/create-and-manage-level-based-hierarchies-semantic-model.html)), so it is open ground that suits Strata's "check against the data" strength. | M |
| 14 | **MCP spec refresh** | Context + Agents | Move to the stateless 2026-07-28 revision (`server/discover`, caching hints on list and read results, OAuth with Client ID Metadata Documents for remote use, stdio for local) ([MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)). Serve context packs as cacheable, versioned resources. | S |

### Later (3+ months, or when a client asks)

| # | Item | Layer | Recommended approach |
|---|---|---|---|
| 15 | **Power BI and Tableau import** | Semantic | Parse .pbit DAX measures and relationships and Tableau calculated fields and filters, as Snowflake Autopilot does ([Snowflake](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot)). Each imported measure enters the conflict check (item 8) against certified metrics. Moves earlier if the client shares BI files for the Report check. |
| 16 | **Documents and policies** | Ontology + Semantic | docling (MIT) to parse PDFs and DOCX ([AlphaSignal](https://alphasignal.ai/news/ibm-s-docling-hits-65k-stars-fixing-the-pdf-problem-that-breaks-rag)). Schema-guided extraction into Strata's own ontology, never a parallel graph. Output lands as draft rules and notes in the review queue. No published accuracy exists for enterprise rule extraction, so treat it as a suggestion source only. |
| 17 | **Hierarchy governance** | Ontology + Semantic | Versioned, effective-dated trees with alternate hierarchies per dimension (SAP's "hierarchy with directory" pattern ([SAP Community](https://community.sap.com/t5/technology-blog-posts-by-sap/an-introduction-to-hierarchy-with-directory-in-sap-datasphere/ba-p/13575573))). A change request shows moved nodes and how much each certified KPI moves before approval. |
| 18 | **Decision traces** | Context | Store question, facts used, answer, user confirmation and later outcome as a searchable record: the Foundation Capital meaning of "context graph". |
| 19 | **Open exports** | Each layer | OpenLineage events with column lineage ([OpenLineage](https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet/)); ODCS v3.1 contracts ([Bitol](https://bitol.io/?p=302)). Do not promise ODCS SLA enforcement unless Strata runs the checks. |
| 20 | **Deep graph engine** | Knowledge graph | Only if a client needs 5+ hop paths or graph algorithms: DuckPGQ first, then Apache AGE. |

Some things should stay out on purpose. An OWL reasoner (HermiT through Owlready2) needs Java and an LGPL dependency, which clashes with the zip bundle. SQL checks plus optional SHACL export cover the need ([pygraft-gen](https://orange-opensource.github.io/pygraft-gen/concepts/consistency-checking)). A2A matters only once outside agents call Strata's agents. MCP comes first, and the Linux Foundation calls the two complementary ([Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year?hs_amp=true)). Bulk AI writes with no review, which Atlan's Context Agent allows ([Atlan docs](https://docs.atlan.com/product/capabilities/atlan-ai/how-tos/use-atlan-ai-for-documentation)), should never ship.

## Vendor numbers to avoid quoting

Almost every number in this field comes from someone selling the layer it measures. The table separates what can be repeated from what cannot.

| Claim | Who says it | Status |
|---|---|---|
| Atlan "5x improvement in AI accuracy" (Workday, Fox) | Atlan ([Atlan](https://atlan.com/about.md)) | Vendor, no method |
| Atlan 60–70% acceptance of AI descriptions | Atlan ([Atlan](https://atlan.com/ai.md)) | Vendor, "accepted" undefined |
| Alation "six weeks of curation in 15 minutes" | Alation ([Alation](https://www.alation.com/DGQ3)) | Vendor, no method |
| Snowflake Cortex Analyst "90%+ accuracy" vs 51% GPT-4o | Snowflake ([Snowflake](https://snowflake.com/en/engineering-blog/cortex-analyst-text-to-sql-accuracy-bi)) | Vendor, internal ~150 questions |
| dbt semantic layer 98–100% | dbt Labs ([dbt](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)) | Vendor, 11 questions |
| data.world 16.7% → 54.2% with a knowledge graph | data.world ([arXiv](https://arxiv.org/pdf/2311.07509v1.pdf)) | Vendor, peer-visible method, 43 questions |
| Glean preferred about 2x over ChatGPT | Glean ([Glean](https://www.glean.com/blog/enterprise-search-evaluation-2026)) | Vendor |
| Neo4j Enterprise "$75k–100k/month" | Forum, AI-generated | Unverified, do not repeat |
| Timbr "$599/user/month" | TrustRadius | Unverified edition |
| Apple acquired Kùzu | Secondary sources | Unconfirmed; the archive itself is confirmed |
| Fabric IQ GA | Mixed | Fabric IQ GA June 2026, Ontology item still in preview ([Microsoft Learn](https://learn.microsoft.com/fabric/iq/overview)) |

The newer notes also resolve one earlier uncertainty. Databricks Genie Ontology now has a live docs page, last updated 16 November 2026. It describes "modeled" (certified) versus "learned" knowledge and an authority score built from origin, usage and freshness ([Databricks](https://docs.databricks.com/en/genie/genie-ontology)). The earlier research had marked it unverified. It is Strata's closest new competitor on Discover, and its authority-score idea is worth copying in item 12. Coverage of Collibra, Alation and data.world discovery features remains thin, and no vendor publishes accuracy for auto-generated semantic models.

## Conclusion

The slide reads like a list of eight new products, but the research shows it is mostly one loop that Strata already runs, with three missing links. Discovery must widen beyond tables. Quality must become measurable per item. Change must have a visible blast radius. The cheapest way to win the meeting's arguments is not new modelling power but **proof**: a Report check score on the client's own reports, a review queue that shows Finance users "12 items need you, 340 were confirmed by the data", and a list of the questions Strata honestly could not answer. Competitors publish marketing multipliers. Strata can publish its own measured numbers, and that is a stronger trust signal than any logo on a standards list.

Standards alignment is still worth building, but as a naming layer on top of data-proven fit, not as a replacement for it. FIBO, GS1 and schema.org will supply familiar names for customers, products and orders. They will not describe a client's cost centres or journal entries, so the data checks remain the real basis of trust. The graph question is settled the same way. Strata's virtual graph over live tables is the market's own preferred low-cost pattern (Timbr, Ontop, DuckPGQ), so the right answer to "Neo4j or not" is "not unless your questions need five-hop paths."
