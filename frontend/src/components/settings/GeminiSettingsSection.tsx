import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, type AiModel, type AiSettings } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

type FormState = {
  api_key: string
  model_id: string
  enabled: boolean
}

const STATUS_LABEL: Record<AiSettings['status'], string> = {
  not_configured: 'Não configurado',
  configured: 'Configurado',
  error: 'Erro',
}

const STATUS_CLASS: Record<AiSettings['status'], string> = {
  not_configured: 'font-medium text-muted',
  configured: 'font-medium text-emerald-700',
  error: 'font-medium text-red-700',
}

function geminiModelPriority(id: string): number {
  const lower = id.toLowerCase()
  let score = 0
  if (lower.includes('flash')) score += 10_000
  if (lower.includes('lite') && lower.includes('flash')) score += 500
  const version = lower.match(/gemini-(\d+)(?:\.(\d+))?/)
  if (version) {
    score += Number(version[1]) * 100
    if (version[2]) score += Number(version[2]) * 10
  }
  if (lower.includes('preview') || lower.includes('exp')) score -= 80
  if (lower.includes('thinking')) score -= 120
  if (lower.includes('pro') && !lower.includes('flash')) score -= 400
  if (lower.includes('embed')) score -= 5_000
  if (lower.includes('image') || lower.includes('imagen')) score -= 3_000
  if (lower.includes('tts') || lower.includes('audio')) score -= 3_000
  if (lower.includes('robotics')) score -= 4_000
  return score
}

function sortGeminiModels(models: AiModel[]): AiModel[] {
  return [...models].sort((a, b) => {
    const diff = geminiModelPriority(b.id) - geminiModelPriority(a.id)
    if (diff !== 0) return diff
    return a.id.localeCompare(b.id)
  })
}

