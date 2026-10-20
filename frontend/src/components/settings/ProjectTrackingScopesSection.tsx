import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, type ProjectTrackingScopeSettings } from '@/lib/api'

export function ProjectTrackingScopesSection() {
  const [data, setData] = useState<ProjectTrackingScopeSettings | null>(null)
  const [ignored, setIgnored] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await api.getProjectTrackingScopeSettings()
      setData(payload)
      setIgnored(new Set(payload.ignored_scope_keys))
    } catch (err) {
      setError((err as Error).message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const filteredScopes = useMemo(() => {
    const rows = data?.scopes ?? []
    const term = filter.trim().toLowerCase()
    if (!term) return rows
    return rows.filter(
      (item) =>
        item.label.toLowerCase().includes(term) ||
        item.team_project.toLowerCase().includes(term) ||
        item.area_path.toLowerCase().includes(term),
    )
  }, [data?.scopes, filter])

  const toggle = (key: string) => {
    setIgnored((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    setMessage(null)
  }

  const save = async () => {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const updated = await api.updateProjectTrackingIgnoredScopes([...ignored])
      setData(updated)
      setIgnored(new Set(updated.ignored_scope_keys))
      setMessage('Escopos ignorados atualizados. Eles deixam de aparecer nos filtros do acompanhamento de projetos.')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="space-y-4 p-5">
      <div>
        <h3 className="text-lg font-semibold">Escopos ignorados — Acompanhamento de Projetos</h3>
        <p className="mt-1 text-sm text-muted">
          Áreas marcadas aqui não aparecem nos filtros (Visão Geral, Sprints, Evolução, Relatórios) e não são
          consultadas no Azure DevOps por esse módulo. Não afeta a Aderência de Atividades.
        </p>
      </div>

      {error ? <p className="text-sm text-red-900">{error}</p> : null}
      {message ? <p className="text-sm text-accent">{message}</p> : null}

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[240px] flex-1">
          <Label htmlFor="scope-filter">Filtrar lista</Label>
          <Input
            id="scope-filter"
            className="mt-1"
            placeholder="Nome da área ou projeto…"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
        <Button type="button" variant="secondary" disabled={busy || loading} onClick={() => void load()}>
          Atualizar lista do Azure
        </Button>
        <Button type="button" disabled={busy || loading || !data} onClick={() => void save()}>
          {busy ? 'Salvando…' : 'Salvar ignorados'}
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Carregando áreas do Azure DevOps…</p>
      ) : !data?.scopes.length ? (
        <p className="text-sm text-muted">
          Nenhuma área disponível. Verifique a conexão com o Azure DevOps e os projetos selecionados na aba
          anterior.
        </p>
      ) : (
        <div className="max-h-[420px] overflow-y-auto rounded-lg border border-line">
          <ul className="divide-y divide-line">
            {filteredScopes.map((scope) => {
              const checked = ignored.has(scope.key)
              return (
                <li key={scope.key}>
                  <label className="flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={checked}
                      onChange={() => toggle(scope.key)}
                    />
                    <span className="text-sm">
                      <span className="font-medium">
                        {scope.team_project} · {scope.label}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">{scope.area_path}</span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <p className="text-xs text-muted">
        {ignored.size} área(s) ignorada(s)
        {data ? ` · ${data.scopes.length} área(s) disponíveis no catálogo` : null}
      </p>
    </Card>
  )
}
