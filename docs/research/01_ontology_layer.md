# Layer 1 — Ontology: how the market builds one, and where it stops

*Research round 2026-10-29. All sources accessed 2026-10-29. Grades: A = measured by us; B = primary vendor docs; C = independent article/analyst; D = our inference. Vendor case studies are B at best, labelled "vendor-reported", never "measured".*

## Executive summary

1. The same idea sells under five names — Palantir **Ontology**, Databricks **Unity Catalog + metric views**, Atlan **context layer**, Stardog/Graphwise **semantic knowledge graph**, metaphactory **virtual knowledge graph**. None is a library you can drop on a local DuckDB file.
2. The category is **model-first and platform-bound**: Palantir is authored (UI or TypeScript OSDK), Stardog/GraphDB need OWL/SPARQL and mapping files, Atlan needs a governance programme, Databricks only knows its own metastore. No vendor documents automatic discovery of classes, keys and relations from an arbitrary source.
3. **Pricing is enterprise-negotiated**: no public Palantir price; Stardog/GraphDB quote Enterprise; Atlan's only public anchor is a Microsoft Marketplace listing at **$120,000/yr** for 10 named users (third-party, grade C).
4. **Time validity is absent from the model layer.** We found model *versioning* (Palantir value-type versions and interface migrations, GraphDB rulesets, Databricks lineage retention), never valid-from/valid-to as a first-class property of relations.
5. The under-served problem is **trust**: all six tools express a model; only GraphDB's inference-provenance plugin and Databricks lineage document any "where did this come from". None labels a relation as stated vs guessed — our product's core rule is nobody's shipped feature.

## Comparison table (Layer 1)

| Tool | Public price anchor (2026-10-29) | Model built by | Time / versioning | Agent path | Grade |
|---|---|---|---|---|---|
| Palantir Foundry Ontology | **Not public** — `/pricing` redirects to homepage | Human modeller (Object/Link/Action/Interface types) or code-first `@osdk/maker` TypeScript | Value-type versions; interface migrations with 7–180 day grace; ontology branches | OSDK SDKs, APIs, AIP | B |
| Databricks Unity Catalog | **Included** in Databricks; no standalone UC price; compute in DBUs | Metadata-driven: auto lineage, LLM auto-classification; metric views in SQL DDL/UI | Lineage retained ≥ 2024-09-01 (UI), 1 yr in system tables; renames break lineage | Genie/Genie Code, metric views, MCP services governed | B |
| Atlan | **$120,000/yr** for 5 admins + 5 members (Microsoft Marketplace listing, via Dawiso Oct 2026) | Connector metadata + human curation + "Context Agents" | Metadata history; no bitemporal facts (D) | Context Engineering Studio, Claude/ChatGPT/custom agents | B / C price |
| Stardog | Free (not OSS, no HA/backups/LDAP/full connectors); Enterprise quote | Model-first OWL + SMS/R2RML/SMS2 mappings; virtual graphs; inference | Point-in-time recovery; named graphs (D) | Voicebox, GraphQL, SQL/BI, REST | B |
| Ontotext GraphDB (Graphwise) | Free limited to 2 concurrent queries; EE **per CPU core**, price unpublished | Model-first OWL + compiled `.pie` rulesets; load-time materialization; relational virtualization | Schema transactions, reinfer, backup; no bitemporal edges (D) | SPARQL/GraphQL; metaphactory apps | B |
| metaphactory (incl. former Ontopic) | Not public | Model-first with AI-assisted modelling; virtual KG over warehouses via JDBC | Model versioning + term-level provenance claimed | metis NL Q&A | B / A redirect |
| Protégé + OWL 2 + SHACL | Free / open source | Manual ontology engineering; SHACL shapes for validation | Ontology version IRIs; file-based | None | B |

## Tool sections

### Palantir Foundry Ontology

