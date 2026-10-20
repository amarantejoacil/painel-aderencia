import { useCallback, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { fieldClass } from '@/pages/timeEntries/TimeEntryShell'

const CATEGORIES = [
  'Acompanhamento dos projetos',
  'Planejamento e priorização',
  'Monitoramento de sprints',
  'Organização de backlog',
  'Alinhamento com analistas',
  'Reuniões com equipe técnica',
  'Apoio à gestão estratégica',
  'Acompanhamento de impedimentos',
  'Monitoramento de chamados e infraestrutura',
  'Elaboração de relatórios gerenciais',
  'Atualização de cronogramas',
  'Comunicação e acompanhamento das entregas',
  'Organização de demandas institucionais',
  'Apoio ao planejamento de novas iniciativas',
  'Acompanhamento de requisitos e validações',
]

type Props = {
  existingTitles: string[]
  onApply: (value: { title: string; description: string; hours: string | null }) => void
  embedded?: boolean
  batch?: boolean
  onBusyChange?: (busy: boolean) => void
}

export function SuggestSection({
  existingTitles,
  onApply,
  embedded = false,
  batch = false,
  onBusyChange,
}: Props) {
  const [selected, setSelected] = useState<string[]>([])
  const [text, setText] = useState('')
  const [hours, setHours] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const setBusyState = useCallback(
    (value: boolean) => {
      setBusy(value)
      onBusyChange?.(value)
    },
    [onBusyChange],
  )

  const suggest = useCallback(async () => {
    if (selected.length === 0) return
    setBusyState(true)
    setError(null)
    try {
      const informed = hours.trim() ? Number(hours.replace(',', '.')) : null
      const result = await api.suggestTimeEntry({
        categories: selected,
        text,
        hours: informed,
        existing_titles: existingTitles,
      })
      onApply({
        title: result.title,
        description: result.description,
        hours: result.hours == null ? null : String(Number(result.hours)),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível sugerir o texto.')
    } finally {
      setBusyState(false)
    }
  }, [existingTitles, hours, onApply, selected, setBusyState, text])

  function toggle(category: string) {
    setSelected((current) =>
      current.includes(category) ? current.filter((item) => item !== category) : [...current, category],
    )
  }

  const suggestLabel = batch
    ? busy
      ? 'Gerando título e descrição para o lote...'
      : 'Gerar com IA'
    : busy
      ? 'Analisando ações marcadas...'
      : 'Sugerir texto das ações marcadas'

  const intro = batch ? (
    <p className="text-sm text-muted">
      Marque as ações realizadas nos dias selecionados e clique em Gerar com IA para preencher título
      e descrição em todos os dias do lote, no contexto de gerência de projetos do Núcleo de Inteligência Artificial.
      Revise cada dia antes de enviar ao Azure.
    </p>
  ) : (
    <p className="text-sm text-muted">
      Marque as ações realizadas. O botão sugere o texto a partir delas. Ele fica editável e só vai ao Azure quando
      você confirmar o lançamento.
    </p>
  )

  const body = (
    <>
      <div>
        <h3 className={embedded ? 'text-sm font-semibold' : 'text-base font-semibold'}>Sugestões com IA</h3>
        {intro}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {CATEGORIES.map((category) => (
          <label key={category} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={selected.includes(category)}
              onChange={() => toggle(category)}
              disabled={busy}
            />
            <span>{category}</span>
          </label>
        ))}
      </div>
      {selected.length > 0 ? (
        <Button type="button" disabled={busy} onClick={() => void suggest()}>
          {suggestLabel}
        </Button>
      ) : (
        <p className="text-sm text-muted">Marque ao menos uma ação para gerar o texto com IA.</p>
      )}
      <div>
        <Label htmlFor="suggest-text">Complemento do que foi realizado (opcional)</Label>
        <textarea
          id="suggest-text"
          className={`${fieldClass} min-h-24`}
          value={text}
          onChange={(event) => setText(event.target.value)}
          disabled={busy}
        />
      </div>
      <div className="max-w-xs">
        <Label htmlFor="suggest-hours">Tempo informado (opcional)</Label>
        <Input
          id="suggest-hours"
          inputMode="decimal"
          value={hours}
          onChange={(event) => setHours(event.target.value)}
          disabled={busy}
        />
      </div>
      {existingTitles.length > 0 ? (
        <p className="text-xs text-muted">
          Títulos já informados no lote, usados só como contexto: {existingTitles.join('; ')}.
        </p>
      ) : null}
      {error ? <p className="text-sm text-red-800">{error}</p> : null}
    </>
  )

  if (embedded) {
    return <div className="space-y-4 rounded-md border border-line p-4">{body}</div>
  }

  return <Card className="space-y-4 p-5">{body}</Card>
}
