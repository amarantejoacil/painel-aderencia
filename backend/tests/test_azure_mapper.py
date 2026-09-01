from datetime import date
from decimal import Decimal

from app.services.azure_mapper import map_work_item, map_work_items


def _sample_item(
    *,
    task_id: int = 3846,
    title: str = "Onboarding",
    assignee: dict | None = None,
    work_date: str = "2026-08-03T00:00:00Z",
    state: str = "Closed",
    completed: float | None = 3.0,
    activity: str | None = "Desenvolvimento",
) -> dict:
    return {
        "id": task_id,
        "fields": {
            "System.Id": task_id,
            "System.Title": title,
            "System.AssignedTo": assignee
            or {"displayName": "Alisson de Souza Louly", "uniqueName": "PJMT\\05172210121"},
            "System.State": state,
            "System.WorkItemType": "Task",
            "System.TeamProject": "Inteligência Artificial",
            "Custom.DataReferencia": work_date,
            "Microsoft.VSTS.Scheduling.CompletedWork": completed,
            "Custom.Atividade": activity,
        },
    }


def test_map_work_item_maps_core_fields() -> None:
    item = _sample_item()
    mapped = map_work_item(
        item,
        work_date_field="Custom.DataReferencia",
        activity_field="Custom.Atividade",
    )
    assert mapped is not None
    assert mapped.task_id == "3846"
    assert mapped.title == "Onboarding"
    assert mapped.work_date == date(2026, 8, 3)
    assert mapped.state == "Closed"
    assert mapped.completed_hours == Decimal("3.00")
    assert mapped.activity_category == "Desenvolvimento"
    assert mapped.source == "azure_api"
    assert "Alisson de Souza Louly" in mapped.azure_assignee


def test_map_work_item_skips_without_work_date() -> None:
    item = _sample_item(work_date="")
    assert map_work_item(item, work_date_field="Custom.DataReferencia", activity_field=None) is None


def test_map_work_items_counts_skipped() -> None:
    valid = _sample_item(task_id=1)
    invalid = _sample_item(task_id=2, work_date="")
    mapped, skipped = map_work_items(
        [valid, invalid],
        work_date_field="Custom.DataReferencia",
        activity_field="Custom.Atividade",
    )
    assert len(mapped) == 1
    assert skipped == 1
