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
    const error = new Error(message) as Error & {
      details?: string[]
      status: number
      detail?: { message?: string; duplicates?: TimeEntryDuplicate[] }
    }
    error.details = data?.detail?.details
    error.detail = typeof data?.detail === 'object' ? data.detail : undefined
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
  type: 'holiday' | 'optional_day' | 'work_release'
  description: string
}

export type WorkReleasePayload = {
  scope: 'team' | 'collaborators'
  collaborator_ids: number[]
  start_date: string
  end_date: string
  description: string
}

export type WorkReleaseResult = {
  scope: string
  start_date: string
  end_date: string
  description: string
  calendar_days: number
  collaborator_count: number
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
  reference_year: number | null
  reference_month: number | null
  source: 'csv' | 'azure_api'
  warnings: ImportWarning[]
}

export type AzureDevOpsStatus = {
  configured: boolean
  last_sync_at: string | null
}

export type AzureDevOpsTestResult = {
  ok: boolean
  message?: string | null
}

export type AzureDevOpsSyncIgnored = {
  task_id: string | null
  title: string | null
  reason: string
}

export type AzureDevOpsSyncPreviewAssignee = {
  assignee_name: string
  task_count: number
  mapped_collaborator_id: number | null
  mapped_collaborator_name: string | null
  ignored_by_rule: boolean
}

export type AzureDevOpsSyncPreview = {
  period_label: string
  year: number
  month: number
  tasks_found: number
  mappable_tasks: number
  mapper_ignored_count: number
  assignees: AzureDevOpsSyncPreviewAssignee[]
  saved_ignored_assignees: string[]
}

export type AzureDevOpsSyncResult = {
  period_label: string
  tasks_found: number
  created: number
  updated: number
  ignored: number
  ignored_items: AzureDevOpsSyncIgnored[]
  last_sync_at: string
  import_id: number
}

export type AzureDevOpsSettings = {
  configured: boolean
  base_url: string | null
  organization: string | null
  project: string | null
  projects: string[]
  pat_configured: boolean
  pat_expires_at: string | null
  last_test_at: string | null
  last_test_ok: boolean | null
}

export type ProjectTrackingScopeOption = {
  key: string
  label: string
  team_project: string
  area_path: string
}

export type ProjectTrackingScopeSettings = {
  scopes: ProjectTrackingScopeOption[]
  ignored_scope_keys: string[]
}

export type AiSettings = {
  provider: string
  provider_label: string
  status: 'not_configured' | 'configured' | 'error'
  api_key_configured: boolean
  model_id: string | null
  enabled: boolean
  last_test_at: string | null
  last_test_ok: boolean | null
  last_test_message: string | null
}

export type AiModel = {
  id: string
  display_name: string | null
}

export type AiTestResult = {
  ok: boolean
  message: string
}

export type ImportPreview = {
  filename: string
  row_count: number
  year: number
  month: number
  min_date: string
  max_date: string
  primary_count: number
  outside_primary_count: number
  periods: Array<{ year: number; month: number; count: number }>
}

export type DayTask = {
  task_id: string
  title: string
  completed_hours: number | string | null
  state: string | null
  project: string | null
  activity_category: string | null
}

export type DayLaunchVerification = {
  kind: string
  message: string
  tasks?: Array<{
    task_id: string
    title: string
    state_label: string
    completed_hours?: number | string | null
    estimated_hours?: number | string | null
    effective_hours?: number | string | null
  }>
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
  launch_verification?: DayLaunchVerification | null
}

export type CollaboratorAbsence = {
  id: number
  collaborator_id: number
  type: 'medical_certificate' | 'vacation' | 'day_off' | 'leave' | 'work_release' | 'other'
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

export type DashboardRow = CollaboratorSummary & {
  days: DayResult[]
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
  rows: DashboardRow[]
  daily_adherence: Array<{
    date: string
    adherence: number | string
    collaborators: number
  }>
}

export type PeriodObservations = {
  year: number
  month: number
  period_label: string
  text: string
}

export type CollaboratorAnalysis = {
  summary: CollaboratorSummary
  days: DayResult[]
}

export type ReportOpenTask = {
  task_id: string
  title: string
  work_date: string
  state: string | null
  state_label: string
  completed_hours: number | string | null
  activity_category?: string | null
  project?: string | null
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
  open_tasks: ReportOpenTask[]
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
    open_tasks: number
  }
  rows: InconsistenciesReportRow[]
}

