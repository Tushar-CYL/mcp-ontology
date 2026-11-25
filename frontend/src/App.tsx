import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { SourceProvider } from './context/SourceProvider'
import { ToastProvider } from './context/ToastProvider'
import { AppShell } from './layout/AppShell'
import { Agents } from './pages/Agents'
import { AgentsHome } from './pages/agents/AgentsHome'
import { Login } from './pages/Login'
import { NotFound } from './pages/NotFound'
import { Onboarding } from './pages/Onboarding'
import { OntologyAccelerator } from './pages/ontology/OntologyAccelerator'
import { SimpleOntology } from './pages/ontology/SimpleOntology'
import { TermsPage } from './pages/ontology/TermsPage'
import { DataPage } from './pages/ontology/DataPage'
import { KnowledgeGraphTool } from './pages/graph/KnowledgeGraphTool'
import { ContextTool } from './pages/context/ContextTool'
import { SemanticTool } from './pages/semantic/SemanticTool'
import { UseAnywhere } from './pages/UseAnywhere'
import { GlobalChat } from './pages/chat/GlobalChat'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <SourceProvider>
          <AppErrorBoundary>
            <Routes>
              <Route path="login" element={<Login />} />
              <Route element={<AppShell />}>
                {/* The app opens on the Ontology tool. /home (the old overview page,
                    removed) still lands there for old bookmarks. */}
                <Route index element={<Navigate to="/tools/ontology" replace />} />
                <Route path="home" element={<Navigate to="/tools/ontology" replace />} />
                <Route path="terms" element={<TermsPage />} />
                <Route path="data" element={<DataPage />} />
                <Route path="tools/ontology" element={<SimpleOntology />} />
                <Route path="tools/ontology/:oid" element={<SimpleOntology />} />
                <Route path="tools/graph" element={<KnowledgeGraphTool />} />
                <Route path="tools/graph/:oid" element={<KnowledgeGraphTool />} />
                <Route path="tools/semantic" element={<SemanticTool />} />
                <Route path="tools/semantic/:oid" element={<SemanticTool />} />
                <Route path="tools/context" element={<ContextTool />} />
                <Route path="tools/context/:oid" element={<ContextTool />} />
                {/* The full governance journey (approvals, roles, maturity). */}
                <Route path="tools/ontology-advanced" element={<OntologyAccelerator />} />
                <Route path="tools/ontology-advanced/:oid" element={<OntologyAccelerator />} />
                <Route path="chat" element={<GlobalChat />} />
                <Route path="chat/:oid" element={<GlobalChat />} />
                <Route path="onboarding" element={<Onboarding />} />
                {/* The old "four layers" pages were replaced by the tools above;
                    their links still land on the matching tool. */}
                <Route path="layers" element={<Navigate to="/tools/ontology" replace />} />
                <Route path="layers/ontology" element={<Navigate to="/tools/ontology" replace />} />
                <Route path="layers/graph" element={<Navigate to="/tools/graph" replace />} />
                <Route path="layers/semantic" element={<Navigate to="/tools/semantic" replace />} />
                <Route path="layers/context" element={<Navigate to="/tools/context" replace />} />
                <Route path="agents" element={<AgentsHome />} />
                <Route path="agents/older" element={<Agents />} />
                <Route path="agents/:oid" element={<AgentsHome />} />
                <Route path="use" element={<UseAnywhere />} />
                <Route path="connections" element={<Navigate to="/agents" replace />} />
                <Route path="factory" element={<Navigate to="/tools/context" replace />} />
                <Route path="glossary" element={<Navigate to="/tools/semantic" replace />} />
                <Route path="certification" element={<Navigate to="/tools/ontology" replace />} />
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
