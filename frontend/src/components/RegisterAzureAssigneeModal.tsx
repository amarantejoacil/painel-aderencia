import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'

type RegisterAzureAssigneeModalProps = {
  assigneeName: string
  defaultStartDate: string
  onClose: () => void
  onRegistered: () => void | Promise<void>
}

export function RegisterAzureAssigneeModal({
  assigneeName,
  defaultStartDate,
  onClose,
  onRegistered,
}: RegisterAzureAssigneeModalProps) {
  const [name, setName] = useState(assigneeName)
  const [azureName, setAzureName] = useState(assigneeName)
  const [startDate, setStartDate] = useState(defaultStartDate)
  const [dailyHours, setDailyHours] = useState('8')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createCollaborator({
        name: name.trim(),
        azure_name: azureName.trim(),
        start_date: startDate,
        end_date: null,
        daily_hours: Number(dailyHours),
        active: true,
      })
      await onRegistered()
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="presentation"
    >
      <Card
        className="w-full max-w-lg p-5"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">Cadastrar colaborador</h3>
        <p className="mt-1 text-sm text-muted">
          Este responsável aparece no Azure DevOps, mas ainda não está no painel. Ao confirmar, ele
          passará a entrar na aderência, dashboard e demais rotinas do período.
        </p>

        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

        <form className="mt-4 space-y-3" onSubmit={(event) => void submit(event)}>
          <div>
            <Label htmlFor="reg-name">Nome no painel</Label>
            <Input
              id="reg-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="reg-azure">Nome no Azure (Assigned To)</Label>
            <Input
              id="reg-azure"
              value={azureName}
              onChange={(event) => setAzureName(event.target.value)}
              required
            />
            <p className="mt-1 text-xs text-muted">
              Deve coincidir com o responsável nas Tasks importadas.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="reg-start">Data de entrada</Label>
              <Input
                id="reg-start"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="reg-hours">Horas diárias</Label>
              <Input
                id="reg-hours"
                type="number"
                min={1}
                max={24}
                step="any"
                inputMode="decimal"
                value={dailyHours}
                onChange={(event) => setDailyHours(event.target.value)}
                required
              />
              <p className="mt-1 text-xs text-muted">Carga diária usual: 8 horas.</p>
            </div>
          </div>
          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" disabled={busy} onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? 'Salvando…' : 'Cadastrar e incluir nas rotinas'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
