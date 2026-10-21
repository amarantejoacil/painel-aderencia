import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { CalendarPage } from '@/pages/CalendarPage'
import { CollaboratorDetailPage } from '@/pages/CollaboratorDetailPage'
import { CollaboratorsPage } from '@/pages/CollaboratorsPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ImportPage } from '@/pages/ImportPage'
import { InconsistenciesReportPage } from '@/pages/InconsistenciesReportPage'
import { EvolutionPage } from '@/pages/projects/EvolutionPage'
import { OverviewPage } from '@/pages/projects/OverviewPage'
import { ReportsPage } from '@/pages/projects/ReportsPage'
import { SprintAnalysisPage } from '@/pages/projects/SprintAnalysisPage'
import { SprintAnalysisPrintPage } from '@/pages/projects/SprintAnalysisPrintPage'
import { SprintDetailPage } from '@/pages/projects/SprintDetailPage'
import { SprintsPage } from '@/pages/projects/SprintsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AuditHistoryPage } from '@/pages/audit/AuditHistoryPage'
import { IssueAuditValidationPage } from '@/pages/audit/IssueAuditValidationPage'
import { IssuesAuditPage } from '@/pages/audit/IssuesAuditPage'
import { BatchPage } from '@/pages/timeEntries/BatchPage'
import { HistoryPage } from '@/pages/timeEntries/HistoryPage'
import { MyEntriesPage } from '@/pages/timeEntries/MyEntriesPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="projetos/sprints/analise/:reportId/impressao" element={<SprintAnalysisPrintPage />} />
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="relatorio-inconsistencias" element={<InconsistenciesReportPage />} />
          <Route path="importacao" element={<ImportPage />} />
          <Route path="colaboradores" element={<CollaboratorsPage />} />
          <Route path="colaboradores/:id" element={<CollaboratorDetailPage />} />
          <Route path="calendario" element={<CalendarPage />} />
          <Route path="apontamentos" element={<MyEntriesPage />} />
          <Route path="apontamentos/lote" element={<BatchPage />} />
          <Route path="apontamentos/historico" element={<HistoryPage />} />
          <Route path="configuracoes" element={<SettingsPage />} />
          <Route path="auditoria/issues" element={<IssuesAuditPage />} />
          <Route path="auditoria/issues/:queryId" element={<IssuesAuditPage />} />
          <Route path="auditoria/issues/:queryId/validacao" element={<IssueAuditValidationPage />} />
          <Route path="auditoria/historico" element={<AuditHistoryPage />} />
          <Route path="projetos" element={<OverviewPage />} />
          <Route path="projetos/sprints" element={<SprintsPage />} />
          <Route path="projetos/sprints/analise/:reportId" element={<SprintAnalysisPage />} />
          <Route path="projetos/sprints/:sprintKey" element={<SprintDetailPage />} />
          <Route path="projetos/evolucao" element={<EvolutionPage />} />
          <Route path="projetos/relatorios" element={<ReportsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
