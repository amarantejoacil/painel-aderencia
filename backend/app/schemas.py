from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CollaboratorBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    azure_name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date | None = None
    daily_hours: Decimal = Field(default=Decimal("8.00"), gt=0)
    active: bool = True


class CollaboratorCreate(CollaboratorBase):
    pass


class CollaboratorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    azure_name: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    daily_hours: Decimal | None = Field(default=None, gt=0)
    active: bool | None = None


class CollaboratorDismissal(BaseModel):
    end_date: date


class CollaboratorOut(CollaboratorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


ABSENCE_TYPES = "medical_certificate|vacation|day_off|leave|work_release|other"


class CollaboratorAbsenceCreate(BaseModel):
    type: str = Field(pattern=f"^({ABSENCE_TYPES})$")
    start_date: date
    end_date: date
    note: str | None = Field(default=None, max_length=500)
    excused_hours: Decimal | None = Field(default=None, gt=0, le=24)

    @model_validator(mode="after")
    def validate_excused_hours(self):
        if self.excused_hours is not None and self.start_date != self.end_date:
            raise ValueError(
                "Horas abonadas só podem ser usadas em atestado de um único dia. "
                "Para vários dias, cadastre dia inteiro ou registre cada dia parcial separadamente."
            )
        return self


class CollaboratorAbsenceOut(CollaboratorAbsenceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collaborator_id: int


CALENDAR_EXCEPTION_TYPES = "holiday|optional_day|work_release"


class CalendarExceptionCreate(BaseModel):
    date: date
    type: str = Field(pattern=f"^({CALENDAR_EXCEPTION_TYPES})$")
    description: str = Field(min_length=1, max_length=300)


class WorkReleaseCreate(BaseModel):
    scope: str = Field(pattern="^(team|collaborators)$")
    collaborator_ids: list[int] = Field(default_factory=list)
    start_date: date
    end_date: date
    description: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_release(self) -> "WorkReleaseCreate":
        if self.end_date < self.start_date:
            raise ValueError("A data final deve ser igual ou posterior à data inicial.")
        if self.scope == "collaborators" and not self.collaborator_ids:
            raise ValueError("Selecione ao menos um colaborador.")
        return self


class WorkReleaseOut(BaseModel):
    scope: str
    start_date: date
    end_date: date
    description: str
    calendar_days: int = 0
    collaborator_count: int = 0


class CalendarExceptionOut(CalendarExceptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ImportWarning(BaseModel):
    kind: str
    message: str
    row: int | None = None


class ImportPeriodSummary(BaseModel):
    year: int
    month: int
    count: int


class ImportPreviewOut(BaseModel):
    filename: str
    row_count: int
    year: int
    month: int
    min_date: date
    max_date: date
    primary_count: int
    outside_primary_count: int
    periods: list[ImportPeriodSummary] = []


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    imported_at: datetime
    row_count: int
    mapped_count: int
    unmapped_count: int
    warning_count: int
    status: str
    reference_year: int | None = None
    reference_month: int | None = None
    source: str = "csv"
    warnings: list[ImportWarning] = []


class AzureDevOpsStatusOut(BaseModel):
    configured: bool
    last_sync_at: datetime | None = None


class AzureDevOpsTestOut(BaseModel):
    ok: bool
    message: str | None = None


class AzureDevOpsFieldProbeOut(BaseModel):
    custom_field_references: list[str] = []
    selected_mapping: dict[str, str | None] = {}


class AzureSyncPreviewAssigneeOut(BaseModel):
    assignee_name: str
    task_count: int
    mapped_collaborator_id: int | None = None
    mapped_collaborator_name: str | None = None
    ignored_by_rule: bool = False


class AzureDevOpsSyncPreviewOut(BaseModel):
    period_label: str
    year: int
    month: int
    tasks_found: int
    mappable_tasks: int
    mapper_ignored_count: int
    assignees: list[AzureSyncPreviewAssigneeOut]
    saved_ignored_assignees: list[str] = Field(default_factory=list)


class AzureDevOpsSyncIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    ignore_assignee_names: list[str] = Field(default_factory=list)


class AzureDevOpsSyncIgnoredOut(BaseModel):
    task_id: str | None = None
    title: str | None = None
    reason: str


class AzureDevOpsSyncOut(BaseModel):
    period_label: str
    tasks_found: int
    created: int
    updated: int
    ignored: int
    ignored_items: list[AzureDevOpsSyncIgnoredOut] = Field(default_factory=list)
    last_sync_at: datetime
    import_id: int


class AzureDevOpsSettingsOut(BaseModel):
    configured: bool
    base_url: str | None = None
    organization: str | None = None
    project: str | None = None
    projects: list[str] = Field(default_factory=list)
    pat_configured: bool = False
    pat_expires_at: date | None = None
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None


class AzureDevOpsSettingsUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    organization: str = Field(min_length=1, max_length=200)
    projects: list[str] = Field(min_length=1, max_length=50)
    pat: str | None = Field(default=None, max_length=500)
    pat_expires_at: date | None = None


class ProjectTrackingScopeOptionOut(BaseModel):
    key: str
    label: str
    team_project: str
    area_path: str


class ProjectTrackingScopeSettingsOut(BaseModel):
    scopes: list[ProjectTrackingScopeOptionOut] = Field(default_factory=list)
    ignored_scope_keys: list[str] = Field(default_factory=list)


class ProjectTrackingIgnoredScopesUpdate(BaseModel):
    ignored_scope_keys: list[str] = Field(default_factory=list, max_length=200)


class InconsistenciesReportSettingsOut(BaseModel):
    copy_intro_requires_review: str
    copy_intro_ok: str
    updated_at: datetime | None = None


class InconsistenciesReportSettingsUpdate(BaseModel):
    copy_intro_requires_review: str = Field(min_length=1, max_length=8000)
    copy_intro_ok: str = Field(min_length=1, max_length=8000)


class AiSettingsOut(BaseModel):
    provider: str
    provider_label: str
    status: Literal["not_configured", "configured", "error"]
    api_key_configured: bool = False
    model_id: str | None = None
    enabled: bool = False
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_message: str | None = None


class AiSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    clear_api_key: bool = False
    model_id: str | None = Field(default=None, max_length=200)
    enabled: bool | None = None


class AiModelOut(BaseModel):
    id: str
    display_name: str | None = None


class AiModelsOut(BaseModel):
    models: list[AiModelOut] = Field(default_factory=list)


class AiTestOut(BaseModel):
    ok: bool
    message: str


class DayTaskOut(BaseModel):
    task_id: str
    title: str
    completed_hours: Decimal | None
    state: str | None
    project: str | None
    activity_category: str | None = None
    azure_url: str | None = None


class DayLaunchVerificationTaskOut(BaseModel):
    task_id: str
    title: str
    state_label: str
    completed_hours: Decimal | None = None
    estimated_hours: Decimal | None = None
    effective_hours: Decimal | None = None
    project: str | None = None
    azure_url: str | None = None


class DayLaunchVerificationOut(BaseModel):
    kind: str
    message: str
    tasks: list[DayLaunchVerificationTaskOut] = []


class DayResultOut(BaseModel):
    date: date
    expected: Decimal
    executed: Decimal
    difference: Decimal
    status: str
    hours_source: str
    task_count: int
    tasks: list[DayTaskOut] = []
    absence_type: str | None = None
    absence_note: str | None = None
    absence_excused_hours: Decimal | None = None
    launch_verification: DayLaunchVerificationOut | None = None


class CollaboratorSummaryOut(BaseModel):
    collaborator: CollaboratorOut
    expected: Decimal
    executed: Decimal
    adherence: Decimal
    regular: int
    incomplete: int
    missing: int
    excess: int
    not_required: int
    justified_absence: int


class DailyAdherenceOut(BaseModel):
    date: date
    adherence: Decimal
    collaborators: int


class DashboardRowOut(CollaboratorSummaryOut):
    days: list[DayResultOut] = []


class DashboardOut(BaseModel):
    year: int
    month: int
    indicators: dict
    rows: list[DashboardRowOut]
    daily_adherence: list[DailyAdherenceOut] = []


class PeriodObservationsOut(BaseModel):
    year: int
    month: int
    period_label: str
    text: str


class CollaboratorAnalysisOut(BaseModel):
    summary: CollaboratorSummaryOut
    days: list[DayResultOut]


class ReportOpenTaskOut(BaseModel):
    task_id: str
    title: str
    work_date: date
    state: str | None = None
    state_label: str
    completed_hours: Decimal | None = None
    activity_category: str | None = None
    project: str | None = None
    azure_url: str | None = None


class MonthlyReportRowOut(BaseModel):
    collaborator: CollaboratorOut
    situation: str
    adherence: Decimal
    missing: int
    incomplete: int
    excess: int
    summary_text: str
    pending_days: list[DayResultOut] = []
    open_tasks: list[ReportOpenTaskOut] = []


class MonthScheduleCalendarOut(BaseModel):
    id: int
    date: date
    type: str
    description: str


class MonthScheduleAbsenceOut(BaseModel):
    id: int
    collaborator_id: int
    collaborator_name: str
    type: str
    start_date: date
    end_date: date
    note: str | None = None


class MonthScheduleContextOut(BaseModel):
    calendar_exceptions: list[MonthScheduleCalendarOut]
    absences: list[MonthScheduleAbsenceOut]
    summary: dict[str, int]


class MonthlyReportOut(BaseModel):
    year: int
    month: int
    indicators: dict
    rows: list[MonthlyReportRowOut]
    month_schedule: MonthScheduleContextOut


class ProjectScopeOut(BaseModel):
    key: str
    label: str
    team_project: str
    area_path: str | None = None


class ProjectOverviewIndicatorsOut(BaseModel):
    projects_tracked: int
    sprints_in_period: int
    stories_created: int
    stories_completed: int
    stories_in_progress: int
    stories_pending: int
    stories_added_after_start: int
    impediments_identified: int


class ProjectOverviewCardOut(BaseModel):
    scope_key: str
    label: str
    team_project: str
    area_path: str | None = None
    sprints: int
    stories_created: int
    stories_completed: int
    stories_in_progress: int
    stories_pending: int


class ProjectOverviewOut(BaseModel):
    year: int
    month: int
    scope_key: str | None = None
    indicators: ProjectOverviewIndicatorsOut
    project_cards: list[ProjectOverviewCardOut]
    limitations: list[str] = Field(default_factory=list)
    data_source: str = "azure_devops"


class ProjectSprintRowOut(BaseModel):
    sprint_key: str
    team_project: str
    name: str
    path: str
    start_date: str
    finish_date: str
    status: str
    stories_total: int
    stories_created_in_sprint: int
    stories_completed_in_sprint: int
    stories_pending: int
    completion_percent: float | None = None
    completion_denominator: int
    completion_numerator: int


class ProjectSprintsOut(BaseModel):
    year: int
    month: int
    scope_key: str | None = None
    rows: list[ProjectSprintRowOut]
    limitations: list[str] = Field(default_factory=list)


class SprintRefOut(BaseModel):
    sprint_key: str
    name: str
    start_date: str
    finish_date: str
    status: str


class ProjectSprintMetricsOut(BaseModel):
    stories_total: int
    stories_created_in_sprint: int
    stories_completed_in_sprint: int
    stories_in_progress: int
    stories_pending: int
    stories_added_after_start: int
    stories_removed: int
    completion_percent: float | None = None
    completion_denominator: int
    completion_numerator: int


class ProjectSprintStoryOut(BaseModel):
    work_item_id: int
    title: str
    state_at_start: str | None = None
    state_at_cut: str | None = None
    state_current: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    area_path: str | None = None
    iteration_current: str | None = None
    assignee: str | None = None
    impediment: str | None = None
    created_in_sprint: bool
    completed_in_sprint: bool
    added_after_start: bool
    azure_url: str


class ProjectSprintDetailOut(BaseModel):
    sprint_key: str
    team_project: str
    name: str
    path: str
    start_date: str
    finish_date: str
    status: str
    metrics: ProjectSprintMetricsOut
    limitations: list[str] = Field(default_factory=list)
    stories: list[ProjectSprintStoryOut] = Field(default_factory=list)


class ProjectEvolutionStoryRefOut(BaseModel):
    work_item_id: int
    title: str
    azure_url: str
    state_at_cut: str | None = None
    impediment: str | None = None


class ProjectEvolutionSprintMetricsOut(BaseModel):
    stories_total: int
    stories_completed_in_sprint: int
    stories_pending: int
    stories_in_progress: int
    completion_percent: float | None = None


class ProjectEvolutionEntryOut(BaseModel):
    sprint_key: str
    team_project: str
    name: str
    path: str
    start_date: str
    finish_date: str
    status: str
    metrics: ProjectEvolutionSprintMetricsOut
    completed_stories: list[ProjectEvolutionStoryRefOut]
    pending_stories: list[ProjectEvolutionStoryRefOut]
    impediments: list[ProjectEvolutionStoryRefOut]


class ProjectEvolutionOut(BaseModel):
    year: int
    month: int | None = None
    scope_key: str
    scope_label: str
    team_project: str
    area_path: str | None = None
    timeline: list[ProjectEvolutionEntryOut]
    limitations: list[str] = Field(default_factory=list)
    data_source: str = "azure_devops"


class ProjectReportSectionOut(BaseModel):
    heading: str
    body: str | None = None
    bullets: list[str] = Field(default_factory=list)


class IndicatorCriterionOut(BaseModel):
    key: str
    label: str
    description: str


class ProjectReportOut(BaseModel):
    report_type: str
    title: str
    year: int
    month: int | None = None
    scope_key: str | None = None
    scope_label: str
    generated_at: str
    sections: list[ProjectReportSectionOut]
    full_text: str
    limitations: list[str] = Field(default_factory=list)
    data_source: str = "azure_devops"
    indicator_criteria: list[IndicatorCriterionOut] = Field(default_factory=list)


class SprintAnalysisCreate(BaseModel):
    scope_key: str = Field(min_length=3)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    sprint_keys: list[str] = Field(min_length=1, max_length=8)


class SprintAnalysisLatestOut(BaseModel):
    report_id: int | None = None
    status: str | None = None
    generated_at: str | None = None


class SprintAnalysisOut(BaseModel):
    id: int
    status: str
    scope_key: str
    scope_label: str
    team_project: str
    area_path: str | None = None
    year: int
    month: int
    sprint_keys: list[str]
    model: str | None = None
    stories_count: int | None = None
    tasks_count: int | None = None
    generated_at: str | None = None
    error_message: str | None = None
    pack: dict | None = None
    result: dict | None = None
    evidence: list | None = None


class ExecutiveReportCreate(BaseModel):
    report_type: Literal["monthly", "sprints", "evolution", "consolidated"]
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=0, le=12)
    scope_key: str | None = None
    sprint_keys: list[str] = Field(default_factory=list, max_length=16)


class ExecutiveReportOut(BaseModel):
    id: int
    status: str
    report_type: str
    scope_key: str | None = None
    scope_keys: list[str]
    scope_label: str
    team_project: str
    area_path: str | None = None
    year: int
    month: int
    sprint_keys: list[str]
    model: str | None = None
    stories_count: int | None = None
    tasks_count: int | None = None
    generated_at: str | None = None
    error_message: str | None = None
    pack: dict | None = None
    result: dict | None = None
    evidence: list | None = None


class ExecutiveReportLatestOut(BaseModel):
    report: ExecutiveReportOut | None = None


class StoryLookupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story_id: int = Field(gt=0)


class StorySearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=3, max_length=200)


class LaunchDefaultsOut(BaseModel):
    task_type: str
    activity: str
    executed_hours: str
    impediment: str
    impediment_hours: str
    state: str
    assignee: str | None = None


class StoryBindingOut(BaseModel):
    id: int
    title: str
    state: str | None = None
    project: str
    area_path: str | None = None
    iteration_path: str | None = None
    url: str | None = None
    accessible: bool
    blocked_reason: str | None = None


class TimeEntryContextOut(BaseModel):
    azure_configured: bool
    azure_error: str | None = None
    projects: list[str]
    assignee_name: str | None = None
    suggested_hours: Decimal
    today: date
    story: StoryBindingOut | None = None
    defaults: LaunchDefaultsOut
    adherence_note: str


class StoryCandidateOut(StoryBindingOut):
    pass


class EntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_date: date
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4000)
    estimated_hours: Decimal = Field(default=Decimal("8"), gt=0, le=24)


