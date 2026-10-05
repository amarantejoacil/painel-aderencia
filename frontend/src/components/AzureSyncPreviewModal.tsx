import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import type { AzureDevOpsSyncPreview } from '@/lib/api'
import { monthLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

type AzureSyncPreviewModalProps = {
  preview: AzureDevOpsSyncPreview
  year: number
  month: number
  busy: boolean
  onConfirm: (ignoreAssigneeNames: string[]) => void
  onCancel: () => void
}

export function AzureSyncPreviewModal({
  preview,
  year,
  month,
  busy,
  onConfirm,
  onCancel,
}: AzureSyncPreviewModalProps) {
  const initialIgnored = useMemo(() => {
    const names = new Set<string>()
    for (const row of preview.assignees) {
      if (row.ignored_by_rule) {
        names.add(row.assignee_name)
      }
    }
    for (const name of preview.saved_ignored_assignees) {
      names.add(name)
    }
    return names
  }, [preview])

  const [ignored, setIgnored] = useState<Set<string>>(initialIgnored)

  const { tasksToImport, tasksExcluded, ignoredRows } = useMemo(() => {
    let importTasks = 0
    let excludedTasks = 0
    const excluded: typeof preview.assignees = []
    for (const row of preview.assignees) {
      if (ignored.has(row.assignee_name)) {
        excludedTasks += row.task_count
        excluded.push(row)
      } else {
        importTasks += row.task_count
      }
    }
    return { tasksToImport: importTasks, tasksExcluded: excludedTasks, ignoredRows: excluded }
  }, [preview.assignees, ignored])

  const toggle = (assigneeName: string, checked: boolean) => {
    setIgnored((current) => {
      const next = new Set(current)
      if (checked) {
        next.add(assigneeName)
      } else {
        next.delete(assigneeName)
      }
      return next
    })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onCancel}
      role="presentation"
    >
      <Card
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden p-0"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-line px-5 py-4">
          <h3 className="text-lg font-semibold">Prévia da sincronização Azure</h3>
          <p className="mt-1 text-sm text-muted">
            {monthLabel(year, month)} — {preview.tasks_found} Task(s) no Azure ·{' '}
            {preview.mappable_tasks} pronta(s) para importar
            {preview.mapper_ignored_count > 0
              ? ` · ${preview.mapper_ignored_count} ignorada(s) por dados inválidos`
              : ''}
          </p>
          <div className="mt-3 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 ring-1 ring-inset ring-red-200">
            <p className="font-semibold text-red-800">
              Marque quem não deve entrar no painel — linhas em vermelho não serão importadas.
            </p>
            <p className="mt-1 text-red-800/90">
              A exclusão vale para este período e a regra fica salva nas próximas sincronizações.
            </p>
          </div>
        </div>

        <div className="overflow-auto px-5 py-4">
          {preview.assignees.length === 0 ? (
            <p className="text-sm text-muted">Nenhuma Task mapeável encontrada para o período.</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th className="w-28">Excluir</Th>
                  <Th>Responsável no Azure</Th>
                  <Th>Tasks</Th>
                  <Th>Colaborador no painel</Th>
                </tr>
              </thead>
              <tbody>
                {preview.assignees.map((row) => {
                  const isExcluded = ignored.has(row.assignee_name)
                  return (
                    <tr
                      key={row.assignee_name}
                      className={cn(
                        isExcluded && 'bg-red-50 ring-1 ring-inset ring-red-200',
                      )}
                    >
                      <Td>
                        <label className="flex cursor-pointer items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isExcluded}
                            onChange={(event) => toggle(row.assignee_name, event.target.checked)}
                            aria-label={`Excluir ${row.assignee_name} da importação`}
                            className="size-4 accent-red-700"
                          />
                          {isExcluded && (
                            <span className="text-xs font-semibold uppercase tracking-wide text-red-700">
                              Sim
                            </span>
                          )}
                        </label>
                      </Td>
                      <Td>
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={cn(
                              'font-medium',
                              isExcluded && 'text-red-800 line-through decoration-red-400',
                            )}
                          >
                            {row.assignee_name}
                          </span>
                          {isExcluded && (
                            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800 ring-1 ring-inset ring-red-300">
                              Não será importado
                            </span>
                          )}
                        </div>
                      </Td>
                      <Td className={cn(isExcluded && 'font-medium text-red-800')}>
                        {row.task_count}
                        {isExcluded && (
                          <span className="ml-1 text-xs font-normal text-red-700">(excluídas)</span>
                        )}
                      </Td>
                      <Td className={cn(isExcluded && 'text-red-700/80')}>
                        {row.mapped_collaborator_name ?? '—'}
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          )}
        </div>

        <div className="flex flex-col gap-3 border-t border-line px-5 py-4">
          {ignoredRows.length > 0 && (
            <div className="rounded-lg border-2 border-red-400 bg-red-50 px-4 py-3 text-sm text-red-900">
              <p className="font-bold text-red-800">
                {ignoredRows.length} responsável(is) excluído(s) — {tasksExcluded} Task(s) não
                serão importadas
              </p>
              <p className="mt-1 font-medium text-red-800">
                {ignoredRows.map((row) => row.assignee_name).join(' · ')}
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm">
              Serão importadas aproximadamente{' '}
              <span className="text-base font-bold text-accent">{tasksToImport}</span> Task(s).
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>
                Cancelar
              </Button>
              <Button
                type="button"
                disabled={busy}
                onClick={() => onConfirm(Array.from(ignored))}
              >
                {busy ? 'Importando…' : 'Confirmar sincronização'}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
