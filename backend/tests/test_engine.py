from datetime import date
from decimal import Decimal

from app.analysis.engine import (
    AbsenceInput,
    ActivityInput,
    CollaboratorInput,
    STATUS_EXCESS,
    STATUS_INCOMPLETE,
    STATUS_JUSTIFIED_ABSENCE,
    STATUS_MISSING,
    STATUS_NOT_REQUIRED,
    STATUS_REGULAR,
    analyze_collaborator,
    analyze_team,
    q,
)


def person(**overrides) -> CollaboratorInput:
    data = dict(
        id=1,
        name="João",
        azure_name="João",
        start_date=date(2026, 8, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )
    data.update(overrides)
    return CollaboratorInput(**data)


def task(day: date, hours: Decimal | None, task_id: str = "1") -> ActivityInput:
    return ActivityInput(
        task_id=task_id,
        title=f"Task {task_id}",
        collaborator_id=1,
        work_date=day,
        completed_hours=hours,
    )


TODAY = date(2026, 8, 31)


def test_multiple_tasks_same_day_sum_to_regular() -> None:
    summary = analyze_collaborator(
        person(),
        [
            task(date(2026, 8, 20), Decimal("3"), "A"),
            task(date(2026, 8, 20), Decimal("5"), "B"),
        ],
        set(),
        2026,
        8,
        TODAY,
    )
    day = next(item for item in summary.days if item.date == date(2026, 8, 20))
    assert day.executed == q(8)
    assert day.status == STATUS_REGULAR
    assert day.task_count == 2


def test_excess_does_not_cover_next_day() -> None:
    summary = analyze_collaborator(
        person(),
        [task(date(2026, 8, 26), Decimal("16"), "A")],
        set(),
        2026,
        8,
        TODAY,
    )
    day26 = next(item for item in summary.days if item.date == date(2026, 8, 26))
    day27 = next(item for item in summary.days if item.date == date(2026, 8, 27))
    assert day26.status == STATUS_EXCESS
    assert day27.status == STATUS_MISSING


def test_weekend_and_holiday_not_required() -> None:
    summary = analyze_collaborator(
        person(),
        [],
        {date(2026, 8, 10), date(2026, 8, 11)},
        2026,
        8,
        TODAY,
    )
    assert next(item for item in summary.days if item.date == date(2026, 8, 8)).status == STATUS_NOT_REQUIRED
    assert next(item for item in summary.days if item.date == date(2026, 8, 10)).status == STATUS_NOT_REQUIRED
    assert next(item for item in summary.days if item.date == date(2026, 8, 3)).status == STATUS_MISSING


def test_start_date_avoids_false_missing() -> None:
    summary = analyze_collaborator(
        person(start_date=date(2026, 8, 19)),
        [task(date(2026, 8, 19), Decimal("8"))],
        set(),
        2026,
        8,
        TODAY,
    )
    assert next(item for item in summary.days if item.date == date(2026, 8, 3)).status == STATUS_NOT_REQUIRED
    assert next(item for item in summary.days if item.date == date(2026, 8, 19)).status == STATUS_REGULAR


def test_adherence_caps_at_100() -> None:
    summary = analyze_collaborator(
        person(),
        [task(date(2026, 8, 3), Decimal("16"))],
        set(),
        2026,
        8,
        TODAY,
    )
    day = next(item for item in summary.days if item.date == date(2026, 8, 3))
    assert day.status == STATUS_EXCESS
    assert summary.adherence <= q(100)
    weekday_expected = Decimal("0")
    for item in summary.days:
        weekday_expected += item.expected
    assert summary.adherence == q((Decimal("8") / weekday_expected) * 100)


def test_incomplete_status() -> None:
    summary = analyze_collaborator(
        person(),
        [task(date(2026, 8, 3), Decimal("5"))],
        set(),
        2026,
        8,
        TODAY,
    )
    day = next(item for item in summary.days if item.date == date(2026, 8, 3))
    assert day.status == STATUS_INCOMPLETE
    assert day.difference == q(-3)


def test_presence_mode_without_hours() -> None:
    summary = analyze_collaborator(
        person(),
        [task(date(2026, 8, 3), None, "10"), task(date(2026, 8, 3), None, "11")],
        set(),
        2026,
        8,
        TODAY,
    )
    day = next(item for item in summary.days if item.date == date(2026, 8, 3))
    assert day.hours_source == "presence"
    assert day.executed == q(8)
    assert day.status == STATUS_REGULAR
    assert day.task_count == 2


def test_future_days_not_required() -> None:
    summary = analyze_collaborator(
        person(),
        [],
        set(),
        2026,
        8,
        date(2026, 8, 5),
    )
    assert next(item for item in summary.days if item.date == date(2026, 8, 6)).status == STATUS_NOT_REQUIRED
    assert next(item for item in summary.days if item.date == date(2026, 8, 5)).status == STATUS_MISSING


def test_justified_absence_removes_missing_and_expected_hours() -> None:
    target = date(2026, 8, 20)
    absences = {target: AbsenceInput(type="medical_certificate", note="Atestado")}
    without = analyze_collaborator(person(), [], set(), 2026, 8, TODAY)
    summary = analyze_collaborator(person(), [], set(), 2026, 8, TODAY, absences)
    day = next(item for item in summary.days if item.date == target)
    assert day.status == STATUS_JUSTIFIED_ABSENCE
    assert day.expected == q(0)
    assert day.executed == q(0)
    assert day.absence_type == "medical_certificate"
    assert summary.missing == without.missing - 1
    assert summary.justified_absence == 1
    assert summary.expected == without.expected - q(8)


def _absence_period(start: date, end: date, absence_type: str, note: str) -> dict[date, AbsenceInput]:
    from datetime import timedelta

    absences: dict[date, AbsenceInput] = {}
    current = start
    while current <= end:
        absences[current] = AbsenceInput(type=absence_type, note=note)
        current += timedelta(days=1)
    return absences


def test_vacation_period_reduces_expected_and_skips_inconsistencies() -> None:
    from app.services.monthly_report import pending_days

    vacation_start = date(2026, 9, 8)
    vacation_end = date(2026, 9, 18)
    month_end = date(2026, 9, 30)
    absences = _absence_period(vacation_start, vacation_end, "vacation", "Férias programadas")

    joao = person(name="João da Silva", start_date=date(2026, 8, 1))
    without = analyze_collaborator(joao, [task(date(2026, 9, 7), Decimal("8"))], set(), 2026, 9, month_end)
    summary = analyze_collaborator(
        joao,
        [task(date(2026, 9, 7), Decimal("8"))],
        set(),
        2026,
        9,
        month_end,
        absences,
    )

    day7 = next(item for item in summary.days if item.date == date(2026, 9, 7))
    day10 = next(item for item in summary.days if item.date == date(2026, 9, 10))
    day13 = next(item for item in summary.days if item.date == date(2026, 9, 13))
    day14 = next(item for item in summary.days if item.date == date(2026, 9, 14))

    assert day7.status == STATUS_REGULAR
    assert day7.expected == q(8)
    assert day10.status == STATUS_JUSTIFIED_ABSENCE
    assert day10.absence_type == "vacation"
    assert day10.expected == q(0)
    assert day10.executed == q(0)
    assert day13.status == STATUS_NOT_REQUIRED
    assert day14.status == STATUS_JUSTIFIED_ABSENCE
    assert day14.absence_type == "vacation"

    day21 = next(item for item in summary.days if item.date == date(2026, 9, 21))
    assert day21.status == STATUS_MISSING
    assert day21.expected == q(8)

    vacation_weekdays = 9
    assert summary.justified_absence == vacation_weekdays
    assert summary.expected == without.expected - q(vacation_weekdays * 8)
    assert summary.missing == without.missing - vacation_weekdays

    vacation_pending = [
        day
        for day in pending_days(summary)
        if vacation_start <= day.date <= vacation_end and day.date.weekday() < 5
    ]
    assert vacation_pending == []

    assert summary.adherence == q((Decimal("8") / summary.expected) * 100)


def test_work_release_absence_does_not_require_tasks() -> None:
    from app.analysis.engine import AbsenceInput

    target = date(2026, 9, 12)
    absences = {target: AbsenceInput(type="work_release", note="Liberados pela chefia")}
    summary = analyze_collaborator(person(), [], set(), 2026, 9, date(2026, 9, 30), absences)
    day = next(item for item in summary.days if item.date == target)
    assert day.status == STATUS_JUSTIFIED_ABSENCE
    assert day.absence_type == "work_release"
    assert day.expected == q(0)


def test_dismissal_from_end_date_no_missing_or_expected() -> None:
    from app.services.monthly_report import pending_days

    dismissal = date(2026, 9, 15)
    joao = person(name="Gabriel Araújo Dos Santos", end_date=dismissal, active=False)
    summary = analyze_collaborator(joao, [], set(), 2026, 9, date(2026, 9, 30))

    day14 = next(item for item in summary.days if item.date == date(2026, 9, 14))
    day15 = next(item for item in summary.days if item.date == date(2026, 9, 15))
    day16 = next(item for item in summary.days if item.date == date(2026, 9, 16))

    assert day14.status == STATUS_MISSING
    assert day14.expected == q(8)
    assert day15.status == STATUS_NOT_REQUIRED
    assert day15.expected == q(0)
    assert day16.status == STATUS_NOT_REQUIRED
    assert day16.expected == q(0)

    without_end = analyze_collaborator(
        person(name="Gabriel Araújo Dos Santos"),
        [],
        set(),
        2026,
        9,
        date(2026, 9, 30),
    )
    assert summary.expected == without_end.expected - q(8 * 12)
    assert all(day.date < dismissal or day.status != STATUS_MISSING for day in pending_days(summary) if day.date.weekday() < 5)


def test_inactive_collaborator_still_in_month_before_dismissal() -> None:
    summaries = analyze_team(
        [person(end_date=date(2026, 9, 20), active=False)],
        [],
        set(),
        2026,
        9,
        date(2026, 9, 30),
    )
    assert len(summaries) == 1
    assert summaries[0].missing == 14


def test_team_daily_adherence_aggregates_obligated_days() -> None:
    from app.analysis.engine import analyze_team, team_daily_adherence

    summaries = analyze_team(
        [person(id=1), person(id=2, name="Maria", azure_name="Maria")],
        [
            task(date(2026, 8, 4), Decimal("8"), "1"),
            task(date(2026, 8, 4), Decimal("4"), "2"),
        ],
        set(),
        2026,
        8,
        TODAY,
    )
    daily = team_daily_adherence(summaries)
    day = next(item for item in daily if item["date"] == date(2026, 8, 4))
    assert day["collaborators"] == 2
    assert day["adherence"] == q(75)
