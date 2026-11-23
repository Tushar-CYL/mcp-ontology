# Evaluation, graph engines and the "Activate" step for Strata

Research date: 2026-11-18. Most numbers below come from vendors or from secondary aggregators (Atlan in particular publishes many comparison pages and sells a competing context product). Each finding says which kind of source it is. Facts marked UNVERIFIED should be checked before anyone repeats them to a client.

## A. How to measure answer accuracy against real client reports

### Takeaway
The industry standard is **execution accuracy**: compare the result set the system returns with the result of a trusted "gold" query, allowing for column order, row order and numeric rounding. Every major vendor's eval feature works this way (Databricks Genie benchmarks, Snowflake Cortex Analyst evaluations). Public leaderboards are a poor guide to enterprise accuracy. On real enterprise schemas, raw text-to-SQL drops to low double digits, while grounding in a semantic layer or knowledge graph raises it a great deal. Strata should build its own golden set from the client's existing reports and score it by result matching. An LLM judge should only handle the questions that have no gold number.

### Cited Findings
**Benchmarks and published numbers**
- Original Spider 2.0 paper: the best code agent (o1-preview) solved 21.3% of Spider 2.0 tasks, against 91.2% on Spider 1.0 and 73.0% on BIRD. A third-party mirror of the leaderboard (imported May 2026) lists top agents at about 94–97, but the variant and scoring behind those numbers are unclear. Treat the high numbers with caution. — [benchmarklist.com Spider 2.0](https://benchmarklist.com/benchmarks/spider_2_0/); [wizwand SOTA](https://www.wizwand.com/sota/text-to-sql-execution-on-sql-execution-benchmarks-spider-bird)
- BIRD: human experts reach about 92.96% execution accuracy. Reported top LLM systems are in the 70s (e.g. Gemini-SQL + Gemini 2.5 Pro at 77.14%; Claude Opus 4.6 reported at 70.15% on test). These are secondary reports. — [benchmarklist.com Spider](https://benchmarklist.com/benchmarks/spider/); [codingfleet 2026](https://codingfleet.com/blog/best-ai-models-for-sql-database-coding-in-2026-text-to-sql-orms-and-beyond/)
- **The benchmarks themselves contain errors.** A Jan 2026 study found annotation error rates of 52.8% (BIRD Mini-Dev) and 62.8% (Spider 2.0-Snow). Correcting BIRD Dev changed agent scores by −7% to +31% (relative) and moved agents up to 9 places in the ranking. — [arXiv 2601.08778](https://web3.arxiv.org/abs/2601.08778); [Daniel Kang substack](https://ddkang.substack.com/p/pervasive-annotation-errors-break)
- BEAVER (built from real private enterprise warehouses): even advanced agent frameworks on GPT-5.2 reached only **10.8%** execution accuracy, per secondary summary. The original 2024 paper reported near-zero results for off-the-shelf LLMs. — [BEAVER arXiv 2409.02038](https://arxiv.org/pdf/2409.02038)
- EntSQL (EMNLP 2026 Findings): the best accuracy on Hard queries in the "Base" setting (no enterprise knowledge supplied) was 0.8%. — [ACL Anthology 2026.findings-emnlp.1971](https://aclanthology.org/2026.findings-emnlp.1971/)
- data.world (Sequeda, Allemang, Jacob, Nov 2023): GPT-4 zero-shot scored **16.7%** on 43 insurance business questions over SQL. It scored **54.2%** when it was given a knowledge-graph (ontology) representation of the same database, roughly 3x better. — [arXiv 2311.07509](https://arxiv.org/pdf/2311.07509v1.pdf); [data.world blog](https://data.world/blog/generative-ai-benchmark-increasing-the-accuracy-of-llms-in-the-enterprise-with-a-knowledge-graph)
- data.world follow-up (June 2024): adding Ontology-based Query Check (OBQC) and LLM repair gave 4.2x over baseline. This is the same as Strata's "check" step. — [data.world GenAI benchmark II](https://data.world/blog/genai-benchmark-ii-increased-llm-accuracy-with-ontology-based-query-checks-and-llm-repair)
- dbt Labs, "Semantic Layer vs Text-to-SQL: 2026 Benchmark Update" (Apr 7, 2026): ACME Insurance dataset, 11 questions, 20 runs per model. Semantic-layer grounding took Claude Sonnet 4.6 from 90.0% to 98.2% and GPT-5.3-Codex from 84.1% to 100% (secondary report). Modelling the schema, without any semantic layer, took text-to-SQL from 64.5% to 90.0%. Its key qualitative point: the semantic layer *refuses* questions it can't express, while "Text-to-SQL will cheerfully give you a wrong number." — [dbt blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026); secondary figures via [Atlan](https://atlan.com/know/ai-agent/data-for-ai/text-to-sql-for-enterprise/)
- A competing vendor (Bodo/PyDough) claims 220/220 (100%) on the same 11 dbt questions. The test set is very small, so it saturates easily. — [Bodo blog](https://www.bodo.ai/blog/how-pydough-reached-100-accuracy-on-dbts-semantic-layer-benchmark)
- Snowflake says Cortex Analyst with a semantic model reaches "90%+ SQL accuracy on real-world use cases". This is an internal set of about 150 BI questions with no published method, against 51% for GPT-4o on the same set. Vendor claim. — [Snowflake engineering blog](https://snowflake.com/en/engineering-blog/cortex-analyst-text-to-sql-accuracy-bi)
- AtScale (a semantic-layer vendor) reports Cortex Analyst at 100% on AtScale's own NLQ benchmark when paired with its semantic layer. Vendor claim. — [AtScale](https://www.atscale.com/?p=27449)

**How vendors let customers build eval sets**
- **Databricks Genie benchmarks**: each benchmark question can carry a gold SQL answer. Genie compares result sets. An answer counts as "Good" if the SQL matches exactly, or the results match apart from extra columns, different sort order, or **numbers that agree to 4 significant digits**. Empty results and errors count as "Bad". Questions with no gold SQL need manual Good/Bad review. Databricks recommends 2–4 phrasings per question. Benchmark questions run as fresh conversations and are not used as context. Runs are timestamped so accuracy can be tracked after each instruction change. — [Databricks docs](https://docs.databricks.com/aws/en/genie/benchmarks); [Databricks blog](https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way)
- **Snowflake Cortex Analyst evaluations**: accuracy is the share of *verified queries* for which the generated SQL is judged correct. Before each run it makes a temporary copy of the semantic view with the chosen verified queries removed, so the test is not just recall of memorised answers. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- Databricks also has "Request Review": end users flag answers, and the authors verify or correct them. This turns production traffic into new test cases. — [Databricks blog](https://www.databricks.com/blog/building-confidence-your-genie-space-benchmarks-and-ask-review)

### Inferences
- **Recommended protocol for turning reports into a golden set** (built from the vendor practices above, not taken from any single source):
  1. Take 3–5 real client reports, for example a Power BI sales dashboard, a monthly trade-spend Excel file, or a share-of-shelf deck. For a CPG client such as Unilever or Kellogg's, use the client's own internal reports. Published annual reports only give rounded group totals.
  2. List every *number* on each report and write the business question it answers, e.g. "Net revenue, Snacks, EU, Q3 2026". Record the filters, grain, period, currency and units shown. Keep the report's figure as the gold value, and where possible also the SQL or DAX measure that produced it.
  3. Write 2–4 phrasings of each question, as Databricks recommends. Include hard cases: synonyms such as "turnover" for "revenue", relative dates ("last quarter"), fiscal versus calendar periods, and questions that *should* be refused.
  4. Score by result-set matching. Allow for column and row order. Compare numbers with a tolerance tied to how the report displays them: a value shown as "€1.2bn" can only be checked to that precision. Databricks' 4-significant-digit rule is a reasonable default. Check units and currency separately, because an answer off by a factor of 1000 is a common silent failure.
  5. Report several measures: execution accuracy, *refusal correctness* (did it decline what it can't answer, per the dbt point), consistency across phrasings, and consistency across repeated runs (dbt ran each question 20 times).
  6. Hold the golden questions out of the context the system is given, as Snowflake and Databricks do. Otherwise the test only measures memory.
  7. Use an LLM judge only for narrative or explanatory answers, and spot-check its verdicts by hand. LLM judges can be fooled by fluent wrong numbers and tend to favour long answers. I found no specific source with numbers on this in the time available.
- **Suggested acceptance thresholds** (judgement, no standard exists): at least 95% correct on "certified" metrics answered through the semantic layer, 0 silent wrong numbers on the top-20 report KPIs, at least 90% agreement across phrasings, and any wrong answer must have produced a visible check warning. Vendor "90%+" claims are on their own question sets, and enterprise benchmarks (BEAVER, EntSQL) show that raw text-to-SQL without context fails badly. So report both a "governed metric" score and an "ad-hoc" score.
- Strata's link → traverse → check → pack → answer pipeline lines up with the data.world finding (ontology plus query check, 4.2x) and the dbt finding (refuse rather than guess). That is the story the accuracy test should be designed to prove.

### Gaps
- I did not find published accuracy numbers for Cube's AI/semantic API or for AtScale's own system on a neutral benchmark.
- I found no peer-reviewed study that quantifies how unreliable LLM-as-judge is for numeric business answers.
- The current top of the BIRD and Spider 2.0 leaderboards could not be confirmed from the official sites. Secondary mirrors conflict.

## B. Graph engines: is Neo4j the leader, licence costs, alternatives (incl. Timbr)

### Takeaway
Yes. Neo4j is clearly the most *popular* graph DBMS on DB-Engines, far ahead of the rest. DB-Engines measures popularity, not revenue share. Neo4j Community Edition is free (GPLv3) but single-node and has no role-based access control. Clustering, RBAC and GDS for production need commercial licences, and Neo4j only quotes those prices through sales. Many "open" alternatives have changed licence or vanished: Kuzu was archived in Oct 2025, ArangoDB moved to a restricted community licence, Memgraph's Community Edition is BSL, and FalkorDB is SSPL. Strata's use case is questions over existing warehouse tables. For that, a **virtual graph** (Timbr, Stardog, Ontop, DuckPGQ/SQL-PGQ, or Strata's own) avoids copying data and avoids a second licence. A native graph DB only pays off for deep multi-hop or graph-algorithm workloads.

### Cited Findings
**Market position**
- The DB-Engines graph ranking puts Neo4j at #1. An independent guide (Feb 2026) gives a score of 49.26, far ahead of the field, with Memgraph around #10 (score about 2). DB-Engines measures popularity (search interest, job ads, discussions), not market share. — [DB-Engines graph ranking](https://db-engines.com/en/ranking/graph+dbms); [unanswered.io guide](https://unanswered.io/guide/most-popular-graph-databases-and-companies-using-them)
- Memgraph's own July 2026 list, which counts graph-only systems, has Neo4j first and TigerGraph, JanusGraph and Memgraph in the top 5. This is a vendor-authored list. — [Memgraph blog](https://memgraph.com/blog/db-engines-ranking-top-graph-databases)

**Neo4j**
- Community Edition is GPLv3. Enterprise uses a separate commercial licence. — [Neo4j licensing](https://neo4j.com/?p=425989)
- Enterprise adds backups, clustering and failover, plus RBAC, property- and sub-graph-level access control and LDAP/AD. Community is for single-instance use, and all its users have full access rights. — [Neo4j Operations Manual](https://neo4j.com/docs/operations-manual/current/introduction/)
- Neo4j does not publish self-hosted Enterprise or GDS Enterprise prices. Enterprise is licensed by number and size of servers. GDS Enterprise is a separate annual licence. A free developer licence for Enterprise ships with Neo4j Desktop. — [Neo4j pricing](https://neo4j.com/pricing); [Neo4j community forum](https://community.neo4j.com/t/pricing-details-on-using-enterprise-edition/72957)
- AuraDB Business Critical is listed at about $292/month for a 2 GB, 1-CPU instance ($0.40/h). Aggregators quote other figures. Virtual Dedicated Cloud and AuraDS Enterprise are "contact sales". — [Neo4j Aura pricing](https://neo4j.com/cloud/aura/pricing/)
- A figure of "$75k–100k per month" for Enterprise circulating on the forum was an AI-generated estimate and is UNVERIFIED. Do not repeat it. — [Neo4j community forum](https://community.neo4j.com/t/pricing-details-on-using-enterprise-edition/72957)

**Alternatives and their licence status (late 2026)**
- **Kuzu (embedded, Cypher, MIT)**: GitHub repo archived on Oct 10, 2025. Final release v0.11.3. Kùzu Inc. stopped sponsoring it. Several sources say Apple acquired Kùzu Inc. (UNVERIFIED, no primary confirmation). Forks: **LadybugDB** (the most active), RyuGraph. — [The Register](https://www.theregister.com/2025/10/14/kuzudb_abandoned/); [oneuptime](https://oneuptime.com/blog/post/2026-08-12-kuzu-archived-pin-0-11-3-fork-or-migrate/view); [DBDB LadybugDB](https://dbdb.io/db/ladybugdb/revisions/2); [RyuGraph](https://blog.ryugraph.io/posts/introducing-predictable-labs-and-ryugraph)
- **Memgraph**: Community Edition is under the Business Source License. Enterprise is under the Memgraph Enterprise License. Enterprise pricing "starts at $25,000/year for 16 GB" (vendor page). — [Memgraph legal](https://memgraph.com/legal); [Memgraph enterprise](https://memgraph.com/enterprise)
- **ArangoDB**: from v3.12 the Community Edition moved from Apache 2.0 to the ArangoDB Community License. It has a 100 GiB data limit and needs a commercial agreement for commercial use (ArangoDB's own pages describe the commercial scope inconsistently). — [ArangoDB licensing post](https://arango.ai/?p=2755); [ArangoDB downloads](https://arango.ai/downloads)
- **FalkorDB**: the core is SSPLv1 (not OSI-approved). The client SDKs are MIT. A commercial licence is available. — [FalkorDB license docs](https://docs.falkordb.com/license.html)
- **TigerGraph Community Edition** (Mar 2025): free and production-usable under a proprietary licence. Limits are 16 CPUs, 200 GB graph and 100 GB vector storage. No HA, no support, and no direct upgrade to Enterprise. — [TigerGraph blog](https://tigergraph.com/blog/tigergraph-db-community-edition-the-most-powerful-free-graph-vector-database-for-turbocharging-ai/); [TigerGraph licence (Mar 2026)](https://www.tigergraph.com/license-agreement/); [editions comparison](https://docs.tigergraph.com/tigergraph-server/4.2/intro/comparison-of-editions)
- **Apache AGE**: Apache 2.0 PostgreSQL extension with openCypher support. GA on Azure Database for PostgreSQL in May 2025. The latest stable release on PGXN is 1.4.0, date unconfirmed. — [PostgreSQL news](https://www.postgresql.org/about/news/apache-age-110-2504/); [PGXN](https://pgxn.org/dist/apacheage/1.1.0); [Azure GA](https://mc.merill.net/message/AZ491161)
- **Amazon Neptune**: managed only. Serverless is billed per second in NCUs (about 2 GB RAM each), with a minimum of 1 NCU since 2023. The per-NCU-hour price could not be confirmed from AWS: secondary sites quote $0.1098 and $0.1608 for us-east-1. — [AWS Neptune pricing](https://aws.amazon.com/neptune/pricing); [AWS what's new](https://aws.amazon.com/about-aws/whats-new/2023/03/amazon-neptune-serverless-scales-down-1-ncu-costs)
- **DuckPGQ**: a DuckDB community extension from CWI that implements ISO SQL:2023 SQL/PGQ graph pattern matching and path finding inside DuckDB (CIDR 2023 paper). — [DuckDB library](https://duckdb.org/library/duckpgq); [CIDR 2023](https://vldb.org/cidrdb/2023/duckpgq-efficient-property-graph-queries-in-an-analytical-rdbms.html)
- **Ontop**: an open-source Virtual Knowledge Graph system under Apache 2.0. It exposes relational databases as knowledge graphs without moving the data, supports R2RML and Ontop mappings, and answers SPARQL queries. Stable version 5.5.0 was released Feb 14, 2026. — [Ontop GitHub](https://github.com/ontop/ontop); [Ontop guide](https://ontop-vkg.org/guide/)
- **Timbr**: a virtual "SQL ontology" or semantic layer that maps ontology concepts onto existing CRM, ERP and lakehouse tables without moving data, queried in SQL. Tiers are Teams, Business and Enterprise with no public price list. A free trial is offered. TrustRadius shows "$599/month per user", edition unknown (UNVERIFIED). Timbr publishes "Timbr vs Neo4j" and "Timbr vs Stardog" pages (vendor-biased). — [Timbr SQL KG](https://timbr.ai/sql-knowledge-graph/); [Timbr vs Neo4j](https://timbr.ai/timbr-vs-neo4j/); [TrustRadius](https://www.trustradius.com/compare-products/timbr); [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-kbswx475a3o52)

### Inferences
- **Answer for the manager**: Neo4j is the clear popularity leader. Real cost only appears once you need clustering, RBAC, or GDS in production, and those prices are quote-only. Credible lower-cost routes:
  1. **Don't copy the data.** Use a virtual graph over the warehouse: Timbr (commercial, SQL-native), Stardog (commercial, SPARQL), Ontop (free, Apache 2), or DuckPGQ/SQL-PGQ (free, inside DuckDB, which Strata already uses).
  2. If a real graph store is needed: Apache AGE (Apache 2, on Postgres), TigerGraph Community (free but proprietary and capped), Memgraph (BSL, $25k+/yr Enterprise), Neptune (pay-as-you-go on AWS).
  3. Avoid building on Kuzu itself. If you need embedded Cypher, pin 0.11.3 or evaluate LadybugDB.
- **When virtual beats copying**: virtual is better when the questions are BI-style (aggregates over facts with 1–3 joins), when the warehouse is the system of record with access policies already in place, and when freshness matters (no ETL lag and no second copy to govern). Copy into a graph DB when you need deep variable-length traversals (fraud rings, supply-chain paths beyond 4–5 hops), graph algorithms (PageRank, community detection, GDS), or sub-second traversal under high concurrency. Strata's existing virtual KG over DuckDB fits the first case. SQL/PGQ through DuckPGQ is a standards-based way to add path queries without a new engine.
- SQL/PGQ is part of ISO SQL:2023, so property-graph querying is moving into relational engines. This weakens the case for a separate graph DB in BI settings. DuckPGQ's documentation confirms the SQL:2023 basis. I did not check which other engines (Oracle 23ai and others) support it.

### Gaps
- I did not obtain Stardog pricing or the current status of its free tier. JanusGraph's current release activity was not checked.
- I could not verify Timbr's actual pricing model (per user or per platform).
- No reliable public revenue or market-share numbers for graph DBMS vendors exist in what I found. DB-Engines is popularity only.
- The Apple–Kùzu acquisition is reported but unconfirmed by a primary source.

## C. "Activate": publishing context to agents (MCP, context packs, A2A, semantic-layer APIs)

### Takeaway
MCP is now the default way to expose governed context to agents. The current spec revision is **2026-07-28**. It made the protocol stateless (no session ID, no initialize handshake), moved tasks into an extension, added caching hints, and standardised on OAuth 2.x with Client ID Metadata Documents, deprecating dynamic client registration. Every data-platform vendor now ships an MCP server that exposes *governed* objects (metrics, semantic views, catalog and lineage) rather than raw tables: dbt, Snowflake, Databricks, Atlan, Neo4j. A2A (Linux Foundation) covers agent-to-agent delegation and complements MCP. Strata should publish its context pack as an MCP server with read-only, permission-scoped tools, plus a plain REST/JSON export.

### Cited Findings
**MCP spec**
- The 2025-11-25 revision added Client ID Metadata Documents (CIMD), OpenID Connect Discovery support, enterprise-managed access via Cross App Access, formal machine-to-machine OAuth, and experimental tasks. Authorization stays OPTIONAL. Servers MUST publish OAuth Protected Resource Metadata (RFC 9728). — [MCP 2025-11-25 changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog); [WorkOS](https://workos.com/blog/mcp-2025-11-25-spec-update)
- The 2026-07-28 revision (current), major changes:
  - Protocol-level sessions and the `Mcp-Session-Id` header are removed, and the `initialize` handshake is gone, so the protocol is stateless.
  - A required `server/discover` call is added.
  - `subscriptions/listen` replaces the GET stream and resource subscribe.
  - Tasks move into the official extension `io.modelcontextprotocol/tasks`.
  - Multi Round-Trip Requests replace server-initiated sampling and elicitation.
  - `ttlMs`/`cacheScope` caching hints are required on list and read results.
  - Deterministic tool ordering is recommended (it improves prompt-cache hit rates).
  - OpenTelemetry trace propagation is added.
  - Clients MUST validate `iss` (RFC 9207) and key their credentials by issuer.
  - Roots, Sampling and Logging are deprecated. Dynamic Client Registration is deprecated in favour of CIMD.
  - Removed features get at least 12 months' deprecation notice.

  — [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

**Vendor MCP / semantic APIs**
- **dbt MCP server** (remote): tools to query Semantic Layer metrics, inspect model metadata and lineage, and run SQL. dbt's framing is "the semantic layer provides the context, MCP provides governed access, and agent skills provide the proven workflows". Snowflake Cortex agents can call the remote dbt MCP server as a tool. — [dbt blog](https://www.getdbt.com/blog/ai-ready-data-in-practice-what-dbt-semantic-layer-and-dbt-s-mcp-server-and-agent-skills-do-for); [dbt docs: Cortex + MCP](https://docs.getdbt.com/docs/dbt-ai/integrate-mcp-snowflake-cortex)
- **Snowflake**: a Snowflake-managed MCP server (reported GA) serves semantic views through Cortex Analyst. This comes from a secondary source (Atlan). I did not fetch Snowflake's own docs. — [Atlan](https://atlan.com/know/ai-agent/data-for-ai/best-ai-ready-data-platforms/)
- **Databricks**: a managed MCP server (`system.ai.genie_one_mcp`), governed through Unity Gateway, sends natural-language questions to Genie, which answers over metric views. Secondary source. — [Atlan](https://atlan.com/know/ai-agent/data-for-ai/best-ai-ready-data-platforms/)
- **Atlan MCP** (hosted, GA): catalog search, lineage, read and update of glossary and DQ metadata, read-only SQL. It runs with the signed-in user's permissions. — [Atlan MCP for dbt](https://atlan.com/know/mcp/mcp-server-for-dbt/)
- **Neo4j**: `mcp-neo4j-cypher` (neo4j-contrib / Neo4j Labs) offers Text2Cypher with separate read and write tools, a `NEO4J_READ_ONLY` mode, and namespacing for running several servers side by side. Many look-alike community servers exist. — [PyPI mcp-neo4j-cypher](https://pypi.org/project/mcp-neo4j-cypher/)
- **Open Semantic Interchange (OSI)**: dbt, Snowflake, Databricks and others back a vendor-neutral semantic-model spec. v0.1 is live and open source (secondary report). — [Atlan](https://atlan.com/know/ai-agent/data-for-ai/best-ai-ready-data-platforms/)

**A2A**
- Google donated A2A to the Linux Foundation in June 2025. At one year (Apr 2026) it had more than 150 supporting organisations and was in production use on the major clouds. The Linux Foundation calls it complementary to MCP: A2A connects agents to each other, MCP connects an agent to its tools and data. — [Linux Foundation press](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year?hs_amp=true); [InfoQ](https://www.infoq.com/news/2025/07/agent2agent-linux-foundation)
- Agents are discovered through an Agent Card: JSON at a well-known URL describing identity, capabilities and endpoints. v1.0 added signed Agent Cards. A signed card proves identity, not what the agent is allowed to access. A claimed move to the Agentic AI Foundation (Aug 2026) is UNVERIFIED. — [pebblous blog](https://blog.pebblous.ai/blog/a2a-mcp-agentic-ai-foundation-authorization/en/); [dev.to](https://dev.to/agentsindex/googles-a2a-protocol-how-ai-agents-communicate-across-frameworks-52jj)

### Inferences
- **Best-practice pattern** (the pattern all the vendors above share): expose a *small set of governed tools* rather than raw SQL. For example `list_metrics`, `query_metric(metric, dims, filters, period)`, `describe_entity`, `traverse(entity, relation)`, `get_context_pack(question)`, `check_answer(sql|result)`. Make them read-only by default and run them under the caller's identity, as Atlan and Neo4j do. Each answer should also return its provenance: tables, metric definition version, and checks passed.
- **A context pack** should be a versioned, cacheable artefact (ontology slice, metric definitions, join paths, verified example queries, policies). Serve it as MCP resources with `ttlMs`/`cacheScope`, plus a JSON file download for non-MCP clients. Stable tool ordering and stable pack content also improve LLM prompt-cache hits, which the 2026-07-28 spec now recommends.
- Build on the 2026-07-28 stateless model now. Use OAuth with CIMD for remote servers and stdio for local or CLI use. This fits the Python-only, no-Docker Strata delivery.
- Exporting the semantic model in OSI format would let Strata metrics be consumed by dbt, Snowflake or Databricks agents. This is worth tracking, but v0.1 is immature.
- A2A only matters if Strata's own agents need to be called by other agents. MCP should come first.

### Gaps
- I did not read Snowflake's and Databricks' own MCP docs. Their GA status and tool lists come from Atlan, a competitor.
- No standard "context pack" format exists. The term is used loosely by vendors. I did not find a spec.
- The A2A v1.0 release date and its current governance home were not confirmed from a2a-protocol.org.
- I did not check whether Neo4j has replaced `mcp-neo4j-cypher` with a newer official server (e.g. one hosted with Aura).
