from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarException, Collaborator, CollaboratorAbsence


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def build_month_schedule_context(db: Session, year: int, month: int) -> dict:
    month_start, month_end = _month_bounds(year, month)

    exceptions = list(
        db.scalars(
            select(CalendarException)
            .where(CalendarException.date >= month_start, CalendarException.date <= month_end)
            .order_by(CalendarException.date)
        ).all()
    )

    absences = list(
        db.scalars(
            select(CollaboratorAbsence)
            .where(
                CollaboratorAbsence.start_date <= month_end,
                CollaboratorAbsence.end_date >= month_start,
            )
            .order_by(CollaboratorAbsence.start_date, CollaboratorAbsence.collaborator_id)
        ).all()
    )

    collaborator_names: dict[int, str] = {}
    if absences:
        ids = {item.collaborator_id for item in absences}
        for row in db.scalars(select(Collaborator).where(Collaborator.id.in_(ids))).all():
            collaborator_names[row.id] = row.name

    absence_rows = [
        {
            "id": item.id,
            "collaborator_id": item.collaborator_id,
            "collaborator_name": collaborator_names.get(item.collaborator_id, "—"),
            "type": item.type,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "note": item.note,
        }
        for item in absences
    ]

    summary: dict[str, int] = {
        "calendar_exceptions": len(exceptions),
        "calendar_work_release": sum(1 for item in exceptions if item.type == "work_release"),
        "absences_total": len(absence_rows),
        "medical_certificate": sum(1 for item in absence_rows if item["type"] == "medical_certificate"),
        "vacation": sum(1 for item in absence_rows if item["type"] == "vacation"),
        "work_release": sum(1 for item in absence_rows if item["type"] == "work_release"),
        "day_off": sum(1 for item in absence_rows if item["type"] == "day_off"),
        "leave": sum(1 for item in absence_rows if item["type"] == "leave"),
        "other": sum(1 for item in absence_rows if item["type"] == "other"),
    }

    return {
        "calendar_exceptions": [
            {
                "id": item.id,
                "date": item.date,
                "type": item.type,
                "description": item.description,
            }
            for item in exceptions
        ],
        "absences": absence_rows,
        "summary": summary,
    }
