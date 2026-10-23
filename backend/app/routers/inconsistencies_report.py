from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CollaboratorOut,
    DayLaunchVerificationOut,
    DayLaunchVerificationTaskOut,
    DayResultOut,
    DayTaskOut,
    MonthScheduleContextOut,
    MonthlyReportOut,
    MonthlyReportRowOut,
    ReportOpenTaskOut,
)
from app.services.azure_devops_config import get_settings_row
from app.services.azure_work_item_url import resolve_work_item_url
from app.services.day_launch_verification import verify_day_launch
from app.services.analysis_context import (
    load_activity_inputs,
    load_collaborator_absences,
    load_collaborator_inputs,
    load_exception_dates,
)
from app.services.month_schedule_context import build_month_schedule_context
from app.services.monthly_report import analyze_monthly_team

router = APIRouter(prefix="/inconsistencies-report", tags=["inconsistencies-report"])


def _azure_link_context(db: Session) -> tuple[str | None, str | None]:
    row = get_settings_row(db)
    if row is None:
        return None, None
    return (row.base_url or "").strip() or None, (row.organization or "").strip() or None


def _task_url(
    base_url: str | None,
    organization: str | None,
    project: str | None,
    task_id: str,
) -> str | None:
    return resolve_work_item_url(
        base_url=base_url,
        organization=organization,
        team_project=project,
        task_id=task_id,
    )


def _day_out(
    day,
    daily_hours: Decimal,
    *,
    base_url: str | None,
    organization: str | None,
) -> DayResultOut:
    raw_verification = verify_day_launch(day, daily_hours)
    verification = None
    if raw_verification is not None:
        verification_tasks = []
        for task in raw_verification.get("tasks") or []:
            verification_tasks.append(
                DayLaunchVerificationTaskOut(
                    **task,
                    azure_url=_task_url(base_url, organization, task.get("project"), task["task_id"]),
                )
            )
        verification = DayLaunchVerificationOut(
            kind=raw_verification["kind"],
            message=raw_verification["message"],
            tasks=verification_tasks,
        )
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
        absence_excused_hours=day.absence_excused_hours,
        launch_verification=verification,
        tasks=[
            DayTaskOut(
                task_id=task.task_id,
                title=task.title,
                completed_hours=task.completed_hours,
                state=task.state,
                project=task.project,
                activity_category=task.activity_category,
                azure_url=_task_url(base_url, organization, task.project, task.task_id),
            )
            for task in day.tasks
        ],
    )


def _row_out(
    item: dict,
    *,
    base_url: str | None,
    organization: str | None,
) -> MonthlyReportRowOut:
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
        pending_days=[
            _day_out(
                day,
                summary.collaborator.daily_hours,
                base_url=base_url,
                organization=organization,
            )
            for day in item["pending_days"]
        ],
        open_tasks=[
            ReportOpenTaskOut(
                **task,
                azure_url=_task_url(base_url, organization, task.get("project"), task["task_id"]),
            )
            for task in item.get("open_tasks", [])
        ],
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
    schedule = build_month_schedule_context(db, year, month)
    base_url, organization = _azure_link_context(db)
    return MonthlyReportOut(
        year=report["year"],
        month=report["month"],
        indicators=report["indicators"],
        rows=[_row_out(item, base_url=base_url, organization=organization) for item in report["rows"]],
        month_schedule=MonthScheduleContextOut(**schedule),
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

    lines.append("")
    lines.append("Tasks com status diferente de Concluído")
    lines.append("Mês/Ano;Colaborador;ID;Data da atividade;Título;Status;Horas executadas")
    for item in report["rows"]:
        collaborator = item["summary"].collaborator
        for task in item.get("open_tasks", []):
            hours = ""
            if task["completed_hours"] is not None:
                hours = str(task["completed_hours"]).replace(".", ",")
            lines.append(
                ";".join(
                    [
                        period,
                        _csv_cell(collaborator.name),
                        _csv_cell(task["task_id"]),
                        task["work_date"].strftime("%d/%m/%Y"),
                        _csv_cell(task["title"]),
                        _csv_cell(task["state_label"]),
                        hours,
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
