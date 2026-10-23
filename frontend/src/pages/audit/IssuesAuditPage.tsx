import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import {
  api,
  type IssueAuditDetail,
  type IssueAuditIssue,
  type IssueAuditSummary,
  type IssueAuditValidationRecord,
} from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const STATUS_LABEL: Record<IssueAuditSummary['status'], string> = {
  queued: 'Na fila',
  running: 'Em andamento',
  complete: 'Completa',
  partial: 'Incompleta',
  failed: 'Falhou',
  cancelled: 'Cancelada',
  ambiguous: 'Identidade ambígua',
}

type SortKey = 'id' | 'title' | 'assigned_to' | 'state' | 'comment_count' | 'person_comment_count' | 'person_commented'

type AuditProfile = {
  id: string
  label: string
  organization: string
  project: string
  work_item_type: string
  comment_strategy: 'history' | 'comments_api'
}

const FALLBACK_PROFILES: AuditProfile[] = [
  {
    id: 'cti-gabinete',
    label: 'Gestão Gabinete Coordenadoria — CTI',
    organization: 'CTI',
    project: 'Gestão Gabinete Coordenadoria',
    work_item_type: 'Issue',
    comment_strategy: 'history',
  },
  {
    id: 'nucleo-pac',
    label: 'Núcleo de Aquisições – PAC — Nucleo',
    organization: 'Nucleo',
    project: 'Núcleo de Aquisições - PAC',
    work_item_type: 'Issue',
    comment_strategy: 'comments_api',
  },
]

function profileFromQuery(data: IssueAuditDetail): string {
  if (data.profile_id === 'nucleo-pac' || data.profile_id === 'cti-gabinete') return data.profile_id
  if (data.organization === 'Nucleo') return 'nucleo-pac'
  return 'cti-gabinete'
}

