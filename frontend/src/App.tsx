import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { SourceProvider } from './context/SourceProvider'
import { ToastProvider } from './context/ToastProvider'
import { AppShell } from './layout/AppShell'
import { Agents } from './pages/Agents'
import { LayersLayout } from './pages/LayersLayout'
import { NotFound } from './pages/NotFound'
import { Onboarding } from './pages/Onboarding'
import { ContextPanel } from './pages/layers/ContextPanel'
import { GraphPanel } from './pages/layers/GraphPanel'
import { OntologyPanel } from './pages/layers/OntologyPanel'
import { SemanticPanel } from './pages/layers/SemanticPanel'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <SourceProvider>
          <AppErrorBoundary>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<Navigate to="/onboarding" replace />} />
                <Route path="onboarding" element={<Onboarding />} />
                <Route path="layers" element={<LayersLayout />}>
                  <Route index element={<Navigate to="ontology" replace />} />
                  <Route path="ontology" element={<OntologyPanel />} />
                  <Route path="graph" element={<GraphPanel />} />
                  <Route path="semantic" element={<SemanticPanel />} />
                  <Route path="context" element={<ContextPanel />} />
                </Route>
                <Route path="agents" element={<Agents />} />
                <Route path="connections" element={<Navigate to="/agents" replace />} />
                <Route path="factory" element={<Navigate to="/layers/context" replace />} />
                <Route path="glossary" element={<Navigate to="/layers/semantic" replace />} />
                <Route path="certification" element={<Navigate to="/layers/ontology" replace />} />
                {/* Old links: the agent builder became agent connections. */}
                <Route path="studio" element={<Navigate to="/agents" replace />} />
                <Route path="agent/*" element={<Navigate to="/agents" replace />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </AppErrorBoundary>
        </SourceProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
