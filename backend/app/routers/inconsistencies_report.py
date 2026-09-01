from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CollaboratorOut,
    DayResultOut,
    DayTaskOut,
    MonthlyReportOut,
    MonthlyReportRowOut,
)
from app.services.analysis_context import (
    load_activity_inputs,
    load_collaborator_absences,
    load_collaborator_inputs,
    load_exception_dates,
)
from app.services.monthly_report import analyze_monthly_team

router = APIRouter(prefix="/inconsistencies-report", tags=["inconsistencies-report"])


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


def _row_out(item: dict) -> MonthlyReportRowOut:
    summary = item["summary"]
    collaborator = summary.collaborator
    return MonthlyReportRowOut(
        collaborator=CollaboratorOut(
            id=collaborator.id,
            name=collaborator.name,
            azure_name=collaborator.azure_name,
            start_date=collaborator.start_date,
            end_date=collaborator.end_date,
            daily_hours=collaborator.daily_hours,
            active=collaborator.active,
        ),
        situation=item["situation"],
        adherence=summary.adherence,
        missing=summary.missing,
        incomplete=summary.incomplete,
        excess=summary.excess,
        summary_text=item["summary_text"],
        pending_days=[_day_out(day) for day in item["pending_days"]],
    )


@router.get("", response_model=MonthlyReportOut)
def get_inconsistencies_report(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    situation: str | None = Query(default=None, pattern="^(ok|pending)$"),
    issue_type: str | None = Query(default=None, pattern="^(missing|incomplete|excess)$"),
    db: Session = Depends(get_db),
) -> MonthlyReportOut:
    report = analyze_monthly_team(
        load_collaborator_inputs(db),
        load_activity_inputs(db),
        load_exception_dates(db),
        year,
        month,
        date.today(),
        situation,
        issue_type,
        load_collaborator_absences(db),
    )
    return MonthlyReportOut(
        year=report["year"],
        month=report["month"],
        indicators=report["indicators"],
        rows=[_row_out(item) for item in report["rows"]],
    )


@router.get("/export")
def export_inconsistencies_report(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    situation: str | None = Query(default=None, pattern="^(ok|pending)$"),
    issue_type: str | None = Query(default=None, pattern="^(missing|incomplete|excess)$"),
    db: Session = Depends(get_db),
) -> Response:
    report = analyze_monthly_team(
        load_collaborator_inputs(db),
        load_activity_inputs(db),
        load_exception_dates(db),
        year,
        month,
        date.today(),
        situation,
        issue_type,
        load_collaborator_absences(db),
    )
    period = f"{month:02d}/{year}"
    lines = ["Mês/Ano;Colaborador;Data;Horas esperadas;Horas executadas;Diferença;Tipo da inconsistência"]
    for item in report["rows"]:
        if item["situation"] != "pending":
            continue
        collaborator = item["summary"].collaborator
        for day in item["pending_days"]:
            lines.append(
                ";".join(
                    [
                        period,
                        _csv_cell(collaborator.name),
                        day.date.strftime("%d/%m/%Y"),
                        str(day.expected).replace(".", ","),
                        str(day.executed).replace(".", ","),
                        str(day.difference).replace(".", ","),
                        _csv_cell(_issue_label(day.status)),
                    ]
                )
            )

    content = "\ufeff" + "\n".join(lines) + "\n"
    filename = f"relatorio-inconsistencias-{year}-{month:02d}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_cell(value: str) -> str:
    text = value.replace('"', '""')
    return f'"{text}"'


def _issue_label(status: str) -> str:
    labels = {
        "missing": "Sem lançamento",
        "incomplete": "Incompleto",
        "excess": "Excedente",
    }
    return labels.get(status, status)
