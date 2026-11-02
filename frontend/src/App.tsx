import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { SourceProvider } from './context/SourceProvider'
import { ToastProvider } from './context/ToastProvider'
import { AppShell } from './layout/AppShell'
import { AgentStudio } from './pages/AgentStudio'
import { Certification } from './pages/Certification'
import { LayersLayout } from './pages/LayersLayout'
import { NotFound } from './pages/NotFound'
import { Onboarding } from './pages/Onboarding'
import { PublishedAgent } from './pages/PublishedAgent'
import { Solutions } from './pages/Solutions'
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
                <Route path="certification" element={<Certification />} />
                <Route path="solutions" element={<Solutions />} />
                <Route path="studio" element={<AgentStudio />} />
                <Route path="agent" element={<PublishedAgent />} />
                <Route path="agent/:agentId" element={<PublishedAgent />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </AppErrorBoundary>
        </SourceProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
