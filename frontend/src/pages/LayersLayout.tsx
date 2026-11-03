import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ChartColumn, FileText, Layers, Network } from 'lucide-react'
import { api } from '../api/client'
import { Badge } from '../components/Badge'
import { LayerExplainer } from '../components/LayerExplainer'
import { PageHeader } from '../components/PageHeader'
import { type LayerId, layerResearch } from '../content/research'
import { useSource } from '../context/SourceContext'
import { useAsync } from '../hooks/useAsync'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { cx } from '../utils/cx'

const TABS: Array<{ to: LayerId; label: string; hint: string; icon: typeof Layers; index: string }> = [
  { to: 'ontology', label: 'Ontology', hint: 'The catalogue', icon: Layers, index: '1' },
  { to: 'graph', label: 'Knowledge graph', hint: 'The connected map', icon: Network, index: '2' },
  { to: 'semantic', label: 'Semantic', hint: 'The rulebook', icon: ChartColumn, index: '3' },
  { to: 'context', label: 'Context', hint: 'The briefing folder', icon: FileText, index: '4' },
]

export function LayersLayout() {
  const { pathname } = useLocation()
  const current = TABS.find((tab) => pathname.endsWith(`/${tab.to}`)) ?? TABS[0]
  const research = layerResearch(current.to)
  useDocumentTitle(research.title)
  const { selectedSource, sources } = useSource()
  const sourceId = selectedSource?.id ?? ''

  // Server-side cached per source, so moving between layers costs nothing.
  const certification = useAsync(
    (signal) => api.certification(sourceId, signal),
    [sourceId],
    { enabled: Boolean(sourceId) },
  )
  const metrics = useAsync(
    (signal) => api.metrics(sourceId, signal),
    [sourceId],
    { enabled: Boolean(sourceId) },
  )
  const approved = metrics.data
    ? metrics.data.metrics.filter((m) => m.status === 'approved').length
    : null

  return (
    <div className="page">
      <PageHeader
        eyebrow={`Layer ${research.number} of 4 · ${research.analogy}`}
        title={research.title}
        description={`It answers questions like: "${research.question}"`}
        meta={
          selectedSource ? (
            <div className="page-header__chips">
              <Badge tone="indigo" dot>
                {selectedSource.name || selectedSource.id}
              </Badge>
              <span className="page-header__meta-text">
                {selectedSource.tables} tables · {selectedSource.classes} kinds of thing ·{' '}
                {selectedSource.nodes.toLocaleString()} records
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

      {selectedSource ? (
        <LayerExplainer
          layer={current.to}
          source={selectedSource}
          metricCount={approved}
          certification={certification.data}
          certificationLoading={certification.loading}
        />
      ) : null}

      <Outlet />
    </div>
  )
}
