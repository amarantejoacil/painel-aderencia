from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.services.csv_parser import ParsedActivity

ActivitySource = Literal["csv", "azure_api"]


@dataclass
class NormalizedActivity:
    task_id: str
    title: str
    azure_assignee: str
    assignee_name: str
    work_date: date
    work_item_type: str | None = None
    completed_hours: Decimal | None = None
    estimated_hours: Decimal | None = None
    state: str | None = None
    project: str | None = None
    activity_category: str | None = None
    source: ActivitySource = "csv"


def from_parsed_csv(item: ParsedActivity, source: ActivitySource = "csv") -> NormalizedActivity:
    return NormalizedActivity(
        task_id=item.task_id,
        title=item.title,
        azure_assignee=item.azure_assignee,
        assignee_name=item.assignee_name,
        work_date=item.work_date,
        work_item_type=item.work_item_type,
        completed_hours=item.completed_hours,
        estimated_hours=item.estimated_hours,
        state=item.state,
        project=item.project,
        activity_category=item.activity_category,
        source=source,
    )
