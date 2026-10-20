from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.engine import (
    HOURS_LOGGED,
    HOURS_NONE,
    STATUS_EXCESS,
    STATUS_INCOMPLETE,
    STATUS_JUSTIFIED_ABSENCE,
    STATUS_MISSING,
    STATUS_NOT_REQUIRED,
    STATUS_REGULAR,
    AbsenceInput,
    ActivityInput,
    CollaboratorInput,
    CollaboratorSummary,
    DayResult,
    analyze_collaborator,
    q,
)
from app.models import Collaborator
from app.services.analysis_context import load_collaborator_absences, load_exception_dates, to_collaborator_input
from app.services.azure_mapper import map_work_item
from app.services.azure_state_labels import is_azure_state_completed
from app.services.csv_parser import normalize_name
from app.services.time_entries.azure import TimeEntryAzure
from app.services.time_entries.dates import today_cuiaba, utc_now_naive
from app.services.time_entries.errors import TimeEntryError

PENDING_STATUSES = {STATUS_INCOMPLETE, STATUS_MISSING, STATUS_EXCESS}
LAUNCH_COMPLETE = "complete"
LAUNCH_PENDING = "pending"
LAUNCH_DISPENSED = "dispensed"
EXCLUDED_STATES = {"removed", "cut", "removido"}
EMPTY_MESSAGE = "Não foram identificadas pendências de apontamento no período analisado."
EXECUTED_LIMIT_NOTE = (
    "Horas executadas são gravadas com o mesmo valor informado nas horas estimadas. "
    "O limite diário vale para a soma das horas executadas já confirmadas no Azure mais este envio."
)

STATUS_LABELS = {
    STATUS_REGULAR: "Completo",
    STATUS_INCOMPLETE: "Incompleto",
    STATUS_MISSING: "Sem lançamento",
    STATUS_EXCESS: "Excesso",
    STATUS_NOT_REQUIRED: "Dispensado",
    STATUS_JUSTIFIED_ABSENCE: "Dispensado",
}

SOURCE_LABELS = {
    "logged": "Horas executadas",
    "presence": "Presença",
    "closed_estimate": "Estimativa de task encerrada",
    "none": "Sem horas",
}


@dataclass
class ConferenceTask:
    task_id: str
    title: str
    state: str | None
    estimated_hours: Decimal
    executed_hours: Decimal
    url: str | None
    project: str | None


@dataclass
class ConferenceDay:
    date: date
    estimated_hours: Decimal
    executed_hours: Decimal
    recognized_hours: Decimal
    missing_hours: Decimal
    expected_hours: Decimal
    status: str
    status_label: str
    hours_source: str
    hours_source_label: str
    suggested_hours: Decimal
    pending: bool
    tasks: list[ConferenceTask] = field(default_factory=list)


@dataclass
class ConferenceReport:
    year: int
    month: int
    checked_at: datetime
    assignee_name: str
    daily_hours: Decimal
    collaborator_matched: bool
    adherence: Decimal
    expected_hours: Decimal
    recognized_hours: Decimal
    estimated_hours: Decimal
    executed_hours: Decimal
    obligatory_days: int
    complete_days: int
    incomplete_days: int
    missing_days: int
    excess_days: int
    dispensed_days: int
    missing_hours: Decimal
    pending: list[ConferenceDay]
    days: list[ConferenceDay]
    empty_message: str | None
    executed_limit_note: str


def launch_state_from_status(status: str) -> str:
    if status == STATUS_REGULAR:
        return LAUNCH_COMPLETE
    if status in PENDING_STATUSES:
        return LAUNCH_PENDING
    return LAUNCH_DISPENSED


def assert_executed_capacity(existing: Decimal, added: Decimal, daily: Decimal) -> None:
    added_hours = q(added)
    if added_hours <= 0:
        return
    total = q(existing) + added_hours
    limit = q(daily)
    if total > limit:
        raise TimeEntryError(
            f"As horas executadas deste envio, somadas às já confirmadas, ficariam em {total}h. "
            f"O limite do dia é {limit}h. O lançamento não foi enviado."
        )


