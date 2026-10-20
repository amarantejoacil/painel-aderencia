import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { ProjectPeriodFilters } from '@/pages/projects/ProjectPeriodFilters'
import { ProjectModuleShell } from '@/pages/projects/ProjectModuleShell'
import { api, type ProjectOverview, type ProjectScope } from '@/lib/api'
import { currentYearMonth } from '@/lib/format'

export function OverviewPage() {
  const initial = currentYearMonth()
  const [year, setYear] = useState(initial.year)
  const [month, setMonth] = useState(initial.month)
  const [scopeKey, setScopeKey] = useState('')
  const [scopes, setScopes] = useState<ProjectScope[]>([])
  const [data, setData] = useState<ProjectOverview | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      return
    }
    setLoading(true)
    setError(null)
    api
      .projectOverview({ year, month, scope_key: scopeKey })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [year, month, scopeKey, canLoad, activeScope])

  const indicators = data?.indicators

  return (
    <ProjectModuleShell
      title="Visão Geral"
      description="Consolidação dos projetos acompanhados no Azure DevOps, com indicadores do período e acesso ao detalhe de cada projeto."
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
        areaScopesOnly
        scopePlaceholder="Selecione o projeto e a área"
      />

      {error ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</Card>
      ) : null}

      {!canLoad ? (
        <Card className="p-4 text-sm text-muted">
          Escolha o <span className="font-medium text-ink">projeto e a área</span> nos filtros acima
          para consultar os indicadores no Azure DevOps. A visão consolidada não carrega
          automaticamente, para evitar consultas pesadas em todo o time.
        </Card>
      ) : loading ? (
        <p className="text-sm text-muted">Consultando Azure DevOps…</p>
      ) : indicators ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Projetos acompanhados" value={String(indicators.projects_tracked)} />
            <MetricCard label="Sprints no período" value={String(indicators.sprints_in_period)} />
            <MetricCard label="Histórias criadas" value={String(indicators.stories_created)} />
            <MetricCard label="Histórias concluídas" value={String(indicators.stories_completed)} />
            <MetricCard label="Histórias em andamento" value={String(indicators.stories_in_progress)} />
            <MetricCard label="Histórias pendentes" value={String(indicators.stories_pending)} />
            <MetricCard
              label="Histórias após início da Sprint"
              value={String(indicators.stories_added_after_start)}
            />
            <MetricCard label="Impedimentos identificados" value={String(indicators.impediments_identified)} />
          </div>

          {data.project_cards.length > 0 ? (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">Resumo por projeto Azure</h3>
              <div className="grid gap-4 lg:grid-cols-2">
                {data.project_cards.map((card) => (
                  <Card key={card.scope_key} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{card.label}</p>
                        <p className="text-sm text-muted">{card.team_project}</p>
                      </div>
                      <Link
                        to={`/projetos/sprints?scope=${encodeURIComponent(card.scope_key)}&year=${year}&month=${month}`}
                        className="text-sm font-medium text-accent hover:underline"
                      >
                        Ver Sprints
                      </Link>
                    </div>
                    <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <dt className="text-muted">Sprints</dt>
                        <dd className="font-semibold">{card.sprints}</dd>
                      </div>
                      <div>
                        <dt className="text-muted">Concluídas</dt>
                        <dd className="font-semibold">{card.stories_completed}</dd>
                      </div>
                      <div>
                        <dt className="text-muted">Criadas</dt>
                        <dd className="font-semibold">{card.stories_created}</dd>
                      </div>
                      <div>
                        <dt className="text-muted">Pendentes</dt>
                        <dd className="font-semibold">{card.stories_pending}</dd>
                      </div>
                    </dl>
                  </Card>
                ))}
              </div>
            </div>
          ) : null}

          {data.limitations.length > 0 ? (
            <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
              <p className="font-medium">Limitações da análise</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {data.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Card>
          ) : null}

          <p className="text-xs text-muted">
            Fonte: Azure DevOps · indicadores com revisões de histórias quando disponíveis.
          </p>
        </>
      ) : null}
    </ProjectModuleShell>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </Card>
  )
}
