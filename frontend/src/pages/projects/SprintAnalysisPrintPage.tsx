import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { SprintAnalysisReportBody } from '@/pages/projects/sprintAnalysis/SprintAnalysisReportBody'
import { api, type SprintAnalysis } from '@/lib/api'
import '@/pages/projects/sprintAnalysis/sprint-analysis-print.css'

export function SprintAnalysisPrintPage() {
  const { reportId } = useParams()
  const [data, setData] = useState<SprintAnalysis | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!reportId) return
    api
      .getSprintAnalysis(Number(reportId))
      .then((payload) => {
        setData(payload)
        if (payload.status === 'success') {
          window.setTimeout(() => window.print(), 400)
        }
      })
      .catch((err: Error) => setError(err.message))
  }, [reportId])

  if (error) {
    return (
      <div className="p-8 text-sm text-red-900">
        <p>{error}</p>
      </div>
    )
  }

  if (!data) {
    return <div className="p-8 text-sm text-muted">Carregando relatório…</div>
  }

  if (data.status !== 'success' || !data.pack) {
    return (
      <div className="p-8 text-sm text-muted">
        {data.error_message || 'Relatório indisponível para impressão.'}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white px-6 py-8 print:p-0">
      <SprintAnalysisReportBody data={data} viewMode="detailed" printMode />
    </div>
  )
}
