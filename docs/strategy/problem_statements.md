# Problem statements — one per layer, evidence-backed

The manager's exact complaint: *"We solve four problems but we don't have a
problem statement. What problem does this layer solve? How does the end user use
it?"* This document fixes that. Each statement is written in buyer language,
grounded in the market evidence in `docs/research/`, and marked with the
evidence that proves the problem is real.

Rules:
- A statement is **generic** (works for 100 clients) and then **tailored** per
  client using the method in §6.
- No invented numbers. The "proof" column says what we will measure; the number
  goes in `docs/benchmark/BENCHMARK.md` when measured.
- One statement per layer, one user, one job. If a layer has two users, split it.

## 1. Layer 1 — Ontology

**Statement.** *"When I get a new source — a hundred tables from an ERP, a folder
of CSVs, a customer's database — nobody can tell me what the things are, which
column identifies one, or what connects to what. Every vendor wants a modelling
project first. I need a usable first model on day one, with the uncertain parts
clearly marked so I know what to check."*

| Field | Content |
|---|---|
| User | data platform lead / analytics engineer onboarding a source |
| Job | "give me the model of this data" |
| Today without us | weeks of manual modelling; catalogs describe tables but not things; CSVs with no keys are ignored |
| What we do | derive classes, keys, relations, time columns, measures/dimensions; label each `measured`/`derived` with confidence; store renames as data |
| Human approves | business names, ambiguous keys, inferred relations, time semantics |
| Consumed by | Layer 2 build, Layer 3 metric proposals, review UI, API `ontology.list` |
| Evidence | no Layer-1 vendor documents auto-derivation; all are model-first; price/entry barriers are high ([01](../research/01_ontology_layer.md)) |
| Proof | 100-table lake coverage, relation recall/precision, key accuracy, time-to-first-model |

**One-line pitch:** *"Your schema already contains most of the ontology — we read it out, label our guesses, and let you correct them instead of building it from a blank page."*

## 2. Layer 2 — Knowledge graph

**Statement.** *"Dashboards show numbers, not connections. When something
changes I can't answer 'what depends on this?', 'what was true at 03:04?', or
'is this the same customer as in the CRM?'. Graph databases can, but I have to
model and load everything first, and they cannot tell me what the graph looked
like last Tuesday."*

| Field | Content |
|---|---|
| User | on-call engineer, risk/fraud analyst, supply-chain analyst, data engineer |
| Job | "show me what is connected, and what it looked like then" |
| Today without us | SQL/recursive queries or a graph project; no as-of answers; no per-edge evidence |
| What we do | rows→nodes, FKs/name evidence→edges, **valid_from/valid_to from date columns**, orphan findings, provenance on every edge, `reach`/`subgraph`/time queries |
| Human approves | low-confidence/ambiguous links (via Layer 1 review) |
| Consumed by | Layer 4 evidence selection, graph UI, API `graph.query`, exports |
| Evidence | no competitor documents bitemporal edges or as-of primitives; every engine requires modelling ([02](../research/02_knowledge_graph_layer.md)) |
| Proof | as-of query returns two different correct answers; edge provenance visible; build time/dangling edges |

**One-line pitch:** *"A graph you don't have to build, that remembers when each link was true."*

## 3. Layer 3 — Semantic

**Statement.** *"Two dashboards, a report and a chatbot give four different
numbers for the same thing. Defining a metric is a modelling project in dbt or
LookML, and the platform charges per user/credit to serve it. I want the numbers
my data can actually support — proposed from the columns, defined once, owned by
someone, and the same in BI and in an agent."*

| Field | Content |
|---|---|
| User | analytics engineer / BI owner / data product owner |
| Job | "one number, everywhere" |
| Today without us | manual YAML/LookML/DAX; auto-proposed counts don't exist; no approval object; as-of not supported |
| What we do | propose counts + 6 aggregates per numeric column; compile to SQL with bound parameters; approved metric catalogue with owner/definition/dimensions/time grain/source precedence; refuse unknown groupings |
| Human approves | which proposals become business metrics, names, owners, definitions |
| Consumed by | BI via SQL/API, agents via MCP `metric.get`, context builder |
| Evidence | served well at enterprise scale, but onboarding is manual everywhere; no per-claim grade or as-of metric semantics ([03](../research/03_semantic_layer.md)) |
| Proof | metric agreement UI/API/agent; approved-only gate; onboarding time |

