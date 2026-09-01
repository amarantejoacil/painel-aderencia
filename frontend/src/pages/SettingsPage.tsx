import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, type AzureDevOpsSettings } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/format'

type FormState = {
  base_url: string
  organization: string
  project: string
  pat: string
  pat_expires_at: string
}

const EMPTY_FORM: FormState = {
  base_url: '',
  organization: '',
  project: '',
  pat: '',
  pat_expires_at: '',
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AzureDevOpsSettings | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [editingPat, setEditingPat] = useState(false)
  const [showPat, setShowPat] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [testMessage, setTestMessage] = useState<string | null>(null)
  const [testOk, setTestOk] = useState<boolean | null>(null)

  const load = async () => {
    setError(null)
    try {
      const data = await api.getAzureDevOpsSettings()
      setSettings(data)
      setForm({
        base_url: data.base_url ?? '',
        organization: data.organization ?? '',
        project: data.project ?? '',
        pat: '',
        pat_expires_at: data.pat_expires_at ?? '',
      })
      setEditingPat(!data.pat_configured)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setSaveMessage(null)
    try {
      const payload = {
        base_url: form.base_url.trim(),
        organization: form.organization.trim(),
        project: form.project.trim(),
        pat: form.pat.trim() ? form.pat.trim() : null,
        pat_expires_at: form.pat_expires_at || null,
      }
      const updated = await api.updateAzureDevOpsSettings(payload)
      setSettings(updated)
      setForm((current) => ({ ...current, pat: '' }))
      setEditingPat(false)
      setShowPat(false)
      setSaveMessage('Configurações salvas com sucesso.')
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
      const result = await api.testAzureDevOpsSettings()
      setTestOk(result.ok)
      setTestMessage(result.message ?? (result.ok ? 'Conexão realizada com sucesso' : 'Não foi possível conectar ao Azure DevOps'))
      await load()
    } catch (err) {
      setTestOk(false)
      setTestMessage((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const configured = settings?.configured ?? false
  const patConfigured = settings?.pat_configured ?? false

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Configurações</h2>
        <p className="mt-1 text-sm text-muted">
          Gerencie a integração com Azure DevOps utilizada pela sincronização de Tasks.
        </p>
      </div>

      <Card className="p-5">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold">Integração Azure DevOps</h3>
            <p className="mt-1 text-sm text-muted">Status da conexão e credenciais de acesso.</p>
          </div>
          <div className="text-sm">
            <p>
              <span className="text-muted">Status: </span>
              <span className={configured ? 'font-medium text-emerald-700' : 'font-medium text-muted'}>
                {configured ? 'Configurado' : 'Não configurado'}
              </span>
            </p>
            {settings?.last_test_at && (
              <p className="mt-1">
                <span className="text-muted">Último teste: </span>
                <span className="font-medium">
                  {formatDateTime(settings.last_test_at)}
                  {settings.last_test_ok === false ? ' · falhou' : settings.last_test_ok ? ' · ok' : ''}
                </span>
              </p>
            )}
            {settings?.project && (
              <p className="mt-1">
                <span className="text-muted">Projeto: </span>
                <span className="font-medium">{settings.project}</span>
              </p>
            )}
          </div>
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label htmlFor="base_url">URL do Azure DevOps</Label>
              <Input
                id="base_url"
                value={form.base_url}
                placeholder="https://azure-devops.tjmt.jus.br"
                onChange={(event) => setForm({ ...form, base_url: event.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="organization">Organização / Collection</Label>
              <Input
                id="organization"
                value={form.organization}
                placeholder="NucleoIA"
                onChange={(event) => setForm({ ...form, organization: event.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="project">Projeto</Label>
              <Input
                id="project"
                value={form.project}
                placeholder="Inteligência Artificial"
                onChange={(event) => setForm({ ...form, project: event.target.value })}
                required
              />
            </div>
          </div>

          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <Label htmlFor="pat">Personal Access Token (PAT)</Label>
              {patConfigured && !editingPat && (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setEditingPat(true)
                    setForm((current) => ({ ...current, pat: '' }))
                  }}
                >
                  Alterar PAT
                </Button>
              )}
            </div>
            {patConfigured && !editingPat ? (
              <Input id="pat" value="••••••••••••••••" readOnly disabled />
            ) : (
              <div className="relative">
                <Input
                  id="pat"
                  type={showPat ? 'text' : 'password'}
                  value={form.pat}
                  placeholder={patConfigured ? 'Informe o novo PAT' : 'Cole o PAT aqui'}
                  onChange={(event) => setForm({ ...form, pat: event.target.value })}
                  autoComplete="new-password"
                  required={!patConfigured}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
                  onClick={() => setShowPat((value) => !value)}
                  aria-label={showPat ? 'Ocultar PAT' : 'Mostrar PAT'}
                >
                  {showPat ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            )}
            {patConfigured && (
              <p className="mt-1 text-xs text-muted">PAT configurado: Sim</p>
            )}
          </div>

          <div className="md:w-1/2">
            <Label htmlFor="pat_expires_at">Expiração do PAT</Label>
            <Input
              id="pat_expires_at"
              type="date"
              value={form.pat_expires_at}
              onChange={(event) => setForm({ ...form, pat_expires_at: event.target.value })}
            />
            {settings?.pat_expires_at && patConfigured && (
              <p className="mt-1 text-xs text-muted">
                Expira em: {formatDate(settings.pat_expires_at)}
              </p>
            )}
          </div>

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
            <Button type="button" variant="secondary" disabled={busy || !configured} onClick={() => void testConnection()}>
              Testar conexão
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? 'Salvando…' : 'Salvar configurações'}
            </Button>
          </div>
        </form>
      </Card>

      <p className="text-sm text-muted">
        A sincronização na página de{' '}
        <Link to="/importacao" className="font-medium text-accent hover:underline">
          Importação
        </Link>{' '}
        utiliza automaticamente estas configurações. A importação CSV permanece independente.
      </p>
    </div>
  )
}
