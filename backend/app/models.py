from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Collaborator(Base):
    __tablename__ = "collaborators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    azure_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("8.00"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    activities: Mapped[list["Activity"]] = relationship(back_populates="collaborator")
    absences: Mapped[list["CollaboratorAbsence"]] = relationship(
        back_populates="collaborator", cascade="all, delete-orphan"
    )


class CollaboratorAbsence(Base):
    __tablename__ = "collaborator_absences"

    id: Mapped[int] = mapped_column(primary_key=True)
    collaborator_id: Mapped[int] = mapped_column(
        ForeignKey("collaborators.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    collaborator: Mapped[Collaborator] = relationship(back_populates="absences")


class CalendarException(Base):
    __tablename__ = "calendar_exceptions"
    __table_args__ = (UniqueConstraint("date", name="uq_calendar_exception_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(300))


class ImportBatch(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(300))
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    row_count: Mapped[int] = mapped_column(default=0)
    mapped_count: Mapped[int] = mapped_column(default=0)
    unmapped_count: Mapped[int] = mapped_column(default=0)
    warning_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="success")
    reference_year: Mapped[int | None] = mapped_column(nullable=True)
    reference_month: Mapped[int | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="csv", index=True)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(Text)
    work_item_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    azure_assignee: Mapped[str] = mapped_column(String(300), index=True)
    collaborator_id: Mapped[int | None] = mapped_column(
        ForeignKey("collaborators.id", ondelete="SET NULL"), nullable=True, index=True
    )
    work_date: Mapped[date] = mapped_column(Date, index=True)
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    completed_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    project: Mapped[str | None] = mapped_column(String(200), nullable=True)
    activity_category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="csv", index=True)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="activities")
    collaborator: Mapped[Collaborator | None] = relationship(back_populates="activities")


class AzureDevOpsSettings(Base):
    __tablename__ = "azure_devops_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project: Mapped[str | None] = mapped_column(String(200), nullable=True)
    projects: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    encrypted_pat: Mapped[str | None] = mapped_column(Text, nullable=True)
    pat_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_date_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    activity_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_hours_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ignored_assignees: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ignored_project_scope_keys: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


AI_PROVIDER_GOOGLE_GEMINI = "google_gemini"


class AiSettings(Base):
    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String(50), default=AI_PROVIDER_GOOGLE_GEMINI)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SprintAiReport(Base):
    __tablename__ = "sprint_ai_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    scope_key: Mapped[str] = mapped_column(String(400))
    scope_label: Mapped[str] = mapped_column(String(300))
    team_project: Mapped[str] = mapped_column(String(200))
    area_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    sprint_keys: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), index=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stories_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tasks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pack: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExecutiveReport(Base):
    __tablename__ = "executive_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    report_type: Mapped[str] = mapped_column(String(30), index=True)
    scope_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    scope_keys: Mapped[list] = mapped_column(JSONB)
    scope_label: Mapped[str] = mapped_column(String(500))
    team_project: Mapped[str] = mapped_column(String(200))
    area_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    sprint_keys: Mapped[list] = mapped_column(JSONB)
    notes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stories_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tasks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pack: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TimeEntrySettings(Base):
    __tablename__ = "time_entry_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    azure_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    azure_unique_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    azure_identity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    story_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    story_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    story_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    story_project: Mapped[str | None] = mapped_column(String(200), nullable=True)
    story_area_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    story_iteration_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    story_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    story_accessible: Mapped[bool] = mapped_column(Boolean, default=True)
    suggested_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("8.00"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TimeEntryOperation(Base):
    __tablename__ = "time_entry_operations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    story_id: Mapped[int] = mapped_column(Integer, index=True)
    story_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    story_project: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    assignee_name: Mapped[str] = mapped_column(String(200))
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    task_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    task_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    justification: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    module: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
