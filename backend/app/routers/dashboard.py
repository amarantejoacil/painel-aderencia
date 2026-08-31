from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.engine import (
    ActivityInput,
    CollaboratorInput,
    analyze_collaborator,
    analyze_team,
    team_indicators,
)
from app.database import get_db
from app.models import Activity, CalendarException, Collaborator, ImportBatch
from app.schemas import (
    CollaboratorAnalysisOut,
    CollaboratorOut,
    CollaboratorSummaryOut,
    DashboardOut,
    DayResultOut,
    DayTaskOut,
)

router = APIRouter(tags=["dashboard"])


def _to_input(item: Collaborator) -> CollaboratorInput:
    return CollaboratorInput(
        id=item.id,
        name=item.name,
        azure_name=item.azure_name,
        start_date=item.start_date,
        end_date=item.end_date,
        daily_hours=item.daily_hours,
        active=item.active,
    )


def _activity_inputs(db: Session) -> list[ActivityInput]:
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
            state=row.state,
            project=row.project,
        )
        for row in rows
    ]


def _exceptions(db: Session) -> set[date]:
    return set(db.scalars(select(CalendarException.date)).all())


def _summary_out(summary) -> CollaboratorSummaryOut:
    return CollaboratorSummaryOut(
        collaborator=CollaboratorOut.model_validate(summary.collaborator)
        if not isinstance(summary.collaborator, CollaboratorInput)
        else CollaboratorOut(
            id=summary.collaborator.id,
            name=summary.collaborator.name,
            azure_name=summary.collaborator.azure_name,
            start_date=summary.collaborator.start_date,
            end_date=summary.collaborator.end_date,
            daily_hours=summary.collaborator.daily_hours,
            active=summary.collaborator.active,
        ),
        expected=summary.expected,
        executed=summary.executed,
        adherence=summary.adherence,
        regular=summary.regular,
        incomplete=summary.incomplete,
        missing=summary.missing,
        excess=summary.excess,
        not_required=summary.not_required,
    )


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    collaborator_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> DashboardOut:
    collaborators = [_to_input(item) for item in db.scalars(select(Collaborator)).all()]
    if collaborator_id is not None:
        collaborators = [item for item in collaborators if item.id == collaborator_id]
        if not collaborators:
            raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    summaries = analyze_team(
        collaborators,
        _activity_inputs(db),
        _exceptions(db),
        year,
        month,
        date.today(),
    )
    if status:
        summaries = [
            row
            for row in summaries
            if any(day.status == status for day in row.days)
        ]
    return DashboardOut(
        year=year,
        month=month,
        indicators=team_indicators(summaries),
        rows=[_summary_out(row) for row in summaries],
    )


@router.get("/collaborators/{collaborator_id}/analysis", response_model=CollaboratorAnalysisOut)
def get_collaborator_analysis(
    collaborator_id: int,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
) -> CollaboratorAnalysisOut:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    summary = analyze_collaborator(
        _to_input(collaborator),
        _activity_inputs(db),
        _exceptions(db),
        year,
        month,
        date.today(),
    )
    days = [
        DayResultOut(
            date=day.date,
            expected=day.expected,
            executed=day.executed,
            difference=day.difference,
            status=day.status,
            hours_source=day.hours_source,
            task_count=day.task_count,
            tasks=[
                DayTaskOut(
                    task_id=task.task_id,
                    title=task.title,
                    completed_hours=task.completed_hours,
                    state=task.state,
                    project=task.project,
                )
                for task in day.tasks
            ],
        )
        for day in summary.days
    ]
    return CollaboratorAnalysisOut(summary=_summary_out(summary), days=days)
