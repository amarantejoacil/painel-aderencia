export const STATUS_LABEL: Record<string, string> = {
  regular: 'Regular',
  incomplete: 'Incompleto',
  missing: 'Sem lançamento',
  excess: 'Excedente',
  not_required: 'Não exigido',
}

export const EXCEPTION_LABEL: Record<string, string> = {
  holiday: 'Feriado',
  optional_day: 'Ponto facultativo',
}

export function formatHours(value: number | string): string {
  const amount = Number(value)
  return `${amount.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}h`
}

export function formatPercent(value: number | string): string {
  return `${Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
}

export function formatDate(value: string): string {
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

export function currentYearMonth(): { year: number; month: number } {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
}

export function monthLabel(year: number, month: number): string {
  const label = new Date(year, month - 1, 1).toLocaleDateString('pt-BR', {
    month: 'long',
    year: 'numeric',
  })
  return label.charAt(0).toUpperCase() + label.slice(1)
}
