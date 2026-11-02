import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import {
  ToastContext,
  type ToastApi,
  type ToastInput,
  type ToastRecord,
} from '../context/ToastContext'
import { cx } from '../utils/cx'

const ICONS = {
  info: Info,
  success: CircleCheck,
  error: CircleAlert,
} as const

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Map<number, number>())

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
    const timer = timers.current.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const push = useCallback(
    (input: ToastInput) => {
      const id = nextId.current
      nextId.current += 1
      const toast: ToastRecord = {
        id,
        tone: input.tone ?? 'info',
        title: input.title,
        message: input.message,
        durationMs: input.durationMs,
      }
      // Keep at most four on screen; older ones fall off the top.
      setToasts((current) => [...current.slice(-3), toast])
      const duration = input.durationMs ?? (toast.tone === 'error' ? 8_000 : 4_500)
      timers.current.set(id, window.setTimeout(() => dismiss(id), duration))
    },
    [dismiss],
  )

  useEffect(() => {
    const activeTimers = timers.current
    return () => {
      activeTimers.forEach((timer) => window.clearTimeout(timer))
      activeTimers.clear()
    }
  }, [])

  const value = useMemo<ToastApi>(() => ({ push, dismiss }), [push, dismiss])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone]
          return (
            <div key={toast.id} className={cx('toast', `toast--${toast.tone}`)}>
              <Icon className="toast__icon" size={18} aria-hidden="true" />
              <div className="toast__body">
                <p className="toast__title">{toast.title}</p>
                {toast.message ? <p className="toast__message">{toast.message}</p> : null}
              </div>
              <button
                type="button"
                className="toast__close"
                onClick={() => dismiss(toast.id)}
                aria-label={`Dismiss: ${toast.title}`}
              >
                <X size={15} aria-hidden="true" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
