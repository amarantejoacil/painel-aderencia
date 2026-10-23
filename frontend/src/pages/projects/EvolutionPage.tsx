import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ProjectPeriodFilters } from '@/pages/projects/ProjectPeriodFilters'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import { SprintAnalysisReportBody } from '@/pages/projects/sprintAnalysis/SprintAnalysisReportBody'
import { SprintAnalysisProcessingState } from '@/pages/projects/sprintAnalysis/SprintAnalysisProcessingState'
import {
  api,
  type ExecutiveReport,
  type ProjectEvolution,
  type ProjectScope,
  type SprintAnalysis,
} from '@/lib/api'
import { buildBriefingPlainText, normalizeSprintAnalysisResult } from '@/lib/sprintAnalysisResult'
import { currentYearMonth, formatDate, formatDateTime, formatPercent } from '@/lib/format'

const STATUS_LABEL: Record<string, string> = {
  planned: 'Planejada',
  active: 'Em andamento',
  closed: 'Encerrada',
}

function StoryList({
  title,
  items,
  empty,
}: {
  title: string
  items: Array<{ work_item_id: number; title: string; azure_url: string; state_at_cut?: string | null; impediment?: string | null }>
  empty: string
}) {
  if (items.length === 0) {
    return (
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{title}</p>
        <p className="mt-1 text-sm text-muted">{empty}</p>
      </div>
    )
  }
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{title}</p>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item.work_item_id} className="text-sm">
            <a
              href={item.azure_url}
              target="_blank"
              rel="noreferrer"
              className="text-accent hover:underline"
            >
              #{item.work_item_id}
            </a>{' '}
            <span>{item.title}</span>
            {item.state_at_cut ? (
              <span className="text-muted"> · {item.state_at_cut}</span>
            ) : null}
            {item.impediment ? (
              <span className="block text-amber-800">{item.impediment}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function EvolutionPage() {
  const initial = currentYearMonth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [year, setYear] = useState(Number(searchParams.get('year')) || initial.year)
  const [month, setMonth] = useState(() => {
    const raw = searchParams.get('month')
    if (raw === '0') return 0
    return Number(raw) || initial.month
  })
  const [scopeKey, setScopeKey] = useState('')
  const [scopes, setScopes] = useState<ProjectScope[]>([])
  const [data, setData] = useState<ProjectEvolution | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [aiReport, setAiReport] = useState<ExecutiveReport | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [savedLoading, setSavedLoading] = useState(false)
  const [geminiReady, setGeminiReady] = useState<boolean | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [showAiResult, setShowAiResult] = useState(false)
  const [copied, setCopied] = useState(false)
  const lookupTicket = useRef(0)

  const activeScope = useMemo(
    () => scopes.find((item) => item.key === scopeKey && item.area_path),
    [scopes, scopeKey],
  )
  const canLoad = Boolean(activeScope)

  useEffect(() => {
    api
      .listProjectScopes()
      .then(setScopes)
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    api
      .getGeminiSettings()
      .then((settings) =>
        setGeminiReady(Boolean(settings.enabled && settings.api_key_configured && settings.model_id)),
      )
      .catch(() => setGeminiReady(false))
  }, [])

  useEffect(() => {
    if (!scopes.length || !scopeKey) return
    const valid = scopes.some((item) => item.key === scopeKey && item.area_path)
    if (!valid) setScopeKey('')
  }, [scopes, scopeKey])

  useEffect(() => {
    if (!canLoad || !activeScope) {
      setData(null)
      setExpanded(null)
      return
    }
    setSearchParams({ scope: scopeKey, year: String(year), month: String(month) })
    setLoading(true)
    setError(null)
    api
      .projectEvolution({ year, month, scope_key: scopeKey })
      .then((payload) => {
        setData(payload)
        setExpanded((prev) =>
          prev && payload.timeline.some((e) => e.sprint_key === prev) ? prev : null,
        )
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [year, month, scopeKey, canLoad, activeScope, setSearchParams])

  useEffect(() => {
    if (!canLoad) {
      setAiReport(null)
      setShowAiResult(false)
      setSavedLoading(false)
      return
    }
    let cancelled = false
    const ticket = ++lookupTicket.current
    setSavedLoading(true)
    setAiError(null)
    api
      .latestExecutiveReport({
        report_type: 'evolution',
        year,
        month,
        scope_key: scopeKey,
      })
      .then((payload) => {
        if (cancelled || ticket !== lookupTicket.current) return
        if (payload.report) {
          setAiReport(payload.report)
          setShowAiResult(true)
        } else {
          setAiReport(null)
          setShowAiResult(false)
        }
      })
      .catch((err: Error) => {
        if (!cancelled && ticket === lookupTicket.current) setAiError(err.message)
      })
      .finally(() => {
        if (!cancelled && ticket === lookupTicket.current) setSavedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [canLoad, year, month, scopeKey])

  const generateWithAi = useCallback(() => {
    if (!canLoad || !geminiReady) return
    lookupTicket.current += 1
    setAiLoading(true)
    setAiError(null)
    setShowAiResult(true)
    api
      .createExecutiveReport({
        report_type: 'evolution',
        year,
        month,
        scope_key: scopeKey,
      })
      .then(setAiReport)
      .catch((err: Error) => setAiError(err.message))
      .finally(() => setAiLoading(false))
  }, [canLoad, geminiReady, year, month, scopeKey])

  useEffect(() => {
    if (!aiReport || (aiReport.status !== 'pending' && aiReport.status !== 'running')) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      api
        .getExecutiveReport(aiReport.id)
        .then((payload) => {
          if (!cancelled) setAiReport(payload)
        })
        .catch((err: Error) => {
          if (!cancelled) setAiError(err.message)
        })
    }, 2500)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [aiReport])

  const aiBusy =
    aiLoading || aiReport?.status === 'pending' || aiReport?.status === 'running'
  const analysisView: SprintAnalysis | null =
    aiReport && aiReport.status === 'success' && aiReport.pack
      ? { ...aiReport, scope_key: aiReport.scope_key ?? '' }
      : null
  const referenceAt = aiReport?.pack?.analysis_at

  const copyAiSummary = async () => {
    if (!aiReport?.result || !aiReport.pack) return
    const normalized = normalizeSprintAnalysisResult(aiReport.result, aiReport.pack)
    if (!normalized) return
    const sprintNames = (aiReport.pack.sprints ?? []).map((sprint) => sprint.name)
    const text = buildBriefingPlainText(normalized, {
      scopeLabel: aiReport.scope_label,
      sprintNames,
      generatedAt: aiReport.generated_at ? formatDateTime(aiReport.generated_at) : null,
    })
    await navigator.clipboard.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <ProjectModuleShell
      title="Evolução dos Projetos"
      description="Linha do tempo das Sprints, entregas, avanços, desafios e pendências de cada projeto."
    >
      <ProjectPeriodFilters
        year={year}
        month={month}
        scopeKey={scopeKey}
        scopes={scopes}
        onYearChange={setYear}
        onMonthChange={setMonth}
        onScopeChange={setScopeKey}
        allowAllScopes={false}
        allowFullYear
        areaScopesOnly
        scopePlaceholder="Selecione o projeto e a área"
      />

      {geminiReady === false ? (
        <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p>
            Configure o Gemini em Administração (chave, modelo e IA ativada) para gerar o resumo automático
            da evolução.
          </p>
          <Link to="/configuracoes" className="mt-2 inline-block font-medium underline">
            Abrir Configurações
          </Link>
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          disabled={!canLoad || !geminiReady || aiBusy || loading || savedLoading}
          onClick={() => generateWithAi()}
        >
          {aiBusy
            ? 'Gerando com IA…'
            : savedLoading
              ? 'Consultando…'
              : aiReport
                ? 'Gerar resumo novamente'
                : 'Gerar resumo com IA'}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={!analysisView}
          onClick={() => void copyAiSummary()}
        >
          {copied ? 'Copiado' : 'Copiar resumo'}
        </Button>
        {canLoad && geminiReady ? (
          <p className="text-sm text-muted">
            Usa as Sprints do período filtrado e o mesmo modelo dos Relatórios Inteligentes.
          </p>
        ) : !canLoad ? (
          <p className="text-sm text-muted">Selecione projeto e área para habilitar o resumo com IA.</p>
        ) : null}
      </div>

      {aiError ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{aiError}</Card>
      ) : null}

      {showAiResult && aiBusy ? (
        <SprintAnalysisProcessingState
          status={aiReport?.status === 'pending' ? 'pending' : aiLoading && !aiReport ? 'loading' : 'running'}
        />
      ) : null}

      {showAiResult && aiReport?.status === 'error' ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">
          {aiReport.error_message || 'Não foi possível gerar o resumo com IA.'}
        </Card>
      ) : null}

      {showAiResult && analysisView ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            {analysisView.generated_at
              ? `Resumo salvo em ${formatDateTime(analysisView.generated_at)}.`
              : 'Resumo salvo.'}{' '}
            {analysisView.model ? `Modelo ${analysisView.model}. ` : ''}
            Fonte: Azure DevOps.
            {referenceAt ? ` Dados de referência em ${formatDateTime(referenceAt)}.` : ''}
          </p>
          <SprintAnalysisReportBody data={analysisView} viewMode="executive" />
        </div>
      ) : null}

      {error ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</Card>
      ) : null}

      {!canLoad ? (
        <Card className="p-4 text-sm text-muted">
          Escolha o <span className="font-medium text-ink">projeto e a área</span> nos filtros acima
          para consultar a evolução no Azure DevOps. A linha do tempo não carrega automaticamente.
        </Card>
      ) : loading ? (
        <p className="text-sm text-muted">Carregando linha do tempo do Azure DevOps…</p>
      ) : data ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            Escopo: <span className="font-medium text-foreground">{data.scope_label}</span>
            {data.timeline.length > 0
              ? ` · ${data.timeline.length} Sprint(s) no período`
              : ' · nenhuma Sprint com histórias no período'}
          </p>

          {data.timeline.length === 0 ? (
            <Card className="p-4 text-sm text-muted">
              Nenhuma Sprint com histórias neste período para o projeto/área selecionado. Tente «Ano
              inteiro» ou confira se a área está correta (ex.: «NiaHub - PAN» ≠ «PAN»).
            </Card>
          ) : (
            <ol className="relative space-y-6 border-l border-line pl-6">
              {data.timeline.map((entry) => {
                const open = expanded === entry.sprint_key
                return (
                  <li key={entry.sprint_key} className="relative">
                    <span className="absolute -left-[1.65rem] top-1.5 h-3 w-3 rounded-full border-2 border-accent bg-card" />
                    <Card className="p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h3 className="text-lg font-semibold">{entry.name}</h3>
                          <p className="text-sm text-muted">
                            {formatDate(entry.start_date)} — {formatDate(entry.finish_date)} ·{' '}
                            {STATUS_LABEL[entry.status] ?? entry.status}
                          </p>
                          <p className="mt-1 text-sm">
                            {entry.metrics.stories_completed_in_sprint} concluída(s),{' '}
                            {entry.metrics.stories_pending} pendente(s),{' '}
                            {entry.metrics.stories_in_progress} em andamento
                            {entry.metrics.completion_percent != null
                              ? ` · ${formatPercent(entry.metrics.completion_percent)} de conclusão`
                              : null}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              setExpanded(open ? null : entry.sprint_key)
                            }
                          >
                            {open ? 'Recolher' : 'Detalhes'}
                          </Button>
                          <Link
                            to={`/projetos/sprints/${encodeURIComponent(entry.sprint_key)}?scope=${encodeURIComponent(scopeKey)}`}
                            className="inline-flex h-8 items-center justify-center rounded-md border border-line bg-white px-3 text-sm font-medium text-ink hover:bg-paper"
                          >
                            Abrir Sprint
                          </Link>
                        </div>
                      </div>

                      {open ? (
                        <div className="mt-4 grid gap-6 border-t border-line pt-4 md:grid-cols-3">
                          <StoryList
                            title="Entregas (concluídas na Sprint)"
                            items={entry.completed_stories}
                            empty="Nenhuma história concluída nesta Sprint."
                          />
                          <StoryList
                            title="Pendências (no corte da Sprint)"
                            items={entry.pending_stories}
                            empty="Nenhuma pendência registrada no corte."
                          />
                          <StoryList
                            title="Impedimentos"
                            items={entry.impediments}
                            empty="Nenhum impedimento identificado nas histórias."
                          />
                        </div>
                      ) : null}
                    </Card>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      ) : null}

      {data?.limitations.length ? (
        <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p className="font-medium">Limitações</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {data.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
      ) : null}
    </ProjectModuleShell>
  )
}