def assignee_keys(names: list[str]) -> set[str]:
    return {normalize_name(name) for name in names if name and normalize_name(name)}


def matches_assignee(assignee_name: str, keys: set[str]) -> bool:
    return bool(keys) and normalize_name(assignee_name) in keys


def describe_source(day: DayResult) -> str:
    if day.hours_source == HOURS_LOGGED:
        return "logged"
    if day.hours_source == HOURS_NONE or not day.tasks:
        return "none"
    if any(task.completed_hours is not None and task.completed_hours > 0 for task in day.tasks):
        return "logged"
    closed_without_executed = any(
        is_azure_state_completed(task.state)
        and not (task.completed_hours is not None and task.completed_hours > 0)
        for task in day.tasks
    )
    if closed_without_executed:
        return "closed_estimate"
    return "presence"


def build_conference(
    *,
    activities: list[ActivityInput],
    collaborator: CollaboratorInput,
    exception_dates: set[date],
    absences: dict[date, AbsenceInput],
    year: int,
    month: int,
    today: date,
    assignee_name: str,
    checked_at: datetime,
    collaborator_matched: bool,
    urls: dict[str, str] | None = None,
) -> ConferenceReport:
    summary = analyze_collaborator(
        collaborator,
        activities,
        exception_dates,
        year,
        month,
        today,
        absences,
    )
    links = urls or {}
    days = [_conference_day(item, collaborator.daily_hours, links) for item in summary.days]
    pending = [item for item in days if item.pending]
    return _report(
        summary,
        days=days,
        pending=pending,
        year=year,
        month=month,
        assignee_name=assignee_name,
        checked_at=checked_at,
        collaborator_matched=collaborator_matched,
    )


def load_conference(db: Session, azure: TimeEntryAzure, year: int, month: int) -> ConferenceReport:
    identity = azure.identity()
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    raw_items = azure.raw_tasks_in_period(start, end)
    row = _collaborator_row(db, identity.display_name)
    if row is not None:
        collaborator = to_collaborator_input(row)
        absences = load_collaborator_absences(db).get(collaborator.id, {})
        names = [identity.display_name, row.azure_name, row.name]
        matched = True
    else:
        collaborator = CollaboratorInput(
            id=0,
            name=identity.display_name,
            azure_name=identity.display_name,
            start_date=date(1900, 1, 1),
            end_date=None,
            daily_hours=Decimal("8"),
            active=True,
        )
        absences = {}
        names = [identity.display_name]
        matched = False
    activities, urls = activities_from_raw(azure, raw_items, collaborator.id, names)
    return build_conference(
        activities=activities,
        collaborator=collaborator,
        exception_dates=load_exception_dates(db),
        absences=absences,
        year=year,
        month=month,
        today=today_cuiaba(),
        assignee_name=identity.display_name,
        checked_at=utc_now_naive(),
        collaborator_matched=matched,
        urls=urls,
    )


def sum_executed_hours(azure: TimeEntryAzure, items: list[dict], names: list[str]) -> Decimal:
    activities, _urls = activities_from_raw(azure, items, 0, names)
    total = Decimal("0")
    for activity in activities:
        if activity.completed_hours is not None:
            total += activity.completed_hours
    return q(total)