| Field | Finding |
|---|---|
| Category / licence | Operational ontology inside a data platform; proprietary, enterprise contract only; **no public list price** (verified absence) |
| Deployment / inputs | Palantir-hosted Foundry; datasets and streams. Entry requires a Foundry contract, data already in Foundry, and Ontology Manager or TypeScript build access |
| How built | Human modelling. The `@osdk/maker` README documents object types with `primaryKeyPropertyApiName`, shared property types, value types with constraints and versions, interfaces with `extends`, one-to-many / many-to-many / intermediary-object links, actions with submission criteria, and derived properties across multi-hop links (`collectList`, `avg`, `max`) |
| Automation / HITL | Low automation for modelling, high for SDK/app generation. Strong review: ontology branching and proposals; interface schema migrations with a 7–180 day grace period and `ontology-schema-lock.json`; builds fail on incompatible changes |
| Artifacts / exit | Ontology (object/link/action/interface/value types), generated OSDK packages, apps, AIP agents, branch proposals. Exit = an app or agent can act on objects |
| Time / provenance / agent | Value-type versions and enforced migrations; dataset lineage exists, ontology-level provenance not documented; OSDK/APIs/AIP are the agent path |
| Problems / outcomes | Operational apps, decisions, digital twins, permissioned workflows. Outcomes are vendor stories; not verified. **Limits:** cost, lock-in, modelling skill, no uncertainty labels |
| Gap for us | Proves buyers pay for a typed, actionable model, but only at enterprise scale inside Foundry. Opening: same semantics auto-derived, local, provenance-labelled |

### Databricks Unity Catalog + metric views

| Field | Finding |
|---|---|
| Category / licence | Governance + semantics inside the lakehouse. No standalone UC list price; compute billed in DBUs; Data Classification has its own billing SKU at list prices from `system.billing.list_prices` |
| Deployment / inputs | Databricks on AWS/Azure/GCP; open-source UC implementation also published. Entry: UC metastore, Runtime 11.3 LTS+, standard/dedicated access mode, Delta/Iceberg managed tables |
| How built | Metadata-driven. Lineage captured automatically at table and column level from queries/jobs/notebooks/pipelines/dashboards/model services; classification by an LLM agent with human review; metric views authored in SQL DDL or UI with YAML validation and agent metadata (synonyms, display names). No class/relation ontology |
| Automation / HITL | High for technical metadata, low for business meaning. HITL: exclude a wrong detection (removes tag, suppresses re-tagging, feeds accuracy), metric view lifecycle, permissions |
| Artifacts / exit | Catalog, tags, lineage graph, metric views for SQL/BI/Genie/alerts, system tables (`table_lineage`, `column_lineage`, `data_classification.results`) |
| Time / provenance / agent | UI lineage back to 2024-09-01; system tables rolling 1 year; not preserved across renames; RDDs, global temp views, path refs and UDF column lineage not captured. Provenance = operational lineage, not fact evidence. Genie Code answers lineage Q&A |
| Problems / outcomes | Governance, PII/GDPR discovery, impact analysis, root cause, metric consistency. Outcomes vendor-published |
| Limits / gap | Databricks-only; external assets metadata-only; no identity, no reasoning. **Gap:** UC is the benchmark for automatic *metadata*; we do the same for *meaning* (classes, keys, relations, time) on sources UC cannot see |

### Atlan

| Field | Finding |
|---|---|
| Category / licence | Active metadata catalog repositioned as "the context layer for AI": Enterprise Data Graph, Context Agents, Context Engineering Studio, Context Lakehouse (Iceberg-native, graph+file, vector search). Pricing not published; `atlan.com/pricing` resolves to talk-to-sales |
| Price anchor | Microsoft Marketplace "Atlan – Context Layer for AI" at **$120,000/yr** for 5 admins + 5 members ($220K/2yr, $340K/3yr) ≈ $12,000/named user/yr — third-party reading (Dawiso, 2026-10-16), **grade C** |
| Inputs / entry | Broad multi-tool estate, connectors, stewards, budget ≥ $120K. Not aimed at one CSV |
| How built / automation / HITL | Connectors pull technical metadata and lineage; humans and "Context Agents" add glossary, owners, descriptions, metrics, quality, READMEs. AI drafts context for human approval |
| Artifacts / exit | Catalog assets, glossary, lineage, ownership, quality context, context served to Claude/ChatGPT/custom agents. Exit = an agent gets a governed answer |
| Time / provenance | Metadata history; "decision history" claimed; no bitemporal instance facts (D). Provenance = system/owner provenance, not per-fact evidence |
| Problems / outcomes | Discovery, definition consistency, governance/ownership, AI grounding. Vendor claims: 400+ enterprises, 8B context reads/90 days, "87% of customers say context on par with human" — all marketing, unverified |
| Limits / gap | Metadata *about* data: no instance graph, no rules engine, no entity resolution, no time-valid edges, no fact query language. **Gap:** Atlan says what data means, not what is connected right now — complementary at the low end, competitive at the agent-context layer |

