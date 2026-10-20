import { useMemo } from 'react'
import { Label } from '@/components/ui/label'
import type { ProjectScope } from '@/lib/api'
import { monthLabel } from '@/lib/format'

export function ProjectPeriodFilters({
  year,
  month,
  scopeKey,
  scopes,
  onYearChange,
  onMonthChange,
  onScopeChange,
  allowAllScopes = true,
  allowFullYear = false,
  hideScope = false,
  scopePlaceholder = '',
  areaScopesOnly = false,
}: {
  year: number
  month: number
  scopeKey: string
  scopes: ProjectScope[]
  onYearChange: (year: number) => void
  onMonthChange: (month: number) => void
  onScopeChange: (scopeKey: string) => void
  allowAllScopes?: boolean
  allowFullYear?: boolean
  hideScope?: boolean
  scopePlaceholder?: string
  areaScopesOnly?: boolean
}) {
  const scopeOptions = useMemo(
    () => (areaScopesOnly ? scopes.filter((scope) => scope.area_path) : scopes),
    [scopes, areaScopesOnly],
  )
  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, index) => ({
        value: index + 1,
        label: new Date(2026, index, 1).toLocaleDateString('pt-BR', { month: 'long' }),
      })),
    [],
  )

  const years = useMemo(() => {
    const current = new Date().getFullYear()
    return [current - 1, current, current + 1]
  }, [])

  return (
    <div
      className={`grid gap-4 rounded-xl border border-line bg-card p-4 ${hideScope ? 'md:grid-cols-2' : 'md:grid-cols-3'}`}
    >
      {hideScope ? null : (
        <div>
          <Label htmlFor="project-scope">Projeto / área</Label>
          <select
            id="project-scope"
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
            value={scopeKey}
            onChange={(event) => onScopeChange(event.target.value)}
          >
            {scopePlaceholder ? <option value="">{scopePlaceholder}</option> : null}
            {allowAllScopes ? <option value="">Todos (visão consolidada)</option> : null}
            {scopeOptions.map((scope) => (
              <option key={scope.key} value={scope.key}>
                {scope.area_path ? `${scope.team_project} · ${scope.label}` : scope.label}
              </option>
            ))}
          </select>
        </div>
      )}
      <div>
        <Label htmlFor="project-month">Mês</Label>
        <select
          id="project-month"
          className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
          value={month}
          onChange={(event) => onMonthChange(Number(event.target.value))}
        >
          {allowFullYear ? <option value={0}>Ano inteiro</option> : null}
          {months.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor="project-year">Ano</Label>
        <select
          id="project-year"
          className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
          value={year}
          onChange={(event) => onYearChange(Number(event.target.value))}
        >
          {years.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <p className={`text-sm text-muted ${hideScope ? 'md:col-span-2' : 'md:col-span-3'}`}>
        Período:{' '}
        {month === 0 ? `Ano de ${year}` : monthLabel(year, month)}. Sprints entram quando o
        intervalo de execução cruza o período selecionado.
      </p>
    </div>
  )
}
