import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DashboardCharts } from '@/components/DashboardCharts'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type Collaborator, type Dashboard } from '@/lib/api'
import { currentYearMonth, formatHours, formatPercent, monthLabel, STATUS_LABEL } from '@/lib/format'

type StrategicIndicators = {
  teamComplianceRate: number
  okCollaborators: number
  needsReview: number
  avgAdherence: number
  fullAdherence: number
  compliantDayRate: number
  launchCoverage: number
  hoursGap: number
  mandatoryDays: number
}

function computeStrategicIndicators(data: Dashboard): StrategicIndicators {
  const { indicators, rows } = data
  const totalCollaborators = rows.length
  const okCollaborators = rows.filter(
    (row) => row.missing === 0 && row.incomplete === 0 && row.excess === 0,
  ).length
  const fullAdherence = rows.filter((row) => Number(row.adherence) >= 100).length
  const mandatoryDays =
    indicators.regular + indicators.incomplete + indicators.missing + indicators.excess
  const daysWithLaunch = indicators.regular + indicators.incomplete + indicators.excess
  const avgAdherence =
    totalCollaborators > 0
      ? rows.reduce((sum, row) => sum + Number(row.adherence), 0) / totalCollaborators
      : 0

  return {
    teamComplianceRate: totalCollaborators > 0 ? (okCollaborators / totalCollaborators) * 100 : 0,
    okCollaborators,
    needsReview: totalCollaborators - okCollaborators,
    avgAdherence,
    fullAdherence,
    compliantDayRate: mandatoryDays > 0 ? (indicators.regular / mandatoryDays) * 100 : 100,
    launchCoverage: mandatoryDays > 0 ? (daysWithLaunch / mandatoryDays) * 100 : 100,
    hoursGap: Math.max(0, Number(indicators.expected_hours) - Number(indicators.executed_hours)),
    mandatoryDays,
  }
}

