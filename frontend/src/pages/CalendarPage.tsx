import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type CalendarException } from '@/lib/api'
import { EXCEPTION_LABEL, formatDate } from '@/lib/format'

const EMPTY_FORM = {
  date: '',
  type: 'optional_day' as CalendarException['type'],
  description: '',
}

export function CalendarPage() {
  const [rows, setRows] = useState<CalendarException[]>([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api
      .listExceptions()
      .then(setRows)
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
        <h2 className="text-2xl font-semibold">Calendário de exceções</h2>
        <p className="mt-1 text-sm text-muted">
          Feriados e pontos facultativos não geram pendência de lançamento.
        </p>
      </div>

      <Card>
        <form className="grid gap-3 md:grid-cols-3" onSubmit={submit}>
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
                  <Td>{EXCEPTION_LABEL[row.type]}</Td>
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
