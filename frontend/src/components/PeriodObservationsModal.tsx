import { useCallback, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { monthLabel } from '@/lib/format'

type PeriodObservationsModalProps = {
  year: number
  month: number
  text: string
  onClose: () => void
}

export function PeriodObservationsModal({
  year,
  month,
  text,
  onClose,
}: PeriodObservationsModalProps) {
  const [copied, setCopied] = useState(false)

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }, [text])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <Card
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden p-0"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <h3 className="text-lg font-semibold">Observações para o relatório</h3>
            <p className="mt-1 text-sm text-muted">
              {monthLabel(year, month)} — liberações, feriados e ausências cadastradas no calendário.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={copy}>
              {copied ? 'Copiado!' : 'Copiar texto'}
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
        <div className="overflow-auto px-5 py-4">
          <textarea
            readOnly
            className="min-h-[320px] w-full resize-y rounded-md border border-line bg-paper px-3 py-2 font-mono text-sm leading-relaxed"
            value={text}
            aria-label="Texto das observações do período"
          />
        </div>
      </Card>
    </div>
  )
}
