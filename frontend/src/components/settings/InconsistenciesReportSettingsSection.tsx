import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { api, type InconsistenciesReportSettings } from '@/lib/api'
import {
  COPY_INTRO_PLACEHOLDERS,
  DEFAULT_COPY_INTRO_OK,
  DEFAULT_COPY_INTRO_REQUIRES_REVIEW,
} from '@/lib/inconsistenciesReportCopy'
import { formatDateTime } from '@/lib/format'

type FormState = {
  copy_intro_requires_review: string
  copy_intro_ok: string
}

export function InconsistenciesReportSettingsSection() {
  const [settings, setSettings] = useState<InconsistenciesReportSettings | null>(null)
  const [form, setForm] = useState<FormState>({
    copy_intro_requires_review: DEFAULT_COPY_INTRO_REQUIRES_REVIEW,
    copy_intro_ok: DEFAULT_COPY_INTRO_OK,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const data = await api.getInconsistenciesReportSettings()
      setSettings(data)
      setForm({
        copy_intro_requires_review: data.copy_intro_requires_review,
        copy_intro_ok: data.copy_intro_ok,
      })
    } catch (err) {
      setError((err as Error).message)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const restoreDefaults = () => {
    setForm({
      copy_intro_requires_review: DEFAULT_COPY_INTRO_REQUIRES_REVIEW,
      copy_intro_ok: DEFAULT_COPY_INTRO_OK,
    })
    setSaveMessage(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await api.updateInconsistenciesReportSettings({
        copy_intro_requires_review: form.copy_intro_requires_review.trim(),
        copy_intro_ok: form.copy_intro_ok.trim(),
      })
      setSettings(updated)
      setForm({
        copy_intro_requires_review: updated.copy_intro_requires_review,
        copy_intro_ok: updated.copy_intro_ok,
      })
      setSaveMessage('Configuração salva.')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-6">
        <h3 className="text-lg font-semibold">Relatório de inconsistências</h3>
        <p className="mt-1 text-sm text-muted">
          Texto inicial incluído ao usar &quot;Copiar texto&quot; no relatório, antes do resumo técnico.
          Use os placeholders abaixo; eles serão substituídos pelo nome e período de cada colaborador.
        </p>
        {settings?.updated_at && (
          <p className="mt-2 text-sm text-muted">
            Última alteração:{' '}
            <span className="font-medium text-ink">{formatDateTime(settings.updated_at)}</span>
          </p>
        )}
      </div>

      <ul className="mb-6 flex flex-wrap gap-2 text-xs text-muted">
        {COPY_INTRO_PLACEHOLDERS.map((item) => (
          <li
            key={item.key}
            className="rounded-md border border-line bg-paper px-2 py-1 font-mono"
            title={item.label}
          >
            {item.key}
          </li>
        ))}
      </ul>

      {error && <p className="mb-4 text-sm text-red-700">{error}</p>}
      {saveMessage && <p className="mb-4 text-sm font-medium text-emerald-700">{saveMessage}</p>}

      <form className="space-y-6" onSubmit={submit}>
        <div>
          <Label htmlFor="copy_intro_requires_review">Mensagem — requer revisão</Label>
          <textarea
            id="copy_intro_requires_review"
            className="mt-1.5 min-h-[140px] w-full resize-y rounded-md border border-line bg-paper px-3 py-2 text-sm leading-relaxed"
            value={form.copy_intro_requires_review}
            onChange={(event) =>
              setForm((current) => ({ ...current, copy_intro_requires_review: event.target.value }))
            }
            required
          />
        </div>

        <div>
          <Label htmlFor="copy_intro_ok">Mensagem — colaborador OK</Label>
          <textarea
            id="copy_intro_ok"
            className="mt-1.5 min-h-[120px] w-full resize-y rounded-md border border-line bg-paper px-3 py-2 text-sm leading-relaxed"
            value={form.copy_intro_ok}
            onChange={(event) =>
              setForm((current) => ({ ...current, copy_intro_ok: event.target.value }))
            }
            required
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>
            {busy ? 'Salvando…' : 'Salvar'}
          </Button>
          <Button type="button" variant="secondary" disabled={busy} onClick={restoreDefaults}>
            Restaurar padrão
          </Button>
        </div>
      </form>
    </Card>
  )
}
