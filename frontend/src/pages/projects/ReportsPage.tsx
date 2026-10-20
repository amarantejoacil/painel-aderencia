import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { ProjectPeriodFilters } from '@/pages/projects/ProjectPeriodFilters'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import { SprintAnalysisReportBody } from '@/pages/projects/sprintAnalysis/SprintAnalysisReportBody'
import { SprintAnalysisProcessingState } from '@/pages/projects/sprintAnalysis/SprintAnalysisProcessingState'
import {
  api,
  type ExecutiveReport,
  type ProjectReport,
  type ProjectReportType,
  type ProjectScope,
  type SprintAnalysis,
  type SprintRef,
} from '@/lib/api'
import { buildBriefingPlainText, normalizeSprintAnalysisResult } from '@/lib/sprintAnalysisResult'
import { currentYearMonth, formatDate, formatDateTime } from '@/lib/format'

const REPORT_TYPES: Array<{ id: ProjectReportType; label: string; hint: string }> = [
  {
    id: 'monthly',
    label: 'Visão do mês',
    hint: 'Indicadores do período para o projeto e a área selecionados.',
  },
  {
    id: 'sprints',
    label: 'Sprints',
    hint: 'Escolha uma ou mais Sprints do período para o relatório.',
  },
  {
    id: 'evolution',
    label: 'Evolução',
    hint: 'Linha do tempo de entregas e pendências (permite ano inteiro).',
  },
  {
    id: 'consolidated',
    label: 'Consolidado',
    hint: 'Todos os projetos Azure acompanhados, sem filtro de área.',
  },
]

const SPRINT_STATUS: Record<string, string> = {
  planned: 'Planejada',
  active: 'Em andamento',
  closed: 'Encerrada',
}

