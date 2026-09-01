from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

STATUS_REGULAR = "regular"
STATUS_INCOMPLETE = "incomplete"
STATUS_MISSING = "missing"
STATUS_EXCESS = "excess"
STATUS_NOT_REQUIRED = "not_required"
STATUS_JUSTIFIED_ABSENCE = "justified_absence"

HOURS_LOGGED = "logged"
HOURS_PRESENCE = "presence"
HOURS_NONE = "none"

QUANT = Decimal("0.01")


def q(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class AbsenceInput:
    type: str
    note: str | None = None


@dataclass(frozen=True)
class CollaboratorInput:
    id: int
    name: str
    azure_name: str
    start_date: date
    end_date: date | None
    daily_hours: Decimal
    active: bool


@dataclass(frozen=True)
class ActivityInput:
    task_id: str
    title: str
    collaborator_id: int | None
    work_date: date
    completed_hours: Decimal | None
    state: str | None = None
    project: str | None = None
    activity_category: str | None = None


@dataclass(frozen=True)
class DayTask:
    task_id: str
    title: str
    completed_hours: Decimal | None
    state: str | None
    project: str | None
    activity_category: str | None = None


@dataclass
class DayResult:
    date: date
    expected: Decimal
    executed: Decimal
    difference: Decimal
    status: str
    hours_source: str
    task_count: int
    tasks: list[DayTask] = field(default_factory=list)
    absence_type: str | None = None
    absence_note: str | None = None


@dataclass
class CollaboratorSummary:
    collaborator: CollaboratorInput
    expected: Decimal
    executed: Decimal
    adherence: Decimal
    regular: int
    incomplete: int
    missing: int
    excess: int
    not_required: int
    justified_absence: int
    days: list[DayResult]


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def expected_hours(
    collaborator: CollaboratorInput,
    day: date,
    exception_dates: set[date],
    today: date,
) -> Decimal:
    if day > today:
        return q(0)
    if is_weekend(day):
        return q(0)
    if day in exception_dates:
        return q(0)
    if day < collaborator.start_date:
        return q(0)
    if collaborator.end_date and day > collaborator.end_date:
        return q(0)
    return q(collaborator.daily_hours)


def classify_status(expected: Decimal, executed: Decimal) -> str:
    if expected == 0:
        return STATUS_NOT_REQUIRED
    if executed == 0:
        return STATUS_MISSING
    if executed < expected:
        return STATUS_INCOMPLETE
    if executed > expected:
        return STATUS_EXCESS
    return STATUS_REGULAR


def executed_for_day(
    tasks: list[ActivityInput],
    daily_hours: Decimal,
) -> tuple[Decimal, str]:
    if not tasks:
        return q(0), HOURS_NONE
    logged = [t.completed_hours for t in tasks if t.completed_hours is not None]
    if logged:
        return q(sum(logged, Decimal("0"))), HOURS_LOGGED
    return q(daily_hours), HOURS_PRESENCE


def adherence_hours(executed: Decimal, expected: Decimal) -> Decimal:
    if expected <= 0:
        return q(0)
    return min(q(executed), q(expected))


def month_days(year: int, month: int) -> list[date]:
    last = monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, last + 1)]