### Stardog

| Field | Finding |
|---|---|
| Category / licence | Enterprise knowledge graph platform (RDF/OWL + inference + virtualization + Voicebox NL). **Stardog Free**: not open source, renewable 1-year, commercial use allowed, excludes HA, caching, backups, LDAP and full connector breadth. Enterprise quote-only |
| Deployment / inputs | On-prem, cloud, marketplaces, Docker/K8s. RDBMS/NoSQL via virtual graphs (customer supplies JDBC drivers), CSV/JSON, RDF. Entry needs OWL/RDF skills and connectivity |
| How built | Model-first OWL, then mappings in SMS/R2RML/SMS2; mapping optional for RDBMS via R2RML direct mapping (table-level only). Inference rules extend the model; `virtual import` materializes; virtual transparency merges local + remote |
| Automation / HITL / artifacts | Low automation; human designs ontology, mappings, rules. Artifacts: KG, registered virtual graphs, materialized copies, inference closure, SPARQL/GraphQL/SQL/BI/REST/Voicebox |
| Time / provenance / agent | Point-in-time recovery, transaction logs, named graphs (D). Reasoning explanation/debugging = inference provenance. Voicebox NL + standard APIs |
| Problems / limits | Data fabric without copying, analytics modernization, drug discovery, operational risk, supply chain. Documented translation gaps: duplicate solutions, `MINUS` untranslated, datatype comparison semantics, R2RML named graphs unsupported; mapping maintenance; no free HA; connectors paywalled |
| Gap for us | Validates query-in-place; weakness is human authoring of ontology + mappings. We auto-derive and let humans review |

### Ontotext GraphDB (now Graphwise)

| Field | Finding |
|---|---|
| Category / licence | RDF store with forward-chaining OWL reasoning, relational virtualization, FedX federation, Raft HA; brand now "Graphwise" (docs footer: ONTOTEXT AD doing business as Graphwise). **Free** limited to 2 concurrent queries; **EE per server CPU core**, each node separately, ~1 concurrent query per core; per-core price unpublished; SE discontinued |
| Deployment / inputs | Java anywhere, Docker/Helm, AWS/Azure/GCP guides, clusters. RDF; relational via data virtualization; Kafka/Solr/ES/OpenSearch connectors in EE |
| How built | Model-first: import OWL/RDFS, choose ruleset (`empty`, `rdfs`, `rdfsplus`, `owl-horst`, `owl-max`, `owl2-ql`, `owl2-rl`; default RDFS-Plus). Rules compile to Java bytecode and are **total-materialized** at load; custom `.pie` rulesets; consistency checks available but off by default |
| Automation / HITL / artifacts | Inference automatic once configured; nothing auto-modelled from data. Artifacts: repository with explicit + inferred triples, fast SPARQL, explain plans, consistency reports, **provenance plugin** that regenerates the inference closure from a named graph |
| Time / provenance / agent | Named graphs, reinfer, schema transactions, backup; no bitemporal edges (D). Inference provenance documented; dataset lineage is not its job. SPARQL/GraphQL/REST; metaphactory app layer |
| Problems / outcomes | Semantic search, knowledge discovery, regulated/pharma ontologies. metaphactory case studies (Boehringer, Scania/TRATON, Sloane Lab) and metrics (BKW break-even, Siemens Energy 1500 hrs) — vendor-reported |
| Limits / gap | Semantic skills, load-time cost, schema-change friction, per-core licensing punishing concurrency, no auto-discovery, free tier effectively single-user. **Gap:** lightweight local inference/validation with OWL/SHACL export for the mid-market |