export function GeminiSettingsSection() {
  const [settings, setSettings] = useState<AiSettings | null>(null)
  const [form, setForm] = useState<FormState>({ api_key: '', model_id: '', enabled: false })
  const [models, setModels] = useState<AiModel[]>([])
  const [editingKey, setEditingKey] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [testMessage, setTestMessage] = useState<string | null>(null)
  const [testOk, setTestOk] = useState<boolean | null>(null)
  const [modelsLoading, setModelsLoading] = useState(false)

  const load = async () => {
    setError(null)
    try {
      const data = await api.getGeminiSettings()
      setSettings(data)
      setForm({
        api_key: '',
        model_id: data.model_id ?? '',
        enabled: data.enabled,
      })
      setEditingKey(!data.api_key_configured)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const loadModels = async () => {
    setModelsError(null)
    setModelsLoading(true)
    try {
      const list = await api.listGeminiModels()
      const sorted = sortGeminiModels(list)
      setModels(sorted)
      if (sorted.length === 0) {
        setModelsError('Nenhum modelo compatível retornado pelo Gemini.')
      }
    } catch (err) {
      setModelsError((err as Error).message)
    } finally {
      setModelsLoading(false)
    }
  }

  useEffect(() => {
    if (settings?.api_key_configured) {
      void loadModels()
    }
  }, [settings?.api_key_configured])

  const modelOptions = useMemo(() => {
    const sorted = sortGeminiModels(models)
    if (form.model_id && !sorted.some((item) => item.id === form.model_id)) {
      return [{ id: form.model_id, display_name: null }, ...sorted]
    }
    return sorted
  }, [models, form.model_id])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await api.updateGeminiSettings({
        api_key: form.api_key.trim() ? form.api_key.trim() : null,
        clear_api_key: false,
        model_id: form.model_id.trim() || null,
        enabled: form.enabled,
      })
      setSettings(updated)
      setForm((current) => ({ ...current, api_key: '' }))
      setEditingKey(false)
      setShowKey(false)
      setSaveMessage('Configurações salvas com sucesso.')
      if (updated.api_key_configured) {
        void loadModels()
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const testConnection = async () => {
    setBusy(true)
    setTestMessage(null)
    setTestOk(null)
    try {
      const result = await api.testGeminiSettings()
      setTestOk(result.ok)
      setTestMessage(result.message)
      await load()
    } catch (err) {
      setTestOk(false)
      setTestMessage((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const removeApiKey = async () => {
    if (!window.confirm('Remover a chave da API? A integração será desabilitada.')) return
    setBusy(true)
    setError(null)
    setSaveMessage(null)
    try {
      const updated = await api.deleteGeminiApiKey()
      setSettings(updated)
      setForm({ api_key: '', model_id: '', enabled: false })
      setModels([])
      setEditingKey(true)
      setSaveMessage('Chave removida.')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const keyConfigured = settings?.api_key_configured ?? false
  const status = settings?.status ?? 'not_configured'
  const canTest = keyConfigured && Boolean(form.model_id || settings?.model_id)

  return (
    <Card className="p-5">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Inteligência Artificial</h3>
          <p className="mt-1 text-sm text-muted">Google Gemini — chave e modelo usados por recursos de IA do painel.</p>
        </div>
        <div className="text-sm">
          <p>
            <span className="text-muted">Provedor: </span>
            <span className="font-medium">{settings?.provider_label ?? 'Google Gemini'}</span>
          </p>
          <p className="mt-1">
            <span className="text-muted">Status: </span>
            <span className={STATUS_CLASS[status]}>{STATUS_LABEL[status]}</span>
          </p>
          {settings?.last_test_at && (
            <p className="mt-1">
              <span className="text-muted">Último teste: </span>
              <span className="font-medium">
                {formatDateTime(settings.last_test_at)}
                {settings.last_test_message ? ` · ${settings.last_test_message}` : ''}
              </span>
            </p>
          )}
        </div>
      </div>

      <form className="space-y-4" onSubmit={submit}>
        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor="gemini_api_key">Chave da API</Label>
            {keyConfigured && !editingKey && (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setEditingKey(true)
                    setForm((current) => ({ ...current, api_key: '' }))
                  }}
                >
                  Alterar chave
                </Button>
                <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void removeApiKey()}>
                  Remover chave
                </Button>
              </div>
            )}
          </div>
          {keyConfigured && !editingKey ? (
            <Input id="gemini_api_key" value="••••••••••••••••" readOnly disabled />
          ) : (
            <div className="relative">
              <Input
                id="gemini_api_key"
                type={showKey ? 'text' : 'password'}
                value={form.api_key}
                placeholder={keyConfigured ? 'Informe a nova chave' : 'Cole a chave da API Gemini'}
                onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                autoComplete="new-password"
                required={!keyConfigured}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
                onClick={() => setShowKey((value) => !value)}
                aria-label={showKey ? 'Ocultar chave' : 'Mostrar chave'}
              >
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          )}
          {keyConfigured && <p className="mt-1 text-xs text-muted">Chave cadastrada no servidor (não exibida após salvar).</p>}
        </div>

        <div className="rounded-md border border-line bg-paper/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <Label htmlFor="gemini_model">Modelo</Label>
              <p className="mt-1 text-xs text-muted">
                Lista obtida da sua conta Gemini. Modelos Flash mais recentes aparecem primeiro.
              </p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={busy || modelsLoading || !keyConfigured}
              onClick={() => void loadModels()}
            >
              {modelsLoading ? 'Atualizando…' : 'Atualizar lista'}
            </Button>
          </div>
          {modelsError ? <p className="mt-2 text-sm text-red-700">{modelsError}</p> : null}
          <select
            id="gemini_model"
            className="mt-3 w-full max-w-xl rounded-md border border-line bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
            value={form.model_id}
            disabled={!keyConfigured || modelsLoading || modelOptions.length === 0}
            onChange={(event) => setForm({ ...form, model_id: event.target.value })}
          >
            {!keyConfigured ? (
              <option value="">Salve a chave da API para carregar os modelos</option>
            ) : modelsLoading ? (
              <option value="">Carregando modelos disponíveis…</option>
            ) : modelOptions.length === 0 ? (
              <option value="">Nenhum modelo disponível — use «Atualizar lista»</option>
            ) : (
              <>
                <option value="">Selecione um modelo</option>
                {modelOptions.map((model) => {
                  const isFlash = model.id.toLowerCase().includes('flash')
                  const label = model.display_name
                    ? `${model.display_name} (${model.id})`
                    : model.id
                  return (
                    <option key={model.id} value={model.id}>
                      {isFlash ? `⚡ ${label}` : label}
                    </option>
                  )
                })}
              </>
            )}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.enabled}
            disabled={!keyConfigured}
            onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
          />
          Integração habilitada
        </label>

        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-900">{error}</p>}
        {saveMessage && (
          <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{saveMessage}</p>
        )}
        {testMessage && (
          <p
            className={`rounded-md px-3 py-2 text-sm ${
              testOk ? 'bg-emerald-50 text-emerald-900' : 'bg-red-50 text-red-900'
            }`}
          >
            {testMessage}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" disabled={busy || !canTest} onClick={() => void testConnection()}>
            Testar conexão
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? 'Salvando…' : 'Salvar configurações'}
          </Button>
        </div>
      </form>
    </Card>
  )
}