def analyze_collaborator(
    collaborator: CollaboratorInput,
    activities: list[ActivityInput],
    exception_dates: set[date],
    year: int,
    month: int,
    today: date,
    collaborator_absences: dict[date, AbsenceInput] | None = None,
) -> CollaboratorSummary:
    absences = collaborator_absences or {}
    by_date: dict[date, list[ActivityInput]] = {}
    for activity in activities:
        if activity.collaborator_id != collaborator.id:
            continue
        by_date.setdefault(activity.work_date, []).append(activity)

    days: list[DayResult] = []
    total_expected = Decimal("0")
    total_executed = Decimal("0")
    capped = Decimal("0")
    counts = {
        STATUS_REGULAR: 0,
        STATUS_INCOMPLETE: 0,
        STATUS_MISSING: 0,
        STATUS_EXCESS: 0,
        STATUS_NOT_REQUIRED: 0,
        STATUS_JUSTIFIED_ABSENCE: 0,
    }

    for day in month_days(year, month):
        absence = absences.get(day)
        if absence is not None:
            day_tasks = by_date.get(day, [])
            result = DayResult(
                date=day,
                expected=q(0),
                executed=q(0),
                difference=q(0),
                status=STATUS_JUSTIFIED_ABSENCE,
                hours_source=HOURS_NONE,
                task_count=len(day_tasks),
                tasks=[
                    DayTask(
                        task_id=task.task_id,
                        title=task.title,
                        completed_hours=q(task.completed_hours) if task.completed_hours is not None else None,
                        state=task.state,
                        project=task.project,
                        activity_category=task.activity_category,
                    )
                    for task in sorted(day_tasks, key=lambda item: item.task_id)
                ],
                absence_type=absence.type,
                absence_note=absence.note,
            )
            days.append(result)
            counts[STATUS_JUSTIFIED_ABSENCE] += 1
            continue

        expected = expected_hours(collaborator, day, exception_dates, today)
        day_tasks = by_date.get(day, [])
        executed, source = executed_for_day(day_tasks, collaborator.daily_hours)
        status = classify_status(expected, executed)
        result = DayResult(
            date=day,
            expected=expected,
            executed=executed,
            difference=q(executed - expected),
            status=status,
            hours_source=source,
            task_count=len(day_tasks),
            tasks=[
                DayTask(
                    task_id=task.task_id,
                    title=task.title,
                    completed_hours=q(task.completed_hours) if task.completed_hours is not None else None,
                    state=task.state,
                    project=task.project,
                    activity_category=task.activity_category,
                )
                for task in sorted(day_tasks, key=lambda item: item.task_id)
            ],
        )
        days.append(result)
        counts[status] += 1
        total_expected += expected
        total_executed += executed
        capped += adherence_hours(executed, expected)

    if total_expected > 0:
        ratio = (capped / total_expected * Decimal("100")).quantize(QUANT, rounding=ROUND_HALF_UP)
        adherence = min(ratio, q(100))
    else:
        adherence = q(100) if total_executed == 0 else q(100)

    return CollaboratorSummary(
        collaborator=collaborator,
        expected=q(total_expected),
        executed=q(total_executed),
        adherence=adherence,
        regular=counts[STATUS_REGULAR],
        incomplete=counts[STATUS_INCOMPLETE],
        missing=counts[STATUS_MISSING],
        excess=counts[STATUS_EXCESS],
        not_required=counts[STATUS_NOT_REQUIRED],
        justified_absence=counts[STATUS_JUSTIFIED_ABSENCE],
        days=days,
    )


def analyze_team(
    collaborators: list[CollaboratorInput],
    activities: list[ActivityInput],
    exception_dates: set[date],
    year: int,
    month: int,
    today: date,
    all_absences: dict[int, dict[date, AbsenceInput]] | None = None,
) -> list[CollaboratorSummary]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    absences = all_absences or {}
    eligible: list[CollaboratorSummary] = []
    for collaborator in collaborators:
        if not collaborator.active:
            continue
        if collaborator.start_date > last:
            continue
        if collaborator.end_date and collaborator.end_date < first:
            continue
        eligible.append(
            analyze_collaborator(
                collaborator,
                activities,
                exception_dates,
                year,
                month,
                today,
                absences.get(collaborator.id, {}),
            )
        )
    return eligible


def team_indicators(summaries: list[CollaboratorSummary]) -> dict:
    expected = q(sum((row.expected for row in summaries), Decimal("0")))
    executed = q(sum((row.executed for row in summaries), Decimal("0")))
    capped = Decimal("0")
    for row in summaries:
        for day in row.days:
            capped += adherence_hours(day.executed, day.expected)
    if expected > 0:
        adherence = min((capped / expected * Decimal("100")).quantize(QUANT, rounding=ROUND_HALF_UP), q(100))
    else:
        adherence = q(100)
    return {
        "collaborators": len(summaries),
        "expected_hours": expected,
        "executed_hours": executed,
        "adherence": adherence,
        "regular": sum(row.regular for row in summaries),
        "incomplete": sum(row.incomplete for row in summaries),
        "missing": sum(row.missing for row in summaries),
        "excess": sum(row.excess for row in summaries),
    }


def team_daily_adherence(summaries: list[CollaboratorSummary]) -> list[dict]:
    totals: dict[date, tuple[Decimal, Decimal, int]] = {}
    for summary in summaries:
        for day in summary.days:
            if day.expected <= 0:
                continue
            expected, capped, count = totals.get(day.date, (Decimal("0"), Decimal("0"), 0))
            totals[day.date] = (
                q(expected + day.expected),
                q(capped + adherence_hours(day.executed, day.expected)),
                count + 1,
            )

    result: list[dict] = []
    for day_date in sorted(totals):
        total_expected, total_capped, collaborators = totals[day_date]
        if total_expected > 0:
            ratio = min(
                (total_capped / total_expected * Decimal("100")).quantize(QUANT, rounding=ROUND_HALF_UP),
                q(100),
            )
        else:
            ratio = q(100)
        result.append(
            {
                "date": day_date,
                "adherence": ratio,
                "collaborators": collaborators,
            }
        )
    return result
