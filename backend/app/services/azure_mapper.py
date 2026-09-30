from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.analysis.engine import q
from app.services.activity_normalization import NormalizedActivity
from app.services.azure_devops_errors import AzureDevOpsError
from app.services.csv_parser import extract_assignee_name


@dataclass
class SyncIgnoredItem:
    task_id: str | None
    title: str | None
    reason: str


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


def _task_preview(fields: dict[str, Any]) -> tuple[str | None, str | None]:
    task_id_raw = _field_value(fields, "System.Id")
    title_raw = _field_value(fields, "System.Title")
    task_id = str(task_id_raw) if task_id_raw is not None else None
    title = str(title_raw).strip() if title_raw is not None else None
    return task_id, title


def _resolve_completed_hours(
    fields: dict[str, Any],
    completed_hours_field: str,
) -> Decimal | None:
    fallbacks = (
        completed_hours_field,
        "Custom.Horasexecutadas",
        "Microsoft.VSTS.Scheduling.CompletedWork",
    )
    seen: set[str] = set()
    for field_name in fallbacks:
        if not field_name or field_name in seen:
            continue
        seen.add(field_name)
        parsed = _parse_azure_hours(_field_value(fields, field_name))
        if parsed is not None:
            return parsed
    return None


def _resolve_estimated_hours(fields: dict[str, Any]) -> Decimal | None:
    fallbacks = (
        "Custom.Horasestimada",
        "Microsoft.VSTS.Scheduling.OriginalEstimate",
    )
    for field_name in fallbacks:
        parsed = _parse_azure_hours(_field_value(fields, field_name))
        if parsed is not None:
            return parsed
    return None


def _resolve_activity_category(
    fields: dict[str, Any],
    activity_field: str | None,
) -> str | None:
    candidates: list[str] = []
    if activity_field:
        candidates.append(activity_field)
    if "Custom.Atividade" not in candidates:
        candidates.append("Custom.Atividade")
    for field_name in candidates:
        raw_category = _field_value(fields, field_name)
        if raw_category is not None and str(raw_category).strip():
            return str(raw_category).strip()
    return None


def map_work_item(
    item: dict[str, Any],
    *,
    work_date_field: str,
    activity_field: str | None,
    completed_hours_field: str = "Microsoft.VSTS.Scheduling.CompletedWork",
) -> tuple[NormalizedActivity | None, str | None]:
    fields = item.get("fields") or {}
    task_id_raw = _field_value(fields, "System.Id")
    title_raw = _field_value(fields, "System.Title")
    if task_id_raw is None or title_raw is None:
        return None, "Task sem ID ou título no Azure."

    work_date = _parse_azure_date(_field_value(fields, work_date_field))
    if work_date is None:
        return None, "Data de referência ausente ou inválida."

    azure_assignee, assignee_name = _format_assignee(_field_value(fields, "System.AssignedTo"))
    if not assignee_name:
        return None, "Responsável (Assigned To) ausente ou inválido."

    activity_category = _resolve_activity_category(fields, activity_field)

    activity = NormalizedActivity(
        task_id=str(task_id_raw),
        title=str(title_raw).strip(),
        azure_assignee=azure_assignee,
        assignee_name=assignee_name,
        work_date=work_date,
        work_item_type=str(_field_value(fields, "System.WorkItemType") or "").strip() or None,
        completed_hours=_resolve_completed_hours(fields, completed_hours_field),
        estimated_hours=_resolve_estimated_hours(fields),
        state=str(_field_value(fields, "System.State") or "").strip() or None,
        project=str(_field_value(fields, "System.AreaPath") or _field_value(fields, "System.TeamProject") or "").strip()
        or None,
        activity_category=activity_category,
        source="azure_api",
    )
    return activity, None


def map_work_items(
    items: list[dict[str, Any]],
    *,
    work_date_field: str,
    activity_field: str | None,
    completed_hours_field: str = "Microsoft.VSTS.Scheduling.CompletedWork",
) -> tuple[list[NormalizedActivity], list[SyncIgnoredItem]]:
    mapped: list[NormalizedActivity] = []
    ignored: list[SyncIgnoredItem] = []
    for item in items:
        fields = item.get("fields") or {}
        task_id, title = _task_preview(fields)
        try:
            normalized, reason = map_work_item(
                item,
                work_date_field=work_date_field,
                activity_field=activity_field,
                completed_hours_field=completed_hours_field,
            )
        except AzureDevOpsError as exc:
            ignored.append(SyncIgnoredItem(task_id=task_id, title=title, reason=str(exc)))
            continue
        if normalized is None:
            ignored.append(
                SyncIgnoredItem(
                    task_id=task_id,
                    title=title,
                    reason=reason or "Dados incompletos ou inválidos.",
                )
            )
            continue
        mapped.append(normalized)
    return mapped, ignored
