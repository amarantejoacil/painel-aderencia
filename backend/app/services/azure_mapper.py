from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.analysis.engine import q
from app.services.activity_normalization import NormalizedActivity
from app.services.azure_devops_errors import AzureDevOpsError
from app.services.csv_parser import extract_assignee_name


def _parse_azure_date(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.date()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_azure_hours(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return q(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_assignee(raw: Any) -> tuple[str, str]:
    if raw is None:
        return ("", "")
    if isinstance(raw, dict):
        display = str(raw.get("displayName") or "").strip()
        unique = str(raw.get("uniqueName") or "").strip()
        if display and unique:
            azure_assignee = f"{display} <{unique}>"
        else:
            azure_assignee = display or unique
        return azure_assignee, extract_assignee_name(azure_assignee)
    text = str(raw).strip()
    return text, extract_assignee_name(text)


def _field_value(fields: dict[str, Any], name: str) -> Any:
    return fields.get(name)


def map_work_item(
    item: dict[str, Any],
    *,
    work_date_field: str,
    activity_field: str | None,
) -> NormalizedActivity | None:
    fields = item.get("fields") or {}
    task_id_raw = _field_value(fields, "System.Id")
    title_raw = _field_value(fields, "System.Title")
    if task_id_raw is None or title_raw is None:
        return None

    work_date = _parse_azure_date(_field_value(fields, work_date_field))
    if work_date is None:
        return None

    azure_assignee, assignee_name = _format_assignee(_field_value(fields, "System.AssignedTo"))
    if not assignee_name:
        return None

    activity_category = None
    if activity_field:
        raw_category = _field_value(fields, activity_field)
        if raw_category is not None and str(raw_category).strip():
            activity_category = str(raw_category).strip()

    return NormalizedActivity(
        task_id=str(task_id_raw),
        title=str(title_raw).strip(),
        azure_assignee=azure_assignee,
        assignee_name=assignee_name,
        work_date=work_date,
        work_item_type=str(_field_value(fields, "System.WorkItemType") or "").strip() or None,
        completed_hours=_parse_azure_hours(_field_value(fields, "Microsoft.VSTS.Scheduling.CompletedWork")),
        estimated_hours=_parse_azure_hours(_field_value(fields, "Microsoft.VSTS.Scheduling.OriginalEstimate")),
        state=str(_field_value(fields, "System.State") or "").strip() or None,
        project=str(_field_value(fields, "System.AreaPath") or _field_value(fields, "System.TeamProject") or "").strip()
        or None,
        activity_category=activity_category,
        source="azure_api",
    )


def map_work_items(
    items: list[dict[str, Any]],
    *,
    work_date_field: str,
    activity_field: str | None,
) -> tuple[list[NormalizedActivity], int]:
    mapped: list[NormalizedActivity] = []
    skipped = 0
    for item in items:
        try:
            normalized = map_work_item(
                item,
                work_date_field=work_date_field,
                activity_field=activity_field,
            )
        except AzureDevOpsError:
            skipped += 1
            continue
        if normalized is None:
            skipped += 1
            continue
        mapped.append(normalized)
    return mapped, skipped
