import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { cx } from '../utils/cx'

type Layer = 'ontology' | 'graph' | 'semantic' | 'context'

const STEPS: Array<{ layer: Layer; label: string; hint: string }> = [
  { layer: 'ontology', label: 'What is it?', hint: 'Ontology' },
  { layer: 'graph', label: 'Connected to?', hint: 'Knowledge graph' },
  { layer: 'semantic', label: 'How we count', hint: 'Semantic' },
  { layer: 'context', label: 'Ask & why', hint: 'Context' },
]

/**
 * The same four-step bar on every layer page, so the four tools read as one
 * journey about the same data. Optionally shows the record being followed and
 * a trust line (plan step 1.3).
 */
export function LayerBar({
  active,
  oid,
  following,
  trust,
}: {
  active: Layer
  oid?: string
  /** The running example record, e.g. "Order 1984611". */
  following?: string
  /** A short trust line, e.g. "12 of 14 report checks match". */
  trust?: { text: string; low?: boolean }
}) {
  const href = (l: Layer) => (oid ? `/tools/${l}/${encodeURIComponent(oid)}` : `/tools/${l}`)
  return (
    <>
      <nav className="layerbar" aria-label="The four layers">
        <div className="layerbar__steps">
          {STEPS.map((s, i) => (
            <Link key={s.layer} to={href(s.layer)}
              className={cx('layerbar__step', s.layer === active && 'is-active')}
              aria-current={s.layer === active ? 'page' : undefined}>
              <span className="num">{i + 1}</span>
              <span>{s.label}</span>
            </Link>
          ))}
        </div>
        {trust ? (
          <span className="layerbar__trust">
            <b className={cx(trust.low && 'is-low')}>{trust.text}</b>
          </span>
        ) : null}
      </nav>
      {following ? (
        <p className="following">
          <Compass size={16} aria-hidden="true" />
          Following <b>{following}</b> across all four pages
        </p>
      ) : null}
    </>
  )
}
