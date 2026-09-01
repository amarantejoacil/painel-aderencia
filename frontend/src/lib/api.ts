const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  })
  if (response.status === 204) {
    return undefined as T
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      data?.detail?.message ||
      (typeof data?.detail === 'string' ? data.detail : null) ||
      'Não foi possível concluir a operação.'
    const error = new Error(message) as Error & { details?: string[]; status: number }
    error.details = data?.detail?.details
    error.status = response.status
    throw error
  }
  return data as T
}

export type Collaborator = {
  id: number
  name: string
  azure_name: string
  start_date: string
  end_date: string | null
  daily_hours: number | string
  active: boolean
}

export type CalendarException = {
  id: number
  date: string
  type: 'holiday' | 'optional_day'
  description: string
}

export type ImportWarning = {
  kind: string
  message: string
  row: number | null
}

export type ImportResult = {
  id: number
  filename: string
  imported_at: string
  row_count: number
  mapped_count: number
  unmapped_count: number
  warning_count: number
  status: string
  warnings: ImportWarning[]
}

export type DayTask = {
  task_id: string
  title: string
  completed_hours: number | string | null
  state: string | null
  project: string | null
}

export type DayResult = {
  date: string
  expected: number | string
  executed: number | string
  difference: number | string
  status: string
  hours_source: string
  task_count: number
  tasks: DayTask[]
  absence_type?: string | null
  absence_note?: string | null
}

export type CollaboratorAbsence = {
  id: number
  collaborator_id: number
  type: 'medical_certificate' | 'vacation' | 'day_off' | 'leave' | 'other'
  start_date: string
  end_date: string
  note: string | null
}

export type CollaboratorSummary = {
  collaborator: Collaborator
  expected: number | string
  executed: number | string
  adherence: number | string
  regular: number
  incomplete: number
  missing: number
  excess: number
  not_required: number
  justified_absence: number
}

export type Dashboard = {
  year: number
  month: number
  indicators: {
    collaborators: number
    expected_hours: number | string
    executed_hours: number | string
    adherence: number | string
    regular: number
    incomplete: number
    missing: number
    excess: number
  }
  rows: CollaboratorSummary[]
}

export type CollaboratorAnalysis = {
  summary: CollaboratorSummary
  days: DayResult[]
}

export type InconsistenciesReportRow = {
  collaborator: Collaborator
  situation: 'ok' | 'pending'
  adherence: number | string
  missing: number
  incomplete: number
  excess: number
  summary_text: string
  pending_days: DayResult[]
}

export type InconsistenciesReport = {
  year: number
  month: number
  indicators: {
    collaborators: number
    ok: number
    with_issues: number
    missing: number
    incomplete: number
    excess: number
  }
  rows: InconsistenciesReportRow[]
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  listCollaborators: () => request<Collaborator[]>('/collaborators'),
  createCollaborator: (payload: Omit<Collaborator, 'id'>) =>
    request<Collaborator>('/collaborators', { method: 'POST', body: JSON.stringify(payload) }),
  updateCollaborator: (id: number, payload: Partial<Omit<Collaborator, 'id'>>) =>
    request<Collaborator>(`/collaborators/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteCollaborator: (id: number) => request<void>(`/collaborators/${id}`, { method: 'DELETE' }),
  listExceptions: () => request<CalendarException[]>('/calendar-exceptions'),
  createException: (payload: Omit<CalendarException, 'id'>) =>
    request<CalendarException>('/calendar-exceptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteException: (id: number) => request<void>(`/calendar-exceptions/${id}`, { method: 'DELETE' }),
  deleteImport: (id: number) => request<void>(`/imports/${id}`, { method: 'DELETE' }),
  latestImport: () => request<ImportResult | null>('/imports/latest'),
  uploadImport: async (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<ImportResult>('/imports', { method: 'POST', body })
  },
  dashboard: (params: { year: number; month: number; collaborator_id?: number; status?: string }) => {
    const query = new URLSearchParams({ year: String(params.year), month: String(params.month) })
    if (params.collaborator_id) query.set('collaborator_id', String(params.collaborator_id))
    if (params.status) query.set('status', params.status)
    return request<Dashboard>(`/dashboard?${query}`)
  },
  analysis: (id: number, year: number, month: number) =>
    request<CollaboratorAnalysis>(`/collaborators/${id}/analysis?year=${year}&month=${month}`),
  listAbsences: (collaboratorId: number) =>
    request<CollaboratorAbsence[]>(`/collaborators/${collaboratorId}/absences`),
  createAbsence: (
    collaboratorId: number,
    payload: Omit<CollaboratorAbsence, 'id' | 'collaborator_id'>,
  ) =>
    request<CollaboratorAbsence>(`/collaborators/${collaboratorId}/absences`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteAbsence: (collaboratorId: number, absenceId: number) =>
    request<void>(`/collaborators/${collaboratorId}/absences/${absenceId}`, { method: 'DELETE' }),
  inconsistenciesReport: (params: {
    year: number
    month: number
    situation?: 'ok' | 'pending'
    issue_type?: 'missing' | 'incomplete' | 'excess'
  }) => {
    const query = new URLSearchParams({ year: String(params.year), month: String(params.month) })
    if (params.situation) query.set('situation', params.situation)
    if (params.issue_type) query.set('issue_type', params.issue_type)
    return request<InconsistenciesReport>(`/inconsistencies-report?${query}`)
  },
}
