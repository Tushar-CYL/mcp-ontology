# Evidence Base and Standards: Ontology, Knowledge Graph, Semantic Layer, Context for AI Agents (2023-2026)

NOTE: Plan mode was active, so this note is in the plan file. Its intended location is:
C:/Users/tusha/AppData/Local/Temp/claude/2e81386eb977b160/f3643104-2f23-4ceb-a2ba-205b24e80fe3/scratchpad/research_notes/Strata four layers and agents/06_evidence_standards.md
Copy it there once plan mode is off. Research date: 2026-11-03.

## 1. Benchmarks with real numbers

### Takeaway
Raw text-to-SQL accuracy on enterprise schemas has gone up a lot (dbt's re-run of the same questions: 32.7% in 2023 to 64.5% in 2026). Adding business semantics (KG, ontology, semantic layer or even a 4 KB markdown doc) still gives 17-30+ point gains in controlled paired studies. However, most paired studies are small (11-100 questions), and several were run by vendors.

### Cited Findings
**data.world / Sequeda, Allemang, Jacob (arXiv 2311.07509, Nov 13 2023)**
- Insurance-domain enterprise SQL schema, with an ontology and mappings that form a KG. GPT-4 zero-shot on SQL got about 16%; on the KG (SPARQL) it got about 54%. The abstract rounds these to 16%/54%. The often-quoted 16.7% vs 54.2% figures come from the paper body and secondary sources; the abstract does not show them. — [arXiv 2311.07509](https://arxiv.org/abs/2311.07509); 16.7/54.2 quoted by [Delphi](https://delphihq.substack.com/p/delphi-at-100-dbt-semantic-layer) (secondary)

**Follow-up: "Ontologies to the Rescue!" (Allemang and Sequeda, arXiv 2405.11706, May 20 2024)**
- Ontology-based Query Check (OBQC) flags SPARQL that violates the ontology (e.g. domain/range). An LLM Repair step then fixes it using the error explanation. Overall accuracy reached 72%, which includes "an additional 8% of 'I don't know'" results. Overall error rate fell to 20%. — [arXiv 2405.11706](https://arxiv.org/abs/2405.11706)
- This matters for refusal behaviour: the ontology turns some wrong answers into explicit "unknown" answers. — same source

**dbt Labs "Semantic Layer vs Text-to-SQL: 2026 Benchmark Update" (Apr 7 2026, Ganz and Perigaud). VENDOR-RUN.**
- Uses the same ACME Insurance dataset from data.world (15 tables, 3NF). 11 questions, each run 20 times. Models: claude-sonnet-4-6 and gpt-5.3-codex. Code is at github.com/dbt-labs/dbt-llm-sl-bench. — [dbt blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- Unmodeled schema, all questions: text-to-SQL scored GPT-4 (2023) 32.7%, Sonnet 4.6 64.5%, GPT-5.3-codex 64.5%. The semantic layer scored 60.5% / 72.7% / 72.7%. On the questions MetricFlow can answer, the semantic layer was 100% for both 2026 models. On the 3 questions that need too many entity hops, it was 0%. — [dbt blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- After adding 3 dbt models that an LLM generated: Sonnet 4.6 scored 90.0% with text-to-SQL and 98.2% with the semantic layer. GPT-5.3-codex scored 84.1% and 100%. GPT-5.2 got 68% with text-to-SQL. — same
- Qualitatively, the semantic layer errors out or says it cannot answer, while text-to-SQL returns plausible but wrong results. The post gives no refusal counts. The text-to-SQL baseline had the full schema in the prompt, which is generous. — same
- Commentary: about 25 points of the gain came from modeling alone, with no semantic layer involved. — [Hackernoon](https://hackernoon.com/why-better-schema-modeling-beats-better-text-to-sql-models) (secondary). Earlier, Delphi reported 83% with a semantic layer versus 16.7% / 54.2%, and later 100% on supported questions only, excluding multi-hop questions. Delphi is a vendor. — [Delphi](https://delphihq.substack.com/p/delphi-at-100-dbt-semantic-layer). Bodo/PyDough also claims 100% (vendor) — [Bodo](https://www.bodo.ai/blog/how-pydough-reached-100-accuracy-on-dbts-semantic-layer-benchmark)

**arXiv 2604.25149 (VERIFIED EXISTS): "Semantic Layers for Reliable LLM-Powered Data Analytics: A Paired Benchmark of Accuracy and Hallucination Across Three Frontier Models" (Rumiantsau and Fokeev, Apr 28 2026)**
- 100 questions on Cleaned Contoso Retail in ClickHouse. Models: Claude Opus 4.7, Claude Sonnet 4.6, GPT-5.4. Each model was run with the schema only, and again with the schema plus a hand-written 4 KB markdown "semantic layer" document covering measures, conventions and disambiguation rules. — [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
- Accuracy was 45.5-50.5% without the document and 67.7-68.7% with it, a gain of 17-23 points, all at p<0.01. Within each condition the three models were statistically indistinguishable. The authors conclude the document "accounts for essentially all of the significant variance." — same
- Caveat: the authors appear to be connected to a vendor (Fokeev and Rumiantsau are associated with Narrative BI / FlowShare-type BI tooling). This affiliation is unverified, so treat it as possible bias.

**Spider 2.0 (enterprise text-to-SQL; leaderboard read 2026-11-03; entries are undated)**
- Spider 2.0-Snow (547 tasks): #1 Genloop Sentinel Agent v2 Pro 96.70; #2 Native mini 96.53; #3 QUVI-3 + Gemini-3-pro-preview 94.15; #4 Tencent TCDataAgent-SQL 93.97; #8 "Ask Data with Relational Knowledge Graph" (AT&T CDO and RelationalAI) 86.28. — [spider2-sql.github.io](https://spider2-sql.github.io/)
- Spider 2.0-Lite (547 tasks: BigQuery 214, Snowflake 198, SQLite 135): #1 Tencent Tianqiong Data Agent + GLM 5.2 76.23; DecisionX 74.95; Kaelio ktx 73.67; Snowflake AI Research x UCSD DivSkill-SQL 73.13; Oracle SOMA-SQL 72.02. — same
- Spider 2.0-DBT (68 tasks): #1 SignalPilot 65.6; JetBrains Databao 60.29; next best about 41. — same
- Inference: Snow scores in the high 90s suggest that agentic systems with heavy context engineering have largely saturated it. Lite (multi-dialect) and DBT (transformation work) are still far from solved.

**BIRD family (bird-bench.github.io, read 2026-11-03)**
- BIRD test EX: #1 AskData (AT&T CDO-DSAIR) 83.40 (Oct 22 2026); GrainSQL 82.95; Huawei DataGallery 82.39; Tencent SiriusAI 82.28; Ant Agentar-Scale-SQL 81.67. Humans score 92.96. — [bird-bench](https://bird-bench.github.io/)
- BIRD-Interact (ICLR 2026 Oral), interactive/ambiguous multi-turn tasks: best success rate on Full (600) is 16.33% (Aug 2025). GPT-5 gets 8.67% on c-Interact and 17.00% on a-Interact. — same
- BIRD-Critic (SQL debugging): the page gives no top score. A BIRD-Critic-SQLite set (500 issues) was released Mar 2026. LiveSQLBench-Base-Full-V1: Gemini-2.5-pro scores 35.67 (normal) and 28.67 (colloquial). — same
- Inference: single-shot SQL is about 10 points below humans. Interactive clarification and ambiguity are still severely unsolved (under 20%), and that is the gap that semantic/ontology context and clarification policies target.

**GraphRAG evaluation: "When to use Graphs in RAG" / GraphRAG-Bench (Xiang et al., arXiv 2506.05690, ICLR 2026)**
- The paper is motivated by reports that GraphRAG "frequently underperforms vanilla RAG on many real-world tasks." Secondary summaries say vanilla RAG matches or beats GraphRAG on simple fact retrieval, while GraphRAG holds up better on complex multi-hop reasoning as corpus size grows. — [arXiv 2506.05690](https://arxiv.org/abs/2506.05690v3); [ICLR 2026](https://iclr.cc/virtual/2026/poster/10007992)
- One summary reports Global-GraphRAG evidence recall at 83.1%, versus vanilla RAG's higher context relevance at 78.8%. The 10-100x token cost claim is UNVERIFIED. — [alphaxiv summary](https://www.alphaxiv.org/benchmarks/the-hong-kong-polytechnic-university/graphrag-bench) (secondary)

### Inferences
- Across 2023-2026, the size of the gain from "semantics" is fairly consistent: +17 to +38 points in controlled paired designs (16→54, 45→68, 64.5→72.7/100%). The baseline keeps rising as models improve, but the gap has not closed.
- Two failure classes show up: (a) meaning errors such as wrong metric definition or wrong join semantics, which semantic layers and ontologies fix; and (b) coverage errors, where the semantic layer cannot express the question (dbt's 0% on multi-hop). This supports a stack where the KG/ontology handles multi-hop and the semantic layer handles governed metrics.
- The leaderboard leaders (AT&T on both BIRD and Spider, and RelationalAI's "Relational Knowledge Graph") show that KG-backed context is competitive on public leaderboards, not only in vendor benchmarks.

### Gaps
- I found no public benchmark that measures citation accuracy or evidence-pack quality for context packs over enterprise structured data. Relevant analogues are RAG attribution benchmarks such as ALCE, which I did not verify here.
- I could not confirm the per-quadrant breakdown in 2311.07509 from the abstract page.
- I could not verify the dates of individual Spider 2.0 leaderboard entries.

## 2. Papers on combining layers

### Takeaway
The academic line runs schema → ontology (RIGOR, LLM-generated) → KG → constrained query generation with ontology checks. Data-agent surveys place current systems at L2 to "proto-L3" autonomy.

### Cited Findings
- RIGOR (arXiv 2506.01232, Nayyeri et al., Jun 2025): uses retrieval-augmented LLM generation to produce OWL ontologies from relational DBs. It iterates table by table along foreign keys, using schema docs, a domain-ontology repository and a growing core ontology. It emits provenance-tagged delta fragments that a judge-LLM or human checks before merging. It was evaluated on medical DBs, and the authors claim no prior work had done LLM ontology generation from relational DBs. — [arXiv 2506.01232](https://arxiv.org/abs/2506.01232v1)
- Follow-up arXiv 2511.05991 compares ontology learning and KG construction methods and their effect on RAG, building on RIGOR. — [arXiv 2511.05991](https://arxiv.org/pdf/2511.05991)
- "A Survey of Data Agents: Emerging Paradigm or Overstated Hype?" (arXiv 2510.23587, Zhu, Li, Luo et al., Oct 2025, rev. Feb 2026) proposes L0-L5 autonomy levels modeled on SAE J3016 and names the L2→L3 transition (from procedural execution to autonomous orchestration) as the current frontier. — [arXiv 2510.23587](https://arxiv.org/abs/2510.23587)
- Companion paper "Data Agents: Levels, State of the Art, and Open Problems" (arXiv 2602.04261) describes "Proto-L3" systems. — [papers.cool](https://papers.cool/arxiv/2602.04261)
- Ontology check and repair (2405.11706) is the clearest paper where the ontology acts as a validator at query time, not only as context. — [arXiv 2405.11706](https://arxiv.org/abs/2405.11706)

### Inferences
- A defensible pipeline backed by papers: generate the ontology (RIGOR-style, human or judge in the loop) → map to a KG → ground questions to governed metrics → validate the generated query against ontology constraints (OBQC) → repair or refuse.

### Gaps
- I found no peer-reviewed head-to-head of "KG vs semantic layer" on the same questions. The dbt and data.world results use the same dataset but come from different studies and models.

## 3. Standards and protocols status (as of Nov 2026)

### Takeaway
MCP (current version 2026-07-28) and A2A (v1.0, Mar 2026) both sit under the Linux Foundation's Agentic AI Foundation. OSI is now Apache Ossie (Incubating), with a v0.1 spec. RDF 1.2 is at Candidate Recommendation, and SHACL 1.2 is still a Working Draft.

### Cited Findings
- **RDF 1.2 Concepts**: W3C Candidate Recommendation Snapshot, 7 Apr 2026. The document says it will not advance before 5 May 2026. I found no Recommendation yet. — [w3.org/TR/rdf12-concepts](https://www.w3.org/TR/rdf12-concepts/)
- **SHACL 1.2**: Core is a Working Draft (latest seen 28 Aug 2026). Rules is a WD (3 Jul 2026). SPARQL Extensions is a WD. The Data Shapes WG charter runs 16 Dec 2024 to 31 Dec 2026, and SHACL 1.2 timing depends on RDF/SPARQL 1.2. — [SHACL 1.2 Core WD](https://www.w3.org/TR/2026/WD-shacl12-core-20260828/); [charter](https://www.w3.org/groups/wg/data-shapes/charters/active/); [WG mail](https://lists.w3.org/Archives/Public/public-rdf-star-wg/2026Mar/0005.html)
- OWL 2 (2012) and SKOS (2009) remain the current Recommendations. I found no new versions; this comes from background knowledge and was not re-fetched.
- **Apache Ossie (Incubating)**, formerly Open Semantic Interchange (OSI): entered the Apache Incubator on 2026-06-22. It was renamed to avoid confusion with the Open Source Initiative. The spec is unchanged at v0.1. Code is at github.com/apache/ossie and the site at ossie.apache.org. A Polaris converter has been merged, according to Dremio. — [incubator.apache.org/projects/ossie](https://incubator.apache.org/projects/ossie.html); [Snowflake](https://snowflake.com/en/blog/apache-ossie-open-semantic-interchange-incubator); [Dremio](https://www.dremio.com/blog/apache-ossie-the-open-semantic-interchange-joins-the-apache-incubator); [OSI discussion #164](https://github.com/open-semantic-interchange/OSI/discussions/164)
- **MCP**: the current protocol version is 2026-07-28. It changed from a handshake to per-request version negotiation through the `_meta` key `io.modelcontextprotocol/protocolVersion` and the `MCP-Protocol-Version` header, and added a mandatory `server/discover` RPC. Revisions 2025-11-25 and earlier are handshake-based. A deprecation policy keeps deprecated features for at least 12 months. — [modelcontextprotocol.io versioning](https://modelcontextprotocol.io/specification/versioning)
- **Agentic AI Foundation (AAIF)**: launched under the Linux Foundation on 9 Dec 2025 with MCP (Anthropic), goose (Block) and AGENTS.md (OpenAI). A2A became an AAIF-hosted project in Aug 2026; sources disagree on whether it was the 17th or the 20th. Google had already donated A2A to the LF in 2025. A2A v1.0 shipped Mar 2026 with signed agent cards, multi-tenancy and version negotiation. AAIF reportedly has 250+ members. — [Flowhunt](https://www.flowhunt.io/blog/agentic-ai-foundation-a2a-mcp-standards/); [Pebblous](https://blog.pebblous.ai/blog/a2a-mcp-agentic-ai-foundation-authorization/en/) (both secondary; confirm against the LF press release)
- OpenLineage (LF AI & Data) and Apache Iceberg/Polaris: not re-verified in this pass. Their relevance is that lineage feeds the "Validate" step, and Polaris now gets an Ossie converter. — [Dremio](https://www.dremio.com/blog/apache-ossie-the-open-semantic-interchange-joins-the-apache-incubator)

### Inferences
- For Strata: serve over MCP 2026-07-28 while staying backward compatible with 2025-11-25 clients. Export semantic-layer definitions as Ossie v0.1 YAML for interoperability. Export ontology and shapes as OWL/SHACL (Core 1.0 is stable; 1.2 is not yet). Expose agents via A2A v1.0 agent cards.

### Gaps
- I did not fetch OpenLineage's current spec version, Polaris graduation status, or the official AAIF press release.

## 4. Reference architectures

### Takeaway
Every major vendor now describes the same chain: governed data platform → semantic/business model (metrics) → ontology/graph of entities and relations → agent context → agents, exposed via MCP. They differ in which layer is primary: metrics-first (dbt, Databricks, Snowflake) or ontology-first (Palantir, Microsoft Fabric IQ, TextQL, NVIDIA).

### Cited Findings
- **Microsoft Fabric IQ**: combines OneLake data, Power BI semantic models and an ontology (entity types, properties, relationships and rules bound to OneLake data). Ontologies can be generated from existing semantic models. Fabric data agents, operations agents, Foundry IQ, Copilot Studio "and any MCP client" consume the same ontology. Release status conflicts: Build 2026 GA claims versus ontology still in preview, and an Aug 2026 roadmap that still says preview. — [element61](https://www.element61.be/en/resource/fabric-iq-when-your-data-needs-speak-business); [letsdatascience](https://letsdatascience.com/news/microsoft-expands-fabric-iq-as-a-context-layer-for-ai-agents-e9a90bd8); [Directions on Microsoft](https://www.directionsonmicrosoft.com/roadmaps/ref/fabric-iq-roadmap/); [Gartner First Take](https://www.gartner.com/en/insights/gartner-first-takes/microsoft-fabric-iq)
- **NVIDIA Auto Ontology** (Apache 2.0, NGC container): builds a graph-based semantic layer over Databricks, Postgres, Snowflake and DuckDB, and exposes it via an MCP server, CLI and REST. It defaults to Nemotron NIM but works with any OpenAI-compatible model. Its workflow is Discover (ontology from metadata) → Ground (questions to governed metrics, reconciling definitions) → Validate (certification rules and lineage) → Expose (MCP/CLI/REST) → Learn (certified corrections). Some sources describe four stages. The "90% faster ontology build" claim is a vendor claim. — [NGC](https://catalog.ngc.nvidia.com/orgs/nvidia/-/containers/auto-ontology/-); [AlphaSignal](https://alphasignal.ai/news/nvidia-s-auto-ontology-stops-ai-agents-from-querying-the-wrong-data); [besthub](https://www.besthub.dev/articles/nvidia-s-auto-ontology-90-faster-ontology-building-but-governance-remains-key-b83fd98bb262) (secondary)
- **TextQL**: the ontology is the semantic layer, stored as version-controlled, role-aware `.tql` files that render SQL. The agent "Ana" navigates only the relevant parts at runtime. — [TextQL docs](https://docs.textql.com/core/ontology/overview)
- Palantir (data → Ontology → AIP), Databricks (Unity Catalog → metric views → Genie) and Atlan (context layer): not re-verified in this pass. Other researchers cover vendors.

### Inferences
- The common pattern maps onto Strata's layers: Ontology = types and rules; KG = instances and relations bound to sources; Semantic layer = governed metrics, which are the only things allowed to compute numbers; Context = a question-scoped pack of definitions, lineage and cited evidence; Agents consume all of it over MCP. NVIDIA's Discover/Ground/Validate/Expose/Learn loop is the closest public match to an end-to-end lifecycle, and the repo already has files with these names (semantic/validate.py, semantic/feedback.py, tests/integration/test_ground_validate_learn.py).

### Gaps
- I did not verify primary Microsoft Learn docs for Fabric IQ GA status, or the NVIDIA GitHub README.

## 5. Where each layer measurably helps

### Takeaway
The evidence is strongest for semantic definitions improving accuracy and for ontology validation converting errors into refusals. It is weak for latency/cost and for citation accuracy.

### Cited Findings
- KG/ontology as query target: 16% → 54% (GPT-4). — [2311.07509](https://arxiv.org/abs/2311.07509)
- Ontology as validator plus repair: 54% → 72% accuracy, 8% "I don't know", 20% errors. — [2405.11706](https://arxiv.org/abs/2405.11706)
- Semantic definitions (4 KB doc): +17-23 points across 3 frontier models; model choice became irrelevant. — [2604.25149](https://arxiv.org/abs/2604.25149)
- Governed semantic layer (dbt MetricFlow): 100% on in-scope questions, 0% on out-of-scope; fails safe with errors instead of wrong numbers (qualitative, vendor-run). Modeling alone gave +25 points to text-to-SQL. — [dbt](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
- GraphRAG over documents: helps multi-hop and large corpora, hurts or ties on simple lookup, and costs more tokens. — [2506.05690](https://arxiv.org/abs/2506.05690v3)

### Inferences
- Strata could position itself with three claims: (1) semantics close about 20+ points of accuracy regardless of model; (2) ontology checks make "I don't know" a first-class result; (3) the semantic layer must pair with KG traversal for multi-hop questions, or coverage collapses.

### Gaps
- I found no rigorous public latency/cost numbers for semantic layer versus text-to-SQL agents, no independent hallucination-rate benchmark apart from 2604.25149's framing, and no citation-accuracy benchmark for structured-data evidence packs.

## 6. Critiques

### Takeaway
There are three live critiques: semantic layers are scoped to a single warehouse (TextQL), good modeling and schema docs capture most of the gain (dbt's own data), and ontology maintenance has a cost. Each critique comes from a party with something to sell.

### Cited Findings
- TextQL, "Semantic Layers Are a Patch. Ontologies Are the Fix." (Ben Shi, May 26 2026): semantic layers are limited to one warehouse, cannot answer cross-system questions, and create vendor lock-in. Its benchmark is internal, and its chart compares GPT-4 (2023) with Sonnet 4.6 (2026), which conflates model gains with layer gains. — [TextQL blog](https://textql.com/blog/semantic-layers-are-a-patch-ontologies-are-the-fix); [FourWeekMBA](https://fourweekmba.com/ai-textql-ontology-ga-context-not-capability/)
- The "good schema and docs suffice" argument is supported by dbt's 64.5% → 90% from 3 LLM-generated models (no semantic layer), and by 2604.25149 using only a 4 KB markdown document. — [dbt](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026); [2604.25149](https://arxiv.org/abs/2604.25149)
- Maintenance cost: NVIDIA's pitch (90% less build time) and RIGOR's judge loop both implicitly concede that manual ontology building is costly. Commentators warn that "Learn" must not turn all feedback into rules automatically. — [besthub](https://www.besthub.dev/articles/nvidia-s-auto-ontology-90-faster-ontology-building-but-governance-remains-key-b83fd98bb262)

### Inferences
- The defensible synthesis is that the value lies in explicit business semantics, not in any particular format. Strata should auto-generate those semantics and keep them governed (versioned, certified), and show measured gains on a paired benchmark of its own (for example, re-running the ACME insurance set with and without each layer).

### Gaps
- I found no independent cost-of-ownership study for ontology maintenance.
