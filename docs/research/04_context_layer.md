# Layer 4 — Context Layer: market research

Research note for the "better middle layer" programme. Scope: what the market means by "context
layer", how task-conditioned evidence reaches an LLM/agent, what is automated vs human-reviewed, and
what the agent actually receives. Prices are public list prices seen on **2026-10-29**; "unknown" =
no public list price found. Grades: **A** = we measured, **B** = primary vendor docs, **C** =
independent/analyst, **D** = our inference. Marketing claims are labelled *(documented — vendor)*.

## Executive summary

1. "Context layer" is now a contested marketing term: Atlan, Neo4j, Cube and Snowflake use it for different things, and none of them is our Layer 4 (runtime answer packing under a budget).
2. The market splits into metadata/context platforms (Atlan, Snowflake Horizon Context), graph-plus-memory engines (Neo4j, Zep, Letta), agent platforms (Palantir AIP, Glean) and retrieval plumbing (GraphRAG, MCP, vector databases).
3. Enterprise context is overwhelmingly **permissioned metadata and memory**; only Palantir documents an approval gate before an agent acts, and nobody documents a per-fact evidence grade.
4. MCP has become the de-facto delivery contract — dbt, Cube, Snowflake, Glean and Zep all ship MCP servers — so an MCP endpoint is table stakes, not a moat.
5. Nobody sells what we build: a **hard-budget, provenance-labelled evidence pack** with an explicit record of what was dropped and why.

## Comparison table

| Tool | Category | Licence / public list price (2026-10-29) | Deployment | How built | Human review | Agent receives | Grade |
|---|---|---|---|---|---|---|---|
| Atlan Context Layer | Metadata/context platform | Proprietary; no public list price (sales-quoted) | SaaS, single-tenant, "deploy anywhere" via MCP | Connectors → enterprise graph; AI Context Agents draft definitions; Studio runs evals, deploys, observes drift | AI + human, versioned context repos, eval suites | MCP: governed definitions, lineage, policies | B |
| Neo4j Context Engine | Graph context layer + agent memory | Proprietary; pricing unknown (launched 2026-10-20; design partners) | Neo4j graph via Context Studio | 6-layer business ontology from Databricks/Snowflake; GraphRAG retrievers; Context Memory | Visual ontology builder + change management | Graph traversal, memory, MCP servers | C |
| Palantir AIP | Enterprise AI platform on an Ontology | Proprietary; no public list price (platform subscription) | Foundry enrollment, cloud/on-prem/gov | Hand-modelled Ontology; agents in AIP Logic / Chatbot Studio / SDK | **Staged writes = approval**; audit, markings | Ontology objects/functions as tools + cited retrieval context | B |
| Microsoft GraphRAG | Open-source graph RAG pipeline | **MIT**; free code, pay LLM tokens | Local Python | LLM extracts entities/claims → Leiden communities → summaries; Global/Local/DRIFT/Basic query | None built in; prompt tuning manual | Prompt passages and community summaries | B |
| MCP | Open integration protocol | Open spec, no fee (LF Projects governance) | Any host/server | Servers expose resources/prompts/tools; host decides the window | Consent/authorisation prompts, not content review | Tool definitions, tool results, resources | B |
| Glean | Enterprise AI work platform | Per-user per-month seat (amount unpublished); Model Hub usage at model rates | Glean-hosted, single-tenant, regional residency | 250+ connectors → Enterprise Graph; permissions enforcement; memory | Admin config, agent governance, RBAC | Permissioned docs/people with citations; remote MCP server | B |
| Zep / Graphiti | Temporal agent memory | Graphiti **Apache-2.0**; Zep **$125/mo Flex**, **$375/mo Flex Plus**, Enterprise custom | Cloud, BYOK, BYOC | Temporal context graph; custom entity/edge types | Custom extraction instructions; Enterprise audit | Memory retrieval API + **Context MCP Server** | B |
| Letta | Stateful agent harness | **Apache-2.0** (letta-code; brand assets excluded); Cloud price unknown | Local, self-hosted, Cloud | Agent rewrites its own memory blocks/skills; context tracked in git (MemFS) | Permission modes, hooks; no enterprise approval | Rewritten memory blocks in its own context | B |
| Vector DBs (Pinecone/Weaviate/Qdrant) | Storage, **not a layer** | Pinecone Free / **Builder $20/mo flat** / **Standard $50/mo min**; Enterprise custom | Managed or self-hosted | Embed, index, similarity search | None (caller owns quality) | Top-k chunks + metadata | B |

