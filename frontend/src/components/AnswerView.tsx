import { useMemo } from 'react'
import { AlignLeft, Lightbulb, Search, TrendingUp, type LucideIcon } from 'lucide-react'
import { parseAnswer, type SectionKey } from '../utils/answer'
import { cx } from '../utils/cx'

const SECTION_CONFIG: Record<SectionKey, { icon: LucideIcon; className: string }> = {
  summary: { icon: AlignLeft, className: 'answer__section--summary' },
  cause: { icon: Search, className: 'answer__section--cause' },
  impact: { icon: TrendingUp, className: 'answer__section--impact' },
  recommendation: { icon: Lightbulb, className: 'answer__section--recommendation' },
}

interface AnswerViewProps {
  answer: unknown
  dense?: boolean
  className?: string
}

/**
 * Renders the agent answer. Named sections (Cause / Impact / Recommendation)
 * get their own block when the backend sends them; otherwise the prose is
 * shown exactly as it arrived, never reformatted into fake structure.
 */
export function AnswerView({ answer, dense = false, className }: AnswerViewProps) {
  const parsed = useMemo(() => parseAnswer(answer), [answer])

  if (!parsed.prose && parsed.sections.length === 0) {
    return <p className="answer__empty">No answer text was returned.</p>
  }

  return (
    <div className={cx('answer', dense && 'answer--dense', className)}>
      {parsed.prose ? <p className="answer__prose">{parsed.prose}</p> : null}
      {parsed.sections.map((section) => {
        const config = SECTION_CONFIG[section.key]
        const Icon = config.icon
        return (
          <section
            key={section.key}
            className={cx('answer__section', config.className)}
            aria-label={section.title}
          >
            <h3 className="answer__section-title">
              <Icon size={15} aria-hidden="true" />
              {section.title}
            </h3>
            <p className="answer__section-body">{section.body}</p>
          </section>
        )
      })}
    </div>
  )
}
