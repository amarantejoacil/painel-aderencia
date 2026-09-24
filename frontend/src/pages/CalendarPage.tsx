import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type CalendarException, type Collaborator } from '@/lib/api'
import { EXCEPTION_LABEL, formatDate } from '@/lib/format'

const EMPTY_FORM = {
  date: '',
  type: 'optional_day' as CalendarException['type'],
  description: '',
}

const EMPTY_RELEASE = {
  scope: 'team' as 'team' | 'collaborators',
  start_date: '',
  end_date: '',
  description: '',
  collaborator_ids: [] as number[],
}

export function CalendarPage() {
  const [rows, setRows] = useState<CalendarException[]>([])
  const [collaborators, setCollaborators] = useState<Collaborator[]>([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [release, setRelease] = useState(EMPTY_RELEASE)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [releaseError, setReleaseError] = useState<string | null>(null)
  const [releaseSuccess, setReleaseSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const activeCollaborators = useMemo(
    () => collaborators.filter((row) => row.active && !row.end_date),
    [collaborators],
  )

  const load = () => {
    setLoading(true)
    Promise.all([api.listExceptions(), api.listCollaborators()])
      .then(([exceptions, people]) => {
        setRows(exceptions)
        setCollaborators(people)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const resetForm = () => {
    setForm(EMPTY_FORM)
    setEditingId(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const payload = {
      date: form.date,
      type: form.type,
      description: form.description.trim(),
    }
    try {
      if (editingId) {
        await api.updateException(editingId, payload)
      } else {
        await api.createException(payload)
      }
      resetForm()
      load()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const submitRelease = async (event: FormEvent) => {
    event.preventDefault()
    setReleaseError(null)
    setReleaseSuccess(null)
    const endDate = release.end_date || release.start_date
    try {
      const result = await api.createWorkRelease({
        scope: release.scope,
        collaborator_ids: release.scope === 'collaborators' ? release.collaborator_ids : [],
        start_date: release.start_date,
        end_date: endDate,
        description: release.description.trim(),
      })
      if (result.scope === 'team') {
        setReleaseSuccess(
          `Liberação registrada para toda a equipe em ${result.calendar_days} dia(s) no calendário.`,
        )
      } else {
        setReleaseSuccess(
          `Liberação registrada para ${result.collaborator_count} colaborador(es) no período informado.`,
        )
      }
      setRelease(EMPTY_RELEASE)
      load()
    } catch (err) {
      setReleaseError((err as Error).message)
    }
  }

  const toggleCollaborator = (id: number) => {
    setRelease((current) => {
      const selected = new Set(current.collaborator_ids)
      if (selected.has(id)) selected.delete(id)
      else selected.add(id)
      return { ...current, collaborator_ids: [...selected] }
    })
  }

  const edit = (row: CalendarException) => {
    setEditingId(row.id)
    setForm({
      date: row.date,
      type: row.type,
      description: row.description,
    })
    setError(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Calendário e liberações</h2>
        <p className="mt-1 text-sm text-muted">
          Registre feriados, pontos facultativos ou liberações de expediente. Nesses dias, os colaboradores afetados não
          precisam lançar Tasks no Azure.
        </p>
      </div>

      <Card>
        <h3 className="text-lg font-semibold">Liberação de expediente</h3>
        <p className="mt-1 text-sm text-muted">
          Use para dias em que a equipe toda ou pessoas específicas foram liberadas e não devem ser cobradas por
          lançamento.
        </p>
        <form className="mt-4 space-y-4" onSubmit={submitRelease}>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="release-scope"
                checked={release.scope === 'team'}
                onChange={() => setRelease({ ...release, scope: 'team', collaborator_ids: [] })}
              />
              Toda a equipe
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="release-scope"
                checked={release.scope === 'collaborators'}
                onChange={() => setRelease({ ...release, scope: 'collaborators' })}
              />
              Colaboradores específicos
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <Label htmlFor="release-start">Data inicial</Label>
              <Input
                id="release-start"
                type="date"
                value={release.start_date}
                onChange={(e) => setRelease({ ...release, start_date: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="release-end">Data final</Label>
              <Input
                id="release-end"
                type="date"
                value={release.end_date}
                min={release.start_date || undefined}
                onChange={(e) => setRelease({ ...release, end_date: e.target.value })}
                placeholder="Opcional para um único dia"
              />
            </div>
            <div>
              <Label htmlFor="release-desc">Motivo / observação</Label>
              <Input
                id="release-desc"
                value={release.description}
                onChange={(e) => setRelease({ ...release, description: e.target.value })}
                placeholder="Ex.: Liberados pela chefia"
                required
              />
            </div>
          </div>

          {release.scope === 'collaborators' && (
            <div className="rounded-md border border-line bg-paper/50 p-3">
              <p className="text-sm font-medium">Selecione os colaboradores</p>
              <div className="mt-2 grid max-h-48 gap-2 overflow-y-auto sm:grid-cols-2">
                {activeCollaborators.map((person) => (
                  <label key={person.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={release.collaborator_ids.includes(person.id)}
                      onChange={() => toggleCollaborator(person.id)}
                    />
                    {person.name}
                  </label>
                ))}
              </div>
              {activeCollaborators.length === 0 && (
                <p className="mt-2 text-sm text-muted">Nenhum colaborador ativo disponível.</p>
              )}
            </div>
          )}

          <Button type="submit">Registrar liberação</Button>
        </form>
        {releaseError && <p className="mt-3 text-sm text-red-700">{releaseError}</p>}
        {releaseSuccess && <p className="mt-3 text-sm text-emerald-800">{releaseSuccess}</p>}
      </Card>

      <Card>
        <h3 className="text-lg font-semibold">Exceção de calendário (dia único)</h3>
        <p className="mt-1 text-sm text-muted">Feriados e pontos facultativos que valem para toda a equipe.</p>
        <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={submit}>
          <div>
            <Label htmlFor="date">Data</Label>
            <Input
              id="date"
              type="date"
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="type">Tipo</Label>
            <select
              id="type"
              className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value as CalendarException['type'] })}
            >
              <option value="optional_day">Ponto facultativo</option>
              <option value="holiday">Feriado</option>
              <option value="work_release">Liberação de expediente</option>
            </select>
          </div>
          <div>
            <Label htmlFor="desc">Descrição</Label>
            <Input
              id="desc"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Ex.: TJMT"
              required
            />
          </div>
          <div className="flex flex-wrap gap-2 md:col-span-3">
            <Button type="submit">{editingId ? 'Salvar alteração' : 'Cadastrar exceção'}</Button>
            {editingId && (
              <Button type="button" variant="secondary" onClick={resetForm}>
                Cancelar
              </Button>
            )}
          </div>
        </form>
        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      </Card>

      <Card className="p-0">
        {loading ? (
          <p className="p-6 text-sm text-muted">Carregando calendário…</p>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted">Nenhuma exceção cadastrada.</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Data</Th>
                <Th>Tipo</Th>
                <Th>Descrição</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <Td>{formatDate(row.date)}</Td>
                  <Td>{EXCEPTION_LABEL[row.type] ?? row.type}</Td>
                  <Td>{row.description}</Td>
                  <Td className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="secondary" onClick={() => edit(row)}>
                        Alterar
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={async () => {
                          await api.deleteException(row.id)
                          if (editingId === row.id) resetForm()
                          load()
                        }}
                      >
                        Remover
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
