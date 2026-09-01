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
