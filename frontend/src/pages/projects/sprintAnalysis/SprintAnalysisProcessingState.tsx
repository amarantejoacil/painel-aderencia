import { useEffect, useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/card'

const STEPS = [
  'Consultando histórias, tasks e revisões no Azure DevOps',
  'Calculando indicadores e organizando evidências',
  'Gerando o relatório executivo com o modelo de IA',
] as const

export function SprintAnalysisProcessingState({
  status,
}: {
  status: 'pending' | 'running' | 'loading'
}) {
  const [stepIndex, setStepIndex] = useState(status === 'pending' ? 0 : 1)

  useEffect(() => {
    if (status === 'pending') {
      setStepIndex(0)
      return
    }
    const timer = window.setInterval(() => {
      setStepIndex((current) => (current + 1) % STEPS.length)
    }, 3200)
    return () => window.clearInterval(timer)
  }, [status])

  const label =
    status === 'loading'
      ? 'Preparando análise…'
      : status === 'pending'
        ? 'Análise na fila de processamento…'
        : 'Processando análise…'

  return (
    <div className="mx-auto max-w-6xl space-y-6" aria-live="polite" aria-busy="true">
      <Card className="overflow-hidden border-line p-0">
        <div className="flex flex-col gap-6 p-6 sm:flex-row sm:items-start">
          <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent/10">
            <Loader2 className="h-7 w-7 animate-spin text-accent" aria-hidden />
            <Sparkles
              className="absolute -right-0.5 -top-0.5 h-4 w-4 text-accent/80 motion-safe:animate-pulse"
              aria-hidden
            />
          </div>
          <div className="min-w-0 flex-1 space-y-3">
            <p className="text-base font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-relaxed text-muted">
              Coletamos os registros no Azure DevOps, montamos os indicadores no painel e só então o modelo
              interpreta o conteúdo. Esta página atualiza automaticamente — não é necessário recarregar.
            </p>
            <ul className="space-y-2 pt-1">
              {STEPS.map((step, index) => {
                const active = index === stepIndex
                const done = index < stepIndex && status !== 'pending'
                return (
                  <li
                    key={step}
                    className={`flex items-start gap-2 text-sm transition-opacity duration-500 ${
                      active ? 'font-medium text-foreground opacity-100' : 'text-muted opacity-70'
                    }`}
                  >
                    <span
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                        active
                          ? 'bg-accent motion-safe:animate-pulse'
                          : done
                            ? 'bg-emerald-500'
                            : 'bg-line'
                      }`}
                      aria-hidden
                    />
                    <span>{step}</span>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
        <div className="h-1 w-full overflow-hidden bg-slate-100">
          <div className="sprint-analysis-progress h-full w-1/3 bg-accent/70" />
        </div>
      </Card>

      <div className="space-y-4 motion-safe:animate-pulse" aria-hidden>
        <div className="h-8 w-2/5 max-w-xs rounded-md bg-slate-200/80" />
        <div className="space-y-2">
          <div className="h-3 w-full rounded bg-slate-100" />
          <div className="h-3 w-full rounded bg-slate-100" />
          <div className="h-3 w-4/5 rounded bg-slate-100" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((key) => (
            <div key={key} className="h-20 rounded-lg border border-line bg-white" />
          ))}
        </div>
        <div className="h-32 rounded-lg border border-line bg-white" />
      </div>
    </div>
  )
}