class EntryRegisterIn(EntryInput):
    operation_key: str = Field(min_length=8, max_length=64)
    confirm: bool = False
    acknowledge_duplicate: bool = False
    justification: str | None = Field(default=None, max_length=500)


class DuplicateHitOut(BaseModel):
    task_id: int | None = None
    title: str
    reference_date: date
    estimated_hours: Decimal | None = None
    origin: str


class EntryPreviewOut(BaseModel):
    story_id: int
    story_title: str
    title: str
    description: str
    reference_date: date
    estimated_hours: Decimal
    task_type: str
    activity: str
    assignee: str
    state: str
    duplicates: list[DuplicateHitOut]


class EntryRegisterOut(BaseModel):
    operation_key: str
    task_id: int | None = None
    title: str
    reference_date: date
    url: str | None = None
    already_registered: bool = False
    message: str


class TimeEntryDayTaskOut(BaseModel):
    task_id: int | None = None
    title: str
    estimated_hours: Decimal | None = None
    executed_hours: Decimal | None = None
    state: str | None = None
    url: str | None = None
    origin: Literal["module", "azure"]
    operation_status: str | None = None


class DayTasksOut(BaseModel):
    date: date
    azure_checked: bool
    azure_error: str | None = None
    tasks: list[TimeEntryDayTaskOut]


class ImproveDescriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class ImproveDescriptionOut(BaseModel):
    text: str


class LastEntryOut(BaseModel):
    title: str
    description: str
    estimated_hours: Decimal
    reference_date: date


class CalendarDayOut(BaseModel):
    date: date
    weekend: bool
    exception_label: str | None = None
    exception_type: str | None = None
    absence_label: str | None = None
    suggested: bool
    launch_state: str | None = None
    status_label: str | None = None


class TimeEntryCalendarOut(BaseModel):
    year: int
    month: int
    suggested_hours: Decimal
    days: list[CalendarDayOut]


class BatchRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool
    items: list[EntryRegisterIn] = Field(min_length=1, max_length=62)


class BatchItemResultOut(BaseModel):
    operation_key: str
    reference_date: date
    title: str
    description: str | None = None
    estimated_hours: Decimal | None = None
    status: str
    message: str
    task_id: int | None = None
    url: str | None = None
    duplicates: list[DuplicateHitOut] = Field(default_factory=list)


class BatchPreviewOut(BaseModel):
    items: list[BatchItemResultOut]


class BatchRegisterOut(BaseModel):
    total: int
    created: int
    pending: int
    failed: int
    items: list[BatchItemResultOut]


class TimeEntryOperationOut(BaseModel):
    operation_key: str
    reference_date: date
    title: str
    description: str | None = None
    estimated_hours: Decimal
    assignee_name: str
    story_id: int
    story_title: str | None = None
    task_id: int | None = None
    task_state: str | None = None
    status: str
    url: str | None = None
    error_message: str | None = None
    justification: str | None = None
    submitted_at: datetime | None = None


