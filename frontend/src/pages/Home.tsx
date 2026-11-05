import { Link } from 'react-router-dom'
import { ArrowRight, Bot, ChartColumn, FileText, Layers, Network } from 'lucide-react'
import { Badge } from '../components/Badge'
import { PageHeader } from '../components/PageHeader'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

/**
 * Strata as four accelerators. Each is pitched on its own (its own input,
 * flow and output) and they compose; the agent on top is the end-to-end
 * story. The Ontology Accelerator is the first one built in depth.
 */
const TOOLS = [
  {
    key: 'ontology',
    title: 'Ontology',
    icon: Layers,
    to: '/tools/ontology',
    status: 'Ready',
    input: 'Any data (file, folder, database) plus any metadata you have: a Power BI model, '
      + 'a dbt file or a data dictionary.',
    flow: 'AI names every business thing and explains every field; the data checks each claim '
      + 'and proves the links. Add context in your own words.',
    output: 'A published ontology in plain words, for Nexus (Excel), Claude or any agent (MCP), '
      + 'and as files (JSON, OWL).',
  },
  {
    key: 'graph',
    title: 'Knowledge Graph',
    icon: Network,
    to: '/layers/graph',
    status: 'Next chunk',
    input: 'The published ontology and the source data.',
    flow: 'Build connected records with measured links and provenance.',
    output: 'A queryable graph of real entities and how they connect.',
  },
  {
    key: 'semantic',
    title: 'Semantic Layer',
    icon: ChartColumn,
    to: '/layers/semantic',
    status: 'Next chunk',
    input: 'The ontology (which column is net revenue) and the business questions.',
    flow: 'Propose metrics from the problem statement, certify them, validate SQL.',
    output: 'Approved metric definitions every report and agent shares.',
  },
  {
    key: 'context',
    title: 'Context Engine',
    icon: FileText,
    to: '/layers/context',
    status: 'Next chunk',
    input: 'A question, plus the ontology, graph and metrics.',
    flow: 'Check answerability, gather cited evidence within a budget.',
    output: 'A cited evidence pack an agent can answer from without guessing.',
  },
] as const

export function Home() {
  useDocumentTitle('Strata')
  return (
    <div className="page">
      <PageHeader
        eyebrow="Strata"
        title="Four accelerators, one product"
        description="Each tool stands on its own with its own input and output, and they work together. The agent on top shows the whole story: what your data looked like, which layers it used, and the answer."
      />
      <div className="tool-grid">
        {TOOLS.map((tool) => (
          <Link key={tool.key} to={tool.to} className={`tool-card tool-card--${tool.key}`}>
            <div className="tool-card__head">
              <tool.icon size={20} aria-hidden="true" />
              <span className="tool-card__title">{tool.title}</span>
              <Badge tone={tool.status === 'Ready' ? 'teal' : 'slate'}>{tool.status}</Badge>
            </div>
            <dl className="tool-card__io">
              <dt>Input</dt><dd>{tool.input}</dd>
              <dt>Flow</dt><dd>{tool.flow}</dd>
              <dt>Output</dt><dd>{tool.output}</dd>
            </dl>
            <span className="tool-card__open">Open <ArrowRight size={14} aria-hidden="true" /></span>
          </Link>
        ))}
        <Link to="/agents" className="tool-card tool-card--agent">
          <div className="tool-card__head">
            <Bot size={20} aria-hidden="true" />
            <span className="tool-card__title">End to end, with an agent on top</span>
            <Badge tone="indigo">Composed</Badge>
          </div>
          <p className="tool-card__story">
            Ask a business question. The agent shows the data it started from, the layers it
            used (ontology, graph, metrics, context) and the cited answer, like a Copilot for
            your enterprise data.
          </p>
          <span className="tool-card__open">Open agents <ArrowRight size={14} aria-hidden="true" /></span>
        </Link>
      </div>
    </div>
  )
}
