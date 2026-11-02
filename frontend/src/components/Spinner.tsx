import { cx } from '../utils/cx'

interface SpinnerProps {
  size?: number
  label?: string
  className?: string
}

/** A busy indicator that is also a status region for screen readers. */
export function Spinner({ size = 18, label = 'Loading', className }: SpinnerProps) {
  return (
    <span
      className={cx('spinner', className)}
      role="status"
      aria-label={label}
      style={{ width: size, height: size }}
    >
      <span className="spinner__ring" aria-hidden="true" />
    </span>
  )
}
