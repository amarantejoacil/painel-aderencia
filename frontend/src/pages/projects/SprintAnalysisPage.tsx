import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import {
  SprintAnalysisReportBody,
  type ViewMode,
} from '@/pages/projects/sprintAnalysis/SprintAnalysisReportBody'
import { api, type SprintAnalysis } from '@/lib/api'
import { buildBriefingPlainText, normalizeSprintAnalysisResult } from '@/lib/sprintAnalysisResult'
import { formatDateTime } from '@/lib/format'
import { SprintAnalysisProcessingState } from '@/pages/projects/sprintAnalysis/SprintAnalysisProcessingState'

export function SprintAnalysisPage() {
  const { reportId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState<SprintAnalysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('executive')
  const [copied, setCopied] = useState(false)
  const [restarting, setRestarting] = useState(false)

  useEffect(() => {
    if (!reportId) return
    let timer: number | undefined
    let cancelled = false

    const load = () => {
      api
        .getSprintAnalysis(Number(reportId))
        .then((payload) => {
          if (cancelled) return
          setData(payload)
          setError(null)
          if (payload.status === 'pending' || payload.status === 'running') {
            timer = window.setTimeout(load, 2500)
          }
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message)
        })
    }
    load()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [reportId])

  const normalized = useMemo(
    () => normalizeSprintAnalysisResult(data?.result ?? null, data?.pack ?? null),
    [data?.result, data?.pack],
  )

  const copySummary = async () => {
    if (!normalized || !data) return
    const sprintNames = (data.pack?.sprints ?? []).map((s) => s.name)
    const text = buildBriefingPlainText(normalized, {
      scopeLabel: data.scope_label,
      sprintNames,
      generatedAt: data.generated_at ? formatDateTime(data.generated_at) : null,
    })
    await navigator.clipboard.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const regenerate = async () => {
    if (!data) return
    setRestarting(true)
    try {
      const created = await api.createSprintAnalysis({
        scope_key: data.scope_key,
        year: data.year,
        month: data.month,
        sprint_keys: data.sprint_keys,
      })
      navigate(`/projetos/sprints/analise/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível gerar novamente.')
    } finally {
      setRestarting(false)
    }
  }

  const exportPdf = () => {
    if (!reportId) return
    window.open(`/projetos/sprints/analise/${reportId}/impressao`, '_blank', 'noopener')
  }

  const isProcessing =
    !data && !error ? true : data?.status === 'pending' || data?.status === 'running'
  const processingStatus =
    !data && !error ? 'loading' : data?.status === 'pending' ? 'pending' : 'running'

  return (
    <ProjectModuleShell
      title="Análise Inteligente de Sprints"
      description="Relatório executivo gerado com os registros do Azure DevOps e interpretação do modelo configurado."
    >
      <div className="flex flex-col gap-4 print:hidden lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          <Link
            to="/projetos/sprints"
            className="inline-flex h-10 items-center rounded-md border border-line bg-white px-4 text-sm font-medium"
          >
            Voltar para Sprints
          </Link>
          <Button type="button" variant="secondary" disabled={!data || restarting} onClick={() => void regenerate()}>
            {restarting ? 'Gerando…' : 'Gerar novamente'}
          </Button>
          <Button type="button" variant="secondary" disabled={!normalized} onClick={() => void copySummary()}>
            {copied ? 'Copiado' : 'Copiar resumo'}
          </Button>
          <Button type="button" variant="secondary" disabled={data?.status !== 'success'} onClick={exportPdf}>
            Exportar PDF
          </Button>
        </div>
        {data?.status === 'success' ? (
          <div
            className="inline-flex rounded-lg border border-line bg-slate-50 p-1 text-sm"
            role="tablist"
            aria-label="Modo de visualização"
          >
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === 'executive'}
              className={`rounded-md px-3 py-1.5 font-medium transition ${
                viewMode === 'executive' ? 'bg-white text-foreground shadow-sm' : 'text-muted hover:text-foreground'
              }`}
              onClick={() => setViewMode('executive')}
            >
              Visão Executiva
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === 'detailed'}
              className={`rounded-md px-3 py-1.5 font-medium transition ${
                viewMode === 'detailed' ? 'bg-white text-foreground shadow-sm' : 'text-muted hover:text-foreground'
              }`}
              onClick={() => setViewMode('detailed')}
            >
              Visão Detalhada
            </button>
          </div>
        ) : null}
      </div>

      {error ? <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</Card> : null}

      {isProcessing ? (
        <SprintAnalysisProcessingState
          status={processingStatus === 'loading' ? 'loading' : processingStatus}
        />
      ) : null}

      {data?.status === 'error' ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">
          {data.error_message || 'Não foi possível concluir a análise.'}
        </Card>
      ) : null}

      {data?.status === 'success' && data.generated_at ? (
        <Card className="border-accent/25 bg-accent-soft/30 p-4 text-sm print:hidden">
          <p className="font-medium">Relatório salvo no painel</p>
          <p className="mt-1 text-muted">
            Esta análise foi gerada e permanece disponível para consulta. Última atualização em{' '}
            <span className="font-medium text-foreground">{formatDateTime(data.generated_at)}</span>. Use{' '}
            <span className="font-medium text-foreground">Gerar novamente</span> somente se quiser refazer com
            dados atuais do Azure DevOps.
          </p>
        </Card>
      ) : null}

      {data?.status === 'success' && data.pack ? (
        <SprintAnalysisReportBody data={data} viewMode={viewMode} />
      ) : null}
    </ProjectModuleShell>
  )
}
