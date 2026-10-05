from datetime import date
from decimal import Decimal

from app.services.activity_normalization import NormalizedActivity
from app.services.azure_sync_preview import filter_by_ignored_assignees


def _item(assignee: str, task_id: str = "1") -> NormalizedActivity:
    return NormalizedActivity(
        task_id=task_id,
        title="Task",
        azure_assignee=assignee,
        assignee_name=assignee,
        work_date=date(2026, 10, 1),
        source="azure_api",
    )


def test_filter_by_ignored_assignees() -> None:
    items = [
        _item("Paula Souza", "1"),
        _item("Bruno Silva", "2"),
        _item("Davi Monteiro Alves", "3"),
    ]
    kept, skipped = filter_by_ignored_assignees(items, ["Paula Souza", "Bruno Silva"])
    assert len(kept) == 1
    assert kept[0].task_id == "3"
    assert len(skipped) == 2
    assert "Paula" in skipped[0].reason
