import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { CalendarPage } from '@/pages/CalendarPage'
import { CollaboratorDetailPage } from '@/pages/CollaboratorDetailPage'
import { CollaboratorsPage } from '@/pages/CollaboratorsPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ImportPage } from '@/pages/ImportPage'
import { InconsistenciesReportPage } from '@/pages/InconsistenciesReportPage'
import { SettingsPage } from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="relatorio-inconsistencias" element={<InconsistenciesReportPage />} />
          <Route path="importacao" element={<ImportPage />} />
          <Route path="colaboradores" element={<CollaboratorsPage />} />
          <Route path="colaboradores/:id" element={<CollaboratorDetailPage />} />
          <Route path="calendario" element={<CalendarPage />} />
          <Route path="configuracoes" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
