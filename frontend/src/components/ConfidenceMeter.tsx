import { confidencePercent } from '../utils/format'

interface ConfidenceMeterProps {
  value: unknown
  label?: string
  showValue?: boolean
  compact?: boolean
}

export function ConfidenceMeter({
  value,
  label = 'Confidence',
  showValue = true,
  compact = false,
}: ConfidenceMeterProps) {
  const percent = confidencePercent(value)
  return (
    <div className={compact ? 'confidence-meter confidence-meter--compact' : 'confidence-meter'}>
      <div
        className="confidence-meter__track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent ?? 0}
        aria-valuetext={percent === null ? 'unknown' : `${percent}%`}
      >
        <span
          className="confidence-meter__fill"
          style={{ width: `${percent ?? 0}%` }}
          aria-hidden="true"
        />
      </div>
      {showValue ? (
        <span className="confidence-meter__value">{percent === null ? '—' : `${percent}%`}</span>
      ) : null}
    </div>
  )
}
