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
  projects: string[]
  pat: string
  pat_expires_at: string
}

const EMPTY_FORM: FormState = {
  base_url: '',
  organization: '',
  projects: [],
  pat: '',
  pat_expires_at: '',
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AzureDevOpsSettings | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [remoteProjects, setRemoteProjects] = useState<string[]>([])
  const [manualProject, setManualProject] = useState('')
  const [editingPat, setEditingPat] = useState(false)
  const [showPat, setShowPat] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [testMessage, setTestMessage] = useState<string | null>(null)
  const [testOk, setTestOk] = useState<boolean | null>(null)

  const load = async () => {
    setError(null)
    try {
      const data = await api.getAzureDevOpsSettings()
      setSettings(data)
      const projects =
        data.projects?.length > 0 ? data.projects : data.project ? [data.project] : []
      setForm({
        base_url: data.base_url ?? '',
        organization: data.organization ?? '',
        projects,
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

  const toggleProject = (name: string) => {
    setForm((current) => {
      const selected = new Set(current.projects)
      if (selected.has(name)) selected.delete(name)
      else selected.add(name)
      return { ...current, projects: [...selected] }
    })
  }

  const addManualProject = () => {
    const label = manualProject.trim()
    if (!label) return
    setForm((current) => {
      if (current.projects.some((item) => item.toLowerCase() === label.toLowerCase())) {
        return current
      }
      return { ...current, projects: [...current.projects, label] }
    })
    setManualProject('')
  }

  const loadRemoteProjects = async () => {
    setProjectsError(null)
    setBusy(true)
    try {
      const names = await api.listAzureDevOpsProjects()
      setRemoteProjects(names)
      if (names.length === 0) {
        setProjectsError('Nenhum projeto retornado pelo Azure DevOps.')
      }
    } catch (err) {
      setProjectsError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (form.projects.length === 0) {
      setError('Selecione ao menos um projeto para sincronizar.')
      return
    }
    setBusy(true)
    setError(null)
    setSaveMessage(null)
    try {
      const payload = {
        base_url: form.base_url.trim(),
        organization: form.organization.trim(),
        projects: form.projects,
        pat: form.pat.trim() ? form.pat.trim() : null,
        pat_expires_at: form.pat_expires_at || null,
      }
      const updated = await api.updateAzureDevOpsSettings(payload)
      setSettings(updated)
      setForm((current) => ({
        ...current,
        projects: updated.projects?.length ? updated.projects : current.projects,
        pat: '',
      }))
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
      setTestMessage(
        result.message ??
          (result.ok ? 'Conexão realizada com sucesso' : 'Não foi possível conectar ao Azure DevOps'),
      )
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
  const displayProjects =
    settings?.projects?.length ? settings.projects : settings?.project ? [settings.project] : []

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
            {displayProjects.length > 0 && (
              <p className="mt-1 max-w-md">
                <span className="text-muted">Projetos sincronizados: </span>
                <span className="font-medium">{displayProjects.join(', ')}</span>
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
            <div className="md:col-span-2">
              <Label htmlFor="organization">Organização / Collection</Label>
              <Input
                id="organization"
                value={form.organization}
                placeholder="NucleoIA"
                onChange={(event) => setForm({ ...form, organization: event.target.value })}
                required
              />
            </div>
          </div>

          <div className="rounded-md border border-line bg-paper/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <Label>Projetos para sincronizar</Label>
                <p className="mt-1 text-xs text-muted">
                  Marque todos os projetos em que a equipe lança Tasks (ex.: Inteligência Artificial e Hannah).
                </p>
              </div>
              <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void loadRemoteProjects()}>
                Carregar projetos do Azure
              </Button>
            </div>

            {projectsError && <p className="mt-2 text-sm text-red-700">{projectsError}</p>}

            {remoteProjects.length > 0 && (
              <div className="mt-3 grid max-h-52 gap-2 overflow-y-auto sm:grid-cols-2">
                {remoteProjects.map((name) => (
                  <label key={name} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.projects.includes(name)}
                      onChange={() => toggleProject(name)}
                    />
                    {name}
                  </label>
                ))}
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-2">
              <Input
                value={manualProject}
                placeholder="Adicionar projeto manualmente (ex.: Hannah)"
                onChange={(event) => setManualProject(event.target.value)}
                className="max-w-sm"
              />
              <Button type="button" variant="secondary" onClick={addManualProject}>
                Adicionar
              </Button>
            </div>

            {form.projects.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {form.projects.map((name) => (
                  <button
                    key={name}
                    type="button"
                    className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent"
                    onClick={() => toggleProject(name)}
                    title="Remover"
                  >
                    {name} ×
                  </button>
                ))}
              </div>
            )}
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
            {patConfigured && <p className="mt-1 text-xs text-muted">PAT configurado: Sim</p>}
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
              <p className="mt-1 text-xs text-muted">Expira em: {formatDate(settings.pat_expires_at)}</p>
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
        busca Tasks em todos os projetos selecionados. A importação CSV permanece independente.
      </p>
    </div>
  )
}