export type ProjectScope = {
  key: string
  label: string
  team_project: string
  area_path: string | null
}

export type ProjectOverview = {
  year: number
  month: number
  scope_key: string | null
  indicators: {
    projects_tracked: number
    sprints_in_period: number
    stories_created: number
    stories_completed: number
    stories_in_progress: number
    stories_pending: number
    stories_added_after_start: number
    impediments_identified: number
  }
  project_cards: Array<{
    scope_key: string
    label: string
    team_project: string
    area_path: string | null
    sprints: number
    stories_created: number
    stories_completed: number
    stories_in_progress: number
    stories_pending: number
  }>
  limitations: string[]
  data_source: string
}

export type ProjectSprintRow = {
  sprint_key: string
  team_project: string
  name: string
  path: string
  start_date: string
  finish_date: string
  status: string
  stories_total: number
  stories_created_in_sprint: number
  stories_completed_in_sprint: number
  stories_pending: number
  completion_percent: number | null
  completion_denominator: number
  completion_numerator: number
}

export type ProjectSprints = {
  year: number
  month: number
  scope_key: string | null
  rows: ProjectSprintRow[]
  limitations: string[]
}

export type ProjectEvolutionStoryRef = {
  work_item_id: number
  title: string
  azure_url: string
  state_at_cut?: string | null
  impediment?: string | null
}

export type ProjectEvolutionEntry = {
  sprint_key: string
  team_project: string
  name: string
  path: string
  start_date: string
  finish_date: string
  status: string
  metrics: {
    stories_total: number
    stories_completed_in_sprint: number
    stories_pending: number
    stories_in_progress: number
    completion_percent: number | null
  }
  completed_stories: ProjectEvolutionStoryRef[]
  pending_stories: ProjectEvolutionStoryRef[]
  impediments: ProjectEvolutionStoryRef[]
}

export type SprintRef = {
  sprint_key: string
  name: string
  start_date: string
  finish_date: string
  status: string
}

export type ProjectReportType = 'monthly' | 'sprints' | 'evolution' | 'consolidated'

export type ProjectReport = {
  report_type: ProjectReportType
  title: string
  year: number
  month: number | null
  scope_key: string | null
  scope_label: string
  generated_at: string
  sections: Array<{ heading: string; body: string | null; bullets: string[] }>
  full_text: string
  limitations: string[]
  data_source: string
}

export type ProjectEvolution = {
  year: number
  month: number | null
  scope_key: string
  scope_label: string
  team_project: string
  area_path: string | null
  timeline: ProjectEvolutionEntry[]
  limitations: string[]
  data_source: string
}

export type SprintAnalysisEvidenceItem = {
  kind: 'fact' | 'inference' | 'recommendation'
  text: string
  evidence_ids: number[]
}

export type SprintAnalysisDeliveryStage =
  | 'planned'
  | 'started'
  | 'in_progress'
  | 'completed'
  | 'validated'

export type SprintAnalysisResultV2 = {
  schema_version?: number
  executive_summary: string
  work_fronts?: Array<{
    name: string
    summary: string
    expected_benefit: string
    situation: string
    story_ids: number[]
  }>
  deliveries?: Array<{
    title: string
    stage: SprintAnalysisDeliveryStage
    narrative: string
    relevance: string
    story_ids: number[]
  }>
  team_highlights?: Array<{
    name: string
    primary_front: string
    activity_summary: string
    story_ids: number[]
    task_ids: number[]
  }>
  risks?: {
    confirmed_impediments: Array<{
      description: string
      impact: string
      known_status: string
      recommended_action?: string | null
      evidence_ids: number[]
      kind: SprintAnalysisEvidenceItem['kind']
    }>
    registered_challenges: Array<{
      description: string
      impact: string
      known_status: string
      recommended_action?: string | null
      evidence_ids: number[]
      kind: SprintAnalysisEvidenceItem['kind']
    }>
    alerts: Array<{
      description: string
      impact: string
      known_status: string
      recommended_action?: string | null
      evidence_ids: number[]
      kind: SprintAnalysisEvidenceItem['kind']
    }>
  }
  management_actions?: Array<{
    action: string
    reason: string
    priority: 'alta' | 'media' | 'baixa'
    responsible?: string | null
    evidence_ids: number[]
  }>
  comparison_narrative?: string | null
  timeline?: SprintAnalysisEvidenceItem[]
  changes_between_sprints?: SprintAnalysisEvidenceItem[]
  impediments_note?: string | null
  advances?: SprintAnalysisEvidenceItem[]
  challenges?: SprintAnalysisEvidenceItem[]
  impediments?: SprintAnalysisEvidenceItem[]
  attention_points?: SprintAnalysisEvidenceItem[]
  next_steps?: SprintAnalysisEvidenceItem[]
}

