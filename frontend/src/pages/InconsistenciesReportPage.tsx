import { useEffect, useMemo, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Table, Td, Th } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/StatusBadge'
import {
  api,
  type DayResult,
  type InconsistenciesReport,
  type InconsistenciesReportRow,
  type MonthScheduleContext,
} from '@/lib/api'
import {
  ABSENCE_TYPE_LABEL,
  currentYearMonth,
  EXCEPTION_LABEL,
  formatAzureState,
  formatDate,
  formatDateRange,
  formatDateWithWeekday,
  formatHours,
  dayStatusLabel,
  monthLabel,
} from '@/lib/format'
import {
  buildCollaboratorIntro,
  type InconsistenciesReportCopySettings,
} from '@/lib/inconsistenciesReportCopy'
import { cn } from '@/lib/utils'

type SelectedIssue = {
  row: InconsistenciesReportRow
  day: DayResult
}

function periodShort(year: number, month: number): string {
  return monthLabel(year, month).replace(' de ', '/')
}

function issueLine(day: DayResult): string {
  const label = dayStatusLabel(day.status, day.absence_type)
  const base = `${formatDate(day.date)} — ${label}`
  const hours = `Esperado: ${formatHours(day.expected)} | Executado: ${formatHours(day.executed)}`
  const gap = Math.abs(Number(day.difference))

  if (day.status === 'missing') {
    const entry =
      day.launch_verification?.message ??
      (day.task_count === 0
        ? 'Nenhuma Task encontrada na importação'
        : 'Horas executadas insuficientes nas Tasks importadas')
    return `${base} — ${entry} — ${hours} | Faltam: ${formatHours(gap)}`
  }
  if (day.status === 'incomplete') {
    return `${base} — ${hours} | Faltam: ${formatHours(gap)}`
  }
  if (day.status === 'excess') {
    return `${base} — ${hours} | Excedente: ${formatHours(gap)}`
  }
  return `${base} — ${hours}`
}

