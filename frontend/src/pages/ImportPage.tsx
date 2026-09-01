import { useCallback, useEffect, useMemo, useState, type DragEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type ImportPreview, type ImportResult } from '@/lib/api'
import { formatDate, formatDateTime, monthLabel } from '@/lib/format'

type PendingImport = {
  file: File
  preview: ImportPreview
  year: number
  month: number
}

export function ImportPage() {
  const [imports, setImports] = useState<ImportResult[]>([])
  const [result, setResult] = useState<ImportResult | null>(null)
  const [pending, setPending] = useState<PendingImport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [details, setDetails] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)

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

  useEffect(() => {
    void loadImports().catch(() => setImports([]))
  }, [loadImports])

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
      await loadImports()
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
      await loadImports()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const latestId = imports[0]?.id
  const pendingSpansMultiplePeriods =
    pending != null && pending.preview.outside_primary_count > 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Importação do Azure Boards</h2>
        <p className="mt-1 text-sm text-muted">
          Envie o CSV do Relatório Contrato. Antes de concluir, confirme o mês e o ano das atividades. Cada
          importação é armazenada; o Dashboard usa sempre a mais recente.
        </p>
      </div>

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
