import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type TimeEntryOperation } from '@/lib/api'
import { formatAzureState, formatDate, formatHours } from '@/lib/format'
import { fieldClass, TimeEntryShell } from '@/pages/timeEntries/TimeEntryShell'

const STATUS_LABEL: Record<string, string> = {
  pending: 'Em envio',
  confirmed: 'Confirmado',
  failed: 'Falha',
  uncertain: 'Incerto',
}

export function HistoryPage() {
  const now = new Date()
  const [year, setYear] = useState(String(now.getFullYear()))
  const [month, setMonth] = useState(String(now.getMonth() + 1))
  const [day, setDay] = useState('')
  const [storyId, setStoryId] = useState('')
  const [state, setState] = useState('')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState<TimeEntryOperation[]>([])
  const [selected, setSelected] = useState<TimeEntryOperation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function load() {
    setLoading(true)
    setError(null)
    api
      .timeEntryOperations({
        year: year ? Number(year) : undefined,
        month: month ? Number(month) : undefined,
        date: day || undefined,
        story_id: storyId ? Number(storyId) : undefined,
        state: state || undefined,
        status: status || undefined,
      })
      .then(setRows)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <TimeEntryShell
      title="Histórico"
      description="Operações criadas por este módulo. Registros que já existiam no Azure não aparecem aqui como se tivessem sido lançados pela aplicação."
    >
      {error ? <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</Card> : null}
      <Card className="grid gap-3 p-5 md:grid-cols-3">
        <div>
          <Label htmlFor="history-month">Mês</Label>
          <Input id="history-month" value={month} onChange={(event) => setMonth(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="history-year">Ano</Label>
          <Input id="history-year" value={year} onChange={(event) => setYear(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="history-date">Data</Label>
          <Input id="history-date" type="date" value={day} onChange={(event) => setDay(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="history-story">História</Label>
          <Input id="history-story" value={storyId} onChange={(event) => setStoryId(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="history-state">Estado</Label>
          <Input id="history-state" value={state} onChange={(event) => setState(event.target.value)} placeholder="New" />
        </div>
        <div>
          <Label htmlFor="history-status">Situação do envio</Label>
          <select id="history-status" className={fieldClass} value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Todas</option>
            <option value="confirmed">Confirmado</option>
            <option value="pending">Em envio</option>
            <option value="uncertain">Incerto</option>
            <option value="failed">Falha</option>
          </select>
        </div>
        <div className="md:col-span-3">
          <Button type="button" disabled={loading} onClick={load}>
            Consultar
          </Button>
        </div>
      </Card>

      <Card className="p-5">
        {rows.length === 0 ? <p className="text-sm text-muted">Nenhum lançamento deste módulo no filtro informado.</p> : null}
        {rows.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>Data</Th>
                <Th>Título</Th>
                <Th>Horas</Th>
                <Th>Responsável</Th>
                <Th>User Story</Th>
                <Th>Task</Th>
                <Th>Estado</Th>
                <Th>Situação</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.operation_key} className="cursor-pointer" onClick={() => setSelected(row)}>
                  <Td>{formatDate(row.reference_date)}</Td>
                  <Td>{row.title}</Td>
                  <Td>{formatHours(row.estimated_hours)}</Td>
                  <Td>{row.assignee_name}</Td>
                  <Td>
                    #{row.story_id}
                    {row.story_title ? ` · ${row.story_title}` : ''}
                  </Td>
                  <Td>
                    {row.url ? (
                      <a className="text-accent underline" href={row.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                        {row.task_id}
                      </a>
                    ) : (
                      '—'
                    )}
                  </Td>
                  <Td>{formatAzureState(row.task_state)}</Td>
                  <Td>{STATUS_LABEL[row.status] ?? row.status}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>

      {selected ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-lg space-y-2 p-5 text-sm">
            <h3 className="text-base font-semibold">Detalhe do lançamento</h3>
            <p>{selected.title}</p>
            <p className="text-muted">{selected.description || 'Sem descrição.'}</p>
            <p>Data de referência: {formatDate(selected.reference_date)}</p>
            <p>Situação: {STATUS_LABEL[selected.status] ?? selected.status}</p>
            {selected.error_message ? <p className="text-red-800">{selected.error_message}</p> : null}
            {selected.justification ? <p>Justificativa: {selected.justification}</p> : null}
            {selected.url ? (
              <a className="text-accent underline" href={selected.url} target="_blank" rel="noreferrer">
                Abrir Task no Azure DevOps
              </a>
            ) : null}
            <div>
              <Button type="button" variant="ghost" onClick={() => setSelected(null)}>
                Fechar
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </TimeEntryShell>
  )
}
