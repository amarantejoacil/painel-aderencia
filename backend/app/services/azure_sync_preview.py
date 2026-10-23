from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Collaborator
from app.services.activity_normalization import NormalizedActivity
from app.services.azure_mapper import SyncIgnoredItem, map_work_items
from app.services.collaborator_matching import find_collaborator_by_assignee
from app.services.csv_parser import normalize_name


def filter_by_ignored_assignees(
    items: list[NormalizedActivity],
    ignore_names: list[str],
) -> tuple[list[NormalizedActivity], list[SyncIgnoredItem]]:
    ignored_keys = {normalize_name(name) for name in ignore_names if name.strip()}
    if not ignored_keys:
        return items, []

    kept: list[NormalizedActivity] = []
    skipped: list[SyncIgnoredItem] = []
    for item in items:
        if normalize_name(item.assignee_name) in ignored_keys:
            skipped.append(
                SyncIgnoredItem(
                    task_id=item.task_id,
                    title=item.title,
                    reason=f"Responsável ignorado na sincronização: {item.assignee_name}.",
                )
            )
            continue
        kept.append(item)
    return kept, skipped


def summarize_assignees(
    db: Session,
    mapped: list[NormalizedActivity],
    saved_ignored: list[str],
) -> list[dict]:
    ignored_keys = {normalize_name(name) for name in saved_ignored}
    collaborators = list(db.scalars(select(Collaborator)).all())

    counts: dict[str, int] = defaultdict(int)
    for item in mapped:
        counts[item.assignee_name] += 1

    rows: list[dict] = []
    for assignee_name in sorted(counts.keys(), key=lambda value: value.casefold()):
        match = find_collaborator_by_assignee(collaborators, assignee_name)
        rows.append(
            {
                "assignee_name": assignee_name,
                "task_count": counts[assignee_name],
                "mapped_collaborator_id": match.id if match else None,
                "mapped_collaborator_name": match.name if match else None,
                "ignored_by_rule": normalize_name(assignee_name) in ignored_keys,
            }
        )
    return rows


def fetch_and_map_period(
    service,
    *,
    year: int,
    month: int,
) -> tuple[list[NormalizedActivity], list[SyncIgnoredItem], int, dict]:
    mapping = service.discover_field_mapping()
    task_ids = service.query_task_ids(year, month)
    raw_items = service.fetch_work_items(task_ids)
    mapped, mapper_ignored = map_work_items(
        raw_items,
        work_date_field=mapping["work_date_field"] or "",
        activity_field=mapping.get("activity_field"),
        completed_hours_field=mapping.get("completed_hours_field")
        or "Microsoft.VSTS.Scheduling.CompletedWork",
    )
    return mapped, mapper_ignored, len(task_ids), mapping
