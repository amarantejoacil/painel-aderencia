import { useEffect, useState, type DragEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { api, type ImportResult } from '@/lib/api'

export function ImportPage() {
  const [latest, setLatest] = useState<ImportResult | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [details, setDetails] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)

  useEffect(() => {
    api.latestImport().then(setLatest).catch(() => setLatest(null))
  }, [])

  const send = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    setDetails([])
    setResult(null)
    try {
      const imported = await api.uploadImport(file)
      setResult(imported)
      setLatest(imported)
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
    void send(event.dataTransfer.files[0])
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Importação do Azure Boards</h2>
        <p className="mt-1 text-sm text-muted">
          Envie o CSV do Relatório Contrato. A importação substitui a carga anterior.
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
            Colunas esperadas: Work Item Type, ID, Data referência, Title, Assigned To, State.
          </p>
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => void send(event.target.files?.[0])}
          />
          <Button type="button" className="mt-4" disabled={busy}>
            {busy ? 'Importando…' : 'Escolher arquivo'}
          </Button>
        </label>
      </Card>

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
          <p className="mt-1 text-sm text-muted">{result.filename}</p>
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

      {!result && latest && (
        <Card>
          <h3 className="font-semibold">Última importação</h3>
          <p className="mt-1 text-sm text-muted">
            {latest.filename} · {latest.row_count} atividades · {latest.mapped_count} mapeadas
          </p>
        </Card>
      )}
    </div>
  )
}
