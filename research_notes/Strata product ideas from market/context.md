# Context layer and AI data analyst products, 2025-2026: features, UX patterns, teaching loops, complaints, and ideas for Strata

Scope note: research run 2026-11-20 with about 16 search and fetch calls. Most sources are vendor docs and blogs, so they describe what the vendor says the product does. I found no independent G2 or Reddit review data of good quality. Products I could not cover (no usable results this run): Dot (getdot.ai), Zenlytic Zoe, Select Star, Secoda AI, Julius, Index, Fabi, Numbers Station, Contextual AI, Tobiko. Those are listed under Gaps.

## How leading products assemble and serve business context, and which UX patterns stand out

### Takeaway
The market has settled on one pattern. A curated, scoped "knowledge store" (definitions, synonyms, joins, SQL snippets, verified question-to-SQL pairs, rules text) is attached to an agent or space. Answers that used certified assets get a trust badge, and the plan, SQL and steps are shown. The 2026 differentiators are lifecycle tooling for context: build, test against golden questions, deploy, then watch for drift (Atlan's Context Engineering Studio, Hex Context Studio). Strata already has the core pattern. Its gaps are mainly the lifecycle and evaluation pieces and some answer-screen affordances.

### Cited Findings
**Atlan: Context Engineering Studio (CES) and context repos**
- The CES workflow has four steps: Bootstrap (build context repos), Simulate (run evaluations), Deploy (push to agents), Observe (traces and drift). — [Atlan CES](https://atlan.com/context-engineering-studio/); [Atlan docs: what is CES](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/what-is-context-engineering-studio)
- A context repository holds linked assets that *reference* governed Atlan context (they are not copied), plus a semantic model that says how those assets answer questions. — [Atlan docs: what's in a context repository](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/whats-in-a-context-repository)
- Repos are model-agnostic and served over MCP. The hosted Remote MCP server is on for all tenants. Deploy targets include Snowflake Cortex Analyst and Databricks Genie as well as MCP agents. One docs page labels context repos "Private Preview". — [Atlan docs: context repositories](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/context-repositories); [Atlan docs: build](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/how-tos/build)
- Atlan says CES "converts your dashboards and historical SQL into automated test suites before an agent goes to production", and markets it as "the SDLC for context" and "the GitHub for enterprise context". — [Atlan Activate 2026](https://atlan.com/know/context-layer-stopped-being-theoretical-activate-2026/); [Atlan Snowflake Summit 2026](https://atlan.com/snowflake-summit-2026-announcements/); [Atlan demo](https://atlan.com/demos/the-github-for-enterprise-context-how-atlans-context-repos-bootstrap-test-and-ship-agent-ready-context)
- Atlan also documents a "memory layer for AI agents". — [Atlan docs: memory layer](https://docs.atlan.com/agents/concepts/memory-layer) (concept page only; I did not read the mechanism in detail)

**Databricks Genie spaces and Genie agents**
- The knowledge store is a curated set of semantic definitions: agent-level table and column descriptions, synonyms, join relationships, SQL expressions and prompt-matching settings. It is scoped to the agent and does not change Unity Catalog metadata. — [Databricks: agent mode](https://docs.databricks.com/aws/en/genie-agents/agent-mode); [MS Learn: Genie agents concepts](https://learn.microsoft.com/azure/databricks/genie-agents/concepts)
- Agent mode (formerly "Research Agent", Beta) builds a research plan and runs several SQL queries, learning from each result. It returns a report with citations, charts and tables. It may ask clarifying questions, and an **"Answer now"** button stops the research and answers from the context gathered so far. "Flash (Beta)" is a faster option for quick questions. — [Databricks: agent mode](https://docs.databricks.com/aws/en/genie-agents/agent-mode); [Databricks blog: introducing Genie agent mode](https://databricks.com/blog/introducing-genie-agent-mode); [Databricks blog: deep analysis, file reasoning](https://databricks.com/blog/expanding-genie-agents-deep-analysis-file-reasoning-and-more)
- Sources conflict on API access. One doc says agent-mode prompts are UI-only, while a newer blog and doc describe Agent mode APIs (Beta). — same sources as above
- The answer screen has an **Analysis** section that shows how the question was interpreted, the relevant data, any SQL example it used, and plain-language thinking steps. It also has a summary, **Show code**, and follow-up suggestions built from instructions and conversation context. — [Databricks: talk to Genie](https://docs.databricks.com/aws/en/genie-agents/talk-to-genie)
- **Trusted asset indicator**: an answer may come from a trusted query or function an editor created, and "Show more" reveals its comments and parameter values. The docs warn that Genie "can occasionally match a question to the wrong asset". — [Databricks: talk to Genie](https://docs.databricks.com/aws/en/genie-agents/talk-to-genie)
- A user can define terms inside a conversation so Genie can answer, for example a definition of churn. — [MS Learn: talk to Genie](https://learn.microsoft.com/en-us/Azure/databricks/genie-agents/talk-to-genie)

**Snowflake Intelligence and Cortex Agents**
- Cortex Agents is the orchestration engine. It plans multi-step work and calls tools: Cortex Analyst for structured data via semantic views, and Cortex Search for unstructured data. — [Snowflake eng blog: Cortex Agents](https://snowflake.com/en/engineering-blog/cortex-agents-unified-data-intelligence)
- Semantic views carry business names, synonyms, sample values and **verified queries (VQRs)**. A VQR pairs a tested SQL with the question it answers, and it is matched to incoming prompts and used as a template. — [Snowflake: native semantic views](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/); [The Data School guide](https://thedataschool.co.uk/ben-hayward/creating-an-agent-in-snowflake/) (third-party)
- Answers backed by verified queries and semantic views show a **"green shield"** icon, meaning certified sources were used. — [SiliconANGLE, Nov 4 2025](https://siliconangle.com/?p=719280)
- Flag: the Snowflake docs URL for Snowflake Intelligence now comes back titled "Overview of Snowflake CoWork", which suggests a rename or rebrand. I did not verify this. — [Snowflake docs](https://docs.snowflake.com/user-guide/snowflake-cortex/snowflake-intelligence)

**Microsoft Fabric data agents**
- Context has three parts: agent-level instructions (objective, term definitions such as "'GMV' refers to Gross Merchandise Value", response guidelines), per-data-source instructions ("When asked about shoe sales, always use the SalesProduct table"), and **example queries** (question plus query pairs used as few-shot examples). — [MS Learn: data agent configurations](https://learn.microsoft.com/fabric/data-science/data-agent-configurations); [MS Learn: example queries](https://learn.microsoft.com/en-us/fabric/data-science/data-agent-example-queries)
- Example queries work for lakehouse, warehouse and KQL sources but not for semantic models or *ontology* sources. The SDK can evaluate examples, but only SQL ones. An agent is limited to five data sources. — [MS Learn: example queries](https://learn.microsoft.com/fabric/data-science/data-agent-example-queries); [MS Learn: concept](https://learn.microsoft.com/fabric/data-science/concept-data-agent)
- Agents can be published to Copilot Studio and connected through MCP. A lab teaches generating instructions with meta-prompting. — [MS Copilot Studio lab](https://microsoft.github.io/mcs-labs/labs/data-fabric-agent)

**Google Looker Conversational Analytics and data agents**
- "Authored context" is guidance written by agent owners: system instructions plus **golden queries** (question to exact Looker Explore query, stored under `looker_golden_queries`). The docs conflict on the key name (`golden_queries` vs `looker_golden_queries`). Golden queries with pivots or custom fields are not supported in dashboard agents. — [Google: data agent authored context (Looker)](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-authored-context-looker); [Looker CA overview](https://docs.cloud.google.com/looker/docs/2610/conversational-analytics-overview)
- BigQuery and other warehouses are reached through the LookML semantic model. I could not confirm a separate BigQuery-only golden-query mechanism. — [Looker CA overview](https://docs.cloud.google.com/looker/docs/2610/conversational-analytics-overview)
- Google's community framing: "layering authored context over Looker models" for trustworthy AI. — [Google dev forum](https://discuss.google.dev/t/trustworthy-ai-layering-authored-context-over-looker-models/365439)

**ThoughtSpot Spotter**
- Spotter Memory (GA, needs Spotter 3, off by default, admin enables). It learns automatically from trusted Liveboards and from corrections made in conversation ("No special mode, no detour to a settings page"). It can pull definitions from Confluence, SharePoint or wikis. — [ThoughtSpot blog: Spotter memory](https://www.thoughtspot.com/blog/spotter-memory); [ThoughtSpot docs: Spotter memory](https://docs.thoughtspot.com/cloud/latest/spotter-memory)
- Two stored kinds: **Rules** (definitions, inclusions and exclusions) and **Recipes** (the query path, filters and logic behind a correct answer, so it can be reproduced). — [ThoughtSpot blog](https://www.thoughtspot.com/blog/spotter-memory)
- Scopes: data-model memory applies only on that model. Personal memory applies to one user and does not overwrite org definitions. Shared memory needs "Manage Memory" permission. Leads can review and correct stored knowledge. RLS and CLS are enforced at query generation. — [ThoughtSpot blog](https://www.thoughtspot.com/blog/spotter-memory); [ThoughtSpot docs](https://docs.thoughtspot.com/cloud/26.7.0.cl/spotter-memory)
- Conflict: the docs say memory does not auto-sync with data model changes, but a blog says renaming a column updates memory automatically. Memory cannot move between orgs or instances. The older manual "coaching" still works. — [ThoughtSpot docs](https://docs.thoughtspot.com/cloud/latest/spotter-memory); [ThoughtSpot blog: memory live](https://www.thoughtspot.com/blog/spotter-memory-live); [Coaching docs](https://docs.thoughtspot.com/cloud/26.5.0.cl/spotter-coaching-options)

**Hex (Threads, Notebook Agent, Context Studio)**
- Threads prefers semantic models and endorsed sources. In "Governed mode", admins choose which sources the agent may use: endorsed only, semantic models only, or a custom set. Excluded objects are removed from table-selection context. — [Hex docs: threads](https://learn.hex.tech/docs/explore-data/threads); [Hex AI overview](https://learn.hex.tech/docs/getting-started/ai-overview)
- A workspace **rules file** (markdown, admin-edited, like Cursor rules) is read by every Hex agent. Hex calls semantic models the "strict layer" and the rules file the "loose layer". — [Hex blog: context engineering for self-serve](https://hex.tech/blog/intro-to-context-engineering-for-self-serve-analytics/); [Notebook agent docs](https://learn.hex.tech/docs/explore-data/notebook-view/notebook-agent)
- **Context Studio** lets admins and managers monitor agent behaviour. A 2026 changelog adds guides synced from GitHub and "View References", which shows which projects use a semantic model. — [Hex Context Studio](https://hex.tech/product/context-studio/); [Hex changelog 2026-04-14](https://learn.hex.tech/changelog/2026-04-14)

**Glean**
- The Enterprise Graph (Sept 2025) combines a company knowledge graph with a per-employee **personal graph** of tasks, projects, collaborators and work style. Agents use it for personalization. — [Glean press](https://www.glean.com/press/glean-introduces-third-generation-ai-assistant-new-enterprise-graph-to-enable-the-superintelligent-enterprise)
- Glean works as an MCP server (Search, Assistant, Agents) and as an MCP host with a curated server directory and more than 100 native actions. Futurum (Apr 2026) calls it an "integration hub" play. — [Techstrong](https://techstrong.ai/features/glean-adds-additional-graphs-and-mcp-servers-to-ai-workflow-platform/); [Futurum](https://futurumgroup.com/insights/glean-doubles-arr-to-200m-can-its-knowledge-graph-beat-copilot/)

**Promethium and TextQL**
- Promethium Mantra (private preview, July 2025): a conversational "Data Answer Agent" over federated sources, using a "Context Hub" of business terms, relationships and *prior interactions*. Outputs include SQL, metadata, **lineage** and charts. — [SiliconANGLE Jul 2025](https://siliconangle.com/2025/07/15/data-fabric-startup-promethium-enables-self-service-data-access-ai-agents/); [Promethium Mantra](https://promethium.ai/mantra/)
- TextQL maps the database to business "nouns" (order, dealer, SKU) and points users to an existing dashboard when the question was already answered. This comes from an older TechCrunch piece, so it may be dated. — [TechCrunch](https://techcrunch.com/?p=2655966)

### Inferences
- The standard UX set is now: interpretation and plan panel, show SQL, trusted or certified badge, follow-up suggestions, Yes/Fix-it feedback, request review, and for deep modes an "answer now" interrupt. Strata's "what the AI saw" already covers the interpretation panel. The badge, the interrupt, the review request and data-driven follow-ups are cheap to add.
- Verified question-to-query pairs appear in every major product (Snowflake VQR, Fabric example queries, Looker golden queries, Wren SQL pairs, Genie trusted queries). Strata's certified metrics play a similar role, but there is no first-class "verified question" object. That is the clearest gap.
- Atlan and Hex both compete on context *lifecycle*: test suites from history, monitoring, drift, references. That ground suits a small team because it is mostly bookkeeping over data Strata already logs.
- Fabric does not support example queries on ontology sources. An ontology-native verified-answer store is a real differentiator for Strata.

### Gaps
- No usable results on Dot, Zenlytic Zoe, Select Star, Secoda AI, Julius, Index, Fabi, Numbers Station, Contextual AI or Tobiko. These need dedicated searches.
- I could not fetch Snowflake's "five pillars" engineering post (HTTP 403), so Snowflake Intelligence's own feedback and evaluation mechanics are unconfirmed.
- I did not verify Genie benchmarks or evaluation features from a source this run. The talk-to-Genie page does not mention them.

## How users teach the system, and how teaching is governed

### Takeaway
There are two camps. In the "author-curated" camp (Genie, Fabric, Looker, Hex), feedback goes to authors and nothing changes until a human acts. Genie says this outright. In the "auto-memory" camp (Spotter Memory, Wren, Vanna, Promethium), corrections become stored rules or recipes on their own, with personal and shared scopes and permissioned review. A governed middle path fits Strata's trust stance: corrections become proposed memories that a steward approves, and they are scoped.

### Cited Findings
- Genie: each answer has **Yes** and **Fix it** (pick a common issue or type one, then "Submit and try again" or "Submit"), plus **Request review** with a comment for editors. Managers see all interactions, feedback and review requests in a **monitoring tab**. Positive feedback on answers that used joins or SQL expressions can lead Genie to *suggest new SQL snippets for managers to approve*. "Genie does not automatically learn or change its behavior in response to feedback." — [Databricks: talk to Genie](https://docs.databricks.com/aws/en/genie-agents/talk-to-genie)
- Spotter: corrections in conversation persist automatically as Rules or Recipes. Personal and shared scopes exist, shared needs "Manage Memory" permission, and leads can review and correct. The blog names no formal approval workflow. — [ThoughtSpot blog](https://www.thoughtspot.com/blog/spotter-memory)
- Wren AI: global instructions plus question-matching instructions, and question-SQL pairs that are **dry-run validated against the latest deployment before saving**. Users can edit generated SQL and feed it back. "Agentic" projects move knowledge to **Git-backed files** and deprecate the old Instructions and SQL-Pairs endpoints (`AGENT_MODE_V1_DEPRECATED`). — [Wren API: knowledge](https://wrenai.readme.io/reference/knowledge-1); [Wren blog, updated Dec 2025](https://getwren.ai/post/beyond-text-to-sql-why-feedback-loops-and-memory-layers-are-the-future-of-genbi)
- Vanna 2.0: memory tools `search_saved_correct_tool_uses` and `save_question_tool_args` (admins save new training data). It stores successful tool-use patterns. The one detailed docs page is labelled "AI-Generated Placeholder Documentation", so treat it as unverified. — [Vanna docs](https://vanna.ai/docs/placeholder/training)
- Hex: teaching happens through the admin-only rules file, endorsements and semantic models. Rules now sync from GitHub. — [Hex blog](https://hex.tech/blog/intro-to-context-engineering-for-self-serve-analytics/); [Hex changelog](https://learn.hex.tech/changelog/2026-04-14)
- Fabric: admins write instructions and example queries, and the SDK evaluates SQL examples. — [MS Learn: example queries](https://learn.microsoft.com/fabric/data-science/data-agent-example-queries)
- Atlan: historical SQL and dashboards become test suites, which is a "learn from query history" pattern applied to evaluation rather than to answering. — [Atlan Activate 2026](https://atlan.com/know/context-layer-stopped-being-theoretical-activate-2026/)
- Research: an arXiv paper (Nov 2025) on continual learning of domain knowledge from human feedback in text-to-SQL. I saw the title only and did not read it. — [arXiv 2511.10674](https://arxiv.org/pdf/2511.10674)

### Inferences
- Strata should adopt Wren's "validate before save" rule: a proposed memory must re-run against current data and pass the number checks before a steward can approve it.
- Spotter's Rules vs Recipes split maps well onto Strata: Rules become user notes or definitions, and Recipes become verified query paths over the ontology and graph.
- The memory-staleness conflict in ThoughtSpot (does memory follow schema changes or not?) is a known weak spot. Strata's ontology drift checks could flag memories that touch changed objects.

### Gaps
- No public data on how often auto-memory goes wrong or poisons shared context, or how vendors detect it.

## How context is packaged for other agents

### Takeaway
MCP is now the default way to hand context to outside agents (Atlan remote MCP, Glean MCP server and host, Fabric via Copilot Studio MCP). Atlan also "deploys" a context repo into competitors' agents (Cortex Analyst, Genie). Versioned, Git-backed context files are emerging (Wren agentic projects, Hex guides from GitHub, Atlan "GitHub for context"). I found nothing on A2A use in data-context products specifically.

### Cited Findings
- Atlan context repos are served through the Atlan MCP server and can deploy to Snowflake Cortex Analyst and Databricks Genie. — [Atlan docs](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/context-repositories)
- Glean's hosted MCP server exposes Search, Assistant and Agents. As an MCP host, Glean agents call external servers from a curated directory. — [Techstrong](https://techstrong.ai/features/glean-adds-additional-graphs-and-mcp-servers-to-ai-workflow-platform/)
- Fabric data agents connect to Copilot Studio through MCP. — [MS lab](https://microsoft.github.io/mcs-labs/labs/data-fabric-agent)
- Wren agentic projects use Git-backed files for knowledge and modelling. — [Wren API](https://wrenai.readme.io/reference/knowledge-1)
- Gartner (May 2026) advises treating the context layer as core D&A infrastructure, and names semantics, operational state and provenance as its three components. Report titles include "Reference Architecture Brief: Enterprise Context Layer" (Oct 2026) and "Context Graphs Ground AI Agents With Enterprise Knowledge" (Sept 2026). Gartner predicts that prioritizing semantics could raise agentic accuracy by up to 80% and cut costs by up to 60% by 2027. — [Gartner press release 2026-05-11](https://www.gartner.com/en/newsroom/press-releases/2026-05-11-gartner-says-lack-of-semantics-causes-inaccurate-artificial-intelligence-agents-and-wasted-spending); [Mexico Business News](https://mexicobusiness.news/cloudanddata/news/context-layer-key-scalable-ai-agents-gartner); [Gartner abstract](https://www.gartner.com/en/documents/8384981)
- Gartner's Aug 2026 Impact Radar lists "AI context platforms" as enabling multi-agent AI, with 1 to 3 years to mainstream. The sample-vendor list (Databricks, Glean, Palantir, Snowflake) comes from Atlan's summary and is unverified. — [Atlan on Gartner radar](https://atlan.com/know/ai-agent/context-layer/gartner-impact-radar-ai-context-platform/)

### Inferences
- Strata's Context Pack over MCP is on trend. To stand out it could carry Gartner's three components on every fact: semantics (the definition), operational state (data-check status and freshness) and provenance (source, who certified it, when). It could also export the pack as a versioned file bundle that can be diffed.
- Deploying context into other vendors' agents (Atlan's model) is probably too large for Strata now. Exporting packs in formats those agents ingest (a Snowflake semantic view YAML with verified queries, Genie instructions) is a medium-effort bridge.

### Gaps
- No evidence of A2A protocol use by any data-context vendor in these sources.

## User and analyst complaints, and unmet needs

### Takeaway
The main complaint is *silent, plausible wrong numbers*: SQL that runs cleanly with a wrong definition, join or grain. Next come inconsistency (different answers to the same question), lack of trust or audit, and the wrong certified asset being matched. Nearly every source pushing these points sells a fix, so the framing is biased even though the failure modes are real. Unmet needs: per-number provenance, answerability before answering, and stable answers to repeated questions.

### Cited Findings
- A vendor test found 7 of 10 misses were plausible wrong numbers with no warning, and 3 came back empty. One example read "month" as elapsed days from each user's first purchase. — [OWOX: text-to-SQL accuracy in production](https://www.owox.com/blog/articles/text-to-sql-accuracy-benchmarks-production/) (vendor)
- OWOX reports secondhand that a late-2025 r/analytics post described a company whose AI analytics tool returned fabricated metrics for months. I could not find the original post. — [OWOX: hallucination and deterministic SQL](https://www.owox.com/blog/articles/ai-analytics-hallucination-deterministic-sql) (vendor)
- "Same question, different answers" is named as a distinct failure. — [OWOX: different answers](https://www.owox.com/blog/articles/ai-different-answers-same-data-question.md) (vendor)
- "Valid SQL, wrong answer": a perfect query against the wrong table or a guessed definition is still wrong. — [DZone](https://dzone.com/articles/valid-sql-wrong-answer); [Omni: why text-to-SQL fails](https://omni.co/blog/why-text-to-sql-fails) (vendor); [Collate: your problem is not the LLM](https://www.getcollate.io/blog/your-text-to-sql-problem-is-not-the-llm) (vendor)
- "Why 90% accuracy in text-to-SQL is 100% useless": partial accuracy kills trust because users cannot tell which answers are wrong. — [Towards Data Science](https://towardsdatascience.com/why-90-accuracy-in-text-to-sql-is-100-useless/)
- "How do I know the AI answer is correct" is a common user question. — [Bruin blog](https://getbruin.com/blog/how-do-i-know-the-ai-answer-is-correct/) (vendor)
- Even with certified assets, Genie "can occasionally match a question to the wrong asset", so users must check. — [Databricks docs](https://docs.databricks.com/aws/en/genie-agents/talk-to-genie)
- Gartner, Mar 2026: AI-ready data is contextual and use-case dependent, and one-time quality checks are not enough. — [Atlan summary of Gartner D&A 2026](https://atlan.com/know/gartner/key-takeaways-from-gartner-da-summit-2026/) (vendor summary)
- Deep or agent modes are slow enough that Genie added "Answer now" and a separate fast mode (Flash), which suggests latency complaints. — [Databricks agent mode](https://docs.databricks.com/aws/en/genie-agents/agent-mode)

### Inferences
- Strata's "reject unsupported numbers" rule addresses the top complaint directly, and it should be the headline in positioning. The next steps are to make it visible per number (a click shows the source fact) and to also catch wrong-definition errors, for example by warning when the question's term maps to more than one metric.
- Consistency: cache verified answers so the same question gets the same number unless the data changed, and say why it changed when it does.

### Gaps
- No primary Reddit, HN or G2 threads retrieved, so user-voice evidence is thin and mostly vendor-filtered. Cost complaints and "context rot" complaints are not evidenced in sources from this run.

## Open-source projects to borrow from

### Takeaway
Wren AI and Vanna 2.0 are the most relevant text-to-SQL references: SQL pairs, instructions, validate-before-save, saved tool uses. For memory, Graphiti (bi-temporal facts with invalidation) fits Strata's graph best. Mem0 is a simple vector memory and Letta is a full runtime. Letta's own result, that a plain filesystem beat Mem0's graph variant on LoCoMo, argues for keeping memory simple.

### Cited Findings
- Wren: instructions, SQL pairs with dry-run validation, Git-backed files in agentic mode, and a transparency view showing chosen tables, interpretation and SQL build. — [Wren API](https://wrenai.readme.io/reference/knowledge-1); [Wren blog](https://getwren.ai/post/beyond-text-to-sql-why-feedback-loops-and-memory-layers-are-the-future-of-genbi)
- Vanna 2.0: streaming tables, charts and summaries; LegacyVannaAdapter; saved correct tool uses. — [Vanna docs](https://vanna.ai/docs/placeholder/training) (placeholder page, so unverified)
- Graphiti (Zep): bi-temporal knowledge graph. Old facts keep timestamps when invalidated, so it can answer point-in-time questions. Mem0 timestamps memories at creation but has no validity window or supersession. Letta (formerly MemGPT) uses tiered core and archival memory with no graph. — [DEV: Letta vs Zep/Graphiti vs Mem0](https://dev.to/agdex_ai/letta-vs-zepgraphiti-vs-mem0-choosing-an-ai-agent-memory-architecture-155a); [Codepointer substack](https://codepointer.substack.com/p/agent-memory-systems-and-knowledge)
- Sources conflict on Mem0 graph memory: one says it is paywalled ($249/mo) and removed from the OSS SDK, another describes it as part of the design. All LongMemEval and LoCoMo scores are vendor self-measurements. — [DEV: Letta vs Zep vs Mem0](https://dev.to/plur9/mem0-vs-letta-vs-zep-which-should-you-use-for-agent-memory-1n8m)

### Inferences
- Strata does not need a memory dependency. Borrowing Graphiti's *idea* (valid_from and valid_to on each user note or correction, plus a superseded_by link) inside DuckDB covers the useful part with no new service. That fits the laptop-limits constraint.

### Gaps
- DB-GPT and LangChain/LlamaIndex SQL agents were not researched this run.

---

### Ranked feature ideas for Strata's Context layer and agents

1. **Verified questions (golden Q to answer pairs over the ontology)**. A steward saves a question with its metric, filters and graph path. It is validated before saving (re-run plus number checks) and matched to new questions first. Who does it: Snowflake VQR, Fabric example queries, Looker golden queries, Wren SQL pairs, Genie trusted queries. Why: the most common accuracy lever in the market, and Fabric lacks it for ontology sources. Effort: **M**.
2. **Trust badge plus per-number provenance**. A "certified" shield when every number came from a certified metric or verified question, a "partly certified" state otherwise, and a click on any number to open its source fact. Who: Snowflake green shield, Genie trusted-asset "Show more", Promethium lineage. Why: the top complaint is silent wrong numbers. Effort: **S**.
3. **Fix-it feedback that becomes proposed memories (steward-approved)**. Yes and Fix-it buttons with common reasons, plus "Request review" with a comment. A correction turns into a *proposed* Rule (definition) or Recipe (path) in the steward agent's queue, re-validated before approval, scoped personal or shared. Who: Genie (feedback to monitoring tab, suggested snippets), Spotter Memory (Rules and Recipes, personal and shared), Wren. Why: teaching without poisoning shared context. Effort: **M**.
4. **Context test suite from history ("golden set" evals)**. Turn verified questions plus past answered questions into a regression suite, re-run after ontology or data changes, and show pass or fail and drifted answers. Who: Atlan CES Simulate/Observe, Fabric SDK evaluation. Why: proves the context still works, and Strata already logs questions. Effort: **M**.
5. **Answerability check before answering**. Before spending tokens, score whether the linked ontology objects, metrics and facts cover the question. Show "can answer / partly / can't" with what's missing, and send "can't" to the unanswered log with a suggested fix. Who: partly Genie ("state its limitations"). No vendor shows an explicit answerability meter, so this is an opening. Effort: **S-M**.
6. **Clarifying question on ambiguous terms**. When a question term maps to two or more metrics or entities (for example two "revenue" definitions), ask a one-click choice instead of guessing, and remember the choice as a personal Rule. Who: Genie and agent mode clarifying questions. Why: wrong definition is the classic plausible-wrong-number cause. Effort: **S**.
7. **Plan, steps and "Answer now" for the investigator agent**. Show the investigation plan and each query as it runs, and let the user stop it and answer from facts gathered so far. Offer a quick vs deep toggle. Who: Genie agent mode (Answer now, Flash). Effort: **S-M**.
8. **Data-driven follow-up suggestions**. After each answer, suggest 2-3 follow-ups taken from neighbouring graph nodes, related certified metrics and anomalies in the result (fits the "suggestions from real data" rule). Who: Genie follow-ups. Effort: **S**.
9. **Workspace rules file (the "loose layer")**. A single admin-edited markdown of business conventions, included in every pack with its own budget slot and shown in "what the AI saw". Who: Hex rules file, Fabric agent instructions, Looker system instructions. Effort: **S**.
10. **Time-valid memories and drift flags**. Each note or correction has valid_from, valid_to and superseded_by. Ontology or schema changes flag memories that touch changed objects. Who: Graphiti idea. Spotter's stale-memory conflict shows the need. Effort: **M**.
11. **Context Pack v2: Gartner's three parts plus versioned export**. Each packed fact carries semantics, operational state (check status, freshness) and provenance (source, certifier, date). Packs export as a diffable versioned bundle, with an optional export to a Snowflake semantic-view YAML or Genie instructions. Who: Atlan context repos (MCP, deploy to Cortex/Genie), Wren Git-backed files. Effort: **M** (export adapters **L**).
12. **Context monitoring screen for stewards**. One screen with questions asked, feedback, review requests, unanswered log, most-used and never-used facts, and a "View references" list of which answers used each metric. Who: Hex Context Studio and View References, Genie monitoring tab. Effort: **M**.
