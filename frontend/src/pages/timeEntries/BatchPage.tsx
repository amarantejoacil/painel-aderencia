import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import {
  api,
  type TimeEntryBatchItem,
  type TimeEntryBatchResult,
  type TimeEntryCalendar,
  type TimeEntryContext,
} from '@/lib/api'
import { formatDate, formatHours } from '@/lib/format'
import { fieldClass, newOperationKey, TimeEntryShell } from '@/pages/timeEntries/TimeEntryShell'
import { SuggestSection } from '@/pages/timeEntries/SuggestSection'

type Draft = {
  operationKey: string
  date: string
  title: string
  description: string
  hours: string
  exceptional: boolean
  acknowledge: boolean
  justification: string
  situation: string
}

const STATUS_LABEL: Record<string, string> = {
  incomplete: 'Incompleto',
  missing: 'Sem lançamento',
  excess: 'Excesso',
}

function pairs(raw: string | null): Map<string, string> {
  const map = new Map<string, string>()
  if (!raw) return map
  for (const part of raw.split(',')) {
    const index = part.indexOf(':')
    if (index <= 0) continue
    map.set(part.slice(0, index), part.slice(index + 1))
  }
  return map
}

const WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

function mondayOffset(iso: string): number {
  const [year, month, day] = iso.split('-').map(Number)
  const weekday = new Date(year, month - 1, day).getDay()
  return weekday === 0 ? 6 : weekday - 1
}

function dayTileClass(day: TimeEntryCalendar['days'][number], selected: boolean): string {
  if (selected) return 'border-accent bg-accent-soft text-ink'
  if (day.launch_state === 'complete') return 'border-emerald-300 bg-emerald-50 text-emerald-950'
  if (day.launch_state === 'pending') return 'border-amber-300 bg-amber-50 text-amber-950'
  switch (day.exception_type) {
    case 'holiday':
      return 'border-rose-300 bg-rose-50 text-rose-950'
    case 'optional_day':
      return 'border-sky-300 bg-sky-50 text-sky-950'
    case 'work_release':
      return 'border-teal-300 bg-teal-50 text-teal-950'
    default:
      break
  }
  if (day.absence_label) return 'border-orange-300 bg-orange-50 text-orange-950'
  if (day.weekend) return 'border-violet-300 bg-violet-50 text-violet-950'
  return 'border-line bg-white'
}

function dayNote(day: TimeEntryCalendar['days'][number]): string | null {
  if (day.exception_label) return day.exception_label
  if (day.absence_label) return day.absence_label
  if (day.weekend) return 'Fim de semana'
  if (day.launch_state === 'complete') return 'Completo'
  if (day.launch_state === 'pending') return day.status_label ?? 'Pendente'
  return null
}

