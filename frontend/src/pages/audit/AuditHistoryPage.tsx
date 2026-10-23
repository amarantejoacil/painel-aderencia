import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type IssueAuditSummary } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

const STATUS_LABEL: Record<IssueAuditSummary['status'], string> = {
  queued: 'Na fila',
  running: 'Em andamento',
  complete: 'Completa',
  partial: 'Incompleta',
  failed: 'Falhou',
  cancelled: 'Cancelada',
  ambiguous: 'Identidade ambígua',
}

const PERIOD_LABEL = {
  created: 'Criadas no ano',
  changed: 'Alteradas no ano',
}

export function AuditHistoryPage() {
  const [rows, setRows] = useState<IssueAuditSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void api
      .listIssueAudits()
      .then(setRows)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Auditoria Azure DevOps</p>
          <h1 className="text-2xl font-semibold">Histórico de consultas</h1>
        </div>
        <Link className="text-sm text-accent" to="/auditoria/issues">
          Nova consulta
        </Link>
      </div>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      <Card>
        <p className="mb-3 text-sm text-muted">
          O histórico guarda os parâmetros, os totais e os comentários da pessoa pesquisada para reabrir o resultado. O Excel é gerado de novo a partir desse recorte.
        </p>
        <Table>
          <thead>
            <tr>
              <Th>Data</Th>
              <Th>Solicitante</Th>
              <Th>Organização</Th>
              <Th>Projeto</Th>
              <Th>Período</Th>
              <Th>Pessoa</Th>
              <Th>Issues</Th>
              <Th title="Comentários da pessoa pesquisada na consulta">Coment. pessoa</Th>
              <Th>Situação</Th>
              <Th>Arquivo</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <Td>{formatDateTime(row.created_at)}</Td>
                <Td>{row.requester || '—'}</Td>
                <Td>{row.organization}</Td>
                <Td>{row.project}</Td>
                <Td>
                  {row.period_start && row.period_end
                    ? `${row.period_start} a ${row.period_end}`
                    : `${PERIOD_LABEL[row.period_criterion]} ${row.year}`}
                  {row.state_filter ? ` · ${row.state_filter}` : ''}
                </Td>
                <Td>{row.person_name}</Td>
                <Td>{row.issues_found}</Td>
                <Td>{row.comments_matched}</Td>
                <Td>
                  <Link className="text-accent" to={`/auditoria/issues/${row.id}`}>
                    {STATUS_LABEL[row.status]}
                  </Link>
                </Td>
                <Td>
                  {row.status === 'queued' || row.status === 'running' || row.status === 'failed' ? (
                    '—'
                  ) : (
                    <a className="text-accent" href={`/api/audit/issues/queries/${row.id}/export`}>
                      Excel
                    </a>
                  )}
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <Td colSpan={10}>Nenhuma consulta registrada.</Td>
              </tr>
            )}
          </tbody>
        </Table>
      </Card>
    </div>
  )
}
