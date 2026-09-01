from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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


class CollaboratorOut(CollaboratorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


ABSENCE_TYPES = "medical_certificate|vacation|day_off|leave|other"


class CollaboratorAbsenceCreate(BaseModel):
    type: str = Field(pattern=f"^({ABSENCE_TYPES})$")
    start_date: date
    end_date: date
    note: str | None = Field(default=None, max_length=500)


class CollaboratorAbsenceOut(CollaboratorAbsenceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collaborator_id: int


class CalendarExceptionCreate(BaseModel):
    date: date
    type: str = Field(pattern="^(holiday|optional_day)$")
    description: str = Field(min_length=1, max_length=300)


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
    warnings: list[ImportWarning] = []


class DayTaskOut(BaseModel):
    task_id: str
    title: str
    completed_hours: Decimal | None
    state: str | None
    project: str | None
    activity_category: str | None = None


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


class CollaboratorAnalysisOut(BaseModel):
    summary: CollaboratorSummaryOut
    days: list[DayResultOut]


class MonthlyReportRowOut(BaseModel):
    collaborator: CollaboratorOut
    situation: str
    adherence: Decimal
    missing: int
    incomplete: int
    excess: int
    summary_text: str
    pending_days: list[DayResultOut] = []


class MonthlyReportOut(BaseModel):
    year: int
    month: int
    indicators: dict
    rows: list[MonthlyReportRowOut]
