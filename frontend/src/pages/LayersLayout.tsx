import { NavLink, Outlet } from 'react-router-dom'
import { ChartColumn, FileText, Layers, Network } from 'lucide-react'
import { Badge } from '../components/Badge'
import { PageHeader } from '../components/PageHeader'
import { useSource } from '../context/SourceContext'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { cx } from '../utils/cx'

const TABS = [
  { to: 'ontology', label: 'Ontology', hint: 'What exists', icon: Layers, index: '1' },
  { to: 'graph', label: 'Knowledge graph', hint: 'What connects', icon: Network, index: '2' },
  { to: 'semantic', label: 'Semantic', hint: 'What you can measure', icon: ChartColumn, index: '3' },
  { to: 'context', label: 'Context', hint: 'One packed answer', icon: FileText, index: '4' },
] as const

export function LayersLayout() {
  useDocumentTitle('Layers')
  const { selectedSource, sources } = useSource()

  return (
    <div className="page">
      <PageHeader
        eyebrow="Four explainable layers"
        title="Layers"
        description="The same source, read four ways. Measured facts and derived inferences are labelled differently on every screen — a guess never looks like a fact."
        meta={
          selectedSource ? (
            <div className="page-header__chips">
              <Badge tone="indigo" dot>
                {selectedSource.name || selectedSource.id}
              </Badge>
              <span className="page-header__meta-text">
                {selectedSource.tables} tables · {selectedSource.classes} classes ·{' '}
                {selectedSource.nodes.toLocaleString()} nodes
              </span>
            </div>
          ) : (
            <span className="page-header__meta-text">
              {sources.length === 0 ? 'No source connected yet' : 'Choose a source in the top bar'}
            </span>
          )
        }
      />

      <nav className="layer-tabs" aria-label="Layer views">
        {TABS.map((tab) => {
          const Icon = tab.icon
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) => cx('layer-tab', isActive && 'layer-tab--active')}
            >
              <span className="layer-tab__index" aria-hidden="true">
                {tab.index}
              </span>
              <Icon size={17} className="layer-tab__icon" aria-hidden="true" />
              <span className="layer-tab__text">
                <span className="layer-tab__label">{tab.label}</span>
                <span className="layer-tab__hint">{tab.hint}</span>
              </span>
            </NavLink>
          )
        })}
      </nav>

      <Outlet />
    </div>
  )
}