export function ReportsPage() {
  const initial = currentYearMonth()
  const [, setSearchParams] = useSearchParams()
  const [reportType, setReportType] = useState<ProjectReportType>('monthly')
  const [year, setYear] = useState(initial.year)
  const [month, setMonth] = useState(initial.month)
  const [scopeKey, setScopeKey] = useState('')
  const [scopes, setScopes] = useState<ProjectScope[]>([])
  const [data, setData] = useState<ProjectReport | null>(null)
  const [aiReport, setAiReport] = useState<ExecutiveReport | null>(null)
  const [resultMode, setResultMode] = useState<'indicators' | 'ai' | null>(null)
  const [loading, setLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [savedLoading, setSavedLoading] = useState(false)
  const [geminiReady, setGeminiReady] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [sprintOptions, setSprintOptions] = useState<SprintRef[]>([])
  const [sprintsLoading, setSprintsLoading] = useState(false)
  const [selectedSprintKeys, setSelectedSprintKeys] = useState<string[]>([])
  const [sprintListKey, setSprintListKey] = useState('')
  const lookupTicket = useRef(0)

  const consolidated = reportType === 'consolidated'
  const sprintMode = reportType === 'sprints'
  const allowFullYear = reportType === 'evolution'
  const sprintSelectionKey = selectedSprintKeys.slice().sort().join('\n')

  const activeScope = useMemo(
    () => scopes.find((item) => item.key === scopeKey && item.area_path),
    [scopes, scopeKey],
  )
  const canLoadScope = Boolean(activeScope)
  const canGenerate = consolidated || canLoadScope
  const sprintQueryKey = sprintMode && canLoadScope && month >= 1 ? `${year}|${month}|${scopeKey}` : ''

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
    if (consolidated) {
      setScopeKey('')
      return
    }
    if (!scopes.length || !scopeKey) return
    const valid = scopes.some((item) => item.key === scopeKey && item.area_path)
    if (!valid) setScopeKey('')
  }, [scopes, scopeKey, consolidated])

  useEffect(() => {
    if (!allowFullYear && month === 0) setMonth(initial.month)
  }, [reportType, allowFullYear, month, initial.month])

  useEffect(() => {
    if (!sprintMode || !canLoadScope || month < 1) {
      setSprintOptions([])
      setSelectedSprintKeys([])
      setSprintListKey('')
      return
    }
    let cancelled = false
    setSprintsLoading(true)
    setSprintOptions([])
    api
      .listSprintRefs({ year, month, scope_key: scopeKey })
      .then((rows) => {
        if (cancelled) return
        setSprintOptions(rows)
        setSelectedSprintKeys((current) =>
          current.filter((key) => rows.some((row) => row.sprint_key === key)),
        )
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setSprintOptions([])
          setSelectedSprintKeys([])
          setError(err.message)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSprintsLoading(false)
          setSprintListKey(sprintQueryKey)
        }
      })
    return () => {
      cancelled = true
    }
  }, [sprintMode, canLoadScope, year, month, scopeKey, sprintQueryKey])

  useEffect(() => {
    setData(null)
    setError(null)
    const selectedKeys = sprintSelectionKey ? sprintSelectionKey.split('\n') : []
    if (!canGenerate || (!allowFullYear && month < 1) || (sprintMode && selectedKeys.length === 0)) {
      setAiReport(null)
      setResultMode(null)
      setSavedLoading(false)
      return
    }
    let cancelled = false
    const ticket = ++lookupTicket.current
    setSavedLoading(true)
    api
      .latestExecutiveReport({
        report_type: reportType,
        year,
        month,
        scope_key: consolidated ? undefined : scopeKey,
        sprint_keys: sprintMode ? selectedKeys : undefined,
      })
      .then((payload) => {
        if (cancelled || ticket !== lookupTicket.current) return
        if (payload.report) {
          setAiReport(payload.report)
          setResultMode('ai')
        } else {
          setAiReport(null)
          setResultMode(null)
        }
      })
      .catch((err: Error) => {
        if (!cancelled && ticket === lookupTicket.current) setError(err.message)
      })
      .finally(() => {
        if (!cancelled && ticket === lookupTicket.current) setSavedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [allowFullYear, canGenerate, consolidated, month, reportType, scopeKey, sprintMode, sprintSelectionKey, year])

  const runReport = useCallback(() => {
    if (!canGenerate) return
    if (!allowFullYear && month < 1) return

    const params: Record<string, string> = {
      tipo: reportType,
      year: String(year),
      month: String(month),
    }
    if (!consolidated && scopeKey) params.scope = scopeKey
    setSearchParams(params)

    lookupTicket.current += 1
    setLoading(true)
    setError(null)
    setResultMode('indicators')
    setAiReport(null)
    api
      .projectReport({
        report_type: reportType,
        year,
        month,
        scope_key: consolidated ? undefined : scopeKey,
      })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [
    allowFullYear,
    canGenerate,
    consolidated,
    month,
    reportType,
    scopeKey,
    setSearchParams,
    year,
  ])

  const generateWithAi = useCallback(() => {
    if (!canGenerate || !geminiReady) return
    if (!allowFullYear && month < 1) return
    if (sprintMode && selectedSprintKeys.length === 0) return
    lookupTicket.current += 1
    setAiLoading(true)
    setError(null)
    setResultMode('ai')
    setData(null)
    api
      .createExecutiveReport({
        report_type: reportType,
        year,
        month,
        scope_key: consolidated ? undefined : scopeKey,
        sprint_keys: sprintMode ? selectedSprintKeys : undefined,
      })
      .then(setAiReport)
      .catch((err: Error) => setError(err.message))
      .finally(() => setAiLoading(false))
  }, [
    allowFullYear,
    canGenerate,
    consolidated,
    geminiReady,
    month,
    reportType,
    scopeKey,
    selectedSprintKeys,
    sprintMode,
    year,
  ])

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
          if (!cancelled) setError(err.message)
        })
    }, 2500)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [aiReport])

  const exportUrl = useMemo(() => {
    const query = new URLSearchParams({
      report_type: reportType,
      year: String(year),
      month: String(month),
    })
    if (!consolidated && scopeKey) query.set('scope_key', scopeKey)
    return `/api/projects/reports/export?${query}`
  }, [reportType, year, month, scopeKey, consolidated])

  const copyText = async () => {
    if (resultMode === 'ai' && aiReport?.result && aiReport.pack) {
      const normalized = normalizeSprintAnalysisResult(aiReport.result, aiReport.pack)
      if (!normalized) return
      const sprintNames = (aiReport.pack.sprints ?? []).map((sprint) => sprint.name)
      const text = buildBriefingPlainText(normalized, {
        scopeLabel: aiReport.scope_label,
        sprintNames,
        generatedAt: aiReport.generated_at ? formatDateTime(aiReport.generated_at) : null,
      })
      await navigator.clipboard.writeText(text)
    } else if (data?.full_text) {
      await navigator.clipboard.writeText(data.full_text)
    } else {
      return
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const typeHint = REPORT_TYPES.find((item) => item.id === reportType)?.hint
  const aiBusy =
    aiLoading || aiReport?.status === 'pending' || aiReport?.status === 'running'
  const analysisView: SprintAnalysis | null =
    aiReport && aiReport.status === 'success' && aiReport.pack
      ? { ...aiReport, scope_key: aiReport.scope_key ?? '' }
      : null
  const referenceAt = aiReport?.pack?.analysis_at

  return (
    <ProjectModuleShell
      title="Relatórios Inteligentes"
      description="Relatórios executivos elaborados com os registros do Azure DevOps e o modelo Gemini configurado."
    >
      <Card className="grid gap-4 p-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <Label htmlFor="report-type">Tipo de relatório</Label>
          <select
            id="report-type"
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm md:max-w-md"
            value={reportType}
            onChange={(event) => setReportType(event.target.value as ProjectReportType)}
          >
            {REPORT_TYPES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          {typeHint ? <p className="mt-2 text-sm text-muted">{typeHint}</p> : null}
        </div>
      </Card>

      <ProjectPeriodFilters
        year={year}
        month={month}
        scopeKey={scopeKey}
        scopes={scopes}
        onYearChange={setYear}
        onMonthChange={setMonth}
        onScopeChange={setScopeKey}
        allowAllScopes={false}
        allowFullYear={allowFullYear}
        hideScope={consolidated}
        areaScopesOnly={!consolidated}
        scopePlaceholder="Selecione o projeto e a área"
      />

      {consolidated ? (
        <p className="text-sm text-muted">
          O relatório consolidado ignora o filtro de área e agrega os times configurados no Azure.
        </p>
      ) : null}

      {sprintMode ? (
        <Card className="p-4">
          <p className="text-sm font-medium text-ink">Sprints do período</p>
          <p className="mt-1 text-sm text-muted">
            Marque uma ou mais. O relatório e a versão salva valem para essa seleção.
          </p>
          {sprintsLoading || (sprintQueryKey && sprintListKey !== sprintQueryKey) ? (
            <p className="mt-3 text-sm text-muted">Carregando Sprints…</p>
          ) : null}
          {!sprintsLoading && sprintListKey === sprintQueryKey && sprintQueryKey && sprintOptions.length === 0 ? (
            <p className="mt-3 text-sm text-muted">Nenhuma Sprint com datas neste período.</p>
          ) : null}
          {!canLoadScope ? (
            <p className="mt-3 text-sm text-muted">Selecione o projeto e a área para listar as Sprints.</p>
          ) : null}
          <ul className="mt-3 grid gap-2">
            {sprintOptions.map((sprint) => {
              const checked = selectedSprintKeys.includes(sprint.sprint_key)
              return (
                <li key={sprint.sprint_key}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-md border border-line bg-white px-3 py-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={checked}
                      onChange={() => {
                        setSelectedSprintKeys((current) =>
                          current.includes(sprint.sprint_key)
                            ? current.filter((key) => key !== sprint.sprint_key)
                            : [...current, sprint.sprint_key],
                        )
                      }}
                    />
                    <span>
                      <span className="font-medium">{sprint.name}</span>
                      <span className="mt-0.5 block text-muted">
                        {formatDate(sprint.start_date)} – {formatDate(sprint.finish_date)}
                        {' · '}
                        {SPRINT_STATUS[sprint.status] ?? sprint.status}
                      </span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        </Card>
      ) : null}

      {geminiReady === false ? (
        <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p>A inteligência artificial não está configurada. O relatório executivo usa o modelo definido em Administração.</p>
          <Link to="/configuracoes" className="mt-2 inline-block font-medium underline">
            Abrir Configurações
          </Link>
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          disabled={
            !canGenerate ||
            !geminiReady ||
            aiBusy ||
            loading ||
            savedLoading ||
            (sprintMode && selectedSprintKeys.length === 0)
          }
          onClick={() => generateWithAi()}
        >
          {aiBusy ? 'Gerando com IA…' : savedLoading ? 'Consultando…' : aiReport ? 'Gerar novamente' : 'Gerar relatório com IA'}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={!canGenerate || loading || aiBusy}
          onClick={() => runReport()}
        >
          {loading ? 'Gerando…' : 'Gerar somente indicadores'}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={resultMode === 'ai' ? !analysisView : !data}
          onClick={() => void copyText()}
        >
          {copied ? 'Copiado' : resultMode === 'ai' ? 'Copiar resumo' : 'Copiar texto'}
        </Button>
        <a
          href={resultMode === 'indicators' && data ? exportUrl : undefined}
          aria-disabled={resultMode !== 'indicators' || !data}
          className="inline-flex h-10 items-center justify-center rounded-md border border-line bg-white px-4 text-sm font-medium text-ink hover:bg-paper disabled:pointer-events-none disabled:opacity-50"
          onClick={(event) => {
            if (resultMode !== 'indicators' || !data) event.preventDefault()
          }}
        >
          Baixar .txt
        </a>
      </div>

      {error ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</Card>
      ) : null}

      {!canGenerate && !consolidated ? (
        <Card className="p-4 text-sm text-muted">
          Escolha o <span className="font-medium text-ink">projeto e a área</span> e clique em{' '}
          <span className="font-medium text-ink">Gerar relatório com IA</span>. Nada é consultado no Azure
          DevOps até você confirmar.
        </Card>
      ) : null}

      {consolidated && resultMode === null && !loading && !aiBusy ? (
        <Card className="p-4 text-sm text-muted">
          Ajuste o período se necessário e clique em{' '}
          <span className="font-medium text-ink">Gerar relatório com IA</span> para elaborar a visão consolidada.
        </Card>
      ) : null}

      {resultMode === 'ai' && aiBusy ? (
        <SprintAnalysisProcessingState status={aiReport?.status === 'pending' ? 'pending' : aiLoading && !aiReport ? 'loading' : 'running'} />
      ) : null}

      {resultMode === 'ai' && aiReport?.status === 'error' ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">
          {aiReport.error_message || 'Não foi possível gerar o relatório com IA.'}
        </Card>
      ) : null}

      {resultMode === 'ai' && analysisView ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            {analysisView.generated_at
              ? `Relatório salvo em ${formatDateTime(analysisView.generated_at)}.`
              : 'Relatório salvo.'}{' '}
            {analysisView.model ? `Modelo ${analysisView.model}. ` : ''}
            Fonte: Azure DevOps.
            {referenceAt ? ` Dados de referência em ${formatDateTime(referenceAt)}.` : ''}{' '}
            Gerar novamente cria outra versão e mantém esta.
          </p>
          <SprintAnalysisReportBody data={analysisView} viewMode="executive" />
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted">Calculando indicadores a partir do Azure DevOps…</p>
      ) : resultMode === 'indicators' && data ? (
        <Card className="space-y-6 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">Somente indicadores, sem IA</p>
            <h3 className="mt-1 text-xl font-semibold">{data.title}</h3>
            <p className="mt-1 text-sm text-muted">
              {data.scope_label} · Gerado em {formatDateTime(data.generated_at)} · Fonte:{' '}
              {data.data_source === 'azure_devops' ? 'Azure DevOps' : data.data_source}
            </p>
          </div>

          {data.sections.map((section) => (
            <section key={section.heading}>
              <h4 className="font-semibold">{section.heading}</h4>
              {section.body ? <p className="mt-2 text-sm leading-relaxed">{section.body}</p> : null}
              {section.bullets.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {section.bullets.map((bullet, index) => (
                    <li key={`${section.heading}-${index}`}>{bullet}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}

          <details className="text-sm">
            <summary className="cursor-pointer font-medium text-muted">Ver texto completo</summary>
            <pre className="mt-3 whitespace-pre-wrap rounded-md border border-line bg-paper p-4 text-xs">
              {data.full_text}
            </pre>
          </details>
        </Card>
      ) : null}

      {resultMode === 'indicators' && data?.limitations.length ? (
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