export type SprintAnalysis = {
  id: number
  status: 'pending' | 'running' | 'success' | 'error' | string
  scope_key: string
  scope_label: string
  team_project: string
  area_path: string | null
  year: number
  month: number
  sprint_keys: string[]
  model: string | null
  stories_count: number | null
  tasks_count: number | null
  generated_at: string | null
  error_message: string | null
  pack: {
    analysis_at?: string
    scope_label?: string
    criteria?: Record<string, string>
    multiple_sprints?: boolean
    impediments_note?: string | null
    limitations?: string[]
    consolidated?: Record<string, number | null>
    sprints?: Array<{
      sprint_key: string
      name: string
      team_project: string
      area_label?: string
      path: string
      start_date: string
      finish_date: string
      status: string
      indicators: Record<string, number | null>
      stories: Array<{
        work_item_id: number
        title: string
        azure_url: string
        state_at_cut?: string | null
        assignee_at_cut?: string | null
        feature?: { title?: string; work_item_type?: string } | null
        bucket?: string
        movements?: string[]
      }>
    }>
    collaborators?: Array<{
      name: string
      stories: number
      tasks: number
      completed: number
      in_progress: number
      pending: number
      items: Array<{
        kind: string
        work_item_id: number
        title: string
        azure_url: string
        bucket: string
        sprint_name?: string
      }>
      reassignments?: Array<{ work_item_id: number; from?: string | null; to?: string | null }>
    }>
    evidence_index?: Array<{ work_item_id: number; title: string; azure_url: string; kind: string }>
    explicit_impediments?: Array<{
      work_item_id: number
      title: string
      azure_url: string
      description: string
      assignee?: string | null
    }>
  } | null
  result: SprintAnalysisResultV2 | null
  evidence: Array<{ work_item_id: number; title: string; azure_url: string; kind: string }> | null
}

export type ExecutiveReport = Omit<SprintAnalysis, 'scope_key'> & {
  report_type: ProjectReportType
  scope_key: string | null
  scope_keys: string[]
}

export type ProjectSprintDetail = {
  sprint_key: string
  team_project: string
  name: string
  path: string
  start_date: string
  finish_date: string
  status: string
  metrics: {
    stories_total: number
    stories_created_in_sprint: number
    stories_completed_in_sprint: number
    stories_in_progress: number
    stories_pending: number
    stories_added_after_start: number
    stories_removed: number
    completion_percent: number | null
    completion_denominator: number
    completion_numerator: number
  }
  limitations: string[]
  stories: Array<{
    work_item_id: number
    title: string
    state_at_start: string | null
    state_at_cut: string | null
    state_current: string | null
    created_at: string | null
    completed_at: string | null
    area_path: string | null
    iteration_current: string | null
    assignee: string | null
    impediment: string | null
    created_in_sprint: boolean
    completed_in_sprint: boolean
    added_after_start: boolean
    azure_url: string
  }>
}

export type TimeEntryDuplicate = {
  task_id: number | null
  title: string
  reference_date: string
  estimated_hours: number | string | null
  origin: string
}

export type TimeEntryStory = {
  id: number
  title: string
  state: string | null
  project: string
  area_path: string | null
  iteration_path: string | null
  url: string | null
  accessible: boolean
  blocked_reason: string | null
}

export type TimeEntryContext = {
  azure_configured: boolean
  azure_error: string | null
  projects: string[]
  assignee_name: string | null
  suggested_hours: number | string
  today: string
  story: TimeEntryStory | null
  defaults: {
    task_type: string
    activity: string
    executed_hours: string
    impediment: string
    impediment_hours: string
    state: string
    assignee: string | null
  }
  adherence_note: string
}

