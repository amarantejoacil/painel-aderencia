import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type Collaborator } from '@/lib/api'
import { formatDate, formatHours } from '@/lib/format'

const EMPTY = {
  name: '',
  azure_name: '',
  start_date: '',
  end_date: '',
  daily_hours: '8',
  active: true,
}

export function CollaboratorsPage() {
  const [rows, setRows] = useState<Collaborator[]>([])
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api
      .listCollaborators()
      .then(setRows)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const payload = {
      name: form.name.trim(),
      azure_name: form.azure_name.trim(),
      start_date: form.start_date,
      end_date: form.end_date || null,
      daily_hours: Number(form.daily_hours),
      active: form.active,
    }
    try {
      if (editingId) {
        await api.updateCollaborator(editingId, payload)
      } else {
        await api.createCollaborator(payload)
      }
      setForm(EMPTY)
      setEditingId(null)
      load()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const edit = (row: Collaborator) => {
    setEditingId(row.id)
    setForm({
      name: row.name,
      azure_name: row.azure_name,
      start_date: row.start_date,
      end_date: row.end_date ?? '',
      daily_hours: String(row.daily_hours),
      active: row.active,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Colaboradores</h2>
        <p className="mt-1 text-sm text-muted">
          O nome do Azure precisa ser igual ao texto que aparece em Assigned To, sem a matrícula.
        </p>
      </div>

      <Card>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={submit}>
          <div>
            <Label htmlFor="name">Nome</Label>
            <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <Label htmlFor="azure">Nome utilizado no Azure</Label>
            <Input
              id="azure"
              value={form.azure_name}
              onChange={(e) => setForm({ ...form, azure_name: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="start">Data de entrada</Label>
            <Input
              id="start"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="end">Data de saída</Label>
            <Input
              id="end"
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="hours">Carga diária (horas)</Label>
            <Input
              id="hours"
              type="number"
              min="1"
              step="0.5"
              value={form.daily_hours}
              onChange={(e) => setForm({ ...form, daily_hours: e.target.value })}
              required
            />
          </div>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(e) => setForm({ ...form, active: e.target.checked })}
            />
            Ativo
          </label>
          <div className="md:col-span-2 flex gap-2">
            <Button type="submit">{editingId ? 'Salvar alteração' : 'Cadastrar colaborador'}</Button>
            {editingId && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setEditingId(null)
                  setForm(EMPTY)
                }}
              >
                Cancelar
              </Button>
            )}
          </div>
        </form>
        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      </Card>

      <Card className="p-0">
        {loading ? (
          <p className="p-6 text-sm text-muted">Carregando cadastro…</p>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted">Nenhum colaborador cadastrado ainda.</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Nome</Th>
                <Th>Nome no Azure</Th>
                <Th>Entrada</Th>
                <Th>Saída</Th>
                <Th>Carga</Th>
                <Th>Situação</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <Td className="font-medium">{row.name}</Td>
                  <Td>{row.azure_name}</Td>
                  <Td>{formatDate(row.start_date)}</Td>
                  <Td>{row.end_date ? formatDate(row.end_date) : '—'}</Td>
                  <Td>{formatHours(row.daily_hours)}</Td>
                  <Td>{row.active ? 'Ativo' : 'Inativo'}</Td>
                  <Td className="text-right">
                    <Button size="sm" variant="secondary" onClick={() => edit(row)}>
                      Editar
                    </Button>
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
