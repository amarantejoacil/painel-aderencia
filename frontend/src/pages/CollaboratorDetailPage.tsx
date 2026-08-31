import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { StatusBadge } from '@/components/StatusBadge'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type CollaboratorAnalysis, type DayResult } from '@/lib/api'
import { currentYearMonth, formatDate, formatHours, formatPercent, monthLabel } from '@/lib/format'

export function CollaboratorDetailPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const initial = currentYearMonth()
  const year = Number(params.get('year') ?? initial.year)
  const month = Number(params.get('month') ?? initial.month)
  const [data, setData] = useState<CollaboratorAnalysis | null>(null)
  const [selected, setSelected] = useState<DayResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api
      .analysis(Number(id), year, month)
      .then((result) => {
        setData(result)
        setSelected(null)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id, year, month])

  if (loading) return <Card className="text-muted">Carregando detalhe do colaborador…</Card>
  if (error) return <Card className="border-red-200 bg-red-50 text-red-800">{error}</Card>
  if (!data) return null

  const { summary } = data

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/?year=${year}&month=${month}`} className="text-sm text-accent hover:underline">
          ← Voltar ao dashboard
        </Link>
        <h2 className="mt-2 text-2xl font-semibold">{summary.collaborator.name}</h2>
        <p className="text-sm text-muted">
          {monthLabel(year, month)} · Azure: {summary.collaborator.azure_name} · carga {formatHours(summary.collaborator.daily_hours)}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs uppercase text-muted">Esperado</p>
          <p className="mt-1 text-xl font-semibold">{formatHours(summary.expected)}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Executado</p>
          <p className="mt-1 text-xl font-semibold">{formatHours(summary.executed)}</p>
        </Card>
        <Card className="bg-accent-soft">
          <p className="text-xs uppercase text-muted">Aderência de Horas</p>
          <p className="mt-1 text-xl font-semibold">{formatPercent(summary.adherence)}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Pendências</p>
          <p className="mt-1 text-xl font-semibold">{summary.missing + summary.incomplete} dias</p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_0.9fr]">
        <Card className="p-0">
          <Table>
            <thead>
              <tr>
                <Th>Data</Th>
                <Th className="text-right">Esperado</Th>
                <Th className="text-right">Executado</Th>
                <Th className="text-right">Diferença</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {data.days.map((day) => (
                <tr
                  key={day.date}
                  className={`cursor-pointer hover:bg-paper/80 ${selected?.date === day.date ? 'bg-accent-soft' : ''}`}
                  onClick={() => setSelected(day)}
                >
                  <Td className="font-medium">{formatDate(day.date)}</Td>
                  <Td className="text-right">{formatHours(day.expected)}</Td>
                  <Td className="text-right">{formatHours(day.executed)}</Td>
                  <Td className="text-right">
                    {Number(day.difference) > 0 ? '+' : ''}
                    {formatHours(day.difference)}
                  </Td>
                  <Td>
                    <StatusBadge status={day.status} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card>
          {!selected && (
            <p className="text-sm text-muted">Clique em um dia para ver as Tasks que compõem o lançamento.</p>
          )}
          {selected && (
            <div className="space-y-3">
              <div>
                <h3 className="text-lg font-semibold">
                  {formatDate(selected.date)} — {formatHours(selected.executed)}
                </h3>
                <p className="text-sm text-muted">
                  {selected.task_count === 0
                    ? 'Nenhuma Task lançada neste dia.'
                    : selected.hours_source === 'presence'
                      ? 'O CSV não trouxe horas. O dia foi considerado pela presença de Task.'
                      : `Soma das horas executadas das ${selected.task_count} Task(s).`}
                </p>
              </div>
              {selected.tasks.length === 0 ? (
                <p className="text-sm text-muted">Sem atividades.</p>
              ) : (
                <ul className="space-y-2">
                  {selected.tasks.map((task) => (
                    <li key={task.task_id} className="rounded-md border border-line p-3">
                      <p className="font-medium">
                        Task {task.task_id} — {task.title}
                      </p>
                      <p className="text-sm text-muted">
                        {task.completed_hours != null ? formatHours(task.completed_hours) : 'Horas não informadas'}
                        {task.state ? ` · ${task.state}` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {selected.tasks.length > 0 && (
                <p className="text-sm font-medium">Total: {formatHours(selected.executed)}</p>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
