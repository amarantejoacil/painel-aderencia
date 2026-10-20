import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import {
  api,
  type ConferenceDay,
  type ConferenceReport,
  type TimeEntryContext,
  type TimeEntryDay,
  type TimeEntryPreview,
  type TimeEntryRegistered,
  type TimeEntryStory,
} from '@/lib/api'
import { formatAzureState, formatDate, formatHours } from '@/lib/format'
import { ConferenceSection } from '@/pages/timeEntries/ConferenceSection'
import { PrepareLaunchModal } from '@/pages/timeEntries/PrepareLaunchModal'
import { fieldClass, newOperationKey, TimeEntryShell } from '@/pages/timeEntries/TimeEntryShell'
import { SuggestSection } from '@/pages/timeEntries/SuggestSection'

const ORIGIN_LABEL: Record<string, string> = {
  module: 'Criada neste módulo',
  azure: 'Já existente no Azure',
}

export function MyEntriesPage() {
  const [context, setContext] = useState<TimeEntryContext | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [linking, setLinking] = useState(false)
  const [storyId, setStoryId] = useState('')
  const [project, setProject] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TimeEntryStory[]>([])
  const [candidate, setCandidate] = useState<TimeEntryStory | null>(null)
  const [busy, setBusy] = useState(false)

  const [referenceDate, setReferenceDate] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [hours, setHours] = useState('8')
  const [operationKey, setOperationKey] = useState(newOperationKey)
  const [preview, setPreview] = useState<TimeEntryPreview | null>(null)
  const [registered, setRegistered] = useState<TimeEntryRegistered | null>(null)
  const [justification, setJustification] = useState('')
  const [day, setDay] = useState<TimeEntryDay | null>(null)
  const [dayLoading, setDayLoading] = useState(false)
  const [conference, setConference] = useState<ConferenceReport | null>(null)
  const [prepareDay, setPrepareDay] = useState<ConferenceDay | null>(null)
  const [conferenceReloadAt, setConferenceReloadAt] = useState(0)

  function loadContext() {
    return api
      .timeEntryContext()
      .then((data) => {
        setContext(data)
        setProject((current) => current || data.projects[0] || '')
        setReferenceDate((current) => current || data.today)
        setHours(String(Number(data.suggested_hours) || 8))
      })
      .catch((err: Error) => setError(err.message))
  }

  function loadDay(date: string) {
    if (!date) return
    setDayLoading(true)
    api
      .timeEntryDay(date)
      .then(setDay)
      .catch((err: Error) => setError(err.message))
      .finally(() => setDayLoading(false))
  }

  useEffect(() => {
    void loadContext()
  }, [])

  useEffect(() => {
    if (referenceDate) loadDay(referenceDate)
  }, [referenceDate])

  const conferenceDay = conference?.days.find((item) => item.date === referenceDate) ?? null
  const existingTitles = useMemo(() => {
    const fromConference = conferenceDay?.tasks.map((item) => item.title) ?? []
    if (fromConference.length > 0) return fromConference
    return day?.tasks.map((item) => item.title) ?? []
  }, [conferenceDay, day])

  function prepareLaunch(item: ConferenceDay) {
    setPrepareDay(item)
    setError(null)
  }

  function applySuggestion(value: { title: string; description: string; hours: string | null }) {
    setTitle(value.title)
    setDescription(value.description)
    if (value.hours) setHours(value.hours)
    setOperationKey(newOperationKey())
    setPreview(null)
    setNotice('Sugestão aplicada ao formulário. Revise o texto antes de confirmar o lançamento.')
    document.getElementById('novo-lancamento')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function consultById() {
    const id = Number(storyId)
    if (!Number.isInteger(id) || id <= 0) {
      setError('Informe o ID numérico da User Story.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      setCandidate(await api.lookupTimeEntryStory(id))
    } catch (err) {
      setCandidate(null)
      setError(err instanceof Error ? err.message : 'Não foi possível consultar a história.')
    } finally {
      setBusy(false)
    }
  }

  async function search() {
    if (query.trim().length < 3) {
      setError('Informe ao menos 3 caracteres do título.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      setResults(await api.searchTimeEntryStories(project, query.trim()))
    } catch (err) {
      setResults([])
      setError(err instanceof Error ? err.message : 'Não foi possível pesquisar.')
    } finally {
      setBusy(false)
    }
  }

  async function confirmStory() {
    if (!candidate) return
    setBusy(true)
    setError(null)
    try {
      const data = await api.saveTimeEntryStory(candidate.id)
      setContext(data)
      setLinking(false)
      setCandidate(null)
      setResults([])
      setNotice('História vinculada. Ela permanece até você alterá-la.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível salvar o vínculo.')
    } finally {
      setBusy(false)
    }
  }

  async function removeStory() {
    if (!window.confirm('Remover o vínculo com a User Story?')) return
    setBusy(true)
    setError(null)
    try {
      await api.clearTimeEntryStory()
      await loadContext()
      setNotice('Vínculo removido.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível remover o vínculo.')
    } finally {
      setBusy(false)
    }
  }

  async function improve() {
    if (!description.trim()) {
      setError('Descreva brevemente o que foi realizado antes de usar a IA.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = await api.improveTimeEntryDescription(description)
      setDescription(result.text)
      setNotice('Descrição reescrita. Revise o texto antes de registrar.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível melhorar a descrição.')
    } finally {
      setBusy(false)
    }
  }

  async function repeatLast() {
    setBusy(true)
    setError(null)
    try {
      const last = await api.lastTimeEntry()
      setTitle(last.title)
      setDescription(last.description)
      setHours(String(Number(last.estimated_hours)))
      setNotice('Último lançamento copiado. A data de referência continua a selecionada.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível repetir o lançamento.')
    } finally {
      setBusy(false)
    }
  }

  function draft(confirm = false, acknowledge = false) {
    return {
      reference_date: referenceDate,
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
    setNotice(null)
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
      setRegistered(result)
      setTitle('')
      setDescription('')
      setOperationKey(newOperationKey())
      setNotice(result.message)
      loadDay(referenceDate)
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

  const story = context?.story
  const blocked = Boolean(story?.blocked_reason)
  const canLaunch = Boolean(story && !blocked && context?.azure_configured)

  return (
    <TimeEntryShell
      title="Meus Apontamentos"
      description="Registre a atividade do dia na User Story que você criou no Azure DevOps. O sistema não cria histórias."
    >
      {error ? (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</Card>
      ) : null}
      {notice ? <Card className="border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{notice}</Card> : null}
      {registered ? (
        <Card className="border-emerald-200 p-4 text-sm">
          <p className="font-medium">{registered.title}</p>
          <p className="mt-1">Data de referência: {formatDate(registered.reference_date)}</p>
          <p>ID: {registered.task_id ?? '—'}</p>
          {registered.url ? (
            <a className="mt-2 inline-block font-medium text-accent underline" href={registered.url} target="_blank" rel="noreferrer">
              Abrir a Task no Azure DevOps
            </a>
          ) : null}
        </Card>
      ) : null}
      {context?.azure_error ? (
        <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">{context.azure_error}</Card>
      ) : null}

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">História vinculada</h3>
            <p className="text-sm text-muted">O vínculo permanece até a alteração manual, inclusive na troca do mês.</p>
          </div>
          {story ? (
            <div className="flex gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={() => setLinking(true)}>
                Alterar história
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => void removeStory()}>
                Remover vínculo
              </Button>
            </div>
          ) : (
            <Button type="button" size="sm" onClick={() => setLinking(true)}>
              Vincular história
            </Button>
          )}
        </div>

        {story ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Info label="ID" value={String(story.id)} />
            <Info label="Estado" value={formatAzureState(story.state)} />
            <Info label="Título" value={story.title} />
            <Info label="Projeto Azure" value={story.project} />
            <Info label="Area Path" value={story.area_path || '—'} />
            <Info label="Iteration Path" value={story.iteration_path || '—'} />
            {story.url ? (
              <a className="text-sm font-medium text-accent underline" href={story.url} target="_blank" rel="noreferrer">
                Abrir no Azure DevOps
              </a>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-muted">Nenhuma User Story vinculada.</p>
        )}
        {story?.blocked_reason ? (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-950">{story.blocked_reason}</p>
        ) : null}

        {linking || !story ? (
          <div className="space-y-4 border-t border-line pt-4">
            <div className="grid gap-3 md:grid-cols-[8rem_1fr_auto]">
              <div>
                <Label htmlFor="story-id">ID</Label>
                <Input id="story-id" inputMode="numeric" value={storyId} onChange={(event) => setStoryId(event.target.value)} />
              </div>
              <div className="md:col-span-1" />
              <div className="flex items-end">
                <Button type="button" variant="secondary" disabled={busy} onClick={() => void consultById()}>
                  Consultar ID
                </Button>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-[14rem_1fr_auto]">
              <div>
                <Label htmlFor="story-project">Projeto</Label>
                <select
                  id="story-project"
                  className={fieldClass}
                  value={project}
                  onChange={(event) => setProject(event.target.value)}
                >
                  {(context?.projects ?? []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="story-query">Título</Label>
                <Input id="story-query" value={query} onChange={(event) => setQuery(event.target.value)} />
              </div>
              <div className="flex items-end">
                <Button type="button" variant="secondary" disabled={busy} onClick={() => void search()}>
                  Pesquisar
                </Button>
              </div>
            </div>
            {results.length ? (
              <ul className="divide-y divide-line rounded-md border border-line">
                {results.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-paper"
                      onClick={() => setCandidate(item)}
                    >
                      <span>
                        <span className="font-medium">#{item.id}</span> {item.title}
                      </span>
                      <span className="text-muted">{formatAzureState(item.state)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {candidate ? (
              <div className="rounded-md border border-line bg-paper p-3 text-sm">
                <p className="font-medium">
                  #{candidate.id} · {candidate.title}
                </p>
                <p className="mt-1 text-muted">
                  {candidate.project} · {formatAzureState(candidate.state)}
                </p>
                {candidate.blocked_reason ? (
                  <p className="mt-2 text-amber-950">{candidate.blocked_reason}</p>
                ) : null}
                <div className="mt-3 flex gap-2">
                  <Button type="button" disabled={busy} onClick={() => void confirmStory()}>
                    Confirmar vínculo
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setCandidate(null)}>
                    Cancelar
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </Card>

      <ConferenceSection
        today={context?.today}
        onPrepare={prepareLaunch}
        onLoaded={setConference}
        reloadAt={conferenceReloadAt}
      />

      {prepareDay && context ? (
        <PrepareLaunchModal
          day={prepareDay}
          context={context}
          dailyHours={Number(conference?.daily_hours ?? context.suggested_hours) || 8}
          onClose={() => setPrepareDay(null)}
          onRegistered={(result) => {
            setPrepareDay(null)
            setRegistered(result)
            setNotice(result.message)
            setConferenceReloadAt((value) => value + 1)
            if (referenceDate === result.reference_date) loadDay(referenceDate)
          }}
        />
      ) : null}

      <Card id="novo-lancamento" className="space-y-4 p-5">
        <h3 className="text-base font-semibold">Novo lançamento</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="reference-date">Data de referência</Label>
            <Input
              id="reference-date"
              type="date"
              value={referenceDate}
              max={context?.today}
              onChange={(event) => setReferenceDate(event.target.value)}
            />
            {referenceDate ? <p className="mt-1 text-xs text-muted">{formatDate(referenceDate)}</p> : null}
          </div>
          <div>
            <Label htmlFor="hours">Horas estimadas</Label>
            <Input id="hours" inputMode="decimal" value={hours} onChange={(event) => setHours(event.target.value)} />
          </div>
        </div>
        <div>
          <Label htmlFor="title">Título da atividade</Label>
          <Input id="title" value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="description">Descrição da atividade</Label>
          <textarea
            id="description"
            className={`${fieldClass} min-h-28`}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        <details className="rounded-md border border-line px-3 py-2 text-sm">
          <summary className="cursor-pointer font-medium">Configurações do lançamento</summary>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            <Info label="Tipo Tarefa" value={context?.defaults.task_type ?? 'Projeto'} />
            <Info label="Atividade" value={context?.defaults.activity ?? 'Gerência'} />
            <Info
              label="Horas executadas"
              value={hours.trim() ? `${hours.trim()} (igual à estimada)` : (context?.defaults.executed_hours ?? '—')}
            />
            <Info label="Horas impedimento" value={context?.defaults.impediment_hours ?? 'vazio'} />
            <Info label="Tem ou Teve impedimento?" value={context?.defaults.impediment ?? 'Não'} />
            <Info label="Estado" value={formatAzureState(context?.defaults.state ?? 'New')} />
            <Info label="Responsável" value={context?.defaults.assignee || context?.assignee_name || '—'} />
          </dl>
        </details>
        <p className="text-sm text-muted">{context?.adherence_note}</p>
        <p className="text-sm text-muted">{conference?.executed_limit_note}</p>
        {conference && conferenceDay ? (
          <p className="text-sm text-muted">
            Nesta data há {formatHours(conferenceDay.executed_hours)} executadas. Saldo de horas executadas:{' '}
            {formatHours(Math.max(0, Number(conference.daily_hours) - Number(conferenceDay.executed_hours)))}.
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" disabled={busy} onClick={() => void improve()}>
            Melhorar descrição com IA
          </Button>
          <Button type="button" variant="secondary" disabled={busy} onClick={() => void repeatLast()}>
            Repetir último lançamento
          </Button>
          <Button type="button" disabled={busy || !canLaunch} onClick={() => void openPreview()}>
            Pré-visualizar
          </Button>
        </div>
      </Card>

      <SuggestSection existingTitles={existingTitles} onApply={applySuggestion} />

      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold">Atividades do dia</h3>
          <Button type="button" variant="secondary" size="sm" disabled={dayLoading} onClick={() => loadDay(referenceDate)}>
            Atualizar
          </Button>
        </div>
        {day?.azure_error ? <p className="text-sm text-amber-950">{day.azure_error}</p> : null}
        {day?.azure_checked && day.tasks.length === 0 ? (
          <p className="text-sm text-muted">Nenhuma Task encontrada no Azure para esta data.</p>
        ) : null}
        {!day?.azure_checked && !day?.azure_error ? (
          <p className="text-sm text-muted">A consulta ao Azure ainda não foi concluída.</p>
        ) : null}
        {day && day.tasks.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>Título</Th>
                <Th>Estimadas</Th>
                <Th>Executadas</Th>
                <Th>Estado</Th>
                <Th>ID</Th>
                <Th>Origem</Th>
              </tr>
            </thead>
            <tbody>
              {day.tasks.map((task) => (
                <tr key={`${task.origin}-${task.task_id ?? task.title}`}>
                  <Td>{task.title}</Td>
                  <Td>{task.estimated_hours != null ? formatHours(task.estimated_hours) : '—'}</Td>
                  <Td>{task.executed_hours != null ? formatHours(task.executed_hours) : '—'}</Td>
                  <Td>{formatAzureState(task.state)}</Td>
                  <Td>
                    {task.url ? (
                      <a className="text-accent underline" href={task.url} target="_blank" rel="noreferrer">
                        {task.task_id}
                      </a>
                    ) : (
                      (task.task_id ?? '—')
                    )}
                  </Td>
                  <Td>{ORIGIN_LABEL[task.origin] ?? task.origin}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>

      {preview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
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
                <Label htmlFor="justification">Justificativa</Label>
                <textarea
                  id="justification"
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
                Cancelar
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </TimeEntryShell>
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