### metaphactory (incl. former Ontopic)

`ontopic.ai` — the vendor named for Snowflake virtualization — now **redirects to metaphactory.com** (observed 2026-10-29, grade A), consistent with consolidation in this category. metaphactory sells a semantic application layer with **live JDBC virtual knowledge graph over Snowflake, Databricks, BigQuery and Redshift "without moving a byte"**, model-first semantic modelling with editorial workflows, versioning and term-level provenance, and an AI-assisted modelling assistant. Business experts contribute via natural language/Excel (vendor claim). "metis" answers NL questions grounded in the governed model. Pricing not public. Limits: needs a warehouse plus semantic specialists; claims unverified. **Gap:** targets warehouses only — nobody offers virtual KG over local files and small DBs with zero modelling, and their AI assistance is still model-first.

### Protégé / OWL 2 / SHACL (brief)

Protégé is a free, open-source OWL editor from Stanford (B), used for OBO Foundry, WHO ICD-11 and the NCI Thesaurus. OWL 2 is a W3C Recommendation (2012) with classes, properties, individuals, profiles (EL/QL/RL) and formal semantics; SHACL is a W3C Recommendation (2017) for validating RDF graphs against shapes, producing a machine-readable report (focus node, path, value, severity, message). **Not a competitor — our interoperability contract:** export OWL/SHACL-compatible shapes so buyers are not locked in, and reuse the SHACL validation-report shape as auditable evidence. Limits: no connectors, no instance runtime, no lineage, no agent path.

## Problems solved / under-served

| # | Buyer problem | Served well by | Under-served |
|---|---|---|---|
| 1 | What kinds of thing exist, and what identifies one? | Palantir (by hand), Stardog/GraphDB (OWL by hand) | **Auto-discovery of classes and keys from arbitrary sources** — undocumented by every vendor |
| 2 | How are things related, with what cardinality? | Palantir link types, OWL object properties | Hand-authored only; FKs absent in CSVs/legacy DBs |
| 3 | Rules/constraints that stop bad data | SHACL, GraphDB checks, Palantir action criteria | Expert-authored; not wired to agent answers |
| 4 | Is this statement given or derived? | GraphDB provenance plugin; Stardog reasoning explanation | **No vendor labels confidence/uncertainty on model elements** |
| 5 | Model change without breaking apps | Palantir (branching, migrations, lockfile) — best in class | Everyone else: ad hoc schema change, no migration tooling |
| 6 | One definition across tools | Databricks metric views, Atlan glossary, OWL ontologies | Meaning split between catalog and semantic layer; no single artifact |
| 7 | Governance/permissions on the model | Palantir, Databricks UC, GraphDB named graphs, Stardog | Small teams cannot afford the governance stack |
| 8 | Agent-readable semantics | Palantir OSDK/AIP, Atlan, Databricks agent metadata, metis | Agent consumption is platform-locked; nothing local |
| 9 | Portability of the model | OWL/RDF/SPARQL/SHACL; metaphactory markets "never locked in" | Palantir/Atlan/Databricks models proprietary; weak export |
| 10 | Cost/time to first useful ontology | Databricks (metadata auto), Atlan (connectors) | Real ontology work is weeks of specialist time |
| 11 | Keeping model in sync with schema drift | Databricks/Atlan observe drift | No tool *updates the model* when the source changes |
| 12 | What was true then vs now | — | **Bitemporal model/relations: greenfield** |

**Served well:** enterprise governance (Databricks, Atlan), formal semantics (Stardog, GraphDB), actionability (Palantir). **Under-served:** automatic discovery; confidence/provenance on every element; time-valid relations; cheap/local deployment; agent-first packaging.

## What a better version must do

