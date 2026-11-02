import { Link } from 'react-router-dom'
import { ArrowRight, Bot, Boxes, Layers, Network, ShieldCheck, Sparkles } from 'lucide-react'
import { Badge } from '../components/Badge'
import { Card } from '../components/Card'
import { PageHeader } from '../components/PageHeader'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

const OFFERS = [
  {
    index: '01',
    title: 'One layer, implemented properly',
    icon: Layers,
    summary:
      'For a team that already knows where the problem is: the ontology, the graph, the semantic definitions or the evidence pack.',
    deliverables: [
      'A certified implementation of the chosen layer',
      'Source connection and key/relationship discovery',
      'Tests that prove the layer before anything is built on it',
    ],
    outcome: 'A precise fix for a known gap, without a platform commitment.',
    action: { to: '/certification', label: 'See how layers are certified' },
  },
  {
    index: '02',
    title: 'The four-layer foundation + one agent',
    icon: Boxes,
    summary:
      'For a client who needs a trusted answer to one business question, end to end, with evidence behind every number.',
    deliverables: [
      'Ontology, knowledge graph, approved metrics and context',
      'A governed agent built, tested and published on top',
      'Traceability, source records and downloadable evidence',
    ],
    outcome: 'One decision-ready answer that a business user can trust and audit.',
    action: { to: '/studio', label: 'Open Agent Studio' },
  },
  {
    index: '03',
    title: 'The governed agent platform',
    icon: Bot,
    summary:
      'For a client who wants to create and publish their own agents over their own data, with the platform doing the governance.',
    deliverables: [
      'Agent Studio with instructions, guardrails and skills',
      'AI-suggested guardrails and custom skills',
      'Certification, preview and publish controls',
    ],
    outcome: 'An internal capability, not a one-off deliverable.',
    action: { to: '/studio', label: 'Build an agent' },
  },
] as const

export function Solutions() {
  useDocumentTitle('Solutions')
  return (
    <div className="page">
      <PageHeader
        eyebrow="Ways to engage"
        title="Solutions"
        description="The same four-layer foundation can be delivered as a focused layer, as one governed answer, or as a platform the client operates. Each route has the same evidence standard."
        meta={
          <div className="page-header__chips">
            <Badge tone="indigo" dot>Layer-first</Badge>
            <Badge tone="teal" dot>Agent-ready</Badge>
            <Badge tone="amber" dot>Governed</Badge>
          </div>
        }
      />

      <div className="solution-grid">
        {OFFERS.map((offer) => {
          const Icon = offer.icon
          return (
            <Card
              key={offer.index}
              title={
                <span className="solution-title">
                  <span className="solution-title__index">{offer.index}</span>
                  {offer.title}
                </span>
              }
              subtitle={offer.summary}
              actions={<Icon size={19} className="solution-icon" aria-hidden="true" />}
            >
              <div className="solution-body">
                <p className="detail-subtitle">Deliverables</p>
                <ul className="detail-list">
                  {offer.deliverables.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <p className="solution-outcome">
                  <Sparkles size={14} aria-hidden="true" />
                  {offer.outcome}
                </p>
                <Link to={offer.action.to} className="solution-link">
                  {offer.action.label}
                  <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </div>
            </Card>
          )
        })}
      </div>

      <Card
        title="The common foundation"
        subtitle="Whatever the engagement, the client gets the same certified chain from data to answer."
      >
        <div className="solution-foundation">
          <div className="solution-foundation__step">
            <Network size={17} aria-hidden="true" />
            <span>Source data connected and profiled</span>
          </div>
          <div className="solution-foundation__step">
            <Layers size={17} aria-hidden="true" />
            <span>Ontology, graph, metric and context certified</span>
          </div>
          <div className="solution-foundation__step">
            <ShieldCheck size={17} aria-hidden="true" />
            <span>Agent guardrails and traceability enforced</span>
          </div>
          <div className="solution-foundation__step">
            <Bot size={17} aria-hidden="true" />
            <span>Published answer with evidence the client can inspect</span>
          </div>
        </div>
        <div className="form-actions">
          <Link to="/onboarding" className="btn btn--primary btn--md">
            Start with a source
          </Link>
          <Link to="/certification" className="btn btn--secondary btn--md">
            Inspect certification
          </Link>
        </div>
      </Card>
    </div>
  )
}
