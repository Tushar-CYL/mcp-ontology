import { Link } from 'react-router-dom'
import { Link2, Plug } from 'lucide-react'
import { EmptyState } from './EmptyState'

interface NoSourceStateProps {
  title?: string
  description?: string
}

/** Shown by every layer screen until a source has been connected. */
export function NoSourceState({
  title = 'No data source selected',
  description = 'The four layers are built from a source. Connect one — a database file, a folder of CSVs, a single file or a database URL — and this screen fills with what was found.',
}: NoSourceStateProps) {
  return (
    <EmptyState
      icon={Link2}
      title={title}
      description={description}
      action={
        <Link to="/onboarding" className="btn btn--primary btn--md">
          <Plug size={15} aria-hidden="true" />
          Connect a source
        </Link>
      }
    />
  )
}
