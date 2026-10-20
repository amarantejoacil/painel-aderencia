import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type ConferenceDay, type ConferenceReport } from '@/lib/api'
import { formatDateWithWeekday, formatDateTime, formatHours, formatPercent } from '@/lib/format'

type Props = {
  today?: string
  onPrepare: (day: ConferenceDay) => void
  onLoaded: (report: ConferenceReport | null) => void
  reloadAt?: number
}

export function ConferenceSection({ today, onPrepare, onLoaded, reloadAt = 0 }: Props) {
  const navigate = useNavigate()
  const [period, setPeriod] = useState('')
  const [report, setReport] = useState<ConferenceReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [openRecords, setOpenRecords] = useState<string | null>(null)

  useEffect(() => {
    if (today && !period) setPeriod(today.slice(0, 7))
  }, [today, period])

  useEffect(() => {
    if (period) void refresh(period)
  }, [period])

  useEffect(() => {
    if (period && reloadAt > 0) void refresh(period)
  }, [reloadAt, period])

  async function refresh(value = period) {
    const [yearText, monthText] = value.split('-')
    const year = Number(yearText)
    const month = Number(monthText)
    if (!year || !month) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.timeEntryConference(year, month)
      setReport(data)
      setSelected([])
      setOpenRecords(null)
      onLoaded(data)
    } catch (err) {
      setReport(null)
      onLoaded(null)
      setError(err instanceof Error ? err.message : 'Não foi possível atualizar a conferência.')
    } finally {
      setLoading(false)
    }
  }

  function toggle(date: string) {
    setSelected((current) => (current.includes(date) ? current.filter((item) => item !== date) : [...current, date]))
  }

  function sendBatch() {
    if (!report) return
    const days = report.pending.filter((item) => selected.includes(item.date))
    if (days.length === 0) return
    const params = new URLSearchParams()
    params.set('dates', days.map((item) => item.date).join(','))
    params.set('hours', days.map((item) => `${item.date}:${Number(item.suggested_hours) || 0}`).join(','))
    params.set('status', days.map((item) => `${item.date}:${item.status}`).join(','))
    navigate(`/apontamentos/lote?${params.toString()}`)
  }

  const monthLabel = period
    ? new Date(Number(period.slice(0, 4)), Number(period.slice(5, 7)) - 1, 1).toLocaleDateString('pt-BR', {
        month: 'long',
        year: 'numeric',
      })
    : ''

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Conferência mensal de apontamentos</h3>
          <p className="text-sm text-muted">
            Tasks do responsável em todos os projetos configurados, pela data de referência.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <Label htmlFor="conference-month">Mês</Label>
            <Input
              id="conference-month"
              type="month"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
            />
          </div>
          <Button type="button" variant="secondary" disabled={loading || !period} onClick={() => void refresh()}>
            {loading ? 'Atualizando...' : 'Atualizar conferência'}
          </Button>
        </div>
      </div>

      {error ? <p className="text-sm text-red-800">{error}</p> : null}

      {report ? (
        <>
          <p className="text-sm text-muted">
            {monthLabel ? <span className="capitalize">{monthLabel}</span> : null}
            {' · '}
            {report.obligatory_days} dias obrigatórios
            {' · '}
            {formatHours(report.recognized_hours)} reconhecidas
            {' · '}
            {formatHours(report.executed_hours)} executadas
            {' · '}
            {formatHours(report.estimated_hours)} estimadas
            {' · '}
            {report.dispensed_days} dias dispensados
            {' · '}
            aderência {formatPercent(report.adherence)}
            {' · '}
            atualizado em {formatDateTime(report.checked_at)}
          </p>
          {report.collaborator_matched ? null : (
            <p className="text-sm text-muted">
              Colaborador não encontrado na base. A carga usada foi 8 horas, sem ausências cadastradas.
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Indicator label="Dias completos" value={String(report.complete_days)} />
            <Indicator label="Dias incompletos" value={String(report.incomplete_days)} />
            <Indicator label="Dias sem lançamento" value={String(report.missing_days)} />
            <Indicator label="Horas faltantes" value={formatHours(report.missing_hours)} />
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold">Dias pendentes</h4>
              <Button type="button" variant="secondary" size="sm" disabled={selected.length === 0} onClick={sendBatch}>
                Lançar selecionados em lote
              </Button>
            </div>
            {report.empty_message ? <p className="text-sm text-muted">{report.empty_message}</p> : null}
            {report.pending.length > 0 ? (
              <Table>
                <thead>
                  <tr>
                    <Th>
                      <span className="sr-only">Selecionar</span>
                    </Th>
                    <Th>Data</Th>
                    <Th>Horas reconhecidas</Th>
                    <Th>Horas faltantes</Th>
                    <Th>Situação</Th>
                    <Th>Ação</Th>
                  </tr>
                </thead>
                <tbody>
                  {report.pending.map((day) => (
                    <tr key={day.date}>
                      <Td>
                        <input
                          type="checkbox"
                          aria-label={`Selecionar ${day.date}`}
                          checked={selected.includes(day.date)}
                          onChange={() => toggle(day.date)}
                        />
                      </Td>
                      <Td>{formatDateWithWeekday(day.date)}</Td>
                      <Td>{formatHours(day.recognized_hours)}</Td>
                      <Td>{formatHours(day.missing_hours)}</Td>
                      <Td>
                        <p>{day.status_label}</p>
                        <p className="text-xs text-muted">
                          Estimadas {formatHours(day.estimated_hours)} · Executadas {formatHours(day.executed_hours)} ·{' '}
                          {day.hours_source_label}
                        </p>
                      </Td>
                      <Td>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setOpenRecords((current) => (current === day.date ? null : day.date))}
                          >
                            Ver registros
                          </Button>
                          <Button type="button" size="sm" onClick={() => onPrepare(day)}>
                            Preparar lançamento
                          </Button>
                        </div>
                        {openRecords === day.date ? <DayRecords day={day} /> : null}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : null}
          </div>
        </>
      ) : loading ? (
        <p className="text-sm text-muted">Consultando as Tasks do mês no Azure DevOps.</p>
      ) : null}
    </Card>
  )
}

function Indicator({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line px-3 py-2">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  )
}

function DayRecords({ day }: { day: ConferenceDay }) {
  if (day.tasks.length === 0) {
    return <p className="mt-2 text-xs text-muted">Nenhuma Task elegível nesta data.</p>
  }
  return (
    <ul className="mt-2 space-y-1 text-xs text-muted">
      {day.tasks.map((task) => (
        <li key={task.task_id}>
          {task.url ? (
            <a className="text-accent underline" href={task.url} target="_blank" rel="noreferrer">
              {task.title}
            </a>
          ) : (
            task.title
          )}
          {' · '}
          estimadas {formatHours(task.estimated_hours)} · executadas {formatHours(task.executed_hours)}
        </li>
      ))}
    </ul>
  )
}
