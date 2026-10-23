export const STATUS_LABEL: Record<string, string> = {
  regular: 'Regular',
  incomplete: 'Incompleto',
  missing: 'Sem lançamento',
  excess: 'Excedente',
  not_required: 'Não exigido',
  justified_absence: 'Ausência justificada',
}

export function dayStatusLabel(status: string, absenceType?: string | null): string {
  if (status === 'justified_absence' && absenceType) {
    return ABSENCE_TYPE_LABEL[absenceType] ?? STATUS_LABEL.justified_absence
  }
  return STATUS_LABEL[status] ?? status
}

/** Dia útil após a data de desligamento (inclusive): não exige lançamento do Azure. */
export function collaboratorDaySituationLabel(
  status: string,
  dayDate: string,
  endDate: string | null | undefined,
  absenceType?: string | null,
): string {
  if (
    endDate &&
    dayDate >= endDate &&
    status === 'not_required' &&
    !isWeekendDate(dayDate)
  ) {
    return 'Desligado'
  }
  return dayStatusLabel(status, absenceType)
}

export const ABSENCE_TYPE_LABEL: Record<string, string> = {
  medical_certificate: 'Atestado médico',
  vacation: 'Férias',
  day_off: 'Folga',
  leave: 'Licença',
  work_release: 'Liberação de expediente',
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
  work_release: 'Liberação de expediente',
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

export function formatDateRange(start: string, end: string): string {
  if (start === end) return formatDate(start)
  return `${formatDate(start)} – ${formatDate(end)}`
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

/** Dias úteis (seg–sex) entre duas datas ISO inclusivas. */
export function countWeekdaysBetween(startIso: string, endIso: string): number {
  if (!startIso || !endIso) return 0
  const [sy, sm, sd] = startIso.split('-').map(Number)
  const [ey, em, ed] = endIso.split('-').map(Number)
  const start = new Date(sy, sm - 1, sd)
  const end = new Date(ey, em - 1, ed)
  if (end < start) return 0
  let count = 0
  const cursor = new Date(start)
  while (cursor <= end) {
    const day = cursor.getDay()
    if (day !== 0 && day !== 6) count += 1
    cursor.setDate(cursor.getDate() + 1)
  }
  return count
}

/** Dias úteis do intervalo que caem no mês/ano informados. */
export function countWeekdaysInMonthRange(
  startIso: string,
  endIso: string,
  year: number,
  month: number,
): number {
  if (!startIso || !endIso) return 0
  const monthStart = `${year}-${String(month).padStart(2, '0')}-01`
  const lastDay = new Date(year, month, 0).getDate()
  const monthEnd = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  const clipStart = startIso > monthStart ? startIso : monthStart
  const clipEnd = endIso < monthEnd ? endIso : monthEnd
  if (clipEnd < clipStart) return 0
  return countWeekdaysBetween(clipStart, clipEnd)
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
