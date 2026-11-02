import { Component, type ErrorInfo, type ReactNode } from 'react'
import { ErrorState } from './ErrorState'

interface AppErrorBoundaryProps {
  children: ReactNode
}

interface AppErrorBoundaryState {
  error: unknown
}

/** Last line of defence: a render failure shows a real message, not a blank page. */
export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  override state: AppErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: unknown): AppErrorBoundaryState {
    return { error }
  }

  override componentDidCatch(error: unknown, info: ErrorInfo): void {
    // Keep the console detail for a developer; the page stays calm.
    console.error('Unhandled render error', error, info.componentStack)
  }

  override render(): ReactNode {
    if (this.state.error !== null) {
      return (
        <div className="boundary">
          <ErrorState
            error={this.state.error}
            title="This screen could not render"
            onRetry={() => window.location.reload()}
          />
        </div>
      )
    }
    return this.props.children
  }
}
