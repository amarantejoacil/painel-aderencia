export const STATUS_LABEL: Record<string, string> = {
  regular: 'Regular',
  incomplete: 'Incompleto',
  missing: 'Sem lançamento',
  excess: 'Excedente',
  not_required: 'Não exigido',
  justified_absence: 'Ausência justificada',
}

export const ABSENCE_TYPE_LABEL: Record<string, string> = {
  medical_certificate: 'Atestado médico',
  vacation: 'Férias',
  day_off: 'Folga',
  leave: 'Licença',
  other: 'Outro',
}

export const AZURE_STATE_LABEL: Record<string, string> = {
  closed: 'Concluído',
  done: 'Concluído',
  resolved: 'Resolvido',
  active: 'Ativo',
  new: 'Novo',
  removed: 'Removido',
  cut: 'Cortado',
  inactive: 'Inativo',
  'in progress': 'Em andamento',
  inprogress: 'Em andamento',
}

export function formatAzureState(state: string | null | undefined): string {
  if (!state?.trim()) return '—'
  return AZURE_STATE_LABEL[state.trim().toLowerCase()] ?? state.trim()
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

/** Timestamps da API são UTC sem sufixo Z — normaliza antes de exibir no fuso local. */
export function parseApiDateTime(value: string): Date {
  if (!value) return new Date(Number.NaN)
  const hasTimezone = /[zZ]$|[+-]\d{2}:\d{2}$/.test(value)
  const normalized = value.includes('T') && !hasTimezone ? `${value}Z` : value
  return new Date(normalized)
}

export function formatDateTime(value: string): string {
  const date = parseApiDateTime(value)
  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDateWithWeekday(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  const weekday = date.toLocaleDateString('pt-BR', { weekday: 'long' })
  const label = weekday.charAt(0).toUpperCase() + weekday.slice(1)
  return `${formatDate(value)} · ${label}`
}

export function isWeekendDate(value: string): boolean {
  const [year, month, day] = value.split('-').map(Number)
  const weekday = new Date(year, month - 1, day).getDay()
  return weekday === 0 || weekday === 6
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