export type TimeEntryDraft = {
  reference_date: string
  title: string
  description: string
  estimated_hours: number
  operation_key: string
  confirm?: boolean
  acknowledge_duplicate?: boolean
  justification?: string | null
}

export type TimeEntryPreview = {
  story_id: number
  story_title: string
  title: string
  description: string
  reference_date: string
  estimated_hours: number | string
  task_type: string
  activity: string
  assignee: string
  state: string
  duplicates: TimeEntryDuplicate[]
}

export type TimeEntryRegistered = {
  operation_key: string
  task_id: number | null
  title: string
  reference_date: string
  url: string | null
  already_registered: boolean
  message: string
}

export type TimeEntryDayTask = {
  task_id: number | null
  title: string
  estimated_hours: number | string | null
  executed_hours: number | string | null
  state: string | null
  url: string | null
  origin: 'module' | 'azure'
  operation_status: string | null
}

export type TimeEntryDay = {
  date: string
  azure_checked: boolean
  azure_error: string | null
  tasks: TimeEntryDayTask[]
}

export type TimeEntryLast = {
  title: string
  description: string
  estimated_hours: number | string
  reference_date: string
}

export type TimeEntryCalendarDay = {
  date: string
  weekend: boolean
  exception_label: string | null
  exception_type: string | null
  absence_label: string | null
  suggested: boolean
  launch_state: 'complete' | 'pending' | 'dispensed' | null
  status_label: string | null
}

export type TimeEntryCalendar = {
  year: number
  month: number
  suggested_hours: number | string
  days: TimeEntryCalendarDay[]
}

export type TimeEntryBatchItem = {
  operation_key: string
  reference_date: string
  title: string
  description?: string | null
  estimated_hours: number | string | null
  status: string
  message: string
  task_id: number | null
  url: string | null
  duplicates: TimeEntryDuplicate[]
}

export type TimeEntryBatchResult = {
  total: number
  created: number
  pending: number
  failed: number
  items: TimeEntryBatchItem[]
}

export type ConferenceTask = {
  task_id: string
  title: string
  state: string | null
  estimated_hours: number | string
  executed_hours: number | string
  url: string | null
  project: string | null
}

export type ConferenceDay = {
  date: string
  estimated_hours: number | string
  executed_hours: number | string
  recognized_hours: number | string
  missing_hours: number | string
  expected_hours: number | string
  status: string
  status_label: string
  hours_source: string
  hours_source_label: string
  suggested_hours: number | string
  pending: boolean
  tasks: ConferenceTask[]
}

export type ConferenceReport = {
  year: number
  month: number
  checked_at: string
  assignee_name: string
  daily_hours: number | string
  collaborator_matched: boolean
  adherence: number | string
  expected_hours: number | string
  recognized_hours: number | string
  estimated_hours: number | string
  executed_hours: number | string
  obligatory_days: number
  complete_days: number
  incomplete_days: number
  missing_days: number
  excess_days: number
  dispensed_days: number
  missing_hours: number | string
  pending: ConferenceDay[]
  days: ConferenceDay[]
  empty_message: string | null
  executed_limit_note: string
}

export type TimeEntrySuggestion = {
  title: string
  description: string
  activities: string | null
  result: string | null
  hours: number | string | null
}

export type TimeEntryOperation = {
  operation_key: string
  reference_date: string
  title: string
  description: string | null
  estimated_hours: number | string
  assignee_name: string
  story_id: number
  story_title: string | null
  task_id: number | null
  task_state: string | null
  status: string
  url: string | null
  error_message: string | null
  justification: string | null
  submitted_at: string | null
}

export type IssueAuditSummary = {
  id: number
  created_at: string
  finished_at: string | null
  requester: string | null
  organization: string
  project: string
  work_item_type: string
  period_criterion: 'created' | 'changed'
  year: number
  comment_scope: 'all' | 'period'
  person_name: string
  person_identity_id: string | null
  person_unique_name: string | null
  status: 'queued' | 'running' | 'complete' | 'partial' | 'failed' | 'cancelled' | 'ambiguous'
  issues_found: number
  issues_processed: number
  comments_analyzed: number
  comments_matched: number
  failure_count: number
  progress_percent: number
  error_message: string | null
  limitations: string[]
}

export type IssueAuditComment = {
  id: string
  author: string
  author_id: string | null
  author_unique_name: string | null
  created_at: string | null
  created_at_local: string | null
  text: string
  is_deleted: boolean | null
}

