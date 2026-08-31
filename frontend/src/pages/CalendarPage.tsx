import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, Td, Th } from '@/components/ui/table'
import { api, type CalendarException } from '@/lib/api'
import { EXCEPTION_LABEL, formatDate } from '@/lib/format'

export function CalendarPage() {
  const [rows, setRows] = useState<CalendarException[]>([])
  const [date, setDate] = useState('')
  const [type, setType] = useState<'holiday' | 'optional_day'>('optional_day')
  const [description, setDescription] = useState('')
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

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await api.createException({ date, type, description: description.trim() })
      setDate('')
      setDescription('')
      load()
    } catch (err) {
      setError((err as Error).message)
    }
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
            <Input id="date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </div>
          <div>
            <Label htmlFor="type">Tipo</Label>
            <select
              id="type"
              className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value as 'holiday' | 'optional_day')}
            >
              <option value="optional_day">Ponto facultativo</option>
              <option value="holiday">Feriado</option>
            </select>
          </div>
          <div>
            <Label htmlFor="desc">Descrição</Label>
            <Input
              id="desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex.: TJMT"
              required
            />
          </div>
          <div className="md:col-span-3">
            <Button type="submit">Cadastrar exceção</Button>
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
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        await api.deleteException(row.id)
                        load()
                      }}
                    >
                      Remover
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
