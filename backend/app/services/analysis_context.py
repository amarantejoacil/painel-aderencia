from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.engine import AbsenceInput, ActivityInput, CollaboratorInput
from app.models import Activity, CalendarException, Collaborator, CollaboratorAbsence, ImportBatch
from app.services.azure_devops_config import get_ignored_assignees
from app.services.csv_parser import normalize_name


def to_collaborator_input(item: Collaborator) -> CollaboratorInput:
    return CollaboratorInput(
        id=item.id,
        name=item.name,
        azure_name=item.azure_name,
        start_date=item.start_date,
        end_date=item.end_date,
        daily_hours=item.daily_hours,
        active=item.active,
    )


def load_activity_inputs(db: Session) -> list[ActivityInput]:
    latest = db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).first()
    if not latest:
        return []
    rows = db.scalars(select(Activity).where(Activity.import_id == latest.id)).all()
    return [
        ActivityInput(
            task_id=row.task_id,
            title=row.title,
            collaborator_id=row.collaborator_id,
            work_date=row.work_date,
            completed_hours=row.completed_hours,
            estimated_hours=row.estimated_hours,
            state=row.state,
            project=row.project,
            activity_category=row.activity_category,
        )
        for row in rows
    ]


def load_exception_dates(db: Session) -> set[date]:
    return set(db.scalars(select(CalendarException.date)).all())


def load_calendar_exceptions_by_date(db: Session) -> dict[date, CalendarException]:
    rows = db.scalars(select(CalendarException)).all()
    return {row.date: row for row in rows}


def load_collaborator_inputs(db: Session) -> list[CollaboratorInput]:
    ignored = {normalize_name(name) for name in get_ignored_assignees(db)}
    rows = db.scalars(select(Collaborator)).all()
    eligible = [
        item
        for item in rows
        if normalize_name(item.azure_name) not in ignored and normalize_name(item.name) not in ignored
    ]
    return [to_collaborator_input(item) for item in eligible]


def _expand_absence_dates(start: date, end: date) -> list[date]:
    if end < start:
        return []
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def load_collaborator_absences(db: Session) -> dict[int, dict[date, AbsenceInput]]:
    rows = db.scalars(select(CollaboratorAbsence)).all()
    result: dict[int, dict[date, AbsenceInput]] = {}
    for row in rows:
        by_date = result.setdefault(row.collaborator_id, {})
        for day in _expand_absence_dates(row.start_date, row.end_date):
            by_date[day] = AbsenceInput(type=row.type, note=row.note)
    return result