export function BatchPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [calendar, setCalendar] = useState<TimeEntryCalendar | null>(null)
  const [context, setContext] = useState<TimeEntryContext | null>(null)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [suggestedTitle, setSuggestedTitle] = useState('')
  const [preview, setPreview] = useState<TimeEntryBatchItem[] | null>(null)
  const [result, setResult] = useState<TimeEntryBatchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [params] = useSearchParams()
  const seeded = useRef(false)

  useEffect(() => {
    api.timeEntryContext().then(setContext).catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    if (seeded.current) return
    const raw = params.get('dates')
    if (!raw) return
    seeded.current = true
    const dates = raw
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    const hours = pairs(params.get('hours'))
    const statuses = pairs(params.get('status'))
    if (dates[0]) {
      const [yearText, monthText] = dates[0].split('-')
      const nextYear = Number(yearText)
      const nextMonth = Number(monthText)
      if (nextYear && nextMonth) {
        setYear(nextYear)
        setMonth(nextMonth)
      }
    }
    setDrafts(
      dates.map((date) => {
        const reference = Number(hours.get(date) || '')
        return {
          operationKey: newOperationKey(),
          date,
          title: '',
          description: '',
          hours: reference > 0 ? String(reference) : '',
          exceptional: false,
          acknowledge: false,
          justification: '',
          situation: STATUS_LABEL[statuses.get(date) || ''] || '',
        }
      }),
    )
  }, [params])

  useEffect(() => {
    api
      .timeEntryCalendar(year, month)
      .then(setCalendar)
      .catch((err: Error) => setError(err.message))
  }, [year, month])

  const selectedDates = useMemo(() => new Set(drafts.map((item) => item.date)), [drafts])
  const existingTitles = useMemo(
    () =>
      drafts
        .map((item) => item.title.trim())
        .filter((title) => title.length >= 8 && !/^empty\s*:/i.test(title) && !/^yes\.?$/i.test(title)),
    [drafts],
  )

  function applyBatchSuggestion(value: { title: string; description: string; hours: string | null }) {
    setSuggestedTitle(value.title)
    setDrafts((current) =>
      current.map((item) => ({
        ...item,
        title: value.title,
        description: value.description,
        hours: value.hours ?? item.hours,
      })),
    )
  }

  function addDraft(date: string, exceptional: boolean) {
    setDrafts((current) => [
      ...current,
      {
        operationKey: newOperationKey(),
        date,
        title: '',
        description: '',
        hours: String(Number(calendar?.suggested_hours ?? context?.suggested_hours ?? 8)),
        exceptional,
        acknowledge: false,
        justification: '',
        situation: '',
      },
    ])
  }

  function toggleDay(date: string, suggested: boolean) {
    if (selectedDates.has(date)) {
      setDrafts((current) => current.filter((item) => item.date !== date))
      return
    }
    addDraft(date, !suggested)
  }

  function updateDraft(key: string, patch: Partial<Draft>) {
    setDrafts((current) => current.map((item) => (item.operationKey === key ? { ...item, ...patch } : item)))
  }

  function applyTitle() {
    const value = suggestedTitle.trim()
    if (!value) return
    setDrafts((current) => current.map((item) => (item.title.trim() ? item : { ...item, title: value })))
  }

  function copyDescription(sourceKey: string) {
    const source = drafts.find((item) => item.operationKey === sourceKey)
    if (!source) return
    setDrafts((current) =>
      current.map((item) =>
        item.operationKey === sourceKey || item.description.trim()
          ? item
          : { ...item, description: source.description },
      ),
    )
  }

  async function improve(key: string) {
    const draft = drafts.find((item) => item.operationKey === key)
    if (!draft?.description.trim()) {
      setError('Informe a descrição do dia antes de usar a IA.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const resultText = await api.improveTimeEntryDescription(draft.description)
      updateDraft(key, { description: resultText.text })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível melhorar a descrição.')
    } finally {
      setBusy(false)
    }
  }

  function payloadItems(acknowledgeFromPreview = false) {
    return drafts.map((item) => ({
      operation_key: item.operationKey,
      reference_date: item.date,
      title: item.title.trim(),
      description: item.description.trim(),
      estimated_hours: Number(item.hours),
      confirm: true,
      acknowledge_duplicate: acknowledgeFromPreview ? item.acknowledge : false,
      justification: item.justification.trim() || null,
    }))
  }

  async function openPreview() {
    const invalid = drafts.filter(
      (item) =>
        !item.title.trim() ||
        item.title.trim().length < 8 ||
        /^empty\s*:/i.test(item.title.trim()) ||
        !item.description.trim() ||
        item.description.trim().length < 20 ||
        !Number(item.hours),
    )
    if (invalid.length) {
      setError(
        'Revise todos os dias: título e descrição válidos (use Gerar com IA ou preencha manualmente) e horas informadas.',
      )
      return
    }
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const response = await api.previewTimeEntryBatch({ confirm: false, items: payloadItems() })
      setPreview(response.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível pré-visualizar o lote.')
    } finally {
      setBusy(false)
    }
  }

  async function sendBatch() {
    const pendingJustification = (preview ?? []).some((item) => {
      if (!item.duplicates.length) return false
      const draft = drafts.find((entry) => entry.operationKey === item.operation_key)
      return !draft?.acknowledge || !draft.justification.trim()
    })
    if (pendingJustification) {
      setError('Confirme a duplicidade e informe a justificativa antes de enviar o lote.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await api.registerTimeEntryBatch({ confirm: true, items: payloadItems(true) })
      setResult(response)
      setPreview(null)
      const done = new Set(
        response.items.filter((item) => item.status === 'confirmed' || item.status === 'already_confirmed').map((item) => item.operation_key),
      )
      setDrafts((current) => current.filter((item) => !done.has(item.operationKey)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível enviar o lote.')
    } finally {
      setBusy(false)
    }
  }

  const first = calendar?.days[0]
  const offset = first ? mondayOffset(first.date) : 0
  const blocked = Boolean(context?.story?.blocked_reason) || !context?.story

  return (
    <TimeEntryShell
      title="Lançamento em Lote"
      description="Prepare vários dias e envie somente depois de revisar. Dias de fim de semana, feriado, ponto facultativo ou ausência não entram sozinhos."
    >
      {error ? <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</Card> : null}
      {context?.story ? (
        <Card className="p-4 text-sm">
          História padrão: #{context.story.id} · {context.story.title}
          {context.story.blocked_reason ? (
            <p className="mt-2 text-amber-950">{context.story.blocked_reason}</p>
          ) : null}
        </Card>
      ) : (
        <Card className="p-4 text-sm text-muted">Vincule uma User Story em Meus Apontamentos antes do envio.</Card>
      )}

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap gap-3">
          <div>
            <Label htmlFor="batch-month">Mês</Label>
            <Input
              id="batch-month"
              type="number"
              min={1}
              max={12}
              value={month}
              onChange={(event) => setMonth(Number(event.target.value))}
            />
          </div>
          <div>
            <Label htmlFor="batch-year">Ano</Label>
            <Input
              id="batch-year"
              type="number"
              min={2000}
              max={2100}
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
            />
          </div>
        </div>
        <div className="grid grid-cols-7 gap-1 text-center text-xs">
          {WEEKDAYS.map((label) => (
            <div key={label} className="py-1 font-semibold text-muted">
              {label}
            </div>
          ))}
          {Array.from({ length: offset }, (_, index) => (
            <div key={`pad-${index}`} />
          ))}
          {calendar?.days.map((day) => {
            const selected = selectedDates.has(day.date)
            const note = dayNote(day)
            return (
              <button
                key={day.date}
                type="button"
                onClick={() => toggleDay(day.date, day.suggested)}
                className={`min-h-16 rounded-md border px-1 py-1 text-left ${dayTileClass(day, selected)}`}
              >
                <span className="block text-sm font-medium">{Number(day.date.slice(8, 10))}</span>
                {note ? <span className="block text-[10px] leading-tight">{note}</span> : null}
              </button>
            )
          })}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-emerald-300 bg-emerald-50" />
            Completo
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-amber-300 bg-amber-50" />
            Pendente
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-rose-300 bg-rose-50" />
            Feriado
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-sky-300 bg-sky-50" />
            Ponto facultativo
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-teal-300 bg-teal-50" />
            Liberação de expediente
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-violet-300 bg-violet-50" />
            Fim de semana
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border border-orange-300 bg-orange-50" />
            Ausência cadastrada
          </span>
        </div>
      </Card>

      {drafts.length > 0 ? (
        <SuggestSection
          batch
          existingTitles={existingTitles}
          onApply={applyBatchSuggestion}
          onBusyChange={setBusy}
        />
      ) : null}

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-64 flex-1">
            <Label htmlFor="suggested-title">Título sugerido (manual)</Label>
            <Input id="suggested-title" value={suggestedTitle} onChange={(event) => setSuggestedTitle(event.target.value)} />
          </div>
          <Button type="button" variant="secondary" onClick={applyTitle}>
            Aplicar aos dias sem título
          </Button>
        </div>
        {drafts.some((item) => item.situation) ? (
          <p className="text-sm text-muted">
            Dias trazidos da conferência. Informe o que foi realizado em cada data. Título e descrição não foram
            preenchidos.
          </p>
        ) : null}
        {drafts.length === 0 ? (
          <p className="text-sm text-muted">Selecione os dias no calendário. Nada é preenchido com atividade fictícia.</p>
        ) : null}
        <div className="space-y-4">
          {drafts.map((draft) => (
            <div key={draft.operationKey} className="space-y-2 rounded-md border border-line p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{formatDate(draft.date)}</p>
                  {draft.situation ? (
                    <p className="text-xs text-muted">
                      Situação atual: {draft.situation}. Horas de referência: {draft.hours ? `${draft.hours}h` : 'informe a estimativa'}.
                    </p>
                  ) : null}
                </div>
                {draft.exceptional ? (
                  <span className="text-xs text-amber-950">Data excepcional — seleção explícita</span>
                ) : null}
              </div>
              <Input
                aria-label={`Título ${draft.date}`}
                placeholder="Título"
                value={draft.title}
                onChange={(event) => updateDraft(draft.operationKey, { title: event.target.value })}
              />
              <textarea
                aria-label={`Descrição ${draft.date}`}
                className={`${fieldClass} min-h-20`}
                placeholder="Descrição"
                value={draft.description}
                onChange={(event) => updateDraft(draft.operationKey, { description: event.target.value })}
              />
              <div className="flex flex-wrap gap-2">
                <Input
                  className="w-28"
                  aria-label={`Horas ${draft.date}`}
                  value={draft.hours}
                  onChange={(event) => updateDraft(draft.operationKey, { hours: event.target.value })}
                />
                <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={() => void improve(draft.operationKey)}>
                  Melhorar descrição com IA
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => copyDescription(draft.operationKey)}>
                  Copiar descrição para os demais vazios
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => addDraft(draft.date, draft.exceptional)}>
                  Outro lançamento neste dia
                </Button>
              </div>
            </div>
          ))}
        </div>
        <Button type="button" disabled={busy || blocked || drafts.length === 0} onClick={() => void openPreview()}>
          Pré-visualizar lote
        </Button>
      </Card>

      {result ? (
        <Card className="space-y-2 p-5 text-sm">
          <p className="font-medium">Envio concluído</p>
          <p>
            Total {result.total} · Criadas {result.created} · Pendentes {result.pending} · Falhas {result.failed}
          </p>
          <ul className="space-y-1">
            {result.items.map((item) => (
              <li key={item.operation_key}>
                {formatDate(item.reference_date)} · {item.title} · {item.message}
                {item.url ? (
                  <>
                    {' '}
                    <a className="text-accent underline" href={item.url} target="_blank" rel="noreferrer">
                      #{item.task_id}
                    </a>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="text-muted">Itens já confirmados não são reenviados. Corrija somente o que ficou pendente ou com falha.</p>
        </Card>
      ) : null}

      {preview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="max-h-[90vh] w-full max-w-4xl space-y-3 overflow-y-auto p-5">
            <h3 className="text-base font-semibold">Confirmar lote</h3>
            <Table>
              <thead>
                <tr>
                  <Th>Data</Th>
                  <Th>Título</Th>
                  <Th>Descrição</Th>
                  <Th>Horas</Th>
                  <Th>História</Th>
                  <Th>Situação</Th>
                </tr>
              </thead>
              <tbody>
                {preview.map((item) => (
                  <tr key={item.operation_key}>
                    <Td>{formatDate(item.reference_date)}</Td>
                    <Td>{item.title}</Td>
                    <Td className="max-w-xs whitespace-pre-wrap text-xs">
                      {item.description ??
                        drafts.find((draft) => draft.operationKey === item.operation_key)?.description ??
                        '—'}
                    </Td>
                    <Td>{item.estimated_hours != null ? formatHours(item.estimated_hours) : '—'}</Td>
                    <Td>{context?.story ? `#${context.story.id}` : '—'}</Td>
                    <Td>
                      {item.message}
                      {item.duplicates.length ? (
                        <div className="mt-2 space-y-1">
                          {item.duplicates.map((hit) => (
                            <p key={`${hit.origin}-${hit.task_id ?? hit.title}`} className="text-xs">
                              {hit.title}
                              {hit.task_id ? ` #${hit.task_id}` : ''}
                            </p>
                          ))}
                          <label className="flex items-center gap-2 text-xs">
                            <input
                              type="checkbox"
                              checked={drafts.find((draft) => draft.operationKey === item.operation_key)?.acknowledge ?? false}
                              onChange={(event) =>
                                updateDraft(item.operation_key, { acknowledge: event.target.checked })
                              }
                            />
                            Registrar mesmo assim
                          </label>
                          <Input
                            placeholder="Justificativa"
                            value={drafts.find((draft) => draft.operationKey === item.operation_key)?.justification ?? ''}
                            onChange={(event) => updateDraft(item.operation_key, { justification: event.target.value })}
                          />
                        </div>
                      ) : null}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="flex gap-2">
              <Button type="button" disabled={busy} onClick={() => void sendBatch()}>
                Confirmar envio
              </Button>
              <Button type="button" variant="ghost" onClick={() => setPreview(null)}>
                Cancelar
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </TimeEntryShell>
  )
}