**One-line pitch:** *"We propose every metric your data can support, with the SQL already written; you approve the ones that matter, and every consumer gets the same number."*

## 4. Layer 4 — Agent Context Builder

**Statement.** *"My agent gets too much context and still misses the right fact
— or it gets a retrieved chunk with no idea whether it was measured or guessed.
I need the smallest set of facts that answers the question, inside a size limit,
with a citation, a timestamp and a confidence on every line — and I need to know
what was left out."*

| Field | Content |
|---|---|
| User | AI product owner / agent builder |
| Job | "give my agent evidence it can cite" |
| Today without us | retrieval APIs and MCP endpoints return chunks; no hard budget; silent truncation; citations ≠ confidence; "context layer" is a contested term |
| What we do | task → evidence selection from ontology/graph/metrics/findings → rank measured>derived>external → pack whole facts under budget → render with provenance/confidence/as-of/citation → report dropped facts |
| Human approves | answer policy, metric/semantic items (gate), context templates if used |
| Consumed by | any LLM/agent via MCP/API, reports, UI |
| Evidence | no vendor documents hard-budget packing with per-fact grades; Palantir staged-writes is the only approval gate; MCP is table stakes ([04](../research/04_context_layer.md)) |
| Proof | 5/5 ground-truth answers; budget never exceeded; every line graded; dropped list present; p95 assembly |

**One-line pitch:** *"We don't hand your agent a pile of search results. We hand it a receipted evidence pack that fits and says what it left out."*

## 5. Three end-to-end scenarios (used for the demo and the proof)

### Scenario A — Authoring: "onboard the lake"
1. Connect the 100-table lake (four domains, messy names, no-FK tables, 3 product masters).
2. Auto-derive ontology + graph; show coverage, confidence, findings, timings.
3. Review queue: approve 5 business names, 3 inferred links, 2 metrics.
4. Publish; show the four layers for one product.
**Angle:** creation. **Proof:** time, coverage, review count, no per-dataset code.

### Scenario B — Consumption: "which product is this?"
1. Agent asks: *"How much A-pack did we sell in the EU last quarter?"*
2. Ontology knows Product across ERP/PIM/marketplace; graph resolves the three
   source rows (`same_as`, confidence); semantic picks the revenue definition and
   the price source of truth; ACB returns a cited, budgeted answer.
3. Show the chosen source, alternatives, divergence, as-of, latency.
**Angle:** consumption. **Proof:** correct answer, citations, source justification.

### Scenario C — Trust: "why should I believe it?"
1. One metric identical in UI, API and agent.
2. Every line shows measured/derived; open a `derived` link and see the method.
3. Approve a metric live; unapproved metric is refused by API with
   `review_pending`.
4. Change the source (add a table) → rebuild/diff surfaced.
**Angle:** trust. **Proof:** gate, audit trail, one number.

## 6. How to tailor a generic statement to a client (the method to sell)

1. Ask three questions: *what data sources? what decision/job? who gets blamed
   when the number is wrong?*
2. Map the client's pain to the layer(s) in §1–4; keep the same structure.
3. Replace our generic proof with their data: run `connect` on their source and
   show the first model; run one of their real questions.
4. State the boundary: what we automate, what they approve, what we cannot know.
5. Agree the scorecard: what "better" means for them (time-to-model, number of
   disputed metrics, answers with citations, cost).

## 7. What these statements deliberately do not claim

- That the ontology is "correct" without human naming — it is structural.
- That every relation is a fact — inferred ones are labelled.
- That we replace Databricks/Atlan/Neo4j — we sit before them and feed agents.
- That the auto-derived metrics are business KPIs — they are candidates until
  approved.

## 8. Evidence index

- L1: [01_ontology_layer.md](../research/01_ontology_layer.md) §problems 1–12, §under-served
- L2: [02_knowledge_graph_layer.md](../research/02_knowledge_graph_layer.md) §problems 1–12
- L3: [03_semantic_layer.md](../research/03_semantic_layer.md) §problems 1–12
- L4: [04_context_layer.md](../research/04_context_layer.md) §problems 1–12
- Opportunity ranking: [gap_analysis.md](gap_analysis.md)
- Build contract: [better_version_blueprint.md](better_version_blueprint.md)