def activities_from_raw(
    azure: TimeEntryAzure,
    items: list[dict],
    collaborator_id: int,
    names: list[str],
) -> tuple[list[ActivityInput], dict[str, str]]:
    keys = assignee_keys(names)
    work_date_field, activity_field, completed_hours_field = azure.mapping_fields()
    activities: list[ActivityInput] = []
    urls: dict[str, str] = {}
    for item in items:
        mapped, _error = map_work_item(
            item,
            work_date_field=work_date_field,
            activity_field=activity_field,
            completed_hours_field=completed_hours_field,
        )
        if mapped is None or not matches_assignee(mapped.assignee_name, keys):
            continue
        if (mapped.state or "").strip().casefold() in EXCLUDED_STATES:
            continue
        activities.append(
            ActivityInput(
                task_id=mapped.task_id,
                title=mapped.title,
                collaborator_id=collaborator_id,
                work_date=mapped.work_date,
                completed_hours=mapped.completed_hours,
                estimated_hours=mapped.estimated_hours,
                state=mapped.state,
                project=mapped.project,
                activity_category=mapped.activity_category,
            )
        )
        fields = item.get("fields") or {}
        project = str(fields.get("System.TeamProject") or "").strip()
        try:
            numeric_id = int(item.get("id") or mapped.task_id)
        except (TypeError, ValueError):
            numeric_id = 0
        if project and numeric_id > 0:
            urls[mapped.task_id] = azure.task_url(project, numeric_id)
    return activities, urls


def _collaborator_row(db: Session, display_name: str) -> Collaborator | None:
    target = normalize_name(display_name)
    if not target:
        return None
    for row in db.scalars(select(Collaborator)).all():
        if normalize_name(row.azure_name) == target or normalize_name(row.name) == target:
            return row
    return None


def _hours(value: Decimal | None) -> Decimal:
    if value is None:
        return q(0)
    return q(value)


def _conference_day(day: DayResult, daily_hours: Decimal, urls: dict[str, str]) -> ConferenceDay:
    tasks = [
        ConferenceTask(
            task_id=task.task_id,
            title=task.title,
            state=task.state,
            estimated_hours=_hours(task.estimated_hours),
            executed_hours=_hours(task.completed_hours),
            url=urls.get(task.task_id),
            project=task.project,
        )
        for task in day.tasks
    ]
    estimated = q(sum((task.estimated_hours for task in tasks), Decimal("0")))
    executed = q(sum((task.executed_hours for task in tasks), Decimal("0")))
    recognized = q(day.executed)
    missing = q(max(Decimal("0"), q(day.expected) - recognized))
    source = describe_source(day)
    pending = day.status in PENDING_STATUSES
    suggested = q(0)
    if pending and missing > 0:
        suggested = min(missing, q(daily_hours), q(8))
    return ConferenceDay(
        date=day.date,
        estimated_hours=estimated,
        executed_hours=executed,
        recognized_hours=recognized,
        missing_hours=missing,
        expected_hours=q(day.expected),
        status=day.status,
        status_label=STATUS_LABELS.get(day.status, day.status),
        hours_source=source,
        hours_source_label=SOURCE_LABELS.get(source, source),
        suggested_hours=suggested,
        pending=pending,
        tasks=tasks,
    )


def _report(
    summary: CollaboratorSummary,
    *,
    days: list[ConferenceDay],
    pending: list[ConferenceDay],
    year: int,
    month: int,
    assignee_name: str,
    checked_at: datetime,
    collaborator_matched: bool,
) -> ConferenceReport:
    return ConferenceReport(
        year=year,
        month=month,
        checked_at=checked_at,
        assignee_name=assignee_name,
        daily_hours=q(summary.collaborator.daily_hours),
        collaborator_matched=collaborator_matched,
        adherence=summary.adherence,
        expected_hours=summary.expected,
        recognized_hours=summary.executed,
        estimated_hours=q(sum((item.estimated_hours for item in days), Decimal("0"))),
        executed_hours=q(sum((item.executed_hours for item in days), Decimal("0"))),
        obligatory_days=summary.regular + summary.incomplete + summary.missing + summary.excess,
        complete_days=summary.regular,
        incomplete_days=summary.incomplete,
        missing_days=summary.missing,
        excess_days=summary.excess,
        dispensed_days=summary.not_required + summary.justified_absence,
        missing_hours=q(sum((item.missing_hours for item in days), Decimal("0"))),
        pending=pending,
        days=days,
        empty_message=None if pending else EMPTY_MESSAGE,
        executed_limit_note=EXECUTED_LIMIT_NOTE,
    )
