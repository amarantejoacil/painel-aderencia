import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type Collaborator, type Dashboard } from '@/lib/api'
import { currentYearMonth, formatHours, formatPercent, monthLabel, STATUS_LABEL } from '@/lib/format'

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
            <Metric title="Colaboradores analisados" value={String(indicators.collaborators)} />
            <Metric title="Horas esperadas" value={formatHours(indicators.expected_hours)} />
            <Metric title="Horas executadas" value={formatHours(indicators.executed_hours)} />
            <Metric title="Aderência de Horas" value={formatPercent(indicators.adherence)} accent />
            <Metric title="Dias regulares" value={String(indicators.regular)} />
            <Metric title="Dias incompletos" value={String(indicators.incomplete)} />
            <Metric title="Dias sem lançamento" value={String(indicators.missing)} />
            <Metric title="Dias excedentes" value={String(indicators.excess)} />
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
        </>
      )}
    </div>
  )
}

function Metric({ title, value, accent }: { title: string; value: string; accent?: boolean }) {
  return (
    <Card className={accent ? 'bg-accent-soft' : undefined}>
      <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </Card>
  )
}
