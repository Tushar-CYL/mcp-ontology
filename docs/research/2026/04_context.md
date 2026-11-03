# Context layer / context engineering for AI agents over enterprise data (2025-2026)

NOTE: Intended destination was `C:/Users/tusha/AppData/Local/Temp/claude/2e81386eb977b160/f3643104-2f23-4ceb-a2ba-205b24e80fe3/scratchpad/research_notes/Strata four layers and agents/04_context.md`. Plan mode blocked writes there, so the notes are saved in this plan file. Copy them to that path once plan mode ends.

Researched 2026-11-03. Vendor-written sources are marked [VENDOR]. Facts from before 2025 are marked [OLDER].

## 1. Plain-language definition: what is context for an agent, and how is it different from data or RAG?

### Takeaway
Context is the small set of tokens the model actually sees when it answers. It is a curated working set taken from data, not the data itself. RAG is one way to fill it. Context engineering is the wider discipline of deciding, at every step, what goes in, in what form and at what size, because more context makes models measurably worse.

### Cited Findings
- Anthropic defines context as "the set of tokens included when sampling from an LLM". It defines context engineering as curating and maintaining "the optimal set of tokens during LLM inference", which covers everything beyond the prompt: tools, MCP, external data and message history. Prompt engineering is the narrower job of writing instructions. Published 29 Sept 2025. — [Anthropic, Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Context is "a finite resource with diminishing marginal returns". Every token spends part of an "attention budget". The goal is "the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome." — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Chroma frames the core finding the same way: whether information is present matters less than how it is presented. They call this "context engineering". — [Chroma, Context Rot (14 Jul 2025)](https://www.trychroma.com/research/context-rot)
- LangChain, citing Karpathy, describes the LLM as a CPU and the context window as RAM. Context engineering decides what is loaded into RAM at each step. — [LangChain, Context engineering for agents (2 Jul 2025)](https://www.langchain.com/blog/context-engineering-for-agents)

### Inferences
- An analogy for Strata: data is the whole library, the semantic layer and the knowledge graph are the catalogue and index, and context is the briefing folder handed to an analyst before a meeting. The folder holds a few pages, each tagged with a source, with a note on what was left out. Strata's "context pack" already matches this idea closely.
- RAG answers "find similar text". Enterprise context also needs governed definitions, measured numbers, lineage, freshness and permissions. That is why vendors now say "context layer" rather than "RAG".

### Gaps
- There is no standard industry definition of an enterprise "context layer". Each vendor defines it its own way (see section 3).

## 2. Principles from primary sources

### Takeaway
The sources agree on a small set of principles: put in the minimum high-signal context; retrieve just in time through lightweight references; compact or summarise long histories; keep notes outside the window; isolate work in sub-agents; use a few non-overlapping tools that return concise output. Every model degrades as input length grows, distractors hurt, and position effects exist.

### Cited Findings
**Anthropic, "Effective context engineering for AI agents" (29 Sept 2025)** — [link](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Context rot: as the token count grows, the model's ability to recall information accurately falls. The decline is gradual, with no hard cliff. The cause is architectural: there are n² pairwise token relationships, and models see less training data at long lengths.
- System prompts should sit at the "right altitude", neither brittle hard-coded logic nor vague guidance. Start minimal and add detail when failures show it is needed.
- Tools: a small, non-overlapping set. "If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better." Tools should return token-efficient output.
- Just-in-time retrieval: keep lightweight identifiers such as file paths, stored queries and links, and load data at runtime through tools. Metadata (names, folder structure, timestamps) helps the agent judge relevance. This is progressive disclosure.
- Hybrid strategy: preload some stable context and let the agent explore the rest. Claude Code loads CLAUDE.md up front and uses glob and grep for the rest. "Do the simplest thing that works."
- Compaction: summarise a conversation that is near the limit and restart with the summary. Tune for recall first, then precision. Clearing old tool results is the lightest form.
- Structured note-taking: the agent writes notes outside the context, such as NOTES.md or to-do lists. Anthropic's memory tool supports this.
- Sub-agents: each works in a clean context and returns a "condensed, distilled summary", often 1,000–2,000 tokens, to a lead agent.
- When to use which: compaction suits long conversations, notes suit iterative milestone work, and multi-agent suits parallel research.

**Anthropic, "Writing effective tools for AI agents" (11 Sept 2025)** — [link](https://www.anthropic.com/engineering/writing-tools-for-agents)
- Build a few tools for high-impact workflows rather than wrapping every endpoint. Fold multi-step operations into one tool.
- Namespace tools by service and resource. Prefix versus suffix naming measurably changed eval results.
- Return meaningful context: natural-language names and interpretable IDs rather than UUIDs or MIME types. Offer a `response_format` enum with "concise" and "detailed" values. In their Slack example, concise output used about one third of the tokens.
- Use pagination, filtering, range selection and truncation with sensible defaults. Claude Code caps tool responses at 25,000 tokens by default. When output is truncated, tell the agent how to narrow its query.
- Error messages should be actionable, with no opaque codes or tracebacks.
- Evaluate on realistic multi-step tasks. Track accuracy, number of tool calls, runtime, tokens and errors, and use held-out test sets.

**LangChain, "Context engineering for agents" (2 Jul 2025)** — [link](https://www.langchain.com/blog/context-engineering-for-agents)
- Four strategies. **Write**: scratchpads and memories. **Select**: pull in memories, tools and knowledge; RAG over tool descriptions is reported to improve tool-selection accuracy about 3x. **Compress**: summarisation (Claude Code auto-compacts at 95% of the window) and trimming, including trained pruners such as Provence. **Isolate**: multi-agent setups, sandboxed environments, and state schemas that keep fields hidden from the LLM.
- Multi-agent systems can use up to 15x more tokens than chat (the post cites Anthropic).
- Four failure modes, taken from Drew Breunig ("How Contexts Fail", 22 Jun 2025): **poisoning** (a hallucination enters the context), **distraction** (too much context overwhelms the model's training), **confusion** (superfluous context changes the answer), and **clash** (parts of the context contradict each other).

**Chroma, "Context Rot" technical report (14 Jul 2025)** — [link](https://www.trychroma.com/research/context-rot)
- 18 models tested: 5 Anthropic, 7 OpenAI, 3 Google and 3 Qwen. 194,480 LLM calls in total.
- Performance falls as input grows, even on simple tasks. The fall is steeper when the needle and the question are less semantically similar.
- Even one distractor lowers accuracy, and four lower it more. The effect is uneven across distractors and grows with length. Claude models abstained most and hallucinated least; GPT models hallucinated most.
- Surprise: across all 18 models, shuffled haystacks with no local coherence beat coherent ones.
- LongMemEval: focused prompts (about 300 tokens) beat full prompts (about 113k tokens) for every model, across 306 prompts.
- Repeated-words copy task (1,090 variants): every model declined as length grew.

**"Lost in the middle" [OLDER: Liu et al., arXiv July 2023, TACL 2024]** — [arXiv 2307.03172](https://arxiv.org/abs/2307.03172)
- U-shaped accuracy curve: models use information at the start and end of the context best and in the middle worst. (From prior knowledge of this well-known paper. Not re-fetched in this session.)
- Conflict to note: Chroma found "no notable effect" of needle position in its needle-question experiment ([Chroma](https://www.trychroma.com/research/context-rot)). Position effects may be weaker in 2025 models or depend on the task. Treat "put the important things first and last" as a cheap hedge, not a law.

### Inferences
- For Strata: ranking plus a character budget plus a dropped-items report is in line with every source above. Defaulting to a short pack (a few hundred to a few thousand tokens) is supported by the LongMemEval focused-versus-full result.
- The `response_format` concise/detailed pattern maps directly onto a `get_context(detail=...)` parameter.
- Chroma's distractor result supports Strata dropping near-duplicate and low-relevance facts aggressively rather than "padding to budget".

### Gaps
- No primary source quantifies the best context size for structured, tabular or metric facts specifically. Chroma's tests use text haystacks.

## 3. Enterprise context-layer products and how they work

### Takeaway
Every major data and AI vendor sells a "context layer" by 2026. The common pattern is a governed metadata or knowledge graph plus semantic definitions, served to agents over MCP with OAuth and permission passthrough. Most delivered context is metadata (definitions, lineage, ownership, quality and certification), not row data. Benchmark claims are almost all vendor-reported and lack methodology.

### Cited Findings
**Atlan [VENDOR]**
- Remote MCP server hosted at `https://mcp.atlan.com/mcp` or a per-tenant `/mcp` endpoint. 29 tools in 8 categories. Read tools include `semantic_search`, `get_assets`, `traverse_lineage` and `resolve_metadata`. Write tools update descriptions, apply tags (optionally propagated through lineage), set certification, create glossary terms and post announcements. — [Atlan MCP](https://atlan.com/mcp/)
- Auth: OAuth for individuals, so calls run with the user's roles. API keys for service accounts. Each tenant gets its own MCP instance. — [Atlan MCP](https://atlan.com/mcp/)
- "Only metadata passes through MCP"; no row data. Metadata is read live from REST APIs with no intermediate cache. Tool calls are audit-logged with masking. Writes are labelled "Updated using Atlan AI". — [Atlan MCP](https://atlan.com/mcp/)
- Claims "400+ source systems". "Context Agents" keep the layer updated from query history, lineage, column usage, BI models and docs. Delivered context includes column-level lineage, certified metric definitions, glossary terms, quality scores, ownership and access rules. — [Atlan MCP](https://atlan.com/mcp/)
- **+38% SQL accuracy claim: UNVERIFIED.** Search snippets attribute it to "Atlan AI Labs benchmarking ... 174 queries (522 evaluations)" on Atlan's own MCP pages. The current atlan.com/mcp page I fetched does not show the figure. No baseline, models or method were found. — [Atlan "What is Atlan MCP"](https://atlan.com/know/what-is-atlan-mcp/) (search snippet only)
- An independent-ish comparison that Atlan cites: Rumiantsau & Fokeev (arXiv 2026), "Semantic Layers for Reliable LLM-Powered Data Analytics". 3 frontier models, 100 questions. Adding a 4 KB semantic document to the schema raised accuracy from 45.5–50.5% to 67.7–68.7% (+17–23 points). Figures are as reported by Atlan; I did not read the paper itself. — [Atlan article](https://atlan.com/know/ai-agent/semantic-layer/mcp-semantic-layer-for-ai-agents/); [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
- Atlan's cookbook pattern: the Atlan MCP finds the certified table and governed definition, then a separate warehouse/SQL MCP runs the query. — [Atlan MCP cookbook](https://atlan.com/mcp-cookbook/talk-to-your-data/)

**Gartner claims (seen only through vendors)**
- "By 2028, 60% of agentic analytics projects relying solely on MCP will fail due to the lack of a consistent semantic layer." Attributed to the Gartner *Market Guide for Agentic Analytics* (Seth, O'Callaghan, Fei, Cornelissen, 9 Feb 2026). **Seen only in vendor pages (Cube, Dremio, ThoughtSpot, Strategy). The Gartner report is paywalled and I did not verify it.** — [Cube blog](https://cube.dev/blog/cube-recognized-in-the-2026-gartner-r-market-guide-for-agentic-analytics); [CData](https://www.cdata.com/resources/predicts-2026-ai-agents-mcp-governance-transforming-analytics)
- A separate claim is often confused with it: Gartner press release (11 May 2026) saying that by 2027, organisations that prioritise semantics will improve agentic AI accuracy by up to 80% and cut costs by up to 60%. This is a primary Gartner newsroom URL, but I only saw it cited by Atlan and did not fetch it. — [Gartner newsroom](https://www.gartner.com/en/newsroom/press-releases/2026-05-11-gartner-says-lack-of-semantics-causes-inaccurate-artificial-intelligence-agents-and-wasted-spending)
- Gartner (via trade press) recommends MCP for secure access, provided the underlying data is structured for AI readiness. — [Mexico Business News](https://mexicobusiness.news/cloudanddata/news/context-layer-key-scalable-ai-agents-gartner)

**Glean [VENDOR]**
- Enterprise Graph launched at Glean:LIVE (25 Sept 2025). It combines an org-wide knowledge graph with per-user Personal Graphs (work habits, projects, collaborators). Remote MCP servers were in beta, with OAuth. — [Reworked](https://www.reworked.co/knowledge-findability/glean-thinks-its-ai-understands-your-company-better-than-you-do/); [Glean Enterprise Graph](https://www.glean.com/enterprise-context/enterprise-graph)
- MCP Gateway extends Glean's permissions and governance to MCP calls, using OAuth 2.1 with enterprise IdPs. Connectors are permission-enforced. More than 100 native actions. — [Glean MCP gateway](https://glean.com/product/mcp-gateway); [Techstrong](https://techstrong.ai/features/glean-adds-additional-graphs-and-mcp-servers-to-ai-workflow-platform/)

**Microsoft Foundry IQ / Work IQ / Fabric IQ**
- Announced at Ignite in Nov 2025. Work IQ covers M365 work signals, Fabric IQ is a semantic layer and ontology over OneLake, and Foundry IQ is the knowledge and retrieval layer. — [Cloud Wars](https://cloudwars.com/ai/microsoft-debuts-work-iq-fabric-iq-and-foundry-iq-a-unified-intelligence-layer-for-the-ai-powered-enterprise/); [Directions on Microsoft](https://www.directionsonmicrosoft.com/cio-talk-microsoft-gets-iq/)
- Foundry IQ (primary docs): a multi-source "knowledge base" built on Azure AI Search agentic retrieval. It plans subqueries, retrieves, **enforces user permissions** (runs queries under the caller's Entra identity; the user token goes in the `x-ms-query-source-authorization` header) and returns **grounded answers with citations**, or extractive data with citations. Several agents can share one knowledge base. It is exposed to agents through the MCP tool `knowledge_base_retrieve`. Some features are GA and some are preview, depending on API version. — [Microsoft Learn: What is Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq); [Learn: knowledge retrieval](https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/knowledge-retrieval)
- A June 2026 GA date is reported by a third party only. Unverified.

**Databricks Genie Ontology**
- Reported as announced at Data + AI Summit (16 Jun 2026). A "self-improving knowledge graph" learned from Databricks data, dashboards, queries and 50+ connected apps, described as the "context engine" under Genie. It is fed by a user-defined semantic foundation in Unity Catalog and reported as Public Preview. The Genie knowledge store holds up to 200 snippets per space (metadata, prompt matching, joins, entity matching). **Sources are Atlan [VENDOR, competitor] and Kanerika. I did not verify against Databricks docs.** — [Atlan: Genie Ontology](https://atlan.com/know/ai-agent/databricks/genie-ontology/); [Kanerika](https://kanerika.com/blogs/databricks-genie-ontology/)
- Critique reported: inferred ("learned") context may be less trustworthy than agreed definitions, and "ontology" is used loosely. — [Kanerika](https://kanerika.com/blogs/databricks-genie-ontology/)

**DataHub / OpenMetadata / Unity Catalog MCP**
- Official `mcp-server-datahub` (PyPI) runs over stdio or HTTP. Tools include structured keyword search (boolean logic, filters, pagination, sort by usage) and `get_lineage`. In HTTP mode each client must send its own token, and there is deliberately no server-wide token. — [PyPI mcp-server-datahub](https://pypi.org/project/mcp-server-datahub/0.8.0/)
- `mcp-server-openmetadata` is a community project, not an official release. It wraps the REST API, including metrics and lineage CRUD. — [llmbase listing](https://llmbase.ai/mcp-servers/open-metadata/)
- No official Unity Catalog metric-view MCP server was found; only community UC metadata and lineage servers. — [proxziima/mcp-databricks-server](https://github.com/proxziima/mcp-databricks-server)

### Inferences
- The products converge on these features: governed definitions, lineage, certification and trust signals, owner, quality/health, permission passthrough via OAuth, audit logs, MCP delivery. Strata's facts (definition, health, caveats, pending reviews, relationships) map onto them well.
- What Strata has that most of them do not advertise: **measured numbers with segment contributions**, plus a measured/derived label, a dropped-items report and a coverage score. Vendors mostly deliver metadata, and Foundry IQ delivers document chunks with citations. This is a real differentiator worth keeping.
- What the vendors have that Strata may lack: permission-aware retrieval under the caller's identity, OAuth on remote MCP, audit logging of tool calls, and certification status as a ranking signal.

### Gaps
- Tellius, Contextual AI, Collibra, and Unity Catalog metric views were not researched within the call budget.
- The Atlan 38% figure and the Gartner 60% figure could not be checked against primary sources.

## 4. Techniques: ranking, budgeting, dedup, citations, freshness, conflicts, permissions, caching, sufficiency

### Takeaway
The techniques with the best evidence are: rank and trim to a small budget; remove distractors and duplicates; return citations and extractive evidence; enforce permissions at retrieval time with the user's identity; and check whether the context is sufficient before answering, abstaining when it is not.

### Cited Findings
- **Sufficiency / "is this answerable?"**: Google Research, "Sufficient Context" (ICLR 2025). Context is sufficient if it "contains all the necessary information to provide a definitive answer". An LLM autorater (prompted Gemini 1.5 Pro) labels sufficiency with at least 93% accuracy. RAG raises correct answers but makes models hallucinate rather than abstain. Example: Gemma's wrong-answer rate went from 10.2% with no context to 66.1% with insufficient context. Selective generation combines the sufficiency signal with self-rated confidence, through a logistic regression, to decide when to abstain. — [Google Research blog (14 May 2025)](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/); [arXiv 2411.06037](https://arxiv.org/pdf/2411.06037.pdf)
- **Distractors and dedup**: even one distractor lowers accuracy. — [Chroma](https://www.trychroma.com/research/context-rot)
- **Budget and truncation defaults**: 25k-token cap, pagination, a concise/detailed switch, and guidance on narrowing when output is truncated. — [Anthropic tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- **Citations and provenance**: Foundry IQ returns "extractive data with citations so agents can reason over raw content and trace answers to source documents". — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq)
- **Freshness metadata in protocol**: MCP content and resource annotations support `audience`, `priority` (0–1) and `lastModified`. — [MCP spec 2025-11-25, Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- **Permission-aware retrieval**: Foundry IQ runs queries under the caller's Entra identity ([Learn](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq)). Atlan uses OAuth so the user's roles apply ([Atlan](https://atlan.com/mcp/)). The DataHub MCP requires per-client tokens ([PyPI](https://pypi.org/project/mcp-server-datahub/0.8.0/)).
- **Caching trade-off**: Atlan explicitly advertises "no intermediate caching", meaning live reads, for freshness. — [Atlan](https://atlan.com/mcp/)
- **Conflict ("context clash")** is a named failure mode. — [LangChain / Breunig](https://www.langchain.com/blog/context-engineering-for-agents)

### Inferences
- Strata's coverage score is a home-grown sufficiency signal. The Google paper suggests turning it into an explicit `answerable: yes|partial|no` with a reason, and telling agents to abstain or ask a follow-up when it is "no". That is backed by evidence that insufficient context increases hallucination.
- Add `as_of` / `lastModified` to every fact, and use MCP `annotations.priority` for weight. This uses protocol-native fields instead of custom ones.
- Conflict detection, such as two definitions of the same metric or a measured value disagreeing with a derived one, should appear as an explicit caveat fact rather than being silently resolved.

### Gaps
- No published benchmark compares ranking methods (weight/relevance/confidence blends) specifically for metric or structured facts.

## 5. MCP: spec status, transports, auth, primitives, security, read-only best practices

### Takeaway
The current MCP spec is **2025-11-25**, which followed 2025-06-18. It adds OIDC discovery, incremental scope consent, Client ID Metadata Documents, URL-mode elicitation, tool calling in sampling, experimental "tasks", icons and tool-naming guidance. The transports are stdio and Streamable HTTP. Auth is OAuth 2.1-based, and token passthrough is forbidden. Tool poisoning and prompt injection through tool output are the main practical threats.

### Cited Findings
- 2025-11-25 changes versus 2025-06-18: OpenID Connect Discovery; icons on tools, resources and prompts (SEP-973); incremental scope consent via `WWW-Authenticate` (SEP-835); tool-name guidance (SEP-986); URL-mode elicitation (SEP-1036); `tools`/`toolChoice` in sampling (SEP-1577); OAuth Client ID Metadata Documents as the recommended registration method (SEP-991); **experimental tasks** for durable, polled requests (SEP-1686); HTTP 403 for invalid Origin in Streamable HTTP; input-validation errors returned as Tool Execution Errors so the model can self-correct (SEP-1303); JSON Schema 2020-12 as the default; formal governance and SDK tiering. — [MCP changelog 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/changelog)
- Tools are "model-controlled", and a human in the loop SHOULD be able to deny calls. Tools can declare `outputSchema`, and the server then MUST return conforming `structuredContent`, with a serialized TextContent copy recommended for compatibility. Tools may return `resource_link` or embedded resources. Annotations (audience, priority, lastModified) apply to all content. **Clients MUST treat tool annotations as untrusted unless the server is trusted.** Servers MUST validate inputs, enforce access controls, rate-limit and sanitize outputs. Clients SHOULD validate results before passing them to the LLM and log usage. Tool names: 1–128 characters, from `[A-Za-z0-9_.-]`. — [MCP spec Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- Security best practices (spec): confused deputy (proxy servers MUST obtain per-client consent); **token passthrough forbidden** ("MCP servers MUST NOT accept any tokens that were not explicitly issued for the MCP server"); SSRF during OAuth discovery; session hijacking (servers MUST NOT use sessions for authentication and SHOULD bind sessions as `<user_id>:<session_id>`); local server compromise (prefer stdio for local use); scope minimization (start with a minimal read scope such as `mcp:tools-basic` and elevate step by step). — [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)
- **Tool poisoning**: named by Invariant Labs in April 2025. Hidden instructions in tool descriptions led to exfiltration of private data. A follow-up GitHub MCP "toxic agent flow" (around 26 May 2025) used a malicious public issue to make an agent leak private repo data into a public PR. — [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-ai-agent-exfiltration-2/) (secondary; Invariant primary posts not fetched)
- CyberArk extends the attack to "Full-Schema Poisoning" and to poisoned **tool outputs**: "no output from your MCP server is safe". — [CyberArk](https://www.cyberark.com/resources/agentic-ai-security/poison-everywhere-no-output-from-your-mcp-server-is-safe)
- Prevalence and success-rate figures conflict and are unverified: about 5.5% of 1,899 public servers showed poisoning; 36.5% average attack success; around 84% with auto-approve. — [CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-ai-agent-exfiltration-2/); [HOL](https://hol.org/blog/mcp-tool-poisoning-ai-agent-protocol-attack-surface). Treat these as indicative only.

### Inferences
- Best practice for Strata's read-only data server:
  - Mark tools with `readOnlyHint` (annotation names are from my prior knowledge of the spec; the fetched page confirms only that annotations exist and are untrusted).
  - Return `structuredContent` with an `outputSchema` for the context pack, plus a text copy.
  - Expose stable entities and definitions as **resources** (URIs such as `strata://metric/{id}`) and use `resource_link`s as citation targets.
  - Use Streamable HTTP with OAuth and audience-checked tokens for remote use, and stdio for local use.
  - Validate Origin.
  - Do not pass user tokens through to warehouses.
  - Return validation failures as `isError` tool results.
- Injection via data: values taken from source rows, such as free-text columns, comments or descriptions, can carry instructions. Strata should fence row text as data (quoted, typed fields, never mixed into instruction text) and could flag suspicious imperative text.

### Gaps
- Status of any MCP spec revision after 2025-11-25 (for example a 2026 release) was not checked. Verify on modelcontextprotocol.io.
- The Invariant Labs primary disclosures were not fetched.

## 6. Memory for agents (Mem0, Letta/MemGPT, Zep): relevance to a data context layer

### Takeaway
Agent memory products store facts extracted from conversations, such as user preferences and episodic history. Benchmarks are contested between vendors. For Strata, the relevant ideas are Zep's temporal knowledge graph (facts with validity periods) and memory as a "write" strategy for corrections and feedback. A general memory product is not a replacement for a governed context layer.

### Cited Findings
- Mem0 paper (arXiv 2504.19413, Apr/May 2025) reports on LoCoMo a 26% relative gain over OpenAI memory (66.9% vs 52.9%), a 91% lower p95 latency, and search latency of p50 0.148 s / p95 0.200 s. — [arXiv 2504.19413](https://arxiv.org/pdf/2504.19413)
- **Disputed**: the Mem0 paper scored Zep at 65.99% (later 58.44% on re-run); Zep claims 75.14% and blames implementation errors, including handling of LoCoMo's adversarial category. — [Zep blog [VENDOR]](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/)
- Zep is built on Graphiti, a temporal knowledge graph. One independent paper measured 536.8 ms average retrieval latency on the OSS code, against sub-200 ms in Zep's docs. — (via search summary; [arXiv 2507.03724 MemOS](https://arxiv.org/pdf/2507.03724) among results, not verified which paper)
- Anthropic's own view of memory is structured note-taking and a file-based memory tool. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- LangChain treats memory as the "write" strategy, with selection by embeddings or knowledge graphs, and warns that larger memory stores are harder to select from. — [LangChain](https://www.langchain.com/blog/context-engineering-for-agents)

### Inferences
- Strata's "pending reviews" and corrections already work as organisational memory. Adopting a temporal model (`valid_from`/`valid_to` on definitions and facts, as Graphiti does) would directly address stale definitions.
- Per-user conversational memory belongs to the agent or client, not to the data context layer. Strata should not build Mem0-style memory.

### Gaps
- Letta/MemGPT current features and licence were not fetched. From prior knowledge it is Apache-2.0, at github.com/letta-ai/letta, with core/archival memory tiers; this is unverified in this session.
- A reported 92.5% LoCoMo score for Mem0 (April 2026) has no primary source.

## 7. Evaluation: measuring context quality

### Takeaway
Standard tools split metrics into retrieval-side ones (context precision, context recall, context relevance, noise sensitivity) and generation-side ones (faithfulness/groundedness, answer relevancy), with newer agent metrics for tool-call accuracy and goal accuracy. Anthropic's advice is to evaluate tools and context on realistic multi-step tasks, tracking tokens and tool calls as well as accuracy.

### Cited Findings
- RAGAS metrics: Context Precision, Context Recall, Context Entities Recall, Noise Sensitivity, Response Relevancy, Faithfulness (plus multimodal versions). Nvidia-style metrics: Answer Accuracy, Context Relevance, Response Groundedness. Agent metrics: Topic Adherence, Tool Call Accuracy, Tool Call F1, Agent Goal Accuracy. — [RAGAS docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- An evaluation loop for tools measures accuracy, tool calls, runtime, tokens and errors on held-out, verifiable tasks. — [Anthropic tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- A sufficiency autorater can label query-context pairs with at least 93% accuracy, which makes it usable as an automatic context-quality metric. — [Google Research](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)
- Text-to-SQL accuracy with versus without a semantic document (+17–23 points) is an example of an A/B context evaluation. — [arXiv 2604.25149 via Atlan](https://atlan.com/know/ai-agent/semantic-layer/mcp-semantic-layer-for-ai-agents/)

### Inferences
- Suggested eval for Strata's context packs:
  1. Answer accuracy with the pack versus a raw-schema baseline.
  2. Citation accuracy: does every claim in the answer map to a fact id in the pack?
  3. Faithfulness: no numbers that are not in the pack.
  4. Sufficiency agreement: Strata's coverage score against an LLM sufficiency autorater.
  5. Abstention correctness on unanswerable questions.
  6. Tokens per correct answer.
- TruLens's "RAG triad" (context relevance, groundedness, answer relevance) and DeepEval's metric set are similar. I did not fetch them this session.

### Gaps
- TruLens and DeepEval docs, and their current licences, were not verified.

## 8. Failure modes

### Takeaway
The well-documented failure modes are: too much context (rot and distraction), distractors and near-duplicates, contradictory context (clash), hallucinations carried forward (poisoning), insufficient context leading to confident wrong answers, stale definitions, and injection through tool descriptions or tool outputs and data.

### Cited Findings
- Too much context: every one of 18 models degrades with length, and focused about 300-token prompts beat about 113k-token prompts. — [Chroma](https://www.trychroma.com/research/context-rot)
- Poisoning, distraction, confusion, clash. — [LangChain / Breunig](https://www.langchain.com/blog/context-engineering-for-agents)
- Insufficient context raises hallucination over abstention (Gemma: 10.2% to 66.1% wrong answers). — [Google Research](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)
- Injection via tool metadata and output (tool poisoning, toxic agent flows). — [CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-ai-agent-exfiltration-2/); [CyberArk](https://www.cyberark.com/resources/agentic-ai-security/poison-everywhere-no-output-from-your-mcp-server-is-safe)
- Trust in inferred context: critics question learned ontologies against agreed definitions. — [Kanerika](https://kanerika.com/blogs/databricks-genie-ontology/)
- Missing semantics: the Gartner MCP-only failure prediction (unverified; see section 3). — [Cube](https://cube.dev/blog/cube-recognized-in-the-2026-gartner-r-market-guide-for-agentic-analytics)

### Inferences
- Strata's measured/derived labels, citations, caveats and health directly mitigate poisoning (derived claims cannot pass as measured) and missing provenance.
- Stale definitions need explicit `as_of`/`version` fields and a staleness caveat once a threshold passes.

### Gaps
- I found no quantitative study of how often stale metric definitions cause agent errors in production.

## 9. Open-source repositories

### Takeaway
The main OSS references are the MCP spec, SDKs and reference servers, RAGAS for evaluation, Mem0, Letta and Graphiti/Zep for memory, LangGraph for orchestration, and DataHub's official MCP server as the closest analogue to a metadata context server.

### Cited Findings
- MCP specification, with changelog and governance including SDK tiering (SEP-1730). — [modelcontextprotocol spec changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog)
- DataHub official MCP server (`mcp-server-datahub`): stdio or HTTP, per-client tokens, search and lineage tools. — [PyPI](https://pypi.org/project/mcp-server-datahub/0.8.0/)
- RAGAS metric catalogue. — [RAGAS docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- Mem0 paper and code. — [arXiv 2504.19413](https://arxiv.org/pdf/2504.19413)
- Google sufficient-context code: github.com/hljoren/sufficientcontext. — [Google Research blog](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)

### Inferences
- Lessons for Strata:
  - From DataHub: per-client tokens with no server-wide token, and search syntax with filters and pagination.
  - From the sufficient-context repo: a ready-made autorater prompt for an "answerable?" check.
  - From the MCP SDKs: native `outputSchema`/`structuredContent` support.
  - From Graphiti: temporal validity on facts.

### Gaps
- I did not collect licence or activity metrics (stars, last commit) for modelcontextprotocol/servers and SDKs, explodinggradients/ragas, mem0ai/mem0, letta-ai/letta, langchain-ai/langgraph or getzep/graphiti, because the call budget ran out. From prior knowledge, which is unverified: MCP SDKs are MIT, RAGAS is Apache-2.0, Mem0 is Apache-2.0, Letta is Apache-2.0, LangGraph is MIT, and Graphiti is Apache-2.0. Check these on GitHub before citing.
