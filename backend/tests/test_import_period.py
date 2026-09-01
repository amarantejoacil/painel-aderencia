from datetime import date
from decimal import Decimal

from app.services.csv_parser import ParsedActivity
from app.services.import_period import count_outside_period, summarize_import_period


def _activity(day: int) -> ParsedActivity:
    return ParsedActivity(
        task_id=str(day),
        title="Task",
        azure_assignee="João",
        assignee_name="João",
        work_date=date(2026, 8, day),
        completed_hours=Decimal("8"),
    )


def test_summarize_import_period_uses_primary_month() -> None:
    activities = [_activity(3), _activity(4), _activity(5)]
    summary = summarize_import_period(activities)
    assert summary["year"] == 2026
    assert summary["month"] == 8
    assert summary["outside_primary_count"] == 0


def test_count_outside_period() -> None:
    activities = [_activity(3), _activity(4)]
    assert count_outside_period(activities, 2026, 8) == 0
    assert count_outside_period(activities, 2026, 9) == 2
