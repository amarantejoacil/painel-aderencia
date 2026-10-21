import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type IssueAuditValidationRecord } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

const STATUS_LABEL = {
  confere: 'Confere',
  divergencia: 'Divergência',
  nao_verificado: 'Não verificado',
}

export function IssueAuditValidationPage() {
  const params = useParams()
  const queryId = Number(params.queryId)
  const [validation, setValidation] = useState<IssueAuditValidationRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [reviewer, setReviewer] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [draft, setDraft] = useState<Record<number, { status: string; notes: string; realComments: string; realPerson: string; divergenceType: string }>>({})

  const load = async () => {
    setError(null)
    try {
      const data = await api.getIssueAuditValidation(queryId)
      setValidation(data)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  useEffect(() => {
    if (!Number.isFinite(queryId)) return
    void load()
  }, [queryId])

  const manualById = useMemo(() => {
    const map = new Map<number, IssueAuditValidationRecord['payload']['manual_reviews'][number]>()
    for (const item of validation?.payload.manual_reviews ?? []) {
      map.set(item.issue_id, item)
    }
    return map
  }, [validation])

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      const data = await api.runIssueAuditValidation(queryId)
      setValidation(data)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const saveReview = async (issueId: number) => {
    const form = draft[issueId]
    if (!form) return
    setBusy(true)
    try {
      const data = await api.saveIssueAuditManualReview(queryId, {
        issue_id: issueId,
        status: form.status as 'confere' | 'divergencia' | 'nao_verificado',
        real_comment_count: form.realComments ? Number(form.realComments) : null,
        real_person_comment_count: form.realPerson ? Number(form.realPerson) : null,
        divergence_type: form.divergenceType || null,
        notes: form.notes || null,
        reviewer: reviewer.trim() || null,
      })
      setValidation(data)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const metrics = validation?.payload.metrics
  const coverage = validation?.payload.coverage

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Auditoria Azure DevOps</p>
          <h1 className="text-2xl font-semibold">Conferência da consulta #{queryId}</h1>
        </div>
        <Link className="text-sm text-accent" to={`/auditoria/issues/${queryId}`}>
          Voltar ao resultado
        </Link>
      </div>

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

      <Card>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => void run()} disabled={busy}>
            Validar consulta
          </Button>
          {validation && (
            <Button type="button" variant="secondary" onClick={() => window.open(`/api/audit/issues/queries/${queryId}/export`, '_blank')}>
              Exportar Excel
            </Button>
          )}
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <Label className="flex flex-col gap-1 text-sm">
            Responsável pela conferência manual
            <Input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Nome do auditor" />
          </Label>
        </div>
        {validation && (
          <p className="mt-2 text-xs text-muted">
            Validação de {formatDateTime(validation.created_at)} — {validation.payload.methodology.limitation}
          </p>
        )}
      </Card>

      {metrics && (
        <Card>
          <h2 className="text-lg font-semibold">Indicadores de confiabilidade</h2>
          <p className="mt-1 text-sm text-muted">{metrics.disclaimer}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="Cobertura WIQL" value={metrics.coverage_consistent ? 'Consistente' : 'Divergente'} />
            <Metric label="Amostra" value={metrics.sample_size} />
            <Metric label="Auto — confere" value={metrics.sample_auto_confere} />
            <Metric label="Auto — divergência" value={metrics.sample_auto_divergencia} />
            <Metric label="Manual — confere" value={metrics.manual_confere} />
            <Metric label="Manual — divergência" value={metrics.manual_divergencia} />
          </div>
          {coverage && !coverage.consistent && (
            <ul className="mt-3 list-disc pl-5 text-sm text-amber-950">
              {coverage.missing_count > 0 && <li>{coverage.missing_count} ID(s) no WIQL ausentes no resultado armazenado.</li>}
              {coverage.extra_count > 0 && <li>{coverage.extra_count} ID(s) extras no resultado armazenado.</li>}
              {coverage.duplicate_stored_ids.length > 0 && <li>IDs duplicados: {coverage.duplicate_stored_ids.join(', ')}</li>}
              {coverage.wiql_limitation_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {validation && (
        <Card>
          <h2 className="mb-3 text-lg font-semibold">Amostra para conferência</h2>
          <Table>
            <thead>
              <tr>
                <Th>ID</Th>
                <Th>Original</Th>
                <Th>Reextraído</Th>
                <Th>Auto</Th>
                <Th>Manual</Th>
                <Th>Ações</Th>
              </tr>
            </thead>
            <tbody>
              {validation.payload.sample.items.map((item) => {
                const manual = manualById.get(item.issue_id)
                const form = draft[item.issue_id] ?? {
                  status: manual?.status ?? 'nao_verificado',
                  notes: manual?.notes ?? '',
                  realComments: manual?.real_comment_count != null ? String(manual.real_comment_count) : '',
                  realPerson: manual?.real_person_comment_count != null ? String(manual.real_person_comment_count) : '',
                  divergenceType: manual?.divergence_type ?? '',
                }
                return (
                  <Fragment key={item.issue_id}>
                    <tr>
                      <Td>{item.issue_id}</Td>
                      <Td>
                        {item.original.comment_count ?? '—'} / pessoa {item.original.person_comment_count ?? '—'}
                      </Td>
                      <Td>
                        {item.reextracted
                          ? `${item.reextracted.comment_count} / pessoa ${item.reextracted.person_comment_count}`
                          : '—'}
                      </Td>
                      <Td>{STATUS_LABEL[item.auto_status as keyof typeof STATUS_LABEL] ?? item.auto_status}</Td>
                      <Td>{manual ? STATUS_LABEL[manual.status] : 'Pendente'}</Td>
                      <Td>
                        {item.url && (
                          <a className="text-accent" href={item.url} target="_blank" rel="noreferrer">
                            Abrir no Azure
                          </a>
                        )}
                        <button type="button" className="ml-2 text-sm text-muted" onClick={() => setExpanded(expanded === item.issue_id ? null : item.issue_id)}>
                          Detalhes
                        </button>
                      </Td>
                    </tr>
                    {expanded === item.issue_id && (
                      <tr key={`${item.issue_id}-detail`}>
                        <Td colSpan={6}>
                          {item.divergence && <p className="text-sm text-amber-900">{item.divergence}</p>}
                          <div className="mt-2 grid gap-2 md:grid-cols-3">
                            <select
                              className="h-10 rounded-md border border-line px-2 text-sm"
                              value={form.status}
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  [item.issue_id]: { ...form, status: event.target.value },
                                }))
                              }
                            >
                              <option value="confere">Confere</option>
                              <option value="divergencia">Divergência</option>
                              <option value="nao_verificado">Não foi possível validar</option>
                            </select>
                            <Input
                              placeholder="Qtd. real comentários"
                              value={form.realComments}
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  [item.issue_id]: { ...form, realComments: event.target.value },
                                }))
                              }
                            />
                            <Input
                              placeholder="Qtd. real da pessoa"
                              value={form.realPerson}
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  [item.issue_id]: { ...form, realPerson: event.target.value },
                                }))
                              }
                            />
                            <Input
                              placeholder="Tipo de divergência"
                              value={form.divergenceType}
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  [item.issue_id]: { ...form, divergenceType: event.target.value },
                                }))
                              }
                            />
                            <Input
                              className="md:col-span-2"
                              placeholder="Observações"
                              value={form.notes}
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  [item.issue_id]: { ...form, notes: event.target.value },
                                }))
                              }
                            />
                          </div>
                          <Button type="button" className="mt-2" size="sm" disabled={busy} onClick={() => void saveReview(item.issue_id)}>
                            Salvar conferência
                          </Button>
                          <ul className="mt-3 space-y-2 text-sm">
                            {item.comments_preview.map((comment) => (
                              <li key={comment.author + (comment.created_at_local ?? '') + comment.text_preview.slice(0, 20)} className="rounded border border-line p-2">
                                <p className="text-xs text-muted">
                                  {comment.created_at_local ?? '—'} · {comment.author}
                                  {comment.matched_person ? ' · da pessoa' : ''}
                                </p>
                                <p className="whitespace-pre-wrap">{comment.text_preview}</p>
                              </li>
                            ))}
                          </ul>
                        </Td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line px-3 py-2">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  )
}
