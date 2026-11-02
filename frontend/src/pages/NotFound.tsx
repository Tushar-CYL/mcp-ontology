import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function NotFound() {
  useDocumentTitle('Page not found')
  return (
    <div className="page">
      <PageHeader title="Page not found" description="That route is not part of this workspace." />
      <EmptyState
        icon={Compass}
        title="Nothing is built at this address"
        description="Choose one of the four screens from the navigation to keep working."
        action={
          <Link to="/onboarding" className="btn btn--primary btn--md">
            Go to onboarding
          </Link>
        }
      />
    </div>
  )
}