export function DashboardPage() {
  const initial = currentYearMonth()
  const [year, setYear] = useState(initial.year)
  const [month, setMonth] = useState(initial.month)
  const [collaboratorId, setCollaboratorId] = useState('')
  const [status, setStatus] = useState('')
  const [people, setPeople] = useState<Collaborator[]>([])
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, index) => ({
        value: index + 1,
        label: new Date(2026, index, 1).toLocaleDateString('pt-BR', { month: 'long' }),
      })),
    [],
  )

  useEffect(() => {
    api.listCollaborators().then(setPeople).catch(() => setPeople([]))
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    api
      .dashboard({
        year,
        month,
        collaborator_id: collaboratorId ? Number(collaboratorId) : undefined,
        status: status || undefined,
      })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [year, month, collaboratorId, status])

  const indicators = data?.indicators
  const strategic = useMemo(
    () => (data ? computeStrategicIndicators(data) : null),
    [data],
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Aderência de Horas · {monthLabel(year, month)}</h2>
          <p className="mt-1 text-sm text-muted">
            A conferência é feita por colaborador e por dia. Horas a mais em um dia não compensam outro.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/relatorio-inconsistencias?year=${year}&month=${month}`}>
            <Button type="button" variant="secondary">
              Relatório de Inconsistências
            </Button>
          </Link>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              const query = new URLSearchParams({ year: String(year), month: String(month) })
              if (collaboratorId) query.set('collaborator_id', collaboratorId)
              window.open(`/api/activities/export?${query}`, '_blank')
            }}
          >
            Exportar Excel
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <label className="text-sm">
          <span className="mb-1 block text-muted">Mês</span>
          <select
            className="h-10 w-full rounded-md border border-line bg-white px-3"
            value={month}
            onChange={(event) => setMonth(Number(event.target.value))}
          >
            {months.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Ano</span>
          <select
            className="h-10 w-full rounded-md border border-line bg-white px-3"
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
          >
            {[2025, 2026, 2027].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Colaborador</span>
          <select
            className="h-10 w-full rounded-md border border-line bg-white px-3"
            value={collaboratorId}
            onChange={(event) => setCollaboratorId(event.target.value)}
          >
            <option value="">Todos</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Status</span>
          <select
            className="h-10 w-full rounded-md border border-line bg-white px-3"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">Todos</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <Card className="border-red-200 bg-red-50 text-red-800">{error}</Card>}

      {loading && <Card className="text-muted">Carregando indicadores…</Card>}

      {!loading && data && indicators && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              title="Colaboradores analisados"
              value={String(indicators.collaborators)}
              description="Colaboradores ativos incluídos na análise do mês, respeitando data de entrada e saída."
            />
            <Metric
              title="Horas esperadas"
              value={formatHours(indicators.expected_hours)}
              description="Soma da carga diária em todos os dias úteis obrigatórios da equipe no período."
            />
            <Metric
              title="Horas executadas"
              value={formatHours(indicators.executed_hours)}
              description="Total de horas lançadas nas Tasks importadas do Azure Boards."
            />
            <Metric
              title="Aderência de Horas"
              value={formatPercent(indicators.adherence)}
              description="Conformidade dos lançamentos com a carga esperada, limitada a 100%. Não mede produtividade."
              accent
            />
            <Metric
              title="Dias regulares"
              value={String(indicators.regular)}
              description="Dias em que as horas executadas foram iguais à carga esperada."
            />
            <Metric
              title="Dias incompletos"
              value={String(indicators.incomplete)}
              description="Dias com lançamento, porém com horas abaixo da carga esperada."
            />
            <Metric
              title="Dias sem lançamento"
              value={String(indicators.missing)}
              description="Dias úteis obrigatórios sem nenhuma Task encontrada na importação."
            />
            <Metric
              title="Dias excedentes"
              value={String(indicators.excess)}
              description="Dias com horas lançadas acima da carga esperada do colaborador."
            />
          </div>

          <Card className="p-0">
            {data.rows.length === 0 ? (
              <div className="p-6 text-sm text-muted">
                Nenhum colaborador encontrado para este filtro. Cadastre a equipe e importe o CSV do Azure Boards.
              </div>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>Colaborador</Th>
                    <Th className="text-right">Esperado</Th>
                    <Th className="text-right">Executado</Th>
                    <Th className="text-right">Aderência</Th>
                    <Th className="text-right">Sem lançamento</Th>
                    <Th className="text-right">Incompleto</Th>
                    <Th className="text-right">Excedente</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr key={row.collaborator.id} className="hover:bg-paper/80">
                      <Td>
                        <Link
                          className="font-medium text-accent hover:underline"
                          to={`/colaboradores/${row.collaborator.id}?year=${year}&month=${month}`}
                        >
                          {row.collaborator.name}
                        </Link>
                      </Td>
                      <Td className="text-right">{formatHours(row.expected)}</Td>
                      <Td className="text-right">{formatHours(row.executed)}</Td>
                      <Td className="text-right font-medium">{formatPercent(row.adherence)}</Td>
                      <Td className="text-right">{row.missing}</Td>
                      <Td className="text-right">{row.incomplete}</Td>
                      <Td className="text-right">{row.excess}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>

          {strategic && data.rows.length > 0 && (
            <section className="space-y-3">
              <div>
                <h3 className="text-lg font-semibold">Indicadores estratégicos</h3>
                <p className="mt-1 text-sm text-muted">
                  Visão gerencial do período, derivada dos lançamentos importados e das regras de aderência.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Metric
                  title="Conformidade da equipe"
                  value={formatPercent(strategic.teamComplianceRate)}
                  description={`${strategic.okCollaborators} de ${data.rows.length} colaborador(es) sem inconsistências (sem lançamento, incompleto ou excedente).`}
                  accent={strategic.teamComplianceRate >= 80}
                />
                <Metric
                  title="Requerem revisão"
                  value={String(strategic.needsReview)}
                  description="Colaboradores com ao menos uma inconsistência no mês analisado."
                  warn={strategic.needsReview > 0}
                />
                <Metric
                  title="Aderência média individual"
                  value={formatPercent(strategic.avgAdherence)}
                  description="Média aritmética da aderência de cada colaborador no período."
                />
                <Metric
                  title="Aderência plena"
                  value={String(strategic.fullAdherence)}
                  description={`Colaboradores com aderência de 100% entre ${data.rows.length} analisado(s).`}
                />
                <Metric
                  title="Taxa de dias conformes"
                  value={formatPercent(strategic.compliantDayRate)}
                  description={`${indicators.regular} dia(s) regulares entre ${strategic.mandatoryDays} dia(s) úteis obrigatórios da equipe.`}
                />
                <Metric
                  title="Cobertura de lançamentos"
                  value={formatPercent(strategic.launchCoverage)}
                  description="Percentual de dias obrigatórios com ao menos uma Task registrada na importação."
                />
                <Metric
                  title="Déficit acumulado de horas"
                  value={formatHours(strategic.hoursGap)}
                  description="Diferença entre horas esperadas e executadas no período (não compensa entre dias)."
                  warn={strategic.hoursGap > 0}
                />
              </div>
            </section>
          )}

          {data.rows.length > 0 && <DashboardCharts data={data} />}
        </>
      )}
    </div>
  )
}

function Metric({
  title,
  value,
  description,
  accent,
  warn,
}: {
  title: string
  value: string
  description: string
  accent?: boolean
  warn?: boolean
}) {
  return (
    <Card
      className={
        accent ? 'bg-accent-soft' : warn ? 'border-amber-200 bg-amber-50/60' : undefined
      }
    >
      <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-muted">{description}</p>
    </Card>
  )
}