## Per-tool findings

### Atlan — "the context layer for AI"

Atlan defines a context layer as the system that turns company knowledge into machine-usable context,
carrying **knowledge** (trusted assets, provenance), **expertise** (procedures) and **norms** (what an
agent may do). Products: Enterprise Data Graph (connectors, lineage), **Context Agents** (AI teammates
that draft ontology, descriptions, metrics, quality rules, glossary, READMEs), **Context Engineering
Studio**, Context Lakehouse.

The Studio UI shows the honest workflow: a versioned context repo (`v3.1.2 · AI + human`, "updated 2h
ago · @jsmith + AI"), a 47-test evaluation suite, and "all agents auto-updated on deploy". So AI
drafts, humans commit, evals gate — the most mature governed-context workflow here. Deployment is via
an MCP server (Workday's quote on the page cites it). The agent receives governed definitions,
lineage and policies: metadata context, not a sized answer. Claims ("400+ enterprises", "8B context
reads / 90 days", "87% of customers say generated context is on par with or better than human-written")
are *(documented — vendor, self-reported)*; **measured: none**. Limits: catalog-scale prerequisite,
curation load, opaque pricing, no budget or per-line grade. **Grade B (docs), C for claims.**

### Neo4j Context Engine

Announced **2026-10-20**, nine days before this note. Sells a shared knowledge layer for agents on a
predefined **6-layer business ontology** said to derive from hundreds of enterprise deployments
*(documented — vendor)*. Components: **Context Build & Runtime** (builds from Databricks/Snowflake,
headless CLI/Python), **Context Studio** (visual ontology builder, MCP setup, change management), and
**Context Memory** (short/long/reasoning memory, skill distillation, logs reasoning paths). Retrieval
uses **GraphRAG retrievers**. The agent gets graph traversal plus memory over MCP — richer than top-k
because relationships and their provenance are first-class. No public price, no measured accuracy,
design partners only. **Grade C.**

### Palantir AIP

AIP is an AI platform on the Ontology (object types, links, actions); agents are built with AIP Logic,
AIP Chatbot Studio (formerly Agent Studio) and the Agent SDK. Docs describe retrieval **context types**
with **citations**, session logging, AIP Evals, and security markings that control LLM data access.
**Staged writes** are the strongest approval mechanism in this set: an agent proposes Ontology changes
that a human approves before they apply — an action-level gate, not just a content gate. The agent
receives typed Ontology objects/functions as tools plus cited context. Pricing is not public; the
platform is services-heavy and the context layer is inseparable from a hand-built Ontology.
**Grade B.**

### Microsoft GraphRAG

An MIT-licensed research pipeline: TextUnits → LLM-extracted entities, relationships and claims →
Leiden clustering → bottom-up community summaries → Global, Local, DRIFT or Basic query. The README is
candid: "largely in maintenance mode", "won't be accepting new PRs", indexing "can be an expensive
operation", prompt tuning strongly recommended. The agent receives passages and community summaries
in its prompt. There is no permission model, no per-line grade, no budget accounting, no human
approval and no enterprise connector story — a corpus pipeline, not a layer. **Grade B.**

### MCP (Model Context Protocol)

An open JSON-RPC protocol: LLM **hosts** connect to **servers** exposing **resources**, **prompts** and
**tools**; clients may offer sampling, roots and elicitation. The spec mandates user consent, explicit
tool authorisation, and treats tool descriptions as untrusted. Governance is "a Series of LF Projects"
(the Agentic AI Foundation under the Linux Foundation); the 2026-07-28 release claims ~half a billion
monthly SDK downloads *(documented — vendor blog)*.

**Why it is not a layer.** MCP standardises delivery: not what is true, what is relevant, who may see
it, or how much fits. The host owns the context window; the server only decides what it will return.
**Implication: MCP is our distribution channel, not our competitor** — the packer should expose an MCP
server and let hosts consume the bounded answer. **Grade B.**

### Glean

Enterprise search, assistant and agents over an **Enterprise Graph** (knowledge graph + hybrid index +
custom semantic/lexical models), 250+ connectors, permission enforcement ("Glean Protect"), saved and
learned memory, agent building/governance, a **remote MCP server** and Search/Chat/Agents APIs.
Licensed per user per month; LLM usage billed at model rates (Model Hub table dated 2026-10-20);
single-tenant hosting with regional residency. The agent receives permission-filtered documents and
people with citations. Strong on permissions and freshness; weak on structured metric facts, budgets
and evidence grades. **Grade B.**

### Zep / Graphiti

Agent memory as a **temporal context graph**: the Apache-2.0 Graphiti engine supports custom
entity/edge types; Zep Cloud adds operations, audit (Enterprise), SOC 2/HIPAA, BYOK/BYOC and a
**Context MCP Server** with seat limits. 2026-10-29 list: **Flex $125/month** (50,000 credits, then
$25/10k; 5 MCP seats), **Flex Plus $375/month** (200,000 credits; 15 seats), Enterprise custom; free
prototyping at 10,000 credits/month. An S&P Global Market Intelligence quote on the page calls it a
"temporal context graph" *(documented — vendor page)*. The agent gets memory retrieval over API/MCP.
Great for user/account history; not metric governance; no per-line grade. **Grade B.**

### Letta

Letta (formerly MemGPT) now ships **Letta Code**, an Apache-2.0 stateful harness: agents rewrite their
own memory blocks and skills, context is tracked in git (MemFS), plus subagents, permissions,
schedules and channels; Letta Cloud stores memory/identity/conversations by default, with a local
backend option. The agent receives its own rewritten memory blocks — self-managed context, not shared
enterprise evidence. Powerful for long-horizon single agents; the opposite of a governed,
permissioned, multi-source layer. Cloud pricing not retrieved (unknown). **Grade B.**

### Vector databases

Storage, not a layer. Pinecone list (2026-10-29): Free, **Builder $20/month flat**, **Standard
$50/month minimum usage**, Enterprise custom; Weaviate/Qdrant are open source and self-hostable
(licences not re-verified). The agent receives top-k chunks plus metadata; permissioning exists only
as metadata filters the caller must apply. No meaning, lineage, budget or approval. Anyone pitching a
vector DB as "the context layer" is selling storage. **Grade B (Pinecone pricing); D (the
"not-a-layer" judgement, though vendor docs treat them as storage).**

## Problems solved / under-served

| # | Buyer problem | Status | Evidence |
|---|---|---|---|
| 1 | Too much context ("context rot") vs missing evidence | **Under-served** | Only our Layer 4 documents a hard budget; vendors ship retrieval, not packing |
| 2 | A guess must not read as a fact | **Under-served** | No vendor documents per-fact grades; citations ≠ confidence |
| 3 | Permissions enforced at retrieval | **Served** | Glean Protect, Atlan policies, Palantir markings; absent in GraphRAG/vector DBs |
| 4 | Freshness and "as at" answers | **Under-served** | Zep/Neo4j are temporal for memory; no bitemporal fact answers |
| 5 | Join "why" (docs/tickets) with "what" (numbers) | **Partly** | Cube MCP Connectors, Atlan lineage; still agent-assembled |
| 6 | Memory contradiction across sessions | **Partly** | Zep temporal graph, Letta self-editing; neither audits contradictions |
| 7 | Silent truncation losing meaning | **Under-served** | No drop-whole-fact semantics documented; truncation is the default failure |
| 8 | Approval before an agent acts | **Served (rare)** | Palantir staged writes is the only documented action gate |
| 9 | Evaluating context/answer quality | **Partly** | Atlan Studio evals, Cube Evals, Glean insights; not context-fit metrics |
| 10 | Cost/latency per question | **Under-served** | Seat/credit pricing hides marginal retrieval cost |
| 11 | Terminology confusion in procurement | **Under-served** | Four vendors, four meanings (see Terminology) |
| 12 | Lock-in: context stored in a vendor cloud | **Under-served** | All hosted; GraphRAG is local but ungoverned |

## What a better version must do

1. **Pack, don't dump.** Hard character/token budget; rank measured > derived > external; drop a fact
   whole rather than truncate it (half a sentence still reads as complete).
2. **Label every line** with provenance and as-of time, in the rendered answer.
3. **Filter permissions before selection,** not after generation; record exclusions as first-class.
4. **Condition on the task** — choose facts per question type, not global top-k similarity.
5. **Be temporal:** answer "as at" a date from a bitemporal graph, and record when the pack was built.
6. **Emit artifacts, not vibes:** one deterministic bundle with a stable schema, an MCP endpoint and a
   testable contract.
7. **Work with zero integrations:** files, SQLite, Postgres, CSV folders — no catalog or warehouse.
8. **Show the trade-off:** report what was dropped and why, so humans and agents see the cost of the
   size limit.
9. **Evaluate with golden questions,** logging coverage (available), fit (kept) and faithfulness (used).

## Candidate differentiators

1. **Hard-budget packing with drop-whole-fact semantics** — the only layer that guarantees size and
   never ships a truncated half-fact.
2. **Per-line evidence grade** — measured / derived / external, with the as-of date, visible to whoever
   reads the pack.
3. **Permission- and time-aware selection** from one bitemporal graph (stated vs guessed edges).
4. **Zero-integration, local-first** — runs on files and databases with no catalog, connectors or
   vendor cloud.
5. **Budget transparency** — an auditable record of what was dropped and why, which no vendor offers.

## Terminology

Four meanings are in active commercial use, and conflating them will confuse buyers or engineers:

1. **Atlan — organisational context platform.** Context = governed enterprise knowledge (definitions,
   lineage, policy, decision history) served to any model. Design-time governance plus a runtime MCP
   feed; the broadest claim, context as the company's knowledge estate.
2. **Neo4j — Context Engine.** Context = a graph ontology of the business plus persistent agent memory,
   traversed at runtime.
3. **Cube — AI Context Layer.** Context = semantic layer plus glossary/rules/lineage delivered over
   MCP. In practice this is Layer 3 renamed for an AI buyer.
4. **Snowflake Horizon Context (preview, 2026-10-12).** Context = catalog metadata extended across
   platforms (18 sources, cross-platform column lineage) — metadata coverage, not answer assembly.

Our Layer 4 is a fifth thing: **runtime, task-conditioned evidence packing under a size budget with
per-fact provenance**. It sits downstream of all four: they supply knowledge, graphs, metrics or
metadata; we decide what fits and how it is labelled.

**Recommendation.** Do not market Layer 4 as "a context layer" — every incumbent claims that phrase and
buyers cannot tell them apart. Use **"Agent Context Builder"** as the external product name, with the
descriptor **"task-conditioned, provenance-graded evidence packs under a hard budget"**. In written
material reserve "context layer" for Atlan-style platforms and "context engine" for Neo4j-style graph
runtimes; say "context packing" or "answer context" for what we do. Short category label for decks:
**"Answer Context Builder (ACB)"**.

## Sources (all accessed 2026-10-29)

- Atlan context layer — https://atlan.com/context-layer/
- Atlan Context Engineering Studio — https://atlan.com/context-engineering-studio/
- Neo4j Context Engine — https://neo4j.com/product/context-engine/
- Neo4j launch press release — https://neo4j.com/press-releases/neo4j-context-engine/
- Neo4j launch coverage (trade press) — https://www.storagereview.com/news/neo4j-context-engine-ai-agents-knowledge-layer-ontology-graph-native-memory
- Palantir AIP overview — https://www.palantir.com/docs/foundry/aip/overview/
- GraphRAG README — https://github.com/microsoft/graphrag
- GraphRAG docs — https://microsoft.github.io/graphrag/
- GraphRAG licence (MIT) — https://raw.githubusercontent.com/microsoft/graphrag/main/LICENSE
- MCP specification — https://modelcontextprotocol.io/specification/2025-06-18
- MCP maintainer blog — https://blog.modelcontextprotocol.io/
- Glean Core Suite pricing/usage — https://docs.glean.com/glean-core-suite-pricing
- Glean platform — https://www.glean.com/
- Zep pricing — https://www.getzep.com/pricing/
- Graphiti licence — https://raw.githubusercontent.com/getzep/graphiti/main/LICENSE
- Letta Code README — https://raw.githubusercontent.com/letta-ai/letta-code/main/README.md
- Letta licence — https://raw.githubusercontent.com/letta-ai/letta-code/main/LICENSE
- Pinecone pricing — https://www.pinecone.io/pricing/
- Snowflake Horizon Context preview — https://docs.snowflake.com/en/release-notes/2026/other/2026-10-12-horizon-context-preview
- Cube AI Context Layer — https://cube.dev/product/ai-context-layer
