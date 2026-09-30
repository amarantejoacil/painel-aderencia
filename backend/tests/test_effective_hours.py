from datetime import date
from decimal import Decimal

from app.analysis.engine import (
    ActivityInput,
    analyze_collaborator,
    effective_task_hours,
    executed_for_day,
    q,
)


def test_closed_task_with_zero_executed_uses_estimated_hours() -> None:
    task = ActivityInput(
        task_id="4594",
        title="Análise",
        collaborator_id=9,
        work_date=date(2026, 9, 25),
        completed_hours=Decimal("0"),
        estimated_hours=Decimal("8"),
        state="Closed",
    )
    assert effective_task_hours(task, q(8)) == Decimal("8.00")
    executed, _source = executed_for_day([task], q(8))
    assert executed == Decimal("8.00")


def test_closed_task_without_hours_uses_daily_load() -> None:
    task = ActivityInput(
        task_id="1",
        title="Task",
        collaborator_id=1,
        work_date=date(2026, 9, 25),
        completed_hours=Decimal("0"),
        estimated_hours=None,
        state="Closed",
    )
    assert effective_task_hours(task, q(8)) == Decimal("8.00")


def test_open_status_tasks_count_as_presence_not_missing() -> None:
    from app.analysis.engine import CollaboratorInput

    collaborator = CollaboratorInput(
        id=2,
        name="Davi",
        azure_name="Davi",
        start_date=date(2026, 9, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )
    tasks = [
        ActivityInput(
            task_id="4670",
            title="Task nova",
            collaborator_id=2,
            work_date=date(2026, 9, 30),
            completed_hours=Decimal("0"),
            estimated_hours=Decimal("6"),
            state="New",
        )
    ]
    summary = analyze_collaborator(
        collaborator,
        tasks,
        set(),
        2026,
        9,
        date(2026, 9, 30),
    )
    day30 = next(day for day in summary.days if day.date == date(2026, 9, 30))
    assert day30.status == "regular"
    assert day30.executed == Decimal("8.00")
    assert day30.task_count == 1


def test_analyze_collaborator_does_not_flag_missing_when_closed_zero_with_estimate() -> None:
    from app.analysis.engine import CollaboratorInput

    collaborator = CollaboratorInput(
        id=9,
        name="Nayan",
        azure_name="Nayan",
        start_date=date(2026, 9, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )
    task = ActivityInput(
        task_id="4594",
        title="Análise",
        collaborator_id=9,
        work_date=date(2026, 9, 25),
        completed_hours=Decimal("0"),
        estimated_hours=Decimal("8"),
        state="Closed",
    )
    summary = analyze_collaborator(
        collaborator,
        [task],
        set(),
        2026,
        9,
        date(2026, 9, 30),
    )
    day25 = next(day for day in summary.days if day.date == date(2026, 9, 25))
    assert day25.status == "regular"
    assert day25.executed == Decimal("8.00")
