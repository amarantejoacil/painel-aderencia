import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import type { DashboardRow, DayResult } from '@/lib/api'
import {
  formatDate,
  formatDateWithWeekday,
  formatHours,
  formatPercent,
  STATUS_LABEL,
} from '@/lib/format'

export type ChartSelection =
  | { kind: 'collaborator'; collaboratorId: number }
  | { kind: 'team-status'; situation: 'ok' | 'review' }
  | { kind: 'inconsistency'; collaboratorId: number; status: 'missing' | 'incomplete' | 'excess' }
  | { kind: 'daily'; date: string }
  | { kind: 'day-compliance'; category: 'regular' | 'inconsistent' }

type ChartDetailModalProps = {
  selection: ChartSelection | null
  rows: DashboardRow[]
  year: number
  month: number
  onClose: () => void
}

const INCONSISTENCY_LABEL: Record<'missing' | 'incomplete' | 'excess', string> = {
  missing: 'Sem lançamento',
  incomplete: 'Incompleto',
  excess: 'Excedente',
}

function findRow(rows: DashboardRow[], collaboratorId: number) {
  return rows.find((row) => row.collaborator.id === collaboratorId)
}

function mandatoryDays(row: DashboardRow) {
  return row.days.filter((day) => Number(day.expected) > 0)
}

function buildTitle(selection: ChartSelection, rows: DashboardRow[]): string {
  switch (selection.kind) {
    case 'collaborator': {
      const row = findRow(rows, selection.collaboratorId)
      return row ? row.collaborator.name : 'Colaborador'
    }
    case 'team-status':
      return selection.situation === 'ok' ? 'Colaboradores OK' : 'Colaboradores que requerem revisão'
    case 'inconsistency': {
      const row = findRow(rows, selection.collaboratorId)
      const name = row?.collaborator.name ?? 'Colaborador'
      return `${name} · ${INCONSISTENCY_LABEL[selection.status]}`
    }
    case 'daily':
      return `Aderência em ${formatDate(selection.date)}`
    case 'day-compliance':
      return selection.category === 'regular' ? 'Dias regulares' : 'Dias com inconsistência'
  }
}

function DayTable({
  days,
  year,
  month,
  showCollaborator = false,
  rows,
}: {
  days: Array<DayResult & { collaboratorName?: string; collaboratorId?: number }>
  year: number
  month: number
  showCollaborator?: boolean
  rows: DashboardRow[]
}) {
  if (days.length === 0) {
    return <p className="text-sm text-muted">Nenhum registro encontrado.</p>
  }

  return (
    <Table>
      <thead>
        <tr>
          {showCollaborator && <Th>Colaborador</Th>}
          <Th>Data</Th>
          <Th>Status</Th>
          <Th className="text-right">Esperado</Th>
          <Th className="text-right">Executado</Th>
          <Th className="text-right">Tasks</Th>
        </tr>
      </thead>
      <tbody>
        {days.map((day) => {
          const collaboratorId =
            day.collaboratorId ??
            rows.find((row) => row.collaborator.name === day.collaboratorName)?.collaborator.id
          return (
            <tr key={`${day.date}-${day.collaboratorName ?? collaboratorId ?? ''}`}>
              {showCollaborator && (
                <Td>
                  {collaboratorId ? (
                    <Link
                      className="font-medium text-accent hover:underline"
                      to={`/colaboradores/${collaboratorId}?year=${year}&month=${month}`}
                    >
                      {day.collaboratorName}
                    </Link>
                  ) : (
                    day.collaboratorName
                  )}
                </Td>
              )}
              <Td>{formatDateWithWeekday(day.date)}</Td>
              <Td>{STATUS_LABEL[day.status] ?? day.status}</Td>
              <Td className="text-right">{formatHours(day.expected)}</Td>
              <Td className="text-right">{formatHours(day.executed)}</Td>
              <Td className="text-right">{day.task_count}</Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

export function ChartDetailModal({ selection, rows, year, month, onClose }: ChartDetailModalProps) {
  if (!selection) return null

  const title = buildTitle(selection, rows)

  let body: ReactNode = null

  if (selection.kind === 'collaborator') {
    const row = findRow(rows, selection.collaboratorId)
    if (!row) {
      body = <p className="text-sm text-muted">Colaborador não encontrado.</p>
    } else {
      body = (
        <div className="space-y-4">
          <dl className="grid gap-3 sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase text-muted">Aderência</dt>
              <dd className="text-lg font-semibold">{formatPercent(row.adherence)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Esperado</dt>
              <dd className="text-lg font-semibold">{formatHours(row.expected)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Executado</dt>
              <dd className="text-lg font-semibold">{formatHours(row.executed)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Sem lançamento</dt>
              <dd className="text-lg font-semibold">{row.missing}</dd>
            </div>
          </dl>
          <DayTable days={mandatoryDays(row)} year={year} month={month} rows={rows} />
        </div>
      )
    }
  }

  if (selection.kind === 'team-status') {
    const filtered = rows.filter((row) => {
      const ok = row.missing === 0 && row.incomplete === 0 && row.excess === 0
      return selection.situation === 'ok' ? ok : !ok
    })
    body = (
      <Table>
        <thead>
          <tr>
            <Th>Colaborador</Th>
            <Th className="text-right">Aderência</Th>
            <Th className="text-right">Sem lançamento</Th>
            <Th className="text-right">Incompleto</Th>
            <Th className="text-right">Excedente</Th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((row) => (
            <tr key={row.collaborator.id}>
              <Td>
                <Link
                  className="font-medium text-accent hover:underline"
                  to={`/colaboradores/${row.collaborator.id}?year=${year}&month=${month}`}
                >
                  {row.collaborator.name}
                </Link>
              </Td>
              <Td className="text-right">{formatPercent(row.adherence)}</Td>
              <Td className="text-right">{row.missing}</Td>
              <Td className="text-right">{row.incomplete}</Td>
              <Td className="text-right">{row.excess}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    )
  }

  if (selection.kind === 'inconsistency') {
    const row = findRow(rows, selection.collaboratorId)
    const days =
      row?.days.filter((day) => day.status === selection.status && Number(day.expected) > 0) ?? []
    body = <DayTable days={days} year={year} month={month} rows={rows} />
  }

  if (selection.kind === 'daily') {
    const days = rows.flatMap((row) =>
      row.days
        .filter((day) => day.date === selection.date && Number(day.expected) > 0)
        .map((day) => ({
          ...day,
          collaboratorName: row.collaborator.name,
          collaboratorId: row.collaborator.id,
        })),
    )
    body = <DayTable days={days} year={year} month={month} showCollaborator rows={rows} />
  }

  if (selection.kind === 'day-compliance') {
    const statuses =
      selection.category === 'regular'
        ? ['regular']
        : ['missing', 'incomplete', 'excess']
    const days = rows.flatMap((row) =>
      row.days
        .filter((day) => statuses.includes(day.status) && Number(day.expected) > 0)
        .map((day) => ({
          ...day,
          collaboratorName: row.collaborator.name,
          collaboratorId: row.collaborator.id,
        })),
    )
    body = <DayTable days={days} year={year} month={month} showCollaborator rows={rows} />
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <Card
        className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden p-0"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <h3 className="text-lg font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-muted">Clique fora ou em Fechar para voltar aos gráficos.</p>
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Fechar
          </Button>
        </div>
        <div className="overflow-auto px-5 py-4">{body}</div>
      </Card>
    </div>
  )
}
