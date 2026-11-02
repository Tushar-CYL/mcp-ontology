import { createContext, useContext } from 'react'

export type ToastTone = 'info' | 'success' | 'error'

export interface ToastInput {
  title: string
  message?: string
  tone?: ToastTone
  durationMs?: number
}

export interface ToastRecord extends ToastInput {
  id: number
  tone: ToastTone
}

export interface ToastApi {
  push: (toast: ToastInput) => void
  dismiss: (id: number) => void
}

export const ToastContext = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const context = useContext(ToastContext)
  if (context === null) {
    throw new Error('useToast must be used inside <ToastProvider>')
  }
  return context
}