function formatCuiaba(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('pt-BR', {
    timeZone: 'America/Cuiaba',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function IssuesAuditPage() {
  const params = useParams()
  const queryId = params.queryId ? Number(params.queryId) : null
  const [profiles, setProfiles] = useState<AuditProfile[]>(FALLBACK_PROFILES)
  const [profileId, setProfileId] = useState('cti-gabinete')
  const [year, setYear] = useState(2025)
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [states, setStates] = useState<string[]>([])
  const [periodCriterion, setPeriodCriterion] = useState<'created' | 'changed'>('created')
  const [personName, setPersonName] = useState('Marcia Regina De Carvalho Buhr')
  const [identityId, setIdentityId] = useState<string | null>(null)
  const [uniqueName, setUniqueName] = useState<string | null>(null)
  const [commentScope, setCommentScope] = useState<'all' | 'period'>('all')
  const [requester, setRequester] = useState('')
  const [peopleMessage, setPeopleMessage] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<Array<{ id: string | null; display_name: string | null; unique_name: string | null }>>([])
  const [query, setQuery] = useState<IssueAuditDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const [commentedFilter, setCommentedFilter] = useState<'all' | 'sim' | 'nao'>('all')
  const [sortKey, setSortKey] = useState<SortKey>('person_comment_count')
  const [sortDesc, setSortDesc] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [discussionFilter, setDiscussionFilter] = useState<'all' | 'person'>('all')
  const [validation, setValidation] = useState<IssueAuditValidationRecord | null>(null)
  const [validating, setValidating] = useState(false)
  const [includeAllDiscussions, setIncludeAllDiscussions] = useState(false)
  const [exportBusy, setExportBusy] = useState(false)

  useEffect(() => {
    if (!queryId) return
    let stop = false
    const load = async () => {
      try {
        const data = await api.getIssueAudit(queryId)
        if (stop) return
        setQuery(data)
        setProfileId(profileFromQuery(data))
        setYear(data.year)
        setPeriodStart(data.period_start ?? '')
        setPeriodEnd(data.period_end ?? '')
        setStateFilter(data.state_filter ?? '')
        setPeriodCriterion(data.period_criterion)
        setPersonName(data.person_name)
        setIdentityId(data.person_identity_id)
        setUniqueName(data.person_unique_name)
        setCommentScope(data.comment_scope)
        setRequester(data.requester ?? '')
        const val = await api.getIssueAuditValidation(queryId)
        if (!stop) setValidation(val)
      } catch (err) {
        if (!stop) setError((err as Error).message)
      }
    }
    void load()
    return () => {
      stop = true
    }
  }, [queryId])

  useEffect(() => {
    void api.auditProfiles().then(setProfiles).catch(() => setProfiles(FALLBACK_PROFILES))
  }, [])

  const profile = profiles.find((item) => item.id === profileId) ?? FALLBACK_PROFILES[0]

  useEffect(() => {
    if (profile.comment_strategy !== 'comments_api') return
    let stop = false
    void api
      .auditStates(profile.organization, profile.project, profile.work_item_type)
      .then((names) => {
        if (!stop) setStates(names)
      })
      .catch(() => {
        if (!stop) setStates([])
      })
    return () => {
      stop = true
    }
  }, [profile.id, profile.comment_strategy, profile.organization, profile.project, profile.work_item_type])

  useEffect(() => {
    if (!query || (query.status !== 'queued' && query.status !== 'running')) return
    const timer = window.setInterval(() => {
      void api.getIssueAudit(query.id).then(setQuery).catch((err: Error) => setError(err.message))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [query])

  const selectProfile = (id: string) => {
    setProfileId(id)
    setIdentityId(null)
    setUniqueName(null)
    setCandidates([])
    setPeopleMessage(null)
    if (id !== 'nucleo-pac') setStateFilter('')
  }

  const searchPerson = async () => {
    setPeopleMessage(null)
    setCandidates([])
    setBusy(true)
    try {
      const found = await api.auditPeople(profile.organization, personName.trim())
      setPeopleMessage(found.message)
      if (found.status === 'matched' && found.people[0]) {
        setIdentityId(found.people[0].id)
        setUniqueName(found.people[0].unique_name)
        setPersonName(found.people[0].display_name || personName)
      } else if (found.status === 'ambiguous') {
        setIdentityId(null)
        setUniqueName(null)
        setCandidates(found.people)
      } else if (found.status === 'unavailable') {
        setIdentityId(null)
        setUniqueName(null)
      } else {
        setIdentityId(null)
        setUniqueName(null)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const exportExcel = async () => {
    if (!query) return
    setExportBusy(true)
    setError(null)
    try {
      if (includeAllDiscussions) {
        const readiness = await api.getIssueAuditExportReadiness(query.id)
        if (!readiness.exportable_full) {
          const message =
            readiness.message ??
            `Gravados ${readiness.comments_stored_full} comentários completos; a consulta analisou ${readiness.comments_analyzed}.`
          if (
            readiness.can_backfill &&
            window.confirm(`${message}\n\nDeseja reprocessar os comentários completos agora? Isso pode levar vários minutos.`)
          ) {
            await api.backfillIssueAuditAllComments(query.id)
            let refreshed = await api.getIssueAudit(query.id)
            setQuery(refreshed)
            const deadline = Date.now() + 30 * 60 * 1000
            while (
              refreshed.status === 'queued' ||
              refreshed.status === 'running'
            ) {
              if (Date.now() > deadline) {
                setError('Reprocessamento ainda em andamento. Aguarde e exporte novamente com a opção marcada.')
                return
              }
              await new Promise((resolve) => window.setTimeout(resolve, 2000))
              refreshed = await api.getIssueAudit(query.id)
              setQuery(refreshed)
            }
            const ready = await api.getIssueAuditExportReadiness(query.id)
            if (!ready.exportable_full) {
              setError(ready.message ?? 'Reprocessamento concluído, mas a exportação completa ainda não está disponível.')
              return
            }
          } else {
            setError(message)
            return
          }
        }
      }
      const url = api.issueAuditExportUrl(query.id, { includeAllDiscussions: includeAllDiscussions })
      window.open(url, '_blank')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setExportBusy(false)
    }
  }

  const start = async () => {
    setError(null)
    setBusy(true)
    try {
      const created = await api.createIssueAudit({
        organization: profile.organization,
        project: profile.project,
        work_item_type: profile.work_item_type,
        period_criterion: periodCriterion,
        year,
        comment_scope: commentScope,
        person_name: personName.trim(),
        person_identity_id: identityId,
        person_unique_name: uniqueName,
        requester: requester.trim() || null,
        profile_id: profile.id,
        state: profile.comment_strategy === 'comments_api' && stateFilter ? stateFilter : null,
        period_start: periodStart || null,
        period_end: periodEnd || null,
      })
      const detail = await api.getIssueAudit(created.id)
      setQuery(detail)
      window.history.replaceState(null, '', `/auditoria/issues/${created.id}`)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const issues = query?.result?.issues ?? []
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    const filtered = issues.filter((issue) => {
      if (commentedFilter === 'sim' && !issue.person_commented) return false
      if (commentedFilter === 'nao' && issue.person_commented) return false
      if (!term) return true
      return String(issue.id).includes(term) || issue.title.toLowerCase().includes(term)
    })
    const sorted = [...filtered].sort((left, right) => compareIssues(left, right, sortKey))
    return sortDesc ? sorted.reverse() : sorted
  }, [issues, search, commentedFilter, sortKey, sortDesc])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc((current) => !current)
    else {
      setSortKey(key)
      setSortDesc(key !== 'title' && key !== 'assigned_to' && key !== 'state')
    }
  }

  const running = query?.status === 'queued' || query?.status === 'running'

  const runValidation = async () => {
    if (!query) return
    setValidating(true)
    setError(null)
    try {
      const data = await api.runIssueAuditValidation(query.id)
      setValidation(data)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setValidating(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Auditoria Azure DevOps</p>
          <h1 className="text-2xl font-semibold">Auditoria de Issues</h1>
        </div>
        <Link className="text-sm text-accent" to="/auditoria/historico">
          Histórico de consultas
        </Link>
      </div>

      <Card>
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Perfil">
            <select
              className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              value={profile.id}
              onChange={(event) => selectProfile(event.target.value)}
            >
              {profiles.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Coleção">
            <Input value={profile.organization} readOnly />
          </Field>
          <Field label="Projeto">
            <Input value={profile.project} readOnly />
          </Field>
          <Field label="Ano">
            <Input type="number" min={2000} max={2100} value={year} onChange={(event) => setYear(Number(event.target.value))} />
          </Field>
          <Field label="Critério de período">
            <select className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm" value={periodCriterion} onChange={(event) => setPeriodCriterion(event.target.value as 'created' | 'changed')}>
              <option value="created">Issues criadas no ano</option>
              <option value="changed">Issues alteradas no ano</option>
            </select>
          </Field>
          <Field label="Comentários">
            <select className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm" value={commentScope} onChange={(event) => setCommentScope(event.target.value as 'all' | 'period')}>
              <option value="all">Todo o histórico</option>
              <option value="period">Apenas no período selecionado</option>
            </select>
          </Field>
          <Field label="Início do período (opcional)">
            <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
          </Field>
          <Field label="Fim do período (opcional)">
            <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
          </Field>
          {profile.comment_strategy === 'comments_api' && (
            <Field label="Estado">
              <select className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm" value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
                <option value="">Todos</option>
                {states.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Pessoa pesquisada">
            <Input value={personName} onChange={(event) => { setPersonName(event.target.value); setIdentityId(null); setUniqueName(null) }} />
          </Field>
          <Field label="Solicitante (opcional)">
            <Input value={requester} onChange={(event) => setRequester(event.target.value)} placeholder="Sem login no painel" />
          </Field>
        </div>
        <p className="mt-2 text-xs text-muted">
          Tipo de Work Item: {profile.work_item_type}. Sem intervalo, a consulta usa o ano selecionado.
          {profile.comment_strategy === 'comments_api'
            ? ' Os comentários deste perfil vêm da API do projeto.'
            : ' Os comentários deste perfil vêm do histórico do Work Item.'}
        </p>
        {identityId && <p className="mt-2 text-xs text-muted">Identidade selecionada: {uniqueName || identityId}</p>}
        {peopleMessage && <p className="mt-2 text-sm text-amber-900">{peopleMessage}</p>}
        {candidates.length > 0 && (
          <div className="mt-3 flex flex-col gap-2">
            {candidates.map((person) => (
              <button
                key={`${person.id}-${person.unique_name}`}
                type="button"
                className="rounded-md border border-line px-3 py-2 text-left text-sm hover:bg-paper"
                onClick={() => {
                  setIdentityId(person.id)
                  setUniqueName(person.unique_name)
                  if (person.display_name) setPersonName(person.display_name)
                  setCandidates([])
                  setPeopleMessage(null)
                }}
              >
                {person.display_name} {person.unique_name ? `· ${person.unique_name}` : ''}
              </button>
            ))}
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={() => void searchPerson()} disabled={busy || personName.trim().length < 2}>
            Buscar pessoa
          </Button>
          <Button type="button" onClick={() => void start()} disabled={busy || running}>
            Consultar
          </Button>
          {running && query && (
            <Button type="button" variant="danger" onClick={() => void api.cancelIssueAudit(query.id)}>
              Cancelar
            </Button>
          )}
        </div>
      </Card>

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

      {query && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">{STATUS_LABEL[query.status]}</p>
              <p className="text-xs text-muted">Consulta {query.id} · {formatDateTime(query.created_at)}</p>
            </div>
            <div className="flex gap-2">
              {query.failure_count > 0 && !running && (
                <Button type="button" variant="secondary" onClick={() => void api.retryIssueAudit(query.id).then(() => api.getIssueAudit(query.id).then(setQuery))}>
                  Tentar falhas novamente
                </Button>
              )}
              {!running && query.result && (
                <>
                  <Button type="button" variant="secondary" disabled={validating} onClick={() => void runValidation()}>
                    Validar consulta
                  </Button>
                  <Link className="inline-flex h-10 items-center rounded-md border border-line px-4 text-sm" to={`/auditoria/issues/${query.id}/validacao`}>
                    Conferência
                  </Link>
                  <label className="inline-flex items-center gap-2 text-sm">
                    <input
                      checked={includeAllDiscussions}
                      className="size-4 rounded border-line"
                      type="checkbox"
                      onChange={(event) => setIncludeAllDiscussions(event.target.checked)}
                    />
                    Incluir todas as discussões no Excel
                  </label>
                  <Button type="button" disabled={exportBusy} onClick={() => void exportExcel()}>
                    {exportBusy ? 'Exportando…' : 'Exportar Excel'}
                  </Button>
                </>
              )}
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-paper">
            <div className="h-full bg-accent" style={{ width: `${running ? query.progress_percent : 100}%` }} />
          </div>
          <p className="mt-3 text-xs text-muted">
            Pessoa pesquisada: <span className="font-medium text-ink">{query.person_name}</span>
          </p>
          <div className="mt-2 grid gap-2 lg:grid-cols-5">
            <Metric
              label="Issues no critério (geral)"
              hint="Total retornado pelo WIQL — todas as Issues do filtro, independente de comentários."
              value={query.issues_found}
            />
            <Metric
              label="Issues processadas (geral)"
              hint="Work items lidos no Azure (com sucesso ou falha parcial por Issue)."
              value={query.issues_processed}
            />
            <Metric
              label={query.profile_id === 'nucleo-pac' ? 'Comentários disponíveis (geral)' : 'Comentários no histórico (geral)'}
              hint={
                query.profile_id === 'nucleo-pac'
                  ? 'Todos os autores — comentários publicados na API do projeto, conforme escopo da consulta.'
                  : 'Todos os autores — revisões com texto em System.History, conforme escopo da consulta.'
              }
              value={query.comments_analyzed}
            />
            <Metric
              label={`Comentários de ${query.person_name}`}
              hint="Somente comentários cuja autoria corresponde à pessoa pesquisada (não inclui menções no texto)."
              value={query.comments_matched}
            />
            <Metric
              label="Issues com falha"
              hint="Não foi possível ler o work item ou o histórico de comentários."
              value={query.failure_count}
            />
          </div>
          {query.error_message && <p className="mt-3 text-sm text-red-800">{query.error_message}</p>}
          {query.status === 'ambiguous' && (
            <div className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-950">
              <p>Há mais de uma identidade com esse nome. A consulta não está concluída até a seleção.</p>
              <div className="mt-2 flex flex-col gap-2">
                {(query.result?.candidates ?? []).map((person) => (
                  <button
                    key={`${person.id}-${person.unique_name}`}
                    type="button"
                    className="rounded-md border border-amber-200 bg-white px-3 py-2 text-left"
                    onClick={() =>
                      void api
                        .selectIssueAuditIdentity(query.id, {
                          identity_id: person.id,
                          unique_name: person.unique_name,
                          display_name: person.display_name,
                        })
                        .then(setQuery)
                    }
                  >
                    {person.display_name} {person.unique_name ? `· ${person.unique_name}` : ''} {person.id ? `· ${person.id}` : ''}
                  </button>
                ))}
              </div>
            </div>
          )}
          {query.limitations.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-xs text-muted">
              {query.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          {validation?.payload.metrics && (
            <div className="mt-4 rounded-md border border-line bg-paper px-3 py-2 text-sm">
              <p className="font-medium">Confiabilidade (validação amostral)</p>
              <p className="text-xs text-muted">{validation.payload.metrics.disclaimer}</p>
              <p className="mt-1">
                Cobertura WIQL: {validation.payload.metrics.coverage_consistent ? 'consistente' : 'com divergência'} · Amostra:{' '}
                {validation.payload.metrics.sample_size} · Auto divergência: {validation.payload.metrics.sample_auto_divergencia} · Manual
                conferido: {validation.payload.metrics.manual_confere}
              </p>
            </div>
          )}
        </Card>
      )}

      {query?.result && (
        <Card>
          <div className="mb-3 grid gap-2 md:grid-cols-4">
            <Metric
              label={`Issues com comentário de ${query.person_name}`}
              hint="Pelo menos um comentário da pessoa nesta Issue (coluna Comentou? = Sim)."
              value={query.result.issues_with_person}
            />
            <Metric
              label={`Issues sem comentário de ${query.person_name}`}
              hint={
                query.profile_id === 'nucleo-pac'
                  ? 'Comentários lidos, mas nenhum atribuído à pessoa pesquisada.'
                  : 'Histórico lido, mas nenhum comentário atribuído à pessoa pesquisada.'
              }
              value={query.result.issues_without_person}
            />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Pesquisar título ou ID" />
            <select className="h-10 rounded-md border border-line bg-white px-3 text-sm" value={commentedFilter} onChange={(event) => setCommentedFilter(event.target.value as 'all' | 'sim' | 'nao')}>
              <option value="all">Sim e não</option>
              <option value="sim">Somente Sim</option>
              <option value="nao">Somente Não</option>
            </select>
          </div>
          <Table>
            <thead>
              <tr>
                <SortableTh label="ID" onClick={() => toggleSort('id')} />
                <SortableTh label="Título" onClick={() => toggleSort('title')} />
                <SortableTh label="Atribuído a" onClick={() => toggleSort('assigned_to')} />
                <SortableTh label="Estado" onClick={() => toggleSort('state')} />
                <SortableTh label="Total comentários (geral)" onClick={() => toggleSort('comment_count')} />
                <SortableTh label={`Coment. ${shortPersonName(query.person_name)}`} onClick={() => toggleSort('person_comment_count')} />
                <SortableTh label="Comentou? (pessoa)" onClick={() => toggleSort('person_commented')} />
                <Th>Ação</Th>
              </tr>
            </thead>
            <tbody>
              {visible.map((issue) => (
                <Fragment key={issue.id}>
                  <tr key={issue.id}>
                    <Td>
                      {issue.url ? (
                        <a className="text-accent" href={issue.url} target="_blank" rel="noreferrer">
                          {issue.id}
                        </a>
                      ) : (
                        issue.id
                      )}
                    </Td>
                    <Td>{issue.title || '—'}</Td>
                    <Td>{issue.assigned_to || '—'}</Td>
                    <Td>{issue.state || '—'}</Td>
                    <Td>{issue.comment_count ?? 'Falha'}</Td>
                    <Td>{issue.person_comment_count}</Td>
                    <Td>
                      <span className={cn('rounded px-2 py-0.5 text-xs font-medium', issue.person_commented ? 'bg-emerald-50 text-emerald-800' : 'bg-zinc-100 text-zinc-600')}>
                        {issue.person_commented ? 'Sim' : 'Não'}
                      </span>
                    </Td>
                    <Td>
                      <button
                        type="button"
                        className="text-sm text-muted"
                        onClick={() => setExpanded(expanded === issue.id ? null : issue.id)}
                      >
                        {expanded === issue.id ? 'Ocultar' : 'Discussões'}
                      </button>
                    </Td>
                  </tr>
                  {expanded === issue.id && (
                    <tr key={`${issue.id}-comments`}>
                      <Td colSpan={8}>
                        <DiscussionList
                          issue={issue}
                          filter={discussionFilter}
                          identityId={query.person_identity_id}
                          personName={query.person_name}
                          onFilter={setDiscussionFilter}
                        />
                      </Td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  )
}

function DiscussionList({
  issue,
  filter,
  identityId,
  personName,
  onFilter,
}: {
  issue: IssueAuditIssue
  filter: 'all' | 'person'
  identityId: string | null
  personName: string
  onFilter: (value: 'all' | 'person') => void
}) {
  const storedAll = Array.isArray(issue.all_comments)
  const source = storedAll ? issue.all_comments ?? [] : issue.comments
  const shown = filter === 'person' ? issue.comments : source
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={cn('rounded-md border px-3 py-1 text-sm', filter === 'all' ? 'border-accent text-accent' : 'border-line text-muted')}
          onClick={() => onFilter('all')}
        >
          Todos os comentários
        </button>
        <button
          type="button"
          className={cn('rounded-md border px-3 py-1 text-sm', filter === 'person' ? 'border-accent text-accent' : 'border-line text-muted')}
          onClick={() => onFilter('person')}
        >
          Somente {shortPersonName(personName)}
        </button>
      </div>
      {!storedAll && filter === 'all' && (
        <p className="text-xs text-muted">Esta consulta guardou somente os comentários da pessoa pesquisada.</p>
      )}
      {issue.error && <p className="text-sm text-red-800">{issue.error}</p>}
      {shown.length === 0 && <p className="text-sm text-muted">Nenhum comentário neste filtro.</p>}
      {shown.map((comment) => {
        const fromPerson = isPersonComment(issue, comment, identityId)
        return (
          <article
            key={`${comment.id}-${comment.created_at}`}
            className={cn('rounded-md border px-3 py-2', fromPerson ? 'border-emerald-300 bg-emerald-50' : 'border-line')}
          >
            <p className="text-xs text-muted">
              {formatCuiaba(comment.created_at_local || comment.created_at)} · {comment.author}
              {fromPerson ? ' · pessoa pesquisada' : ''}
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm">{comment.text}</p>
          </article>
        )
      })}
    </div>
  )
}

function isPersonComment(
  issue: IssueAuditIssue,
  comment: IssueAuditIssue['comments'][number],
  identityId: string | null,
): boolean {
  if (comment.id && issue.comments.some((item) => item.id === comment.id)) return true
  return Boolean(identityId && comment.author_id === identityId)
}

function compareIssues(left: IssueAuditIssue, right: IssueAuditIssue, key: SortKey): number {
  const value = (issue: IssueAuditIssue) => {
    if (key === 'person_commented') return issue.person_commented ? 1 : 0
    if (key === 'comment_count') return issue.comment_count ?? -1
    return issue[key] ?? ''
  }
  const a = value(left)
  const b = value(right)
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), 'pt-BR')
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <Label>{label}</Label>
      {children}
    </label>
  )
}

function shortPersonName(fullName: string): string {
  const trimmed = fullName.trim()
  if (!trimmed) return 'pesquisada'
  const first = trimmed.split(/\s+/)[0]
  return first.length > 18 ? `${first.slice(0, 16)}…` : first
}

function Metric({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="rounded-md border border-line px-3 py-2">
      <p className="text-xs font-medium leading-snug">{label}</p>
      {hint ? <p className="mt-0.5 text-[11px] leading-snug text-muted">{hint}</p> : null}
      <p className="mt-1.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function SortableTh({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Th>
      <button type="button" className="uppercase" onClick={onClick}>
        {label}
      </button>
    </Th>
  )
}
