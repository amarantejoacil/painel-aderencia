from datetime import date
from decimal import Decimal

from app.analysis.engine import (
    STATUS_EXCESS,
    STATUS_INCOMPLETE,
    STATUS_MISSING,
    STATUS_REGULAR,
    analyze_collaborator,
    analyze_team,
)
from app.services.monthly_report import (
    SITUATION_OK,
    SITUATION_PENDING,
    analyze_monthly_team,
    build_monthly_report,
    is_collaborator_ok,
    pending_days,
)


def person(**overrides):
    from app.analysis.engine import CollaboratorInput

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


def task(day: date, hours: Decimal | None, task_id: str = "1"):
    from app.analysis.engine import ActivityInput

    return ActivityInput(
        task_id=task_id,
        title=f"Task {task_id}",
        collaborator_id=1,
        work_date=day,
        completed_hours=hours,
    )


TODAY = date(2026, 8, 31)


def test_collaborator_ok_when_no_inconsistencies() -> None:
    summary = analyze_collaborator(
        person(),
        [task(date(2026, 8, 4), Decimal("8"))],
        set(),
        2026,
        8,
        TODAY,
    )
    assert is_collaborator_ok(summary) is True
    assert summary.missing == 20


def test_collaborator_pending_with_missing_days() -> None:
    summary = analyze_collaborator(person(), [], set(), 2026, 8, TODAY)
    assert is_collaborator_ok(summary) is False
    assert len(pending_days(summary)) == summary.missing


def test_report_sorts_pending_before_ok() -> None:
    ok_person = person(id=1, name="Ana")
    pending_person = person(id=2, name="Bruno")
    activities = [task(date(2026, 8, 4), Decimal("8"))]
    report = build_monthly_report(
        [
            analyze_collaborator(ok_person, activities, set(), 2026, 8, TODAY),
            analyze_collaborator(pending_person, [], set(), 2026, 8, TODAY),
        ],
        2026,
        8,
    )
    assert report["rows"][0]["situation"] == SITUATION_PENDING
    assert report["rows"][1]["situation"] == SITUATION_OK


def test_report_filters_by_issue_type() -> None:
    summary = analyze_collaborator(
        person(),
        [
            task(date(2026, 8, 4), Decimal("5")),
            task(date(2026, 8, 5), Decimal("16"), "2"),
        ],
        set(),
        2026,
        8,
        TODAY,
    )
    day4 = next(item for item in summary.days if item.date == date(2026, 8, 4))
    day5 = next(item for item in summary.days if item.date == date(2026, 8, 5))
    assert day4.status == STATUS_INCOMPLETE
    assert day5.status == STATUS_EXCESS

    report = build_monthly_report([summary], 2026, 8, issue_type=STATUS_INCOMPLETE)
    assert len(report["rows"]) == 1
    assert len(report["rows"][0]["pending_days"]) == 1
    assert report["rows"][0]["pending_days"][0].status == STATUS_INCOMPLETE


def test_report_situation_filter_ok_only() -> None:
    summaries = analyze_team([person(id=1), person(id=2, name="Maria")], [], set(), 2026, 8, TODAY)
    report = build_monthly_report(summaries, 2026, 8, situation=SITUATION_OK)
    assert all(row["situation"] == SITUATION_OK for row in report["rows"])
