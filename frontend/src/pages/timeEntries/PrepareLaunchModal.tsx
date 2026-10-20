import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  api,
  type ConferenceDay,
  type TimeEntryContext,
  type TimeEntryPreview,
  type TimeEntryRegistered,
} from '@/lib/api'
import { formatAzureState, formatDate, formatDateWithWeekday, formatHours } from '@/lib/format'
import { fieldClass, newOperationKey } from '@/pages/timeEntries/TimeEntryShell'
import { SuggestSection } from '@/pages/timeEntries/SuggestSection'

type Props = {
  day: ConferenceDay
  context: TimeEntryContext
  dailyHours: number
  onClose: () => void
  onRegistered: (result: TimeEntryRegistered) => void
}

export function PrepareLaunchModal({ day, context, dailyHours, onClose, onRegistered }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [hours, setHours] = useState('')
  const [operationKey, setOperationKey] = useState(newOperationKey)
  const [preview, setPreview] = useState<TimeEntryPreview | null>(null)
  const [justification, setJustification] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const story = context.story
  const blocked = Boolean(story?.blocked_reason)
  const canLaunch = Boolean(story && !blocked && context.azure_configured)
  const executed = Number(day.executed_hours)
  const balance = Math.max(0, dailyHours - executed)
  const existingTitles = day.tasks.map((item) => item.title)

  useEffect(() => {
    const suggested = Number(day.suggested_hours)
    setTitle('')
    setDescription('')
    setHours(suggested > 0 ? String(suggested) : '')
    setOperationKey(newOperationKey())
    setPreview(null)
    setJustification('')
    setError(null)
  }, [day.date, day.suggested_hours])

  function draft(confirm = false, acknowledge = false) {
    return {
      reference_date: day.date,
      title: title.trim(),
      description: description.trim(),
      estimated_hours: Number(hours),
      operation_key: operationKey,
      confirm,
      acknowledge_duplicate: acknowledge,
      justification: justification.trim() || null,
    }
  }

  async function openPreview() {
    setBusy(true)
    setError(null)
    try {
      setPreview(await api.previewTimeEntry(draft()))
      setJustification('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível pré-visualizar.')
    } finally {
      setBusy(false)
    }
  }

  async function register(acknowledge: boolean) {
    setBusy(true)
    setError(null)
    try {
      const result = await api.registerTimeEntry(draft(true, acknowledge))
      setPreview(null)
      onRegistered(result)
    } catch (err) {
      const apiError = err as Error & { detail?: { duplicates?: unknown[] } }
      if (apiError.detail?.duplicates?.length) {
        setError(`${apiError.message} Confirme o lançamento distinto na pré-visualização.`)
      } else {
        setError(err instanceof Error ? err.message : 'Não foi possível registrar.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <Card className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden">
          <div className="space-y-4 overflow-y-auto p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold">Preparar lançamento</h3>
                <p className="text-sm text-muted">{formatDateWithWeekday(day.date)}</p>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                Fechar
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Summary label="Situação" value={day.status_label} />
              <Summary label="Horas reconhecidas" value={formatHours(day.recognized_hours)} />
              <Summary label="Horas faltantes" value={formatHours(day.missing_hours)} />
              <Summary label="Origem" value={day.hours_source_label} />
            </div>

            <p className="text-sm text-muted">
              Estimadas {formatHours(day.estimated_hours)} · Executadas {formatHours(day.executed_hours)} · Saldo de
              horas executadas: {formatHours(balance)}. Este envio grava o mesmo valor nas horas executadas e
              estimadas ({hours.trim() ? `${hours.trim()}h` : 'informe abaixo'}).
            </p>

            {story ? (
              <p className="rounded-md border border-line bg-paper px-3 py-2 text-sm">
                Destino: #{story.id} · {story.title}
              </p>
            ) : (
              <p className="text-sm text-amber-950">Vincule uma User Story antes de registrar.</p>
            )}

            {day.tasks.length > 0 ? (
              <div className="rounded-md border border-line px-3 py-2 text-sm">
                <p className="font-medium">Registros já encontrados nesta data</p>
                <ul className="mt-2 space-y-1 text-muted">
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
              </div>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="prepare-hours">Horas estimadas</Label>
                <Input
                  id="prepare-hours"
                  inputMode="decimal"
                  value={hours}
                  onChange={(event) => setHours(event.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="prepare-date">Data de referência</Label>
                <Input id="prepare-date" type="date" value={day.date} readOnly />
              </div>
            </div>
            <div>
              <Label htmlFor="prepare-title">Título da atividade</Label>
              <Input id="prepare-title" value={title} onChange={(event) => setTitle(event.target.value)} />
            </div>
            <div>
              <Label htmlFor="prepare-description">Descrição da atividade</Label>
              <textarea
                id="prepare-description"
                className={`${fieldClass} min-h-28`}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>

            <SuggestSection
              embedded
              existingTitles={existingTitles}
              onApply={(value) => {
                setTitle(value.title)
                setDescription(value.description)
                if (value.hours) setHours(value.hours)
                setOperationKey(newOperationKey())
                setPreview(null)
              }}
            />

            {error ? <p className="text-sm text-red-800">{error}</p> : null}

            <div className="flex flex-wrap gap-2 border-t border-line pt-4">
              <Button type="button" disabled={busy || !canLaunch || !title.trim() || !hours.trim()} onClick={() => void openPreview()}>
                Pré-visualizar
              </Button>
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancelar
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {preview ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4">
          <Card className="max-h-[90vh] w-full max-w-lg space-y-3 overflow-y-auto p-5">
            <h3 className="text-base font-semibold">Confirmar lançamento</h3>
            <Info label="História de destino" value={`#${preview.story_id} · ${preview.story_title}`} />
            <Info label="Título" value={preview.title} />
            <Info label="Descrição" value={preview.description || '—'} />
            <Info label="Data de referência" value={formatDate(preview.reference_date)} />
            <Info label="Horas estimadas" value={formatHours(preview.estimated_hours)} />
            <Info label="Horas executadas" value={formatHours(preview.estimated_hours)} />
            <Info label="Tipo Tarefa" value={preview.task_type} />
            <Info label="Atividade" value={preview.activity} />
            <Info label="Responsável" value={preview.assignee} />
            <Info label="Estado após registro" value={formatAzureState(preview.state)} />
            {preview.duplicates.length ? (
              <div className="space-y-2 rounded-md bg-amber-50 p-3 text-sm text-amber-950">
                <p>Possível duplicidade. O registro só segue com a sua confirmação e uma justificativa.</p>
                {preview.duplicates.map((item) => (
                  <p key={`${item.origin}-${item.task_id ?? item.title}`}>
                    {item.origin === 'module' ? 'Módulo' : 'Azure'} · {item.title}
                    {item.task_id ? ` · #${item.task_id}` : ''}
                    {item.estimated_hours != null ? ` · ${formatHours(item.estimated_hours)}` : ''}
                  </p>
                ))}
                <Label htmlFor="prepare-justification">Justificativa</Label>
                <textarea
                  id="prepare-justification"
                  className={`${fieldClass} min-h-20`}
                  value={justification}
                  onChange={(event) => setJustification(event.target.value)}
                />
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={busy || (preview.duplicates.length > 0 && !justification.trim())}
                onClick={() => void register(preview.duplicates.length > 0)}
              >
                Registrar no Azure
              </Button>
              <Button type="button" variant="ghost" onClick={() => setPreview(null)}>
                Voltar
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </>
  )
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line px-3 py-2">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="text-sm">{value}</p>
    </div>
  )
}