export type IssueAuditIssue = {
  id: number
  title: string
  state: string
  assigned_to: string
  url: string
  comment_count: number | null
  person_comment_count: number
  person_commented: boolean
  error: string | null
  comments: IssueAuditComment[]
}

export type IssueAuditCandidate = {
  id: string | null
  display_name: string | null
  unique_name: string | null
  descriptor: string | null
}

export type IssueAuditDetail = IssueAuditSummary & {
  failed_ids: number[]
  result: {
    issues: IssueAuditIssue[]
    candidates: IssueAuditCandidate[]
    issues_with_person: number
    issues_without_person: number
    ambiguous: boolean
  } | null
}

export type IssueAuditPeople = {
  status: 'matched' | 'ambiguous' | 'not_found' | 'unavailable'
  people: IssueAuditCandidate[]
  message: string | null
}

export type IssueAuditValidationRecord = {
  id: number
  query_id: number
  created_at: string
  updated_at: string | null
  payload: {
    validated_at: string
    methodology: { limitation: string; risks: string[] }
    coverage: {
      consistent: boolean
      wiql_count: number
      stored_count: number
      missing_count: number
      extra_count: number
      duplicate_stored_ids: number[]
      wiql_limitation_notes: string[]
    }
    metrics: {
      coverage_consistent: boolean
      sample_size: number
      sample_auto_confere: number
      sample_auto_divergencia: number
      sample_auto_nao_verificado: number
      sample_divergence_rate: number | null
      manual_confere: number
      manual_divergencia: number
      manual_nao_verificado: number
      manual_divergence_rate: number | null
      disclaimer: string
    }
    sample: {
      issue_ids: number[]
      items: Array<{
        issue_id: number
        url: string | null
        title: string
        auto_status: string
        divergence: string | null
        original: { comment_count: number | null; person_comment_count: number | null }
        reextracted: { comment_count: number; person_comment_count: number } | null
        comments_preview: Array<{
          author: string
          author_id: string | null
          created_at_local: string | null
          text_preview: string
          matched_person: boolean
        }>
      }>
    }
    manual_reviews: Array<{
      issue_id: number
      status: 'confere' | 'divergencia' | 'nao_verificado'
      real_comment_count: number | null
      real_person_comment_count: number | null
      divergence_type: string | null
      notes: string | null
      reviewed_by: string | null
      reviewed_at: string
    }>
  }
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  listCollaborators: () => request<Collaborator[]>('/collaborators'),
  createCollaborator: (payload: Omit<Collaborator, 'id'>) =>
    request<Collaborator>('/collaborators', { method: 'POST', body: JSON.stringify(payload) }),
  updateCollaborator: (id: number, payload: Partial<Omit<Collaborator, 'id'>>) =>
    request<Collaborator>(`/collaborators/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  registerDismissal: (id: number, end_date: string) =>
    request<Collaborator>(`/collaborators/${id}/dismissal`, {
      method: 'POST',
      body: JSON.stringify({ end_date }),
    }),
  deleteCollaborator: (id: number) => request<void>(`/collaborators/${id}`, { method: 'DELETE' }),
  listExceptions: () => request<CalendarException[]>('/calendar-exceptions'),
  createException: (payload: Omit<CalendarException, 'id'>) =>
    request<CalendarException>('/calendar-exceptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateException: (id: number, payload: Omit<CalendarException, 'id'>) =>
    request<CalendarException>(`/calendar-exceptions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteException: (id: number) => request<void>(`/calendar-exceptions/${id}`, { method: 'DELETE' }),
  createWorkRelease: (payload: WorkReleasePayload) =>
    request<WorkReleaseResult>('/work-releases', { method: 'POST', body: JSON.stringify(payload) }),
  deleteImport: (id: number) => request<void>(`/imports/${id}`, { method: 'DELETE' }),
  listImports: () => request<ImportResult[]>('/imports'),
  latestImport: () => request<ImportResult | null>('/imports/latest'),
  previewImport: async (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<ImportPreview>('/imports/preview', { method: 'POST', body })
  },
  uploadImport: async (file: File, year: number, month: number) => {
    const body = new FormData()
    body.append('file', file)
    body.append('year', String(year))
    body.append('month', String(month))
    return request<ImportResult>('/imports', { method: 'POST', body })
  },
  getAzureDevOpsStatus: () => request<AzureDevOpsStatus>('/azure-devops/status'),
  testAzureDevOpsConnection: () =>
    request<AzureDevOpsTestResult>('/azure-devops/test-connection', { method: 'POST' }),
  previewAzureDevOpsSync: (year: number, month: number) =>
    request<AzureDevOpsSyncPreview>('/azure-devops/sync-preview', {
      method: 'POST',
      body: JSON.stringify({ year, month }),
    }),
  syncAzureDevOps: (year: number, month: number, ignoreAssigneeNames: string[] = []) =>
    request<AzureDevOpsSyncResult>('/azure-devops/sync', {
      method: 'POST',
      body: JSON.stringify({ year, month, ignore_assignee_names: ignoreAssigneeNames }),
    }),
  getAzureDevOpsSettings: () => request<AzureDevOpsSettings>('/settings/azure-devops'),
  listAzureDevOpsProjects: () => request<string[]>('/azure-devops/projects'),
  updateAzureDevOpsSettings: (payload: {
    base_url: string
    organization: string
    projects: string[]
    pat: string | null
    pat_expires_at: string | null
  }) =>
    request<AzureDevOpsSettings>('/settings/azure-devops', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  testAzureDevOpsSettings: () =>
    request<AzureDevOpsTestResult>('/settings/azure-devops/test-connection', { method: 'POST' }),
  getProjectTrackingScopeSettings: () =>
    request<ProjectTrackingScopeSettings>('/settings/project-tracking/scopes'),
  updateProjectTrackingIgnoredScopes: (ignored_scope_keys: string[]) =>
    request<ProjectTrackingScopeSettings>('/settings/project-tracking/ignored-scopes', {
      method: 'PUT',
      body: JSON.stringify({ ignored_scope_keys }),
    }),
  getGeminiSettings: () => request<AiSettings>('/settings/gemini'),
  updateGeminiSettings: (payload: {
    api_key: string | null
    clear_api_key?: boolean
    model_id: string | null
    enabled: boolean | null
  }) =>
    request<AiSettings>('/settings/gemini', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteGeminiApiKey: () => request<AiSettings>('/settings/gemini/api-key', { method: 'DELETE' }),
  listGeminiModels: () =>
    request<{ models: AiModel[] }>('/settings/gemini/models').then((data) => data.models),
  testGeminiSettings: () => request<AiTestResult>('/settings/gemini/test-connection', { method: 'POST' }),
  dashboard: (params: { year: number; month: number; collaborator_id?: number; status?: string }) => {
    const query = new URLSearchParams({ year: String(params.year), month: String(params.month) })
    if (params.collaborator_id) query.set('collaborator_id', String(params.collaborator_id))
    if (params.status) query.set('status', params.status)
    return request<Dashboard>(`/dashboard?${query}`)
  },
  periodObservations: (params: { year: number; month: number; collaborator_id?: number }) => {
    const query = new URLSearchParams({ year: String(params.year), month: String(params.month) })
    if (params.collaborator_id) query.set('collaborator_id', String(params.collaborator_id))
    return request<PeriodObservations>(`/dashboard/period-observations?${query}`)
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
  listProjectScopes: () => request<ProjectScope[]>('/projects/scopes'),
  projectOverview: (params: { year: number; month: number; scope_key?: string }) => {
    const query = new URLSearchParams({
      year: String(params.year),
      month: String(params.month),
    })
    if (params.scope_key) query.set('scope_key', params.scope_key)
    return request<ProjectOverview>(`/projects/overview?${query}`)
  },
  projectSprints: (params: { year: number; month: number; scope_key: string }) => {
    const query = new URLSearchParams({
      year: String(params.year),
      month: String(params.month),
      scope_key: params.scope_key,
    })
    return request<ProjectSprints>(`/projects/sprints?${query}`)
  },
  listSprintRefs: (params: { year: number; month: number; scope_key: string }) => {
    const query = new URLSearchParams({
      year: String(params.year),
      month: String(params.month),
      scope_key: params.scope_key,
    })
    return request<SprintRef[]>(`/projects/sprint-refs?${query}`)
  },
  projectReport: (params: {
    report_type: ProjectReportType
    year: number
    month: number
    scope_key?: string
  }) => {
    const query = new URLSearchParams({
      report_type: params.report_type,
      year: String(params.year),
      month: String(params.month),
    })
    if (params.scope_key) query.set('scope_key', params.scope_key)
    return request<ProjectReport>(`/projects/reports?${query}`)
  },
  projectEvolution: (params: { year: number; month: number; scope_key: string }) => {
    const query = new URLSearchParams({
      year: String(params.year),
      scope_key: params.scope_key,
      month: String(params.month),
    })
    return request<ProjectEvolution>(`/projects/evolution?${query}`)
  },
  latestSprintAnalysis: (params: { scope_key: string; sprint_keys: string[] }) => {
    const query = new URLSearchParams({ scope_key: params.scope_key })
    params.sprint_keys.forEach((key) => query.append('sprint_keys', key))
    return request<{ report_id: number | null; status: string | null; generated_at: string | null }>(
      `/projects/sprint-analyses/latest?${query}`,
    )
  },
  createSprintAnalysis: (payload: {
    scope_key: string
    year: number
    month: number
    sprint_keys: string[]
  }) =>
    request<SprintAnalysis>('/projects/sprint-analyses', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getSprintAnalysis: (id: number) => request<SprintAnalysis>(`/projects/sprint-analyses/${id}`),
  createExecutiveReport: (payload: {
    report_type: ProjectReportType
    year: number
    month: number
    scope_key?: string
    sprint_keys?: string[]
  }) =>
    request<ExecutiveReport>('/projects/executive-reports', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getExecutiveReport: (id: number) => request<ExecutiveReport>(`/projects/executive-reports/${id}`),
  latestExecutiveReport: (params: {
    report_type: ProjectReportType
    year: number
    month: number
    scope_key?: string
    sprint_keys?: string[]
  }) => {
    const query = new URLSearchParams({
      report_type: params.report_type,
      year: String(params.year),
      month: String(params.month),
    })
    if (params.scope_key) query.set('scope_key', params.scope_key)
    params.sprint_keys?.forEach((key) => query.append('sprint_keys', key))
    return request<{ report: ExecutiveReport | null }>(`/projects/executive-reports/latest?${query}`)
  },
  timeEntryContext: () => request<TimeEntryContext>('/time-entries/context'),
  lookupTimeEntryStory: (story_id: number) =>
    request<TimeEntryStory>('/time-entries/story/lookup', {
      method: 'POST',
      body: JSON.stringify({ story_id }),
    }),
  searchTimeEntryStories: (project: string, query: string) =>
    request<TimeEntryStory[]>('/time-entries/story/search', {
      method: 'POST',
      body: JSON.stringify({ project, query }),
    }),
  saveTimeEntryStory: (story_id: number) =>
    request<TimeEntryContext>('/time-entries/story', {
      method: 'PUT',
      body: JSON.stringify({ story_id }),
    }),
  clearTimeEntryStory: () => request<void>('/time-entries/story', { method: 'DELETE' }),
  previewTimeEntry: (payload: TimeEntryDraft) =>
    request<TimeEntryPreview>('/time-entries/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  registerTimeEntry: (payload: TimeEntryDraft) =>
    request<TimeEntryRegistered>('/time-entries/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  timeEntryDay: (date: string) => request<TimeEntryDay>(`/time-entries/day?date=${date}`),
  lastTimeEntry: () => request<TimeEntryLast>('/time-entries/last'),
  improveTimeEntryDescription: (text: string) =>
    request<{ text: string }>('/time-entries/improve-description', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  timeEntryCalendar: (year: number, month: number) =>
    request<TimeEntryCalendar>(`/time-entries/calendar?year=${year}&month=${month}`),
  timeEntryConference: (year: number, month: number) =>
    request<ConferenceReport>(`/time-entries/conference?year=${year}&month=${month}`),
  suggestTimeEntry: (payload: {
    categories: string[]
    text: string
    hours?: number | null
    existing_titles: string[]
  }) =>
    request<TimeEntrySuggestion>('/time-entries/suggest', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  previewTimeEntryBatch: (payload: { confirm: boolean; items: TimeEntryDraft[] }) =>
    request<{ items: TimeEntryBatchItem[] }>('/time-entries/batch/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  registerTimeEntryBatch: (payload: { confirm: boolean; items: TimeEntryDraft[] }) =>
    request<TimeEntryBatchResult>('/time-entries/batch/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  timeEntryOperations: (params: {
    year?: number
    month?: number
    date?: string
    story_id?: number
    state?: string
    status?: string
  }) => {
    const query = new URLSearchParams()
    if (params.year) query.set('year', String(params.year))
    if (params.month) query.set('month', String(params.month))
    if (params.date) query.set('date', params.date)
    if (params.story_id) query.set('story_id', String(params.story_id))
    if (params.state) query.set('state', params.state)
    if (params.status) query.set('status', params.status)
    const suffix = query.toString() ? `?${query}` : ''
    return request<TimeEntryOperation[]>(`/time-entries/operations${suffix}`)
  },
  projectSprintDetail: (sprintKey: string, areaPath?: string) => {
    const query = new URLSearchParams()
    if (areaPath) query.set('area_path', areaPath)
    const suffix = query.toString() ? `?${query}` : ''
    return request<ProjectSprintDetail>(
      `/projects/sprints/${encodeURIComponent(sprintKey)}${suffix}`,
    )
  },
  auditProjects: (organization: string) =>
    request<string[]>(`/audit/issues/projects?organization=${encodeURIComponent(organization)}`),
  auditPeople: (organization: string, name: string) =>
    request<IssueAuditPeople>(
      `/audit/issues/people?organization=${encodeURIComponent(organization)}&name=${encodeURIComponent(name)}`,
    ),
  listIssueAudits: () => request<IssueAuditSummary[]>('/audit/issues/queries'),
  createIssueAudit: (payload: {
    organization: string
    project: string
    work_item_type: string
    period_criterion: 'created' | 'changed'
    year: number
    comment_scope: 'all' | 'period'
    person_name: string
    person_identity_id?: string | null
    person_unique_name?: string | null
    requester?: string | null
  }) => request<IssueAuditSummary>('/audit/issues/queries', { method: 'POST', body: JSON.stringify(payload) }),
  getIssueAudit: (id: number) => request<IssueAuditDetail>(`/audit/issues/queries/${id}`),
  cancelIssueAudit: (id: number) =>
    request<IssueAuditSummary>(`/audit/issues/queries/${id}/cancel`, { method: 'POST' }),
  retryIssueAudit: (id: number) =>
    request<IssueAuditSummary>(`/audit/issues/queries/${id}/retry`, { method: 'POST' }),
  backfillIssueAuditAllComments: (id: number) =>
    request<IssueAuditSummary>(`/audit/issues/queries/${id}/backfill-all-comments`, {
      method: 'POST',
      body: JSON.stringify({ confirm: true }),
    }),
  getIssueAuditExportReadiness: (id: number) =>
    request<{
      comments_analyzed: number
      comments_stored_full: number
      comments_stored_person: number
      comments_matched: number
      comments_storage_version: number
      issues_incomplete: number
      exportable_full: boolean
      message: string | null
      can_backfill: boolean
      query_status: string
    }>(`/audit/issues/queries/${id}/export-readiness`),
  issueAuditExportUrl: (id: number, options?: { includeAllDiscussions?: boolean }) => {
    const params = new URLSearchParams()
    if (options?.includeAllDiscussions) params.set('include_all_discussions', 'true')
    const query = params.toString()
    return `/api/audit/issues/queries/${id}/export${query ? `?${query}` : ''}`
  },
  selectIssueAuditIdentity: (
    id: number,
    payload: { identity_id?: string | null; unique_name?: string | null; display_name?: string | null },
  ) => request<IssueAuditDetail>(`/audit/issues/queries/${id}/identity`, { method: 'POST', body: JSON.stringify(payload) }),
  getIssueAuditValidation: (id: number) =>
    request<IssueAuditValidationRecord | null>(`/audit/issues/queries/${id}/validation`),
  runIssueAuditValidation: (id: number) =>
    request<IssueAuditValidationRecord>(`/audit/issues/queries/${id}/validate`, { method: 'POST' }),
  saveIssueAuditManualReview: (
    id: number,
    payload: {
      issue_id: number
      status: 'confere' | 'divergencia' | 'nao_verificado'
      real_comment_count?: number | null
      real_person_comment_count?: number | null
      divergence_type?: string | null
      notes?: string | null
      reviewer?: string | null
    },
  ) =>
    request<IssueAuditValidationRecord>(`/audit/issues/queries/${id}/validation/manual`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
