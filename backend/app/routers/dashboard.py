from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analysis.engine import (
    CollaboratorInput,
    analyze_collaborator,
    analyze_team,
    team_daily_adherence,
    team_indicators,
)
from app.database import get_db
from app.models import Collaborator
from app.schemas import (
    CollaboratorAnalysisOut,
    CollaboratorOut,
    CollaboratorSummaryOut,
    DailyAdherenceOut,
    DashboardOut,
    DashboardRowOut,
    DayResultOut,
    DayTaskOut,
)
from app.services.analysis_context import (
    load_activity_inputs,
    load_collaborator_absences,
    load_collaborator_inputs,
    load_exception_dates,
    to_collaborator_input,
)

router = APIRouter(tags=["dashboard"])


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
        justified_absence=summary.justified_absence,
    )


def _day_out(day) -> DayResultOut:
    return DayResultOut(
        date=day.date,
        expected=day.expected,
        executed=day.executed,
        difference=day.difference,
        status=day.status,
        hours_source=day.hours_source,
        task_count=day.task_count,
        absence_type=day.absence_type,
        absence_note=day.absence_note,
        tasks=[
            DayTaskOut(
                task_id=task.task_id,
                title=task.title,
                completed_hours=task.completed_hours,
                state=task.state,
                project=task.project,
                activity_category=task.activity_category,
            )
            for task in day.tasks
        ],
    )


def _row_out(summary) -> DashboardRowOut:
    base = _summary_out(summary)
    return DashboardRowOut(
        **base.model_dump(),
        days=[_day_out(day) for day in summary.days],
    )


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    collaborator_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> DashboardOut:
    collaborators = load_collaborator_inputs(db)
    if collaborator_id is not None:
        collaborators = [item for item in collaborators if item.id == collaborator_id]
        if not collaborators:
            raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    summaries = analyze_team(
        collaborators,
        load_activity_inputs(db),
        load_exception_dates(db),
        year,
        month,
        date.today(),
        load_collaborator_absences(db),
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
        rows=[_row_out(row) for row in summaries],
        daily_adherence=[
            DailyAdherenceOut(
                date=item["date"],
                adherence=item["adherence"],
                collaborators=item["collaborators"],
            )
            for item in team_daily_adherence(summaries)
        ],
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
        to_collaborator_input(collaborator),
        load_activity_inputs(db),
        load_exception_dates(db),
        year,
        month,
        date.today(),
        load_collaborator_absences(db).get(collaborator_id, {}),
    )
    days = [_day_out(day) for day in summary.days]
    return CollaboratorAnalysisOut(summary=_summary_out(summary), days=days)
