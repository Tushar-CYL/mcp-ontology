/**
 * What the November 2026 deep research found, per layer, in plain language.
 *
 * Source of truth: docs/research/2026/ (REPORT.md and catalogue.md). Every
 * link here was checked during that research; vendor-run evidence is flagged.
 * The layer pages render this in their "How others do this" panel so the app
 * and the docs never disagree.
 */

export type LayerId = 'ontology' | 'graph' | 'semantic' | 'context'

export interface Company {
  name: string
  how: string
  url: string
}

export interface Repo {
  name: string
  licence: string
  learn: string
  url: string
}

export interface Evidence {
  claim: string
  url: string
  /** Set when the party that ran the study sells this kind of layer. */
  bias?: string
}

export interface LayerResearch {
  id: LayerId
  number: 1 | 2 | 3 | 4
  title: string
  analogy: string
  plain: string
  question: string
  companies: Company[]
  repos: Repo[]
  evidence: Evidence[]
  strata: string
}

export const LAYER_RESEARCH: LayerResearch[] = [
  {
    id: 'ontology',
    number: 1,
    title: 'Ontology',
    analogy: 'The catalogue',
    plain:
      'A catalogue of the kinds of thing in your business (customers, orders, products), how each one is identified, and how they relate. It describes meaning, not storage.',
    question: 'What is a Customer, and how does it link to Orders?',
    companies: [
      { name: 'Palantir Foundry', how: 'Object types and link types ("the digital twin of an organisation"), plus actions agents can call with confirmation.', url: 'https://www.palantir.com/docs/foundry/ontology/core-concepts' },
      { name: 'Microsoft Fabric IQ', how: 'Ontology built from Power BI semantic models, bound to live data; still in preview (Oct 2026).', url: 'https://learn.microsoft.com/en-us/fabric/iq/ontology/overview' },
      { name: 'NVIDIA auto-ontology', how: 'Discover, ground, validate, expose over read-only MCP, learn from certified corrections.', url: 'https://github.com/NVIDIA/auto-ontology' },
      { name: 'Timbr', how: 'An ontology written in SQL over existing databases, without copying data.', url: 'https://docs.timbr.ai/doc/docs/platform/' },
    ],
    repos: [
      { name: 'NVIDIA/auto-ontology', licence: 'Apache-2.0', learn: 'The full lifecycle with certify, publish and roll back.', url: 'https://github.com/NVIDIA/auto-ontology' },
      { name: 'linkml/linkml', licence: 'Apache-2.0', learn: 'One YAML model compiled to OWL, SHACL, JSON Schema and SQL.', url: 'https://github.com/linkml/linkml' },
      { name: 'RDFLib/rdflib', licence: 'BSD-3-Clause', learn: 'Cheap export to Turtle, OWL and JSON-LD.', url: 'https://github.com/RDFLib/rdflib' },
    ],
    evidence: [
      { claim: 'Rule-based schema-to-ontology mapping beat LLM-based systems on 54 real database mappings (Burr, SIGMOD 2026).', url: 'https://hpi.de/naumann/news/paper-accepted-at-sigmod-2026.html' },
      { claim: 'Checking queries against an ontology raised accuracy to 72% and turned 8% of errors into an honest "I don\'t know".', url: 'https://arxiv.org/abs/2405.11706', bias: 'Run by data.world, which sold knowledge graphs' },
    ],
    strata:
      'Strata derives the ontology from the schema with fixed rules (the W3C Direct Mapping approach the research found most reliable) and labels every link as measured or derived, which no vendor document reviewed does per link.',
  },
  {
    id: 'graph',
    number: 2,
    title: 'Knowledge graph',
    analogy: 'The connected map',
    plain:
      'The catalogue filled in with your real records: every customer and order as a point, every link between them as a line, each line saying where it came from and since when it was true.',
    question: 'Which orders did customer C1 place, and what was true on 1 March?',
    companies: [
      { name: 'Neo4j', how: 'Graph database with Aura Agent and a hosted MCP server in every Aura instance.', url: 'https://github.com/neo4j-contrib/mcp-neo4j' },
      { name: 'Microsoft GraphRAG', how: 'Builds a graph from documents with an LLM; now in maintenance mode.', url: 'https://github.com/microsoft/graphrag' },
      { name: 'Zep / Graphiti', how: 'Time-aware graph that closes superseded facts instead of deleting them.', url: 'https://github.com/getzep/graphiti' },
      { name: 'Timbr', how: 'A virtual knowledge graph over SQL sources, the same family as Strata.', url: 'https://docs.timbr.ai/doc/docs/platform/' },
    ],
    repos: [
      { name: 'getzep/graphiti', licence: 'Apache-2.0', learn: 'Valid-from and valid-to on every fact.', url: 'https://github.com/getzep/graphiti' },
      { name: 'HKUDS/LightRAG', licence: 'MIT', learn: 'Graph plus vector retrieval for documents.', url: 'https://github.com/HKUDS/LightRAG' },
      { name: 'microsoft/graphrag', licence: 'MIT', learn: 'Corpus-wide summaries over documents; costly indexing.', url: 'https://github.com/microsoft/graphrag' },
    ],
    evidence: [
      { claim: 'GPT-4 answered 16% of enterprise questions over raw SQL and 54% over a knowledge graph of the same database.', url: 'https://arxiv.org/abs/2311.07509', bias: 'Run by data.world on its own benchmark' },
      { claim: 'Once judge bias is removed, GraphRAG gains over plain retrieval are "much more moderate than reported".', url: 'https://arxiv.org/abs/2506.06331' },
    ],
    strata:
      'Strata builds its graph from structured rows (no LLM extraction), which is the only graph family with published enterprise accuracy evidence. Each edge keeps its provenance and a valid-from time; inbound links are capped so a busy node stays cheap.',
  },
  {
    id: 'semantic',
    number: 3,
    title: 'Semantic layer',
    analogy: 'The rulebook of approved numbers',
    plain:
      'The agreed rules for every business number, such as "revenue counts completed orders only", compiled into SQL so every person and every agent gets the same answer.',
    question: 'What was net revenue last quarter, by the certified definition?',
    companies: [
      { name: 'dbt Semantic Layer (MetricFlow)', how: 'Metrics as code; engine open-source (Apache-2.0) since Oct 2025; MCP tools for agents.', url: 'https://github.com/dbt-labs/metricflow' },
      { name: 'Cube', how: 'Semantic layer with caching and row-level security; MCP server in Cube Cloud.', url: 'https://github.com/cube-js/cube' },
      { name: 'AtScale', how: 'Universal semantic layer; MCP server on the Databricks marketplace (Dec 2025).', url: 'https://www.atscale.com/' },
      { name: 'Databricks metric views', how: 'Separate measures from the dimensions used to group and filter them.', url: 'https://docs.databricks.com/aws/en/metric-views/' },
    ],
    repos: [
      { name: 'dbt-labs/dbt-mcp', licence: 'Apache-2.0', learn: 'Discover-then-query tools: list_metrics, get_dimensions, query_metrics.', url: 'https://github.com/dbt-labs/dbt-mcp' },
      { name: 'malloydata/malloy', licence: 'MIT', learn: 'Symmetric aggregates that stop join double-counting.', url: 'https://github.com/malloydata/malloy' },
      { name: 'apache/ossie', licence: 'Apache-2.0', learn: 'The open interchange format for metrics (incubating since June 2026).', url: 'https://github.com/apache/ossie' },
    ],
    evidence: [
      { claim: 'A semantic layer scored 100% on questions it covers and refused the rest; raw text-to-SQL "fails silently" with plausible wrong numbers.', url: 'https://www.getdbt.com/blog/semantic-layer-as-the-data-interface-for-llms', bias: 'Run by dbt Labs, which sells a semantic layer' },
      { claim: 'Adding a 4 KB business-definitions document lifted accuracy from 45-50% to 68% across three frontier models.', url: 'https://arxiv.org/abs/2604.25149', bias: 'Linked to a Cube repository' },
    ],
    strata:
      'Strata keeps governed metrics with owner, status, caveats and health, adds synonyms so "sales" finds Revenue, and checks agent-written SQL against the certified definition, a tool no vendor reviewed offers agents.',
  },
  {
    id: 'context',
    number: 4,
    title: 'Context',
    analogy: 'The cited briefing folder',
    plain:
      'The few pages an agent should read before answering: the facts that matter for this question, each tagged with its source, with a note on what was left out and whether the evidence is enough.',
    question: 'What exactly should the model see to answer this?',
    companies: [
      { name: 'Anthropic', how: 'Context engineering: the smallest set of high-signal tokens, fetched just in time.', url: 'https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents' },
      { name: 'Microsoft Foundry IQ', how: 'Cited answers under the caller\'s identity through one MCP tool.', url: 'https://learn.microsoft.com/en-us/azure/ai-foundry/' },
      { name: 'Atlan', how: 'Governed metadata for agents over MCP with OAuth.', url: 'https://atlan.com/know/context-layer-for-ai-agents/' },
      { name: 'DataHub', how: 'Per-client tokens, filtered search and lineage over MCP.', url: 'https://pypi.org/project/mcp-server-datahub/0.8.0/' },
    ],
    repos: [
      { name: 'Model Context Protocol', licence: 'Open specification', learn: 'Tool annotations, structured results and security rules.', url: 'https://modelcontextprotocol.io/specification/versioning' },
      { name: 'RAGAS', licence: 'Open source', learn: 'Measures context precision, recall and faithfulness.', url: 'https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/' },
    ],
    evidence: [
      { claim: 'All 18 models tested got worse as input grew; a focused ~300-token prompt beat a ~113k-token one.', url: 'https://research.trychroma.com/context-rot' },
      { claim: 'With insufficient context, models guess: one model\'s wrong answers rose from 10.2% to 66.1%.', url: 'https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/' },
    ],
    strata:
      'Strata packs a few ranked, cited facts under a budget, says what it dropped and why, labels measured versus derived, and gives every pack a yes / partial / no verdict so an agent refuses instead of guessing.',
  },
]

export function layerResearch(id: LayerId): LayerResearch {
  const found = LAYER_RESEARCH.find((layer) => layer.id === id)
  if (!found) throw new Error(`unknown layer ${id}`)
  return found
}
