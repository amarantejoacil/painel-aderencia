import { useCallback, useEffect, useMemo, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import {
  api,
  type AzureDevOpsSyncResult,
  type ImportPreview,
  type ImportResult,
} from '@/lib/api'
import { formatDate, formatDateTime, monthLabel } from '@/lib/format'

type PendingImport = {
  file: File
  preview: ImportPreview
  year: number
  month: number
}

const SOURCE_LABEL: Record<'csv' | 'azure_api', string> = {
  csv: 'CSV',
  azure_api: 'Azure',
}

function importsForPeriod(imports: ImportResult[], year: number, month: number) {
  return imports.filter(
    (item) => item.reference_year === year && item.reference_month === month,
  )
}

function buildCsvRepeatWarning(periodLabel: string, existing: ImportResult[]): string {
  const count = existing.length
  const sources = [...new Set(existing.map((item) => SOURCE_LABEL[item.source ?? 'csv']))].join(' e ')
  return (
    `Já existe ${count} importação${count === 1 ? '' : 'ões'} para ${periodLabel} (${sources}). ` +
    'Ao confirmar, uma nova importação CSV será criada e passará a ser usada no Dashboard. ' +
    'O painel exibirá somente as atividades deste arquivo, substituindo a visão atual. ' +
    'As importações anteriores permanecem no histórico.'
  )
}

function buildAzureRepeatWarning(periodLabel: string, existing: ImportResult[]): string {
  const count = existing.length
  return (
    `Já existe ${count} importação${count === 1 ? '' : 'ões'} para ${periodLabel}. ` +
    'Ao sincronizar, as Tasks serão atualizadas por ID (sem duplicar) e a nova importação passará a ser usada no Dashboard. ' +
    'Importações anteriores permanecem no histórico.'
  )
}

function PeriodImportNotice({ message }: { message: string }) {
  return (
    <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">{message}</p>
  )
}

export function ImportPage() {
  const [imports, setImports] = useState<ImportResult[]>([])
  const [result, setResult] = useState<ImportResult | null>(null)
  const [pending, setPending] = useState<PendingImport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [details, setDetails] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)

  const [azureConfigured, setAzureConfigured] = useState(false)
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null)
  const [azureYear, setAzureYear] = useState(2026)
  const [azureMonth, setAzureMonth] = useState(new Date().getMonth() + 1)
  const [syncResult, setSyncResult] = useState<AzureDevOpsSyncResult | null>(null)

  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, index) => ({
        value: index + 1,
        label: new Date(2026, index, 1).toLocaleDateString('pt-BR', { month: 'long' }),
      })),
    [],
  )

  const loadImports = useCallback(async () => {
    const items = await api.listImports()
    setImports(items)
  }, [])

  const loadAzureStatus = useCallback(async () => {
    try {
      const status = await api.getAzureDevOpsStatus()
      setAzureConfigured(status.configured)
      setLastSyncAt(status.last_sync_at)
    } catch {
      setAzureConfigured(false)
      setLastSyncAt(null)
    }
  }, [])

  useEffect(() => {
    void loadImports().catch(() => setImports([]))
    void loadAzureStatus()
  }, [loadImports, loadAzureStatus])

  const prepareImport = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    setDetails([])
    setResult(null)
    try {
      const preview = await api.previewImport(file)
      setPending({
        file,
        preview,
        year: preview.year,
        month: preview.month,
      })
    } catch (err) {
      const typed = err as Error & { details?: string[] }
      setError(typed.message)
      setDetails(typed.details ?? [])
    } finally {
      setBusy(false)
    }
  }

  const confirmImport = async () => {
    if (!pending) return
    setBusy(true)
    setError(null)
    setDetails([])
    try {
      const imported = await api.uploadImport(pending.file, pending.year, pending.month)
      setResult(imported)
      setPending(null)
      setSyncResult(null)
      await loadImports()
    } catch (err) {
      const typed = err as Error & { details?: string[] }
      setError(typed.message)
      setDetails(typed.details ?? [])
    } finally {
      setBusy(false)
    }
  }

  const syncAzure = async () => {
    const periodExisting = importsForPeriod(imports, azureYear, azureMonth)
    if (periodExisting.length > 0) {
      const confirmed = window.confirm(
        buildAzureRepeatWarning(monthLabel(azureYear, azureMonth), periodExisting),
      )
      if (!confirmed) return
    }

    setBusy(true)
    setError(null)
    setDetails([])
    setSyncResult(null)
    try {
      const response = await api.syncAzureDevOps(azureYear, azureMonth)
      setSyncResult(response)
      setLastSyncAt(response.last_sync_at)
      setResult(null)
      await loadImports()
      await loadAzureStatus()
    } catch (err) {
      const typed = err as Error & { details?: string[] }
      setError(typed.message)
      setDetails(typed.details ?? [])
    } finally {
      setBusy(false)
    }
  }

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDrag(false)
    void prepareImport(event.dataTransfer.files[0])
  }

  const remove = async (importId: number) => {
    const confirmed = window.confirm(
      'Excluir esta importação? Todas as atividades importadas vinculadas a ela serão removidas do painel.',
    )
    if (!confirmed) return
    setBusy(true)
    setError(null)
    try {
      await api.deleteImport(importId)
      if (result?.id === importId) setResult(null)
      if (syncResult?.import_id === importId) setSyncResult(null)
      await loadImports()
      await loadAzureStatus()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const latestId = imports[0]?.id
  const pendingSpansMultiplePeriods =
    pending != null && pending.preview.outside_primary_count > 0
  const pendingPeriodExisting =
    pending != null ? importsForPeriod(imports, pending.year, pending.month) : []
  const azurePeriodExisting = importsForPeriod(imports, azureYear, azureMonth)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Obter atividades</h2>
        <p className="mt-1 text-sm text-muted">
          Importe o CSV do Relatório Contrato ou sincronize diretamente com o Azure DevOps. Cada operação
          é armazenada; o Dashboard usa sempre a mais recente.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Importar CSV</h3>
          <Card>
            <label
              onDragOver={(event) => {
                event.preventDefault()
                setDrag(true)
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center ${
                drag ? 'border-accent bg-accent-soft' : 'border-line'
              }`}
            >
              <p className="font-medium">Arraste o CSV ou clique para selecionar</p>
              <p className="mt-1 text-sm text-muted">
                Colunas esperadas: Work Item Type, ID, Data referência, Title, Assigned To, State, Atividade.
              </p>
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(event) => {
                  void prepareImport(event.target.files?.[0])
                  event.target.value = ''
                }}
              />
              <Button type="button" className="mt-4" disabled={busy}>
                {busy && !pending ? 'Analisando arquivo…' : 'Escolher arquivo'}
              </Button>
            </label>
          </Card>
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Sincronizar Azure DevOps</h3>
          <Card className="space-y-4 p-4">
            <p className="text-sm text-muted">
              Busca Tasks diretamente do Azure DevOps via API. O PAT fica configurado apenas no servidor.
            </p>
            <p className="text-sm">
              <span className="text-muted">Última sincronização: </span>
              <span className="font-medium">
                {lastSyncAt ? formatDateTime(lastSyncAt) : 'Nunca realizada'}
              </span>
            </p>
            {!azureConfigured && (
              <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
                Integração não configurada. Cadastre URL, organização, projeto e PAT em{' '}
                <Link to="/configuracoes" className="font-medium underline">
                  Configurações
                </Link>
                .
              </p>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                <span className="mb-1 block text-muted">Mês</span>
                <select
                  className="h-10 w-full rounded-md border border-line bg-white px-3"
                  value={azureMonth}
                  onChange={(event) => setAzureMonth(Number(event.target.value))}
                  disabled={!azureConfigured || busy}
                >
                  {months.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-muted">Ano</span>
                <select
                  className="h-10 w-full rounded-md border border-line bg-white px-3"
                  value={azureYear}
                  onChange={(event) => setAzureYear(Number(event.target.value))}
                  disabled={!azureConfigured || busy}
                >
                  {[2025, 2026, 2027, 2028].map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {azurePeriodExisting.length > 0 && (
              <PeriodImportNotice
                message={buildAzureRepeatWarning(
                  monthLabel(azureYear, azureMonth),
                  azurePeriodExisting,
                )}
              />
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!azureConfigured || busy}
                onClick={() => void syncAzure()}
              >
                {busy ? 'Sincronizando…' : 'Sincronizar Azure DevOps'}
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {pending && (
        <Card className="border-accent/30 bg-accent-soft/30">
          <h3 className="font-semibold">Confirmar período da importação</h3>
          <p className="mt-1 text-sm text-muted">
            Arquivo <span className="font-medium text-ink">{pending.preview.filename}</span> ·{' '}
            {pending.preview.row_count} atividade{pending.preview.row_count === 1 ? '' : 's'}
          </p>
          <p className="mt-2 text-sm text-muted">
            Datas no arquivo: {formatDate(pending.preview.min_date)} a {formatDate(pending.preview.max_date)}
          </p>
          {pendingSpansMultiplePeriods && (
            <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
              O CSV contém atividades de mais de um mês. Confirme abaixo qual período deve ser importado.
            </p>
          )}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-muted">Mês das atividades</span>
              <select
                className="h-10 w-full rounded-md border border-line bg-white px-3"
                value={pending.month}
                onChange={(event) =>
                  setPending({ ...pending, month: Number(event.target.value) })
                }
              >
                {months.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted">Ano das atividades</span>
              <select
                className="h-10 w-full rounded-md border border-line bg-white px-3"
                value={pending.year}
                onChange={(event) =>
                  setPending({ ...pending, year: Number(event.target.value) })
                }
              >
                {[2025, 2026, 2027, 2028].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="mt-3 text-sm">
            Período selecionado:{' '}
            <span className="font-medium">{monthLabel(pending.year, pending.month)}</span>
          </p>
          {pendingPeriodExisting.length > 0 && (
            <PeriodImportNotice
              message={buildCsvRepeatWarning(
                monthLabel(pending.year, pending.month),
                pendingPeriodExisting,
              )}
            />
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" disabled={busy} onClick={() => void confirmImport()}>
              {busy ? 'Importando…' : 'Confirmar e importar'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() => setPending(null)}
            >
              Cancelar
            </Button>
          </div>
        </Card>
      )}

      {error && (
        <Card className="border-red-200 bg-red-50 text-red-900">
          <p className="font-medium">{error}</p>
          {details.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {details.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {syncResult && (
        <Card>
          <h3 className="font-semibold">Sincronização concluída</h3>
          <p className="mt-1 text-sm text-muted">Período: {syncResult.period_label}</p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase text-muted">Tasks encontradas</dt>
              <dd className="text-xl font-semibold">{syncResult.tasks_found}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Novas</dt>
              <dd className="text-xl font-semibold">{syncResult.created}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Atualizadas</dt>
              <dd className="text-xl font-semibold">{syncResult.updated}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Ignoradas</dt>
              <dd className="text-xl font-semibold">{syncResult.ignored}</dd>
            </div>
          </dl>
          <p className="mt-3 text-sm text-muted">
            Última sincronização: {formatDateTime(syncResult.last_sync_at)}
          </p>
        </Card>
      )}

      {result && (
        <Card>
          <h3 className="font-semibold">Importação concluída</h3>
          <p className="mt-1 text-sm text-muted">
            {result.filename}
            {result.reference_year && result.reference_month
              ? ` · ${monthLabel(result.reference_year, result.reference_month)}`
              : ''}
          </p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase text-muted">Linhas válidas</dt>
              <dd className="text-xl font-semibold">{result.row_count}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Mapeadas</dt>
              <dd className="text-xl font-semibold">{result.mapped_count}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Sem cadastro</dt>
              <dd className="text-xl font-semibold">{result.unmapped_count}</dd>
            </div>
          </dl>
          {result.warnings.length > 0 && (
            <ul className="mt-4 space-y-2 text-sm">
              {result.warnings.map((warning, index) => (
                <li key={`${warning.kind}-${index}`} className="rounded-md bg-amber-50 px-3 py-2 text-amber-900">
                  {warning.message}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {imports.length > 0 && (
        <Card>
          <h3 className="font-semibold">Importações realizadas</h3>
          <p className="mt-1 text-sm text-muted">
            {imports.length} importação{imports.length === 1 ? '' : 'ões'} armazenada
            {imports.length === 1 ? '' : 's'}.
          </p>
          <Table className="mt-4">
            <thead>
              <tr>
                <Th>Data</Th>
                <Th>Origem</Th>
                <Th>Período</Th>
                <Th>Arquivo</Th>
                <Th>Atividades</Th>
                <Th>Mapeadas</Th>
                <Th>Avisos</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {imports.map((item) => (
                <tr key={item.id}>
                  <Td className="whitespace-nowrap">{formatDateTime(item.imported_at)}</Td>
                  <Td>{SOURCE_LABEL[item.source ?? 'csv']}</Td>
                  <Td className="whitespace-nowrap">
                    {item.reference_year && item.reference_month
                      ? monthLabel(item.reference_year, item.reference_month)
                      : '—'}
                  </Td>
                  <Td>
                    <div className="flex flex-wrap items-center gap-2">
                      <span>{item.filename}</span>
                      {item.id === latestId && (
                        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
                          Em uso no painel
                        </span>
                      )}
                    </div>
                  </Td>
                  <Td>{item.row_count}</Td>
                  <Td>{item.mapped_count}</Td>
                  <Td>{item.warning_count}</Td>
                  <Td className="text-right">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void remove(item.id)}
                    >
                      Excluir
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  )
}
