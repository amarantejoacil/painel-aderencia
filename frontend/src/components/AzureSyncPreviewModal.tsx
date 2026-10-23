import { useMemo, useState } from 'react'
import { RegisterAzureAssigneeModal } from '@/components/RegisterAzureAssigneeModal'
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
  onRefreshPreview: () => Promise<void>
  onQuickRegisterAssignees: (assigneeNames: string[]) => Promise<void>
}

function monthStartIso(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}-01`
}

export function AzureSyncPreviewModal({
  preview,
  year,
  month,
  busy,
  onConfirm,
  onCancel,
  onRefreshPreview,
  onQuickRegisterAssignees,
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
  const [registerAssignee, setRegisterAssignee] = useState<string | null>(null)
  const [unmappedPrompt, setUnmappedPrompt] = useState(false)
  const [registerAllBusy, setRegisterAllBusy] = useState(false)

  const unmappedActive = useMemo(
    () =>
      preview.assignees.filter(
        (row) => !row.mapped_collaborator_id && !ignored.has(row.assignee_name),
      ),
    [preview.assignees, ignored],
  )

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

  const requestConfirm = () => {
    if (unmappedActive.length > 0) {
      setUnmappedPrompt(true)
      return
    }
    onConfirm(Array.from(ignored))
  }

  const registerAllAndSync = async () => {
    setRegisterAllBusy(true)
    try {
      await onQuickRegisterAssignees(unmappedActive.map((row) => row.assignee_name))
      setUnmappedPrompt(false)
      onConfirm(Array.from(ignored))
    } finally {
      setRegisterAllBusy(false)
    }
  }

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
          {unmappedActive.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 ring-1 ring-inset ring-amber-200">
              <p className="font-semibold text-amber-900">
                {unmappedActive.length} responsável(is) sem cadastro no painel
              </p>
              <p className="mt-1 text-amber-900/90">
                As Tasks seriam importadas, mas não entrariam na aderência até cadastrar o colaborador
                (ativo). Use <span className="font-medium">Cadastrar</span> na linha ou confirme a
                sincronização para decidir em lote.
              </p>
              <p className="mt-2 font-medium text-amber-900">
                {unmappedActive.map((row) => row.assignee_name).join(' · ')}
              </p>
            </div>
          )}
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
                  const isUnmapped = !row.mapped_collaborator_id && !isExcluded
                  return (
                    <tr
                      key={row.assignee_name}
                      className={cn(
                        isExcluded && 'bg-red-50 ring-1 ring-inset ring-red-200',
                        isUnmapped && 'bg-amber-50/80 ring-1 ring-inset ring-amber-200',
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
                        {row.mapped_collaborator_name ? (
                          row.mapped_collaborator_name
                        ) : isExcluded ? (
                          '—'
                        ) : (
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-inset ring-amber-300">
                              Sem cadastro
                            </span>
                            <Button
                              type="button"
                              size="sm"
                              variant="secondary"
                              disabled={busy}
                              onClick={() => setRegisterAssignee(row.assignee_name)}
                            >
                              Cadastrar
                            </Button>
                          </div>
                        )}
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
              <Button type="button" disabled={busy} onClick={requestConfirm}>
                {busy ? 'Importando…' : 'Confirmar sincronização'}
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {registerAssignee && (
        <RegisterAzureAssigneeModal
          assigneeName={registerAssignee}
          defaultStartDate={monthStartIso(year, month)}
          onClose={() => setRegisterAssignee(null)}
          onRegistered={onRefreshPreview}
        />
      )}

      {unmappedPrompt && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
          onClick={() => !registerAllBusy && setUnmappedPrompt(false)}
          role="presentation"
        >
          <Card
            className="w-full max-w-lg p-5"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 className="text-lg font-semibold">Cadastrar colaboradores novos?</h3>
            <p className="mt-2 text-sm text-muted">
              Ainda há responsáveis no Azure sem vínculo no painel. Deseja cadastrá-los como
              colaboradores ativos (8h/dia, entrada no 1º dia do mês) antes de importar?
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
              {unmappedActive.map((row) => (
                <li key={row.assignee_name}>
                  {row.assignee_name}{' '}
                  <span className="text-muted">({row.task_count} Task(s))</span>
                </li>
              ))}
            </ul>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                disabled={registerAllBusy || busy}
                onClick={() => setUnmappedPrompt(false)}
              >
                Voltar
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={registerAllBusy || busy}
                onClick={() => {
                  setUnmappedPrompt(false)
                  onConfirm(Array.from(ignored))
                }}
              >
                Sincronizar sem cadastrar
              </Button>
              <Button
                type="button"
                disabled={registerAllBusy || busy}
                onClick={() => void registerAllAndSync()}
              >
                {registerAllBusy ? 'Cadastrando…' : 'Cadastrar todos e sincronizar'}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