export function InconsistenciesReportPage() {
  const [params] = useSearchParams()
  const initial = currentYearMonth()
  const year = Number(params.get('year') ?? initial.year)
  const month = Number(params.get('month') ?? initial.month)
  const [situation, setSituation] = useState<'ok' | 'pending' | ''>('')
  const [issueType, setIssueType] = useState<'missing' | 'incomplete' | 'excess' | ''>('')
  const [data, setData] = useState<InconsistenciesReport | null>(null)
  const [selected, setSelected] = useState<SelectedIssue | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [copySettings, setCopySettings] = useState<InconsistenciesReportCopySettings | null>(null)

  useEffect(() => {
    api
      .getInconsistenciesReportSettings()
      .then((settings) =>
        setCopySettings({
          copy_intro_requires_review: settings.copy_intro_requires_review,
          copy_intro_ok: settings.copy_intro_ok,
        }),
      )
      .catch(() => setCopySettings(null))
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSelected(null)
    api
      .inconsistenciesReport({
        year,
        month,
        situation: situation || undefined,
        issue_type: issueType || undefined,
      })
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [year, month, situation, issueType])

  const pendingRows = useMemo(() => data?.rows.filter((row) => row.situation === 'pending') ?? [], [data])
  const okRows = useMemo(() => data?.rows.filter((row) => row.situation === 'ok') ?? [], [data])

  const exportCsv = () => {
    const query = new URLSearchParams({ year: String(year), month: String(month) })
    if (situation) query.set('situation', situation)
    if (issueType) query.set('issue_type', issueType)
    window.open(`/api/inconsistencies-report/export?${query}`, '_blank')
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <Link to={`/?year=${year}&month=${month}`} className="text-sm text-accent hover:underline">
            ← Voltar ao dashboard
          </Link>
          <h2 className="mt-2 text-2xl font-semibold">
            Relatório de Inconsistências — {periodShort(year, month)}
          </h2>
          <p className="mt-1 text-sm text-muted">
            Visão consolidada para fechamento do mês. Colaboradores com inconsistências aparecem primeiro.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={exportCsv}>
          Exportar CSV
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <FilterSelect
          label="Situação"
          value={situation}
          onChange={(value) => setSituation(value as 'ok' | 'pending' | '')}
          options={[
            ['', 'Todos'],
            ['pending', 'Somente com inconsistências'],
            ['ok', 'Somente OK'],
          ]}
        />
        <FilterSelect
          label="Tipo de inconsistência"
          value={issueType}
          onChange={(value) => setIssueType(value as 'missing' | 'incomplete' | 'excess' | '')}
          options={[
            ['', 'Todos os tipos'],
            ['missing', 'Sem lançamento'],
            ['incomplete', 'Incompleto'],
            ['excess', 'Excedente'],
          ]}
        />
      </div>

      {error && <Card className="border-red-200 bg-red-50 text-red-800">{error}</Card>}
      {loading && <Card className="text-muted">Gerando relatório…</Card>}

      {!loading && data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <Metric title="Colaboradores analisados" value={String(data.indicators.collaborators)} />
            <Metric title="Colaboradores OK" value={String(data.indicators.ok)} accent="ok" />
            <Metric title="Com inconsistências" value={String(data.indicators.with_issues)} accent="warn" />
            <Metric title="Dias sem lançamento" value={String(data.indicators.missing)} />
            <Metric title="Dias incompletos" value={String(data.indicators.incomplete)} />
            <Metric title="Dias excedentes" value={String(data.indicators.excess)} />
            <Metric
              title="Tasks não concluídas"
              value={String(data.indicators.open_tasks ?? 0)}
              accent={data.indicators.open_tasks ? 'warn' : undefined}
            />
          </div>

          {data.month_schedule && (
            <MonthSchedulePanel schedule={data.month_schedule} year={year} month={month} />
          )}

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-6">
              {pendingRows.length > 0 && (
                <section className="space-y-3">
                  <h3 className="text-lg font-semibold">Requerem revisão</h3>
                  {pendingRows.map((row) => (
                    <CollaboratorBlock
                      key={row.collaborator.id}
                      row={row}
                      year={year}
                      month={month}
                      copySettings={copySettings}
                      selected={selected}
                      onSelect={setSelected}
                    />
                  ))}
                </section>
              )}

              {okRows.length > 0 && (
                <section className="space-y-3">
                  <h3 className="text-lg font-semibold">Colaboradores OK</h3>
                  {okRows.map((row) => (
                    <CollaboratorBlock
                      key={row.collaborator.id}
                      row={row}
                      year={year}
                      month={month}
                      copySettings={copySettings}
                      selected={selected}
                      onSelect={setSelected}
                    />
                  ))}
                </section>
              )}

              {data.rows.length === 0 && (
                <Card className="text-sm text-muted">Nenhum colaborador encontrado para os filtros selecionados.</Card>
              )}
            </div>

            <Card>
              {!selected && (
                <p className="text-sm text-muted">
                  Clique em uma inconsistência para ver as Tasks daquele dia.
                </p>
              )}
              {selected && <IssueDetail selected={selected} onClose={() => setSelected(null)} />}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function buildCollaboratorCardText(
  row: InconsistenciesReportRow,
  year: number,
  month: number,
  copySettings: InconsistenciesReportCopySettings | null,
): string {
  const isOk = row.situation === 'ok'
  const lines = [
    buildCollaboratorIntro(row, year, month, copySettings),
    row.collaborator.name,
    `Situação: ${isOk ? 'OK' : 'Requer revisão'}`,
    `Período: ${periodShort(year, month)}`,
    '',
    row.summary_text,
  ]
  if (row.pending_days.length > 0) {
    lines.push(
      '',
      `Inconsistências (${row.pending_days.length}):`,
      ...row.pending_days.map((day) => `- ${issueLine(day)}`),
    )
  }
  if (row.open_tasks.length > 0) {
    lines.push(
      '',
      `Tasks não concluídas no Azure (${row.open_tasks.length}) — não impactam aderência de horas:`,
      ...row.open_tasks.map(
        (task) =>
          `- #${task.task_id} — ${task.title} · ${formatDate(task.work_date)} · ${task.state_label}${
            task.completed_hours != null ? ` · ${formatHours(task.completed_hours)}` : ''
          }`,
      ),
    )
  }
  return lines.join('\n')
}

function CollaboratorBlock({
  row,
  year,
  month,
  copySettings,
  selected,
  onSelect,
}: {
  row: InconsistenciesReportRow
  year: number
  month: number
  copySettings: InconsistenciesReportCopySettings | null
  selected: SelectedIssue | null
  onSelect: (value: SelectedIssue) => void
}) {
  const isOk = row.situation === 'ok'
  const [copied, setCopied] = useState(false)

  const copyCardText = useCallback(async () => {
    const text = buildCollaboratorCardText(row, year, month, copySettings)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      const area = document.createElement('textarea')
      area.value = text
      area.style.position = 'fixed'
      area.style.left = '-9999px'
      document.body.appendChild(area)
      area.select()
      try {
        document.execCommand('copy')
        setCopied(true)
        window.setTimeout(() => setCopied(false), 2500)
      } finally {
        document.body.removeChild(area)
      }
    }
  }, [row, year, month, copySettings])

  return (
    <Card className={cn(isOk ? 'border-emerald-200 bg-emerald-50/40' : 'border-amber-200 bg-amber-50/30')}>
      <div className="flex items-start gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <span aria-hidden className="mt-0.5 shrink-0">
            {isOk ? '✅' : '⚠️'}
          </span>
          <div className="min-w-0 flex-1">
            <h4 className="pr-2 font-semibold leading-snug">{row.collaborator.name}</h4>
            <p className="text-sm font-medium text-muted">
              Situação: {isOk ? 'OK' : 'Requer revisão'}
            </p>
          <p className="mt-2 text-sm">{row.summary_text}</p>

          {!isOk && row.pending_days.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-sm font-medium">
                Foram identificadas {row.pending_days.length}{' '}
                {row.pending_days.length === 1 ? 'inconsistência' : 'inconsistências'}:
              </p>
              <ul className="space-y-1">
                {row.pending_days.map((day) => {
                  const active =
                    selected?.row.collaborator.id === row.collaborator.id && selected.day.date === day.date
                  return (
                    <li key={day.date}>
                      <button
                        type="button"
                        className={cn(
                          'w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-white/80',
                          active && 'bg-white ring-1 ring-accent/30',
                        )}
                        onClick={() => onSelect({ row, day })}
                      >
                        {issueLine(day)}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {row.open_tasks.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-sm font-medium text-sky-900">
                Alerta: {row.open_tasks.length}{' '}
                {row.open_tasks.length === 1 ? 'Task' : 'Tasks'} no mês ainda não Concluída(s) no Azure
                (não impacta aderência de horas).
              </p>
              <ul className="space-y-1.5">
                {row.open_tasks.map((task) => (
                  <li
                    key={`${task.task_id}-${task.work_date}`}
                    className="rounded-md border border-sky-200/80 bg-sky-50/50 px-2 py-1.5 text-sm"
                  >
                    <p className="font-medium">
                      #{task.task_id} — {task.title}
                    </p>
                    <p className="text-muted">
                      {formatDate(task.work_date)}
                      {' · '}
                      Situação: {task.state_label}
                      {task.completed_hours != null ? ` · ${formatHours(task.completed_hours)}` : ''}
                      {task.activity_category ? ` · ${task.activity_category}` : ''}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

            <div className="mt-3">
              <Link
                className="text-sm text-accent hover:underline"
                to={`/colaboradores/${row.collaborator.id}?year=${year}&month=${month}`}
              >
                Ver detalhe completo
              </Link>
            </div>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="shrink-0 border-accent/40 bg-white shadow-sm"
          onClick={() => void copyCardText()}
        >
          {copied ? 'Copiado!' : 'Copiar texto'}
        </Button>
      </div>
    </Card>
  )
}

function IssueDetail({ selected, onClose }: { selected: SelectedIssue; onClose: () => void }) {
  const { row, day } = selected
  const gap = Math.abs(Number(day.difference))

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">{row.collaborator.name}</h3>
          <p className="text-sm text-muted">{formatDateWithWeekday(day.date)} — {formatHours(day.executed)}</p>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={onClose}>
          Fechar
        </Button>
      </div>

      <StatusBadge status={day.status} />

      {day.launch_verification && (
        <div
          className={cn(
            'space-y-2 rounded-md px-3 py-2 text-sm',
            day.status === 'excess' ? 'bg-sky-50 text-sky-950' : 'bg-amber-50 text-amber-900',
          )}
        >
          <p>{day.launch_verification.message}</p>
          {(day.launch_verification.tasks?.length ?? 0) > 0 && (
            <ul className="space-y-1 text-amber-950">
              {day.launch_verification.tasks!.map((task) => (
                <li key={task.task_id}>
                  #{task.task_id} — {task.title} · {task.state_label}
                  {task.completed_hours != null ? ` · executadas: ${formatHours(task.completed_hours)}` : ''}
                  {task.estimated_hours != null ? ` · estimadas: ${formatHours(task.estimated_hours)}` : ''}
                  {'effective_hours' in task && task.effective_hours != null
                    ? ` · contabilizadas: ${formatHours(task.effective_hours as number)}`
                    : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {day.status === 'missing' && day.tasks.length === 0 && !day.launch_verification && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
          Não existe lançamento para este dia na importação do Azure Boards.
        </p>
      )}

      {day.tasks.length === 0 ? (
        day.status !== 'missing' && (
          <p className="text-sm text-muted">Nenhuma Task lançada neste dia.</p>
        )
      ) : (
        <>
          <p className="text-sm font-medium">Tasks:</p>
          <ul className="space-y-2">
            {day.tasks.map((task) => (
              <li key={task.task_id} className="rounded-md border border-line p-3">
                <p className="font-medium">
                  #{task.task_id} — {task.title}
                </p>
                <p className="text-sm text-muted">
                  {task.activity_category ? `${task.activity_category} · ` : ''}
                  {task.completed_hours != null ? formatHours(task.completed_hours) : 'Horas executadas não informadas'}
                  {task.state ? ` · ${formatAzureState(task.state)}` : ''}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="space-y-1 text-sm">
        <p>
          <span className="font-medium">Total executado:</span> {formatHours(day.executed)}
        </p>
        <p>
          <span className="font-medium">Esperado:</span> {formatHours(day.expected)}
        </p>
        {day.status === 'excess' && (
          <p>
            <span className="font-medium">Excedente:</span> {formatHours(gap)}
          </p>
        )}
        {(day.status === 'missing' || day.status === 'incomplete') && (
          <p>
            <span className="font-medium">Faltam:</span> {formatHours(gap)}
          </p>
        )}
      </div>
    </div>
  )
}

function MonthSchedulePanel({
  schedule,
  year,
  month,
}: {
  schedule: MonthScheduleContext
  year: number
  month: number
}) {
  const { summary } = schedule
  const chips = [
    { label: 'Atestados (períodos)', value: summary.medical_certificate, highlight: summary.medical_certificate > 0 },
    { label: 'Férias', value: summary.vacation },
    { label: 'Liberação — colaborador', value: summary.work_release },
    { label: 'Liberação — calendário (equipe)', value: summary.calendar_work_release },
    { label: 'Folgas / licenças / outros', value: summary.day_off + summary.leave + summary.other },
  ]

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Calendário e ausências — {periodShort(year, month)}</h3>
          <p className="mt-1 text-sm text-muted">
            Dias em que não se exige lançamento no Azure (feriado, liberação, atestado, etc.). Use para interpretar
            inconsistências de “sem lançamento”.
          </p>
        </div>
        <Link to="/calendario" className="text-sm text-accent hover:underline">
          Gerenciar calendário →
        </Link>
      </div>

      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <span
            key={chip.label}
            className={cn(
              'rounded-full border px-3 py-1 text-xs',
              chip.highlight ? 'border-amber-300 bg-amber-50 text-amber-950' : 'border-line bg-paper text-muted',
            )}
          >
            {chip.label}: <strong className="font-semibold text-ink">{chip.value}</strong>
          </span>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold">Exceções de calendário do mês</h4>
          <p className="text-xs text-muted">Feriados, pontos facultativos e liberações para toda a equipe.</p>
          {schedule.calendar_exceptions.length === 0 ? (
            <p className="mt-2 text-sm text-muted">Nenhuma exceção cadastrada neste mês.</p>
          ) : (
            <Table className="mt-2">
              <thead>
                <tr>
                  <Th>Data</Th>
                  <Th>Tipo</Th>
                  <Th>Descrição</Th>
                </tr>
              </thead>
              <tbody>
                {schedule.calendar_exceptions.map((row) => (
                  <tr key={row.id}>
                    <Td>{formatDateWithWeekday(row.date)}</Td>
                    <Td>{EXCEPTION_LABEL[row.type] ?? row.type}</Td>
                    <Td>{row.description}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </div>

        <div>
          <h4 className="text-sm font-semibold">Ausências e liberações por colaborador</h4>
          <p className="text-xs text-muted">Períodos individuais (atestado, férias, liberação de expediente, etc.).</p>
          {schedule.absences.length === 0 ? (
            <p className="mt-2 text-sm text-muted">Nenhuma ausência cadastrada que caia neste mês.</p>
          ) : (
            <Table className="mt-2">
              <thead>
                <tr>
                  <Th>Colaborador</Th>
                  <Th>Período</Th>
                  <Th>Tipo</Th>
                  <Th>Observação</Th>
                </tr>
              </thead>
              <tbody>
                {schedule.absences.map((row) => (
                  <tr key={row.id}>
                    <Td>
                      <Link className="text-accent hover:underline" to={`/colaboradores/${row.collaborator_id}`}>
                        {row.collaborator_name}
                      </Link>
                    </Td>
                    <Td>{formatDateRange(row.start_date, row.end_date)}</Td>
                    <Td>{ABSENCE_TYPE_LABEL[row.type] ?? row.type}</Td>
                    <Td>{row.note || '—'}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </div>
      </div>
    </Card>
  )
}

function Metric({ title, value, accent }: { title: string; value: string; accent?: 'ok' | 'warn' }) {
  return (
    <Card
      className={cn(
        accent === 'ok' && 'bg-emerald-50',
        accent === 'warn' && 'bg-amber-50',
      )}
    >
      <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </Card>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: [string, string][]
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-muted">{label}</span>
      <select
        className="h-10 w-full rounded-md border border-line bg-white px-3"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue || 'all'} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  )
}
