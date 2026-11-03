# Agent types and architectures over enterprise data layers (2025-2026)

NOTE: These notes were meant for `C:/Users/tusha/AppData/Local/Temp/claude/2e81386eb977b160/f3643104-2f23-4ceb-a2ba-205b24e80fe3/scratchpad/research_notes/Strata four layers and agents/05_agents.md`. Plan mode was on, so they are saved here instead. Copy them to that path when plan mode ends.

Research date: 2026-11-03. Vendor docs are vendor-authored, so read them as describing what the product claims to do, not as independent evidence of quality.

## Taxonomy: what agent types do vendors and practitioners build, and which layers do they map to?

### Takeaway
In practice, vendors build three kinds of thing over enterprise data. (a) Structured-query agents: text-to-SQL, DAX or KQL, increasingly grounded in a semantic model. (b) Retrieval or search agents over unstructured content or ontology objects. (c) An orchestrator or supervisor that routes between those tools and adds code execution, charting and actions. Shipped products rarely offer a standalone "catalog guide" or "graph investigator" agent. Those jobs usually exist as tools or retrieval context inside one orchestrated agent.

### Cited Findings
- An academic survey (arXiv 2510.23587, Oct 2025, revised Feb 2026) says "data agent" is used loosely, covering everything from simple query responders to autonomous systems. It proposes autonomy levels L0 to L5, modelled on SAE J3016, across data management, preparation and analysis. It names the L2-to-L3 step (from following procedures to orchestrating work autonomously) as the current frontier. — [arXiv 2510.23587](https://arxiv.org/abs/2510.23587); paper list at [HKUSTDial/awesome-data-agents](https://github.com/HKUSTDial/awesome-data-agents)
- Snowflake Cortex Agents: one agent with typed tools. Cortex Analyst does text-to-SQL over semantic views. Cortex Search does unstructured retrieval. "Analytical search" (Public Preview) answers counts and trends over document collections. Other tools: code execution, Data to Chart, custom stored-procedure and UDF tools, agent skills, MCP connectors, "agent toolsets" (tools inherited from other agents) and web search. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents) (vendor)
- Microsoft Fabric data agent: one agent picks the source, then calls NL2SQL (lakehouse or warehouse), NL2DAX (Power BI semantic models), NL2KQL (KQL or Eventhouse) or Microsoft Graph queries. Ontologies are now also a supported source. It does not support unstructured files. — [Microsoft Learn, updated 2026-10-21](https://learn.microsoft.com/fabric/data-science/concept-data-agent) (vendor)
- Palantir AIP Agent Studio tool types: Action (can require user confirmation), Object query (filter, aggregate, inspect and traverse links over chosen object types and properties), Command, Request clarification, and a legacy Ontology semantic search. That legacy tool has been replaced by "Ontology context", a retrieval context that runs on every user message and can emit citations. "Function-backed context" lets you write custom retrieval logic. — [Palantir tools](https://palantir.com/docs/foundry/agent-studio/tools), [Palantir retrieval context](https://palantir.com/docs/foundry/agent-studio/retrieval-context) (vendor)
- Databricks Agent Bricks: the subagent types are Genie Agents (the text-to-SQL "Genie" lineage), Knowledge Assistant (RAG over documents), published dashboards, UC functions, tables and volumes, AI Search indexes, MCP servers, custom agents, web search and sandboxed code execution. All of them sit under a supervisor. — [Databricks docs, updated 2026-10-14](https://docs.databricks.com/generative-ai/agent-bricks/multi-agent-supervisor) (vendor)
- Looker Conversational Analytics: agents grounded in the LookML semantic model, fetching the schema of connected Explores at the start of each request. A Conversational Analytics API lets you build custom agents that use NL2SQL, RAG and VizGen. — [Looker overview](https://docs.cloud.google.com/looker/docs/2606/conversational-analytics-overview), [GA blog](https://cloud.google.com/blog/products/business-intelligence/looker-conversational-analytics-now-ga) (vendor)
- dbt-mcp is a de facto "semantic layer plus catalog" tool surface. Semantic Layer tools: `list_metrics`, `get_dimensions`, `get_dimension_values`, `get_entities`, `get_metrics_compiled_sql`, `query_metrics`, `list_saved_queries`. Discovery tools: `get_all_models`, `get_lineage`, `get_node_details`, `get_model_health`, `search`. There are also SQL tools (`execute_sql`, `text_to_sql`) and write-capable CLI and Admin tools (`build`, `run`, `trigger_job_run`). Apache-2.0. — [dbt-labs/dbt-mcp](https://github.com/dbt-labs/dbt-mcp)

### Inferences
- Mapping to Strata's layers:
  - Ontology maps to a catalog or discovery capability. The closest shipped equivalents are dbt-mcp Discovery tools and Palantir ontology context, and both are tools rather than standalone agents.
  - The knowledge graph maps to Palantir's Object query with link traversal.
  - The semantic layer maps to Cortex Analyst over semantic views, Genie, LookML-grounded Looker agents and dbt `query_metrics`.
  - Context packs map to Cortex Search, Knowledge Assistant and Palantir retrieval context with citations.
  - Root-cause or insight work is done by the orchestrator using several tools plus code execution, not by a separate retrieval layer.
- Strata's list of four is defensible as four user-facing modes or "skills". The vendor evidence suggests building them as typed tool bundles under one orchestrator, with the Insight/Root-cause Analyst as that orchestrator, rather than as four separate agent runtimes. The Data Guide and Entity Investigator are the cheapest to ship. They are low-risk (they read metadata or single entities) and match patterns vendors already ship as tools.
- Missing from the candidate list, and present in vendor stacks:
  - A data-quality or "can I trust it" capability. dbt `get_model_health`, freshness and test results, and lineage all feed this.
  - Action or write-back agents, as in Palantir Actions with confirmation. Defer these; they carry high risk.

### Gaps
- I found no vendor that markets a standalone "data guide" or "graph investigator" as a separate agent product. Absence in my searches is not proof that none exist.
- I did not research ThoughtSpot Spotter, Glean agents, Amazon Q or Bedrock agents in this pass, so I have no sourced details on them.

## Vendor architectures: tools, routing, planning, guardrails, MCP exposure

### Takeaway
All major vendors converged in 2025-2026 on the same design: a plan, use-tools, reflect loop. Routing is driven by developer-written tool and source descriptions and instructions. The agent runs under the caller's identity, with RBAC, row-level and column-level security enforced by the platform. Vendors add labelled examples, verified queries and feedback loops, and consumption budgets. Databricks has already moved its supervisor product to "legacy" status, so this market is still churning.

### Cited Findings
- **Snowflake Cortex Agents**
  - Orchestration loop: plan, use tools, reflect and respond, repeated within one request. Developers shape it with natural-language "planning" and "response" instructions. A model setting of "auto" picks the best available model.
  - Access: callers need the SNOWFLAKE.CORTEX_USER or CORTEX_AGENT_USER role, privileges on the agent, and privileges on every object its tools use. If the caller lacks access to some tools, the run continues with the rest. "Secure agents" hide the agent's spec from non-owner roles.
  - Cost controls: an orchestration budget per run, and resource budgets against thresholds.
  - Observability: threads, logs and traces, user feedback, and evaluations.
  - MCP connectors reach remote servers over the public internet.
  - Snowflake itself warns that answers and citations are not guaranteed to be accurate.
  - [Snowflake docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents) (vendor)
  - The fetched page did not mention Snowflake Intelligence or verified queries. It names "Snowflake CoWork" and "Cortex Code" as user surfaces. This may reflect a 2026 rebrand; I did not verify it.
- **Databricks Agent Bricks**
  - The Supervisor Agent is now marked "legacy … not recommended for new systems". New low-code builds should use Genie Agents; code-based orchestration should use the Agent Bricks CLI (`agentbricks tools add genie-agent`).
  - The supervisor routes using the descriptions written for each subagent plus an Instructions field. It allows at most 50 agents and tools per supervisor.
  - Permissions are per user. If a user can reach no subagents, the conversation ends. If they can reach some, the supervisor routes away from the rest.
  - Web search asks the user to approve each query. Code execution runs in a sandbox with no internet and read-only table access.
  - Evaluation: labelled questions in an Examples tab with guidelines, review by subject-matter experts, "retrain and optimize" from labelled data, an AI Judge and synthetic task generation.
  - [Databricks docs](https://docs.databricks.com/generative-ai/agent-bricks/multi-agent-supervisor) (vendor)
  - Community threads report setup friction: Genie had to be declared explicitly as a tool, and UC functions needed the Managed MCP preview. — [Databricks community](https://community.databricks.com/t5/generative-ai/multi-agent-supervisor-not-able-to-coordinate-with-genie-when/td-p/140504)
- **Microsoft Fabric data agent**
  - Generally available. Built on the Azure OpenAI Assistants API.
  - Pipeline: parse and validate the question against policy, identify the source using the user's credentials and any instructions, rephrase the question, call the NL2SQL, NL2DAX or NL2KQL tool, validate the query, execute it, and format the answer.
  - Read-only in every case: no create, update or delete queries, and no notebooks or jobs triggered.
  - At most 5 data sources per agent, and up to 100 example queries per source. Examples are not supported for semantic models.
  - Answers are capped at 25 rows by 25 columns.
  - The LLM cannot be changed. Only English is supported. Sources must be in the same region as the agent.
  - Precedence model: organizational intent > role-based intent > developer intent > user intent. Instructions that try to bypass read-only or scope are refused.
  - Purview DLP, audit and eDiscovery apply. Row-level and column-level security apply.
  - Read permission on a semantic model is enough; Build permission is not needed.
  - Agents can be published to Copilot Studio, Azure AI Foundry, Teams and M365 Copilot. Git integration and deployment pipelines provide ALM, and there is a built-in diagnostics view.
  - [Microsoft Learn](https://learn.microsoft.com/fabric/data-science/concept-data-agent) (vendor)
  - A community reply claims Build permission *is* needed. That contradicts the docs. — [Fabric community](https://community.fabric.microsoft.com/t5/Data-Engineering/interact-with-a-Fabric-data-agent-with-minimum-permission/m-p/4847398)
- **Palantir AIP Agent Studio**
  - Object query limits the agent to the object types and properties you choose, which also reduces token use. Actions can be set to auto-run or to require user confirmation.
  - Retrieval context runs on every message and can feed citations and object sets into app variables.
  - Tool mode works only with a subset of models.
  - A Palantir MCP exists.
  - [tools](https://palantir.com/docs/foundry/agent-studio/tools), [retrieval context](https://palantir.com/docs/foundry/agent-studio/retrieval-context), [Palantir MCP](https://palantir.com/docs/foundry/palantir-mcp) (vendor)
  - The Ontology context limits come from a Chinese machine translation that I did not confirm in English: one object type per set, a vector property required, and 1 to 25 objects (default 5). — [zh retrieval context](https://www.palantir.com/docs/zh/foundry/agent-studio/retrieval-context)
- **Google Looker**
  - Grounded in LookML. Google's internal tests claim the semantic layer cuts generative-AI query errors "by as much as two thirds". I found no independent verification. — [Google blog](https://cloud.google.com/blog/products/business-intelligence/looker-conversational-analytics-now-ga) (vendor)
  - Google's own deck says not every LookML parameter is used yet. — [Google PDF](https://services.google.com/fh/files/misc/conversational_analytics_in_looker.pdf)
  - Google's best-practice guidance includes CI/CD for the semantic model. — [Looker best practices](https://docs.cloud.google.com/looker/docs/conversational-analytics-looker-best-practices)

### Inferences
- Strata already exposes MCP with per-agent keys and scope. To match the vendors, Strata must also carry the *end user's* identity through to execution, which every vendor does: Fabric uses the user's credentials, Snowflake uses the caller's role, Databricks applies per-user subagent access. Per-agent keys alone do not provide this.
- Fabric's caps (5 sources, 25x25 rows, read-only, a precedence model) are a useful, concrete template for Strata guardrail defaults.
- Fabric and Databricks both make routing depend on the descriptions developers write for each source and tool. Strata can generate these descriptions automatically from the ontology, which is a possible differentiator.

### Gaps
- ThoughtSpot Spotter, Glean, Amazon Q and Bedrock agents, and Copilot Studio internals were not researched.
- I could not confirm whether Snowflake Intelligence still exists under that name in late 2026.
- No vendor publishes independent accuracy numbers.

## Open-source frameworks and data-agent repos

### Takeaway
Open-source text-to-SQL agents have moved toward agent, tool-registry and MCP designs that are aware of user permissions. Vanna, the best-known of them, was archived in March 2026. dbt-mcp and WrenAI show the "semantic layer over MCP" pattern that Strata is pursuing.

### Cited Findings
- **Vanna**
  - The repo was "archived by the owner on Mar 29, 2026" and is read-only. MIT licence, about 23.8k stars.
  - v2 moved from `VannaBase` to an `Agent` with a `ToolRegistry` (for example `RunSqlTool`), tools that declare `access_groups`, and a `UserResolver` that maps requests to users and groups. The README describes row-level security, per-user audit logs and SQL shown only to admins by default.
  - [github.com/vanna-ai/vanna](https://github.com/vanna-ai/vanna) (archive confirmed directly, so the earlier question is resolved)
- **WrenAI**
  - Its MDL semantic model encodes business definitions once and grounds every generated query in them. `wren serve` exposes an MCP server with query, context and knowledge tools.
  - The licence is reported inconsistently. The wiki says the core, SDK and skills are Apache-2.0 but also lists AGPL-3.0 files. PyPI says Apache-2.0. A third party says AGPL-3.0. Check the LICENSE files before relying on any of these.
  - [WrenAI wiki](https://github.com/Canner/WrenAI/wiki), [PyPI](https://pypi.org/project/wrenai/), [jimmysong](https://jimmysong.io/ai/wrenai)
- **dbt-mcp**: Apache-2.0. Its tool groups are listed above. It warns that the CLI tools "could modify your data models, sources, and warehouse objects". — [dbt-mcp](https://github.com/dbt-labs/dbt-mcp)
- **LangGraph**
  - The `langgraph-supervisor` package includes fixes from LangChain's benchmarking: handoff messages are removed from subagent context, and a `forward_message` tool lets the supervisor pass a subagent's reply through without paraphrasing it.
  - [LangChain blog, 2025-06-10](https://www.langchain.com/blog/benchmarking-multi-agent-architectures) (vendor)

### Inferences
- Vanna v2's design (tools with `access_groups`, a `UserResolver`, SQL visible only to admins) maps directly onto Strata's per-agent scope plus per-user permissions. Being archived, it is a reference design, not a dependency.
- dbt-mcp's split between metadata or discovery tools and metric-query tools, with write tools in separate groups, is a good model for Strata's MCP tool grouping:
  - ontology and discovery tools: read metadata
  - semantic tools: governed metrics only
  - raw SQL: off by default
  - writes: never

### Gaps
- Not researched in this pass, so I have no sourced current facts on licence or activity: DB-GPT, LlamaIndex agents, CrewAI, Pydantic AI, Microsoft Agent Framework or AutoGen, Google ADK, Neo4j text2cypher or the Neo4j MCP, and the OpenAI Agents SDK. The parent should not rely on them without further research.
- The WrenAI licence is unresolved.

## Trustworthiness: guardrails, refusal, verification, evaluation, observability, permissions

### Takeaway
Across vendors, the trust stack is consistent:
- read-only execution
- the caller's identity, with row-level and column-level security
- a fixed source and tool scope
- an instruction precedence that user prompts cannot override
- labelled examples or verified queries
- traces and feedback
- evaluation against golden question sets

Public benchmarks show raw enterprise text-to-SQL is still only about 50% accurate at best. That is the strongest argument for routing through governed metrics instead of free SQL.

### Cited Findings
- **Read-only, scope and precedence**: Fabric enforces read-only connections, scope guardrails on tool calls, and the organizational > role > developer > user precedence. — [Microsoft Learn](https://learn.microsoft.com/fabric/data-science/concept-data-agent)
- **Human confirmation**: Palantir Actions can require user confirmation. Databricks web search requires per-query user approval. — [Palantir](https://palantir.com/docs/foundry/agent-studio/tools), [Databricks](https://docs.databricks.com/generative-ai/agent-bricks/multi-agent-supervisor)
- **Evaluation and feedback**:
  - Databricks: labelled examples, SME review, AI Judge, synthetic tasks.
  - Snowflake: threads, traces, feedback, evaluations.
  - Fabric: diagnostics, Git, deployment pipelines, human-in-the-loop escalation.
  - Sources: the three vendor docs above.
- **Benchmark state**:
  - Spider 2.0-Lite has 547 examples (likewise Spider 2.0-Snow); Spider 2.0-DBT has 68. At launch, DAIL-SQL with GPT-4o scored 5.68%. — [xlang-ai/Spider2](https://github.com/xlang-ai/Spider2), [arXiv 2411.07763](https://www.alphaxiv.org/abs/2411.07763v2)
  - A third-party 2026 leaderboard puts the top Spider 2.0-Lite scores at roughly 50 to 53% (Interfaze 52.9%, Claude Sonnet 5 50.6%). This is unofficial and the ordering has been changing. — [Interfaze leaderboard](https://interfaze.ai/leaderboards/spider-2-lite)
- **Benchmark reliability**: a VLDB 2026 study reports annotation error rates of 52.8% in BIRD Mini-Dev and 62.8% in Spider 2.0-Snow, and finds that fixing them reorders agent rankings. — [Illinois Experts](https://experts.illinois.edu/en/publications/pervasive-annotation-errors-break-text-to-sql-benchmarks-and-lead/)
- **Vendor accuracy claims**:
  - Google claims its semantic layer cuts errors by up to two thirds. This is an internal test and unverified. — [Google](https://cloud.google.com/blog/products/business-intelligence/looker-conversational-analytics-now-ga)
  - Snowflake disclaims the accuracy of answers and citations. — [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)

### Inferences
- Benchmark annotations are this noisy, so Strata should build its own golden question set per tenant from approved metrics and verified queries, rather than quoting BIRD or Spider scores.
- "Refuse when not answerable" is under-documented by vendors. Fabric documents refusal only for policy conflicts. Strata can make refusal explicit, for example "no approved metric covers this", and that could be a differentiator.

### Gaps
- I found no vendor documentation that quantifies refusal or abstention behaviour.
- I did not pull primary documentation on Snowflake verified queries in this pass.

## Routing and multi-agent: one agent with many tools, or typed specialists?

### Takeaway
The evidence favours one agent with a small, well-described toolset while the domain is narrow. Split into specialists, or retrieve tools, once tools or domains multiply. A supervisor needs specific fixes to avoid "telephone" losses. Exact thresholds for when to split are folklore.

### Cited Findings
- **LangChain benchmark** (June 2025, modified Tau-bench, gpt-4o; vendor-run):
  - A single agent was slightly better with one distractor domain but fell sharply with two or more.
  - Swarm slightly beat supervisor.
  - The supervisor suffered a "translation" or telephone effect and used more tokens. Single-agent token use grew with the number of domains, while multi-agent use stayed flat.
  - Fixes to the supervisor improved it by nearly 50%.
  - Supervisor "makes the fewest assumptions about sub-agents", which suits third-party agents.
  - [LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- **RAG-MCP** (arXiv 2505.03275): retrieving a shortlist of tools instead of listing all of them reportedly raised tool-selection accuracy from 13.62% to 43.13% and more than halved prompt tokens. This is a secondary report; I did not verify the paper itself. — [StackOne summary](https://www.stackone.com/blog/agent-tool-count-ceiling/)
- **Thresholds**: blog claims such as "degrades after 10 to 15 tools" or "split above 20 to 30 tools" have no controlled study behind them. — [MachineLearningMastery](https://machinelearningmastery.com/the-complete-guide-to-tool-selection-in-ai-agents/), [tianpan.co](https://tianpan.co/blog/2026-04-19-over-tooled-agent-problem) (practitioner blogs, low evidential weight)
- **Vendor patterns**: Databricks caps a supervisor at 50 subagents and tools. Fabric caps an agent at 5 sources. — the vendor docs above
- **Anthropic** ("Building effective agents", Dec 2024, older than this research window): recommends starting with the simplest solution, and using workflows such as routing and orchestrator-workers before adding autonomous agents. — [Anthropic](https://www.anthropic.com/engineering/building-effective-agents) (from prior knowledge; not re-fetched this session)

### Inferences
- For Strata, use one orchestrator (today's insight analyst) with about 4 typed tool bundles (ontology, graph, semantic, context), each with 3 to 6 tools. Expose the four "agent types" as presets: a restricted tool subset plus a prompt and output template. This avoids the supervisor telephone effect, keeps scope least-privilege, and maps directly to MCP scopes for external agents.
- External agents such as Claude, Copilot and Cursor will act as Strata's "supervisor". Strata's MCP tools therefore need precise descriptions and small per-key toolsets.

### Gaps
- I found no evidence specific to data-agent routing, such as text-to-SQL accuracy versus number of tools.

## Explaining answers to non-experts ("which layers or data did this use")

### Takeaway
Vendors expose provenance mainly through citations from retrieval (Palantir citations, Snowflake citations) and through traces and diagnostics aimed at builders. Plain-language, layer-level provenance for end users is not a documented standard feature.

### Cited Findings
- Palantir Ontology context can output citations and object sets into app variables. — [Palantir](https://palantir.com/docs/foundry/agent-studio/retrieval-context)
- Snowflake agents return citations, but warns they may be inaccurate, and provides traces. — [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)
- Fabric offers diagnostics showing how a question was processed and which source was chosen, aimed at builders. — [Microsoft Learn](https://learn.microsoft.com/fabric/data-science/concept-data-agent)
- Vanna v2 shows generated SQL only to admin users by default, which hides it from non-experts. — [Vanna](https://github.com/vanna-ai/vanna)

### Inferences
- A per-answer "used: Ontology (Order), Semantic (net_revenue v3, approved), Graph (customer c1, 2 hops), Context (5 cited rows)" receipt would be a clear differentiator. It is not documented by the vendors reviewed.

### Gaps
- I found no user research on how non-experts read agent provenance.

## Failure modes

### Takeaway
The documented failure modes are:
- wrong SQL on complex schemas (about 50% ceiling on Spider 2.0-Lite)
- semantic-model gaps
- truncated context leading to wrong follow-ups
- over-privileged tools combined with prompt injection through data (the "lethal trifecta")
- setup friction and rapid product churn

### Cited Findings
- **Prompt injection via data**:
  - In July 2025, a support ticket containing hidden instructions led Cursor, using the Supabase MCP with a service_role key that bypasses row-level security, to copy the `integration_tokens` table into an attacker-visible table.
  - Simon Willison calls this the "lethal trifecta": private data, untrusted input, and an exfiltration channel. The mitigation was a read-only, project-scoped default. Willison argues read-only still carries risk.
  - [Simon Willison](https://simonwillison.net/2025/Jul/6/supabase-mcp-lethal-trifecta/) (secondary write-up of the General Analysis research)
- **Truncation**: Fabric's 25-row cap means a follow-up question can be answered from already-truncated context. Microsoft advises starting a new chat. — [Microsoft Learn](https://learn.microsoft.com/fabric/data-science/concept-data-agent)
- **Semantic-model quality**: answer quality depends on how complete and correct LookML is. — [Google PDF](https://services.google.com/fh/files/misc/conversational_analytics_in_looker.pdf), [fitgap (third party)](https://us.fitgap.com/products/025069/gemini-in-looker)
- **Over-broad tools**: dbt-mcp CLI tools can modify warehouse objects. — [dbt-mcp](https://github.com/dbt-labs/dbt-mcp)
- **Cost**: Snowflake bills orchestration tokens plus a charge per tool and provides per-run budgets. Single-agent token use grows with the number of domains. — [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents), [LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- **Supervisor paraphrasing errors** (the telephone effect). — [LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)

### Inferences
- The Context layer returns sampled source rows, so it is exactly where untrusted text enters the prompt. Strata should treat sampled rows as data, not instructions:
  - delimit them
  - redact PII
  - give no write or egress tools in the same session

### Gaps
- I found no sourced quantification of how often wrong joins or hallucinated metrics occur in production.