class ConferenceTaskOut(BaseModel):
    task_id: str
    title: str
    state: str | None = None
    estimated_hours: Decimal
    executed_hours: Decimal
    url: str | None = None
    project: str | None = None


class ConferenceDayOut(BaseModel):
    date: date
    estimated_hours: Decimal
    executed_hours: Decimal
    recognized_hours: Decimal
    missing_hours: Decimal
    expected_hours: Decimal
    status: str
    status_label: str
    hours_source: str
    hours_source_label: str
    suggested_hours: Decimal
    pending: bool
    tasks: list[ConferenceTaskOut] = Field(default_factory=list)


class ConferenceOut(BaseModel):
    year: int
    month: int
    checked_at: datetime
    assignee_name: str
    daily_hours: Decimal
    collaborator_matched: bool
    adherence: Decimal
    expected_hours: Decimal
    recognized_hours: Decimal
    estimated_hours: Decimal
    executed_hours: Decimal
    obligatory_days: int
    complete_days: int
    incomplete_days: int
    missing_days: int
    excess_days: int
    dispensed_days: int
    missing_hours: Decimal
    pending: list[ConferenceDayOut]
    days: list[ConferenceDayOut]
    empty_message: str | None = None
    executed_limit_note: str


class SuggestIn(BaseModel):
    categories: list[str] = Field(default_factory=list, max_length=15)
    text: str = Field(default="", max_length=2000)
    hours: Decimal | None = None
    existing_titles: list[str] = Field(default_factory=list, max_length=30)


class SuggestOut(BaseModel):
    title: str
    description: str
    activities: str | None = None
    result: str | None = None
    hours: Decimal | None = None
