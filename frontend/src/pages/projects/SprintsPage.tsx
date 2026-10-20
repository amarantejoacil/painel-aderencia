import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { ProjectPeriodFilters } from '@/pages/projects/ProjectPeriodFilters'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import { api, type ProjectScope, type ProjectSprints } from '@/lib/api'
import { currentYearMonth, formatDate, formatDateTime, formatPercent } from '@/lib/format'

type SavedSprintAnalysis = {
  reportId: number
  status: string
  generatedAt: string | null
}

const STATUS_LABEL: Record<string, string> = {
  planned: 'Planejada',
  active: 'Em andamento',
  closed: 'Encerrada',
}

function readFiltersFromSearch(params: URLSearchParams, initial: { year: number; month: number }) {
  const scope = params.get('scope')?.trim() || ''
  const yearRaw = params.get('year')
  const monthRaw = params.get('month')
  return {
    scopeKey: scope,
    year: yearRaw ? Number(yearRaw) : initial.year,
    month: monthRaw ? Number(monthRaw) : initial.month,
  }
}

export function SprintsPage() {
  const initial = currentYearMonth()
  const [searchParams, setSearchParams] = useSearchParams()
  const fromUrl = readFiltersFromSearch(searchParams, initial)
  const [year, setYear] = useState(fromUrl.year)
  const [month, setMonth] = useState(fromUrl.month)
  const [scopeKey, setScopeKey] = useState(fromUrl.scopeKey)
  const [scopes, setScopes] = useState<ProjectScope[]>([])
  const [data, setData] = useState<ProjectSprints | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [savedAnalysis, setSavedAnalysis] = useState<SavedSprintAnalysis | null>(null)
  const [starting, setStarting] = useState(false)
  const navigate = useNavigate()

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
    const next = readFiltersFromSearch(searchParams, initial)
    if (next.scopeKey) {
      setScopeKey(next.scopeKey)
      setYear(next.year)
      setMonth(next.month)
    }
  }, [searchParams])

  useEffect(() => {
    if (!scopes.length || !scopeKey) return
    const valid = scopes.some((item) => item.key === scopeKey && item.area_path)
    if (!valid) setScopeKey('')
  }, [scopes, scopeKey])

  useEffect(() => {
    if (!canLoad || !activeScope) {
      setData(null)
      setSelected([])
      return
    }
    setSearchParams({ scope: scopeKey, year: String(year), month: String(month) })
    setLoading(true)
    setError(null)
    api
      .projectSprints({ year, month, scope_key: scopeKey })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [year, month, scopeKey, canLoad, activeScope, setSearchParams])

  const rows = useMemo(() => data?.rows ?? [], [data])
  const visibleKeys = useMemo(() => rows.map((row) => row.sprint_key), [rows])
  const allVisibleSelected = visibleKeys.length > 0 && visibleKeys.every((key) => selected.includes(key))

  useEffect(() => {
    setSelected((current) => current.filter((key) => visibleKeys.includes(key)))
  }, [visibleKeys])

  useEffect(() => {
    if (!scopeKey || selected.length === 0) {
      setSavedAnalysis(null)
      return
    }
    let cancelled = false
    api
      .latestSprintAnalysis({ scope_key: scopeKey, sprint_keys: selected })
      .then((latest) => {
        if (cancelled) return
        if (latest.report_id == null) {
          setSavedAnalysis(null)
          return
        }
        setSavedAnalysis({
          reportId: latest.report_id,
          status: latest.status ?? 'unknown',
          generatedAt: latest.generated_at,
        })
      })
      .catch(() => {
        if (!cancelled) setSavedAnalysis(null)
      })
    return () => {
      cancelled = true
    }
  }, [scopeKey, selected])

  const toggle = (key: string) => {
    setSelected((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    )
  }

  const openSavedAnalysis = () => {
    if (!savedAnalysis) return
    navigate(`/projetos/sprints/analise/${savedAnalysis.reportId}`)
  }

  const createNewAnalysis = async () => {
    if (!scopeKey || selected.length === 0) return
    setStarting(true)
    setError(null)
    try {
      const created = await api.createSprintAnalysis({
        scope_key: scopeKey,
        year,
        month,
        sprint_keys: selected,
      })
      navigate(`/projetos/sprints/analise/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível iniciar a análise.')
    } finally {
      setStarting(false)
    }
  }

  const hasSavedSuccess = savedAnalysis?.status === 'success' && savedAnalysis.generatedAt
  const hasInProgress =
    savedAnalysis != null &&
    (savedAnalysis.status === 'pending' || savedAnalysis.status === 'running')

  return (
    <ProjectModuleShell
      title="Sprints"
      description="Sprints cuja execução cruza o mês selecionado, com situação, histórias e percentual de conclusão."
    >
      <ProjectPeriodFilters
        year={year}
        month={month}
        scopeKey={scopeKey}
        scopes={scopes}
        onYearChange={setYear}
        onMonthChange={setMonth}
        onScopeChange={(key) => {
          setScopeKey(key)
          setSelected([])
          setData(null)
        }}
        allowAllScopes={false}
        areaScopesOnly
        scopePlaceholder="Selecione projeto e área"
      />

      {hasSavedSuccess ? (
        <Card className="border-accent/25 bg-accent-soft/40 p-4 text-sm">
          <p className="font-medium text-foreground">Análise já disponível para esta seleção</p>
          <p className="mt-1 text-muted">
            Atualizada em{' '}
            <span className="font-medium text-foreground">
              {formatDateTime(savedAnalysis.generatedAt!)}
            </span>
            . Abra o relatório salvo ou gere novamente para refazer com dados atuais do Azure DevOps.
          </p>
        </Card>
      ) : null}

      {hasInProgress ? (
        <Card className="p-4 text-sm text-muted">
          Há uma análise em processamento para esta seleção. Você pode acompanhar o andamento ou aguardar
          a conclusão antes de gerar outra.
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        {hasSavedSuccess ? (
          <Button type="button" disabled={selected.length === 0} onClick={openSavedAnalysis}>
            Abrir análise salva
          </Button>
        ) : hasInProgress ? (
          <Button type="button" disabled={selected.length === 0} onClick={openSavedAnalysis}>
            Acompanhar análise
          </Button>
        ) : (
          <Button
            type="button"
            disabled={selected.length === 0 || starting}
            onClick={() => void createNewAnalysis()}
          >
            {starting ? 'Iniciando…' : 'Gerar análise com IA'}
          </Button>
        )}
        {hasSavedSuccess || hasInProgress ? (
          <Button
            type="button"
            variant="secondary"
            disabled={selected.length === 0 || starting || hasInProgress}
            onClick={() => void createNewAnalysis()}
          >
            {starting ? 'Gerando…' : 'Gerar novamente'}
          </Button>
        ) : null}
        <Button type="button" variant="secondary" disabled={selected.length === 0} onClick={() => setSelected([])}>
          Limpar seleção
        </Button>
        <p className="text-sm text-muted">
          {selected.length === 0
            ? 'Nenhuma Sprint selecionada'
            : `${selected.length} Sprint(s) selecionada(s)`}
        </p>
      </div>

      {error ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</Card>
      ) : null}

      {!canLoad ? (
        <Card className="p-4 text-sm text-muted">
          Escolha o <span className="font-medium text-ink">projeto e a área</span> nos filtros acima
          para consultar as Sprints no Azure DevOps. A listagem não carrega automaticamente para evitar
          consultas pesadas em todo o time.
        </Card>
      ) : loading ? (
        <p className="text-sm text-muted">Carregando Sprints do Azure DevOps…</p>
      ) : (
        <Card className="overflow-x-auto p-0">
          <Table>
            <thead>
              <tr>
                <Th className="w-10">
                  <input
                    type="checkbox"
                    aria-label="Selecionar Sprints visíveis"
                    checked={allVisibleSelected}
                    onChange={() => setSelected(allVisibleSelected ? [] : visibleKeys)}
                  />
                </Th>
                <Th>Sprint</Th>
                <Th>Projeto</Th>
                <Th>Início</Th>
                <Th>Término</Th>
                <Th>Situação</Th>
                <Th>Histórias</Th>
                <Th>Concluídas</Th>
                <Th>Pendentes</Th>
                <Th>Conclusão</Th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <Td colSpan={10} className="text-center text-muted">
                    Nenhuma Sprint com histórias neste mês para o projeto/área selecionado. Confira se
                    escolheu a área correta (ex.: «NiaHub - PAN» é diferente de «PAN»).
                  </Td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.sprint_key}>
                    <Td>
                      <input
                        type="checkbox"
                        aria-label={`Selecionar ${row.name}`}
                        checked={selected.includes(row.sprint_key)}
                        onChange={() => toggle(row.sprint_key)}
                      />
                    </Td>
                    <Td>
                      <Link
                        to={`/projetos/sprints/${encodeURIComponent(row.sprint_key)}?scope=${encodeURIComponent(scopeKey)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {row.name}
                      </Link>
                    </Td>
                    <Td>{row.team_project}</Td>
                    <Td>{formatDate(row.start_date)}</Td>
                    <Td>{formatDate(row.finish_date)}</Td>
                    <Td>{STATUS_LABEL[row.status] ?? row.status}</Td>
                    <Td>{row.stories_total}</Td>
                    <Td>{row.stories_completed_in_sprint}</Td>
                    <Td>{row.stories_pending}</Td>
                    <Td>
                      {row.completion_percent != null
                        ? `${formatPercent(row.completion_percent)} (${row.completion_numerator}/${row.completion_denominator})`
                        : '—'}
                    </Td>
                  </tr>
                ))
              )}
            </tbody>
          </Table>
        </Card>
      )}

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
