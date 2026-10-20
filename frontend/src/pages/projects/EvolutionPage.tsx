import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ProjectPeriodFilters } from '@/pages/projects/ProjectPeriodFilters'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import { api, type ProjectEvolution, type ProjectScope } from '@/lib/api'
import { currentYearMonth, formatDate, formatPercent } from '@/lib/format'

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

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" disabled title="Disponível na etapa de IA">
          Gerar resumo com IA
        </Button>
        <p className="text-sm text-muted">
          Resumo automático será habilitado quando a integração de IA estiver configurada.
        </p>
      </div>

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
