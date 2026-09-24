from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarException, Collaborator, CollaboratorAbsence
from app.schemas import WorkReleaseCreate, WorkReleaseOut

WORK_RELEASE_ABSENCE = "work_release"
WORK_RELEASE_CALENDAR = "work_release"


def _expand_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def apply_work_release(db: Session, payload: WorkReleaseCreate) -> WorkReleaseOut:
    if payload.scope == "team":
        calendar_days = 0
        for day in _expand_dates(payload.start_date, payload.end_date):
            item = db.scalar(select(CalendarException).where(CalendarException.date == day))
            if item:
                item.type = WORK_RELEASE_CALENDAR
                item.description = payload.description
            else:
                db.add(
                    CalendarException(
                        date=day,
                        type=WORK_RELEASE_CALENDAR,
                        description=payload.description,
                    )
                )
            calendar_days += 1
        db.commit()
        return WorkReleaseOut(
            scope=payload.scope,
            start_date=payload.start_date,
            end_date=payload.end_date,
            description=payload.description,
            calendar_days=calendar_days,
            collaborator_count=0,
        )

    collaborators = list(
        db.scalars(select(Collaborator).where(Collaborator.id.in_(payload.collaborator_ids))).all()
    )
    found_ids = {item.id for item in collaborators}
    missing = [item for item in payload.collaborator_ids if item not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")

    for collaborator in collaborators:
        db.add(
            CollaboratorAbsence(
                collaborator_id=collaborator.id,
                type=WORK_RELEASE_ABSENCE,
                start_date=payload.start_date,
                end_date=payload.end_date,
                note=payload.description,
            )
        )
    db.commit()
    return WorkReleaseOut(
        scope=payload.scope,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
        calendar_days=0,
        collaborator_count=len(collaborators),
    )
