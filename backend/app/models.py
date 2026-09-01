from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
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

    import_batch: Mapped[ImportBatch] = relationship(back_populates="activities")
    collaborator: Mapped[Collaborator | None] = relationship(back_populates="activities")
