import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type CollaboratorAbsence, type CollaboratorAnalysis, type DayResult, type DayTask } from '@/lib/api'
import {
  ABSENCE_TYPE_LABEL,
  currentYearMonth,
  formatDate,
  formatAzureState,
  formatDateWithWeekday,
  formatHours,
  formatPercent,
  isWeekendDate,
  monthLabel,
} from '@/lib/format'
import { cn } from '@/lib/utils'

const EMPTY_ABSENCE: {
  type: CollaboratorAbsence['type']
  start_date: string
  end_date: string
  note: string
} = {
  type: 'medical_certificate',
  start_date: '',
  end_date: '',
  note: '',
}

function formatDayTaskStatuses(tasks: DayTask[]): string {
  if (tasks.length === 0) return '—'
  const labels = [
    ...new Set(
      tasks
        .map((task) => task.state)
        .filter((state): state is string => Boolean(state?.trim()))
        .map((state) => formatAzureState(state)),
    ),
  ]
  return labels.length > 0 ? labels.join(', ') : '—'
}

export function CollaboratorDetailPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const initial = currentYearMonth()
  const year = Number(params.get('year') ?? initial.year)
  const month = Number(params.get('month') ?? initial.month)
  const collaboratorId = Number(id)
  const [data, setData] = useState<CollaboratorAnalysis | null>(null)
  const [absences, setAbsences] = useState<CollaboratorAbsence[]>([])
  const [form, setForm] = useState(EMPTY_ABSENCE)
  const [selected, setSelected] = useState<DayResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [absenceError, setAbsenceError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    Promise.all([api.analysis(collaboratorId, year, month), api.listAbsences(collaboratorId)])
      .then(([result, absenceRows]) => {
        setData(result)
        setAbsences(absenceRows)
        setSelected(null)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [collaboratorId, id, month, year])

  useEffect(load, [load])

  const submitAbsence = async (event: FormEvent) => {
    event.preventDefault()
    setAbsenceError(null)
    try {
      await api.createAbsence(collaboratorId, {
        type: form.type,
        start_date: form.start_date,
        end_date: form.end_date || form.start_date,
        note: form.note.trim() || null,
      })
      setForm(EMPTY_ABSENCE)
      load()
    } catch (err) {
      setAbsenceError((err as Error).message)
    }
  }

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
          {monthLabel(year, month)} · Azure: {summary.collaborator.azure_name} · carga{' '}
          {formatHours(summary.collaborator.daily_hours)}
          {summary.collaborator.end_date && (
            <>
              {' '}
              · Desligamento: {formatDate(summary.collaborator.end_date)}
              {!summary.collaborator.active ? ' (inativo)' : ''}
            </>
          )}
        </p>
        {summary.collaborator.end_date && (
          <p className="mt-2 text-sm text-slate-700">
            A partir de {formatDate(summary.collaborator.end_date)} não são exigidos lançamentos do Azure para este
            colaborador.
          </p>
        )}
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

      <Card>
        <h3 className="text-lg font-semibold">Ausências / Exceções</h3>
        <p className="mt-1 text-sm text-muted">
          Registre ausências individuais do colaborador. Esses dias não exigem lançamento e não entram como inconsistência.
        </p>
        <form className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4" onSubmit={submitAbsence}>
          <div>
            <Label htmlFor="absence-type">Tipo</Label>
            <select
              id="absence-type"
              className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              value={form.type}
              onChange={(event) =>
                setForm({ ...form, type: event.target.value as CollaboratorAbsence['type'] })
              }
              required
            >
              {Object.entries(ABSENCE_TYPE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="absence-start">Data inicial</Label>
            <Input
              id="absence-start"
              type="date"
              value={form.start_date}
              onChange={(event) => setForm({ ...form, start_date: event.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="absence-end">Data final</Label>
            <Input
              id="absence-end"
              type="date"
              value={form.end_date}
              onChange={(event) => setForm({ ...form, end_date: event.target.value })}
              placeholder="Opcional para um único dia"
            />
          </div>
          <div>
            <Label htmlFor="absence-note">Observação</Label>
            <Input
              id="absence-note"
              value={form.note}
              onChange={(event) => setForm({ ...form, note: event.target.value })}
              placeholder="Opcional"
            />
          </div>
          <div className="md:col-span-2 lg:col-span-4">
            <Button type="submit">Cadastrar ausência</Button>
          </div>
        </form>
        {absenceError && <p className="mt-3 text-sm text-red-700">{absenceError}</p>}

        {absences.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <Table>
              <thead>
                <tr>
                  <Th>Tipo</Th>
                  <Th>Início</Th>
                  <Th>Fim</Th>
                  <Th>Observação</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {absences.map((row) => (
                  <tr key={row.id}>
                    <Td>{ABSENCE_TYPE_LABEL[row.type]}</Td>
                    <Td>{formatDate(row.start_date)}</Td>
                    <Td>{formatDate(row.end_date)}</Td>
                    <Td>{row.note || '—'}</Td>
                    <Td className="text-right">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={async () => {
                          await api.deleteAbsence(collaboratorId, row.id)
                          load()
                        }}
                      >
                        Remover
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_0.9fr]">
        <Card className="p-0">
          <Table>
            <thead>
              <tr>
                <Th>Data</Th>
                <Th className="text-right">Esperado</Th>
                <Th className="text-right">Executado</Th>
                <Th className="text-right">Diferença</Th>
                <Th>Status da Task</Th>
                <Th>Situação</Th>
              </tr>
            </thead>
            <tbody>
              {data.days.map((day) => {
                const weekend = isWeekendDate(day.date)
                const absence = day.status === 'justified_absence'
                return (
                  <tr
                    key={day.date}
                    className={cn(
                      'cursor-pointer',
                      absence && 'bg-blue-50 hover:bg-blue-100',
                      !absence && weekend && 'bg-red-50 hover:bg-red-100',
                      !absence && !weekend && 'hover:bg-paper/80',
                      selected?.date === day.date &&
                        (absence
                          ? 'bg-blue-100 ring-2 ring-inset ring-blue-200'
                          : weekend
                            ? 'bg-red-100 ring-2 ring-inset ring-red-200'
                            : 'bg-accent-soft'),
                    )}
                    onClick={() => setSelected(day)}
                  >
                    <Td className={cn('font-medium', absence && 'text-blue-800', weekend && !absence && 'text-red-700')}>
                      {formatDateWithWeekday(day.date)}
                    </Td>
                    <Td className="text-right">{formatHours(day.expected)}</Td>
                    <Td className="text-right">{formatHours(day.executed)}</Td>
                    <Td className="text-right">
                      {Number(day.difference) > 0 ? '+' : ''}
                      {formatHours(day.difference)}
                    </Td>
                    <Td className="text-sm">{formatDayTaskStatuses(day.tasks)}</Td>
                    <Td>
                      <StatusBadge
                        status={day.status}
                        absenceType={day.absence_type}
                        dayDate={day.date}
                        endDate={summary.collaborator.end_date}
                      />
                    </Td>
                  </tr>
                )
              })}
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
                  {formatDateWithWeekday(selected.date)} — {formatHours(selected.executed)}
                </h3>
                {selected.status === 'justified_absence' && selected.absence_type && (
                  <p className="text-sm text-blue-800">
                    Motivo: {ABSENCE_TYPE_LABEL[selected.absence_type] ?? selected.absence_type}
                    {selected.absence_note ? ` · ${selected.absence_note}` : ''}
                  </p>
                )}
                {isWeekendDate(selected.date) && selected.status !== 'justified_absence' && (
                  <p className="text-sm text-red-700">Fim de semana — não exige lançamento de Tasks.</p>
                )}
                {summary.collaborator.end_date &&
                  selected.date >= summary.collaborator.end_date &&
                  selected.status === 'not_required' &&
                  !isWeekendDate(selected.date) && (
                    <p className="text-sm text-slate-700">
                      Colaborador desligado — lançamentos do Azure não são exigidos a partir de{' '}
                      {formatDate(summary.collaborator.end_date)}.
                    </p>
                  )}
                {selected.status === 'justified_absence' ? (
                  <p className="text-sm text-muted">Ausência justificada — não exige lançamento de Tasks.</p>
                ) : selected.status === 'missing' && selected.task_count === 0 ? (
                  <p className="text-sm font-medium text-red-800">
                    Não existe lançamento para este dia na importação do Azure Boards.
                  </p>
                ) : (
                  <p className="text-sm text-muted">
                    {selected.task_count === 0
                      ? 'Nenhuma Task lançada neste dia.'
                      : selected.hours_source === 'presence'
                        ? 'O CSV não trouxe horas. O dia foi considerado pela presença de Task.'
                        : `Soma das horas executadas das ${selected.task_count} Task(s).`}
                  </p>
                )}
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
                      <dl className="mt-2 space-y-1 text-sm">
                        {task.activity_category && (
                          <div className="flex flex-wrap gap-1">
                            <dt className="font-medium text-muted">Atividade:</dt>
                            <dd>{task.activity_category}</dd>
                          </div>
                        )}
                        <div className="flex flex-wrap gap-1">
                          <dt className="font-medium text-muted">Horas executadas:</dt>
                          <dd>
                            {task.completed_hours != null
                              ? formatHours(task.completed_hours)
                              : 'Não informadas'}
                          </dd>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <dt className="font-medium text-muted">Status da Task:</dt>
                          <dd className="font-medium text-ink">
                            {task.state ? formatAzureState(task.state) : '—'}
                          </dd>
                        </div>
                      </dl>
                    </li>
                  ))}
                </ul>
              )}
              {selected.tasks.length > 0 && selected.status !== 'justified_absence' && (
                <p className="text-sm font-medium">Total: {formatHours(selected.executed)}</p>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
