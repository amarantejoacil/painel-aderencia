from __future__ import annotations

from calendar import monthrange
from datetime import date

from app.analysis.engine import ActivityInput
from app.services.azure_state_labels import is_azure_state_completed, translate_azure_state


def collect_non_completed_tasks(
    activities: list[ActivityInput],
    collaborator_id: int,
    year: int,
    month: int,
) -> list[dict]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    rows: list[dict] = []
    for activity in activities:
        if activity.collaborator_id != collaborator_id:
            continue
        if not (first <= activity.work_date <= last):
            continue
        if is_azure_state_completed(activity.state):
            continue
        rows.append(
            {
                "task_id": activity.task_id,
                "title": activity.title,
                "work_date": activity.work_date,
                "state": activity.state,
                "state_label": translate_azure_state(activity.state),
                "completed_hours": activity.completed_hours,
                "activity_category": activity.activity_category,
                "project": activity.project,
            }
        )
    rows.sort(key=lambda item: (item["work_date"], item["task_id"]))
    return rows