1. **Derive before asking.** Tables→classes, keys→identity, FKs→relations, dates→validity, as a first draft humans review — not a blank canvas.
2. **Carry evidence on every element.** Source, method (stated/declared/inferred/guessed), confidence, timestamp — surfaced in UI, API and agent context.
3. **Make time first-class.** Valid-from/valid-to on relations, derived from date columns, so as-of questions are answerable.
4. **Run without a platform.** Local, embedded, no cluster; export OWL/SHACL; expose token-budgeted semantic context for agents.
5. **Stay cheap to re-run.** A new messy dataset with zero per-dataset code is the test.
6. **Refuse to lie.** A guessed key or link must look different from a declared one, everywhere.
7. **Support change.** Version, diff and approve model changes (borrow Palantir's migration/grace-period pattern).

## Candidate differentiators (Layer 1)

| # | Differentiator | Why it wins | Proof |
|---|---|---|---|
| D1 | Auto-derived ontology with stated-vs-guessed labels | Competitors require authoring and never label uncertainty | Unseen-source suite: % classes/keys/links recovered vs hand reference + confidence split |
| D2 | Keys/identity discovery without declarations (composite, accidental uniqueness) | CSVs and legacy DBs declare nothing | Adversarial corpus with no keys; identity precision/recall |
| D3 | Time-valid relations in the model | No Layer-1 vendor documents bitemporal relations | As-of query correctness on a changing source |
| D4 | Agent-ready context export + OWL/SHACL export | Agent paths are platform-locked; standards export kills lock-in objections | Tokens and answer accuracy vs raw-schema prompting |
| D5 | Local, no-cluster, no-connector deployment | All competitors need platform contracts | Time-to-first-model on a laptop; $0 infra for 1M rows |

## Sources

All accessed **2026-10-29**; grade in brackets.

1. [Palantir OSDK Maker README](https://raw.githubusercontent.com/palantir/osdk-ts/main/packages/maker/README.md) — object/link/interface/value-type/action primitives, schema migrations, lockfile. [B]
2. [Palantir docs — Ontology overview](https://www.palantir.com/docs/foundry/ontology/overview/) / [Core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts) — navigation only; body JS-rendered. [B-limited]
3. [palantir.com/pricing](https://www.palantir.com/pricing/) — redirects to homepage; no public price. [B for absence]
4. [Databricks — What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) (upd. 2026-09-11). [B]
5. [Databricks — Lineage](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) (upd. 2026-10-26). [B]
6. [Databricks — Metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views) (upd. 2026-09-11). [B]
7. [Databricks — Data Classification](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-classification) (upd. 2026-10-09). [B]
8. [Databricks — UC requirements](https://docs.databricks.com/aws/en/data-governance/unity-catalog/requirements) (upd. 2026-09-16). [B]
9. [atlan.com/pricing](https://atlan.com/pricing/) — resolves to talk-to-sales. [A]
10. [Dawiso — Atlan pricing](https://dawiso.com/glossary/atlan-pricing) (2026-10-16) — $120K/1yr, $220K/2yr, $340K/3yr. [C]
11. [Atlan — Context layer for AI](https://atlan.com/context-layer/) — products, customer claims (marketing). [B]
12. [Stardog — Pricing](https://www.stardog.com/pricing/). [B]
13. [Stardog — Virtual Graphs docs](https://docs.stardog.com/virtual-graphs/). [B]
14. [GraphDB 10.8 — Licensing](https://graphdb.ontotext.com/documentation/10.8/licensing.html) (upd. 2026-05-07). [B]
15. [GraphDB 10.8 — Reasoning](https://graphdb.ontotext.com/documentation/10.8/reasoning.html). [B]
16. [metaphactory](https://metaphactory.com/) — virtual KG over warehouses; AI-assisted modelling; customer metrics (marketing). [B]
17. [ontopic.ai](https://www.ontopic.ai/en/) → redirects to metaphactory.com. [A]
18. [W3C OWL 2 overview](https://www.w3.org/TR/owl2-overview/) (REC 2012). [B]
19. [W3C SHACL](https://www.w3.org/TR/shacl/) (REC 2017-07-20). [B]
20. [Protégé](https://protege.stanford.edu/). [B]

### Could not verify

- Any **Palantir list price** (none public) — do not quote a number.
- **Databricks DBU rates** for UC compute and Data Classification.
- **Stardog Enterprise / GraphDB EE per-core prices** (quote-only).
- Palantir case-study outcomes and self-hosted/air-gapped terms.
- Whether any vendor supports **bitemporal instance facts** — absence of docs is not proof of absence (D).
