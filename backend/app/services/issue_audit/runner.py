from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

from app.services.azure_devops_errors import AzureDevOpsAuthError, AzureDevOpsError
from app.services.issue_audit.client import COMMENT_SOURCE_LIMITATION, AzureCollectionClient, work_item_url
from app.services.issue_audit.field_refs import (
    extract_planning_fields,
    load_field_catalog_from_client,
    resolve_issue_work_item_fields,
)
from app.services.issue_audit.matching import (
    PersonTarget,
    author_key,
    candidate_from_comment,
    comment_from_update,
    display_identity,
    in_selected_year,
    name_matches,
    person_matches,
)

MAX_WORKERS = 4
DATE_FIELDS = {
    "created": "System.CreatedDate",
    "changed": "System.ChangedDate",
}


ProgressCallback = Callable[[int, int, int, int], None]


def execute_audit(
    client: AzureCollectionClient,
    *,
    project: str,
    work_item_type: str,
    period_criterion: str,
    year: int,
    comment_scope: str,
    person: PersonTarget,
    on_progress: ProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    limitations = [COMMENT_SOURCE_LIMITATION]
    client.ensure_project(project)
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    date_field = DATE_FIELDS[period_criterion]
    ids, split_notes = client.query_work_item_ids(
        project=project,
        work_item_type=work_item_type,
        date_field=date_field,
        start=start,
        end=end,
    )
    limitations.extend(split_notes)
    found = len(ids)
    if on_progress:
        on_progress(found, 0, 0, 0)

    field_resolution = resolve_issue_work_item_fields(load_field_catalog_from_client(client))
    field_mapping = field_resolution["mapping"]
    field_meta = {
        "work_item_field_refs": field_resolution["refs"],
        "work_item_field_mapping": field_resolution["mapping"],
    }
    items, item_failures = client.fetch_work_items(ids, field_refs=field_resolution["refs"])
    by_id = {}
    for item in items:
        try:
            by_id[int(item["id"])] = item
        except (KeyError, TypeError, ValueError):
            continue

    issues: list[dict[str, Any]] = []
    comments_analyzed = 0
    failure_count = 0
    failed_ids: list[int] = []
    processed = 0

    def cancelled() -> bool:
        return bool(should_cancel and should_cancel())

    pending = list(ids)
    while pending:
        if cancelled():
            return _payload(
                issues=issues,
                person=person,
                limitations=limitations + ["A consulta foi cancelada antes de terminar."],
                failed_ids=failed_ids,
                failure_count=failure_count,
                comments_analyzed=comments_analyzed,
                issues_found=found,
                status="cancelled",
                ambiguous=False,
                candidates=[],
                **field_meta,
            )
        chunk = pending[:40]
        pending = pending[40:]
        comment_map: dict[int, list[dict[str, Any]] | Exception] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(client.fetch_comment_updates, item_id): item_id for item_id in chunk}
            for future in as_completed(futures):
                item_id = futures[future]
                try:
                    comment_map[item_id] = future.result()
                except AzureDevOpsAuthError as exc:
                    return _payload(
                        issues=issues,
                        person=person,
                        limitations=limitations,
                        failed_ids=failed_ids,
                        failure_count=failure_count,
                        comments_analyzed=comments_analyzed,
                        issues_found=found,
                        status="failed",
                        ambiguous=False,
                        candidates=[],
                        error_message=str(exc),
                        **field_meta,
                    )
                except Exception as exc:  # noqa: BLE001 - falha parcial por Issue
                    comment_map[item_id] = exc

        for item_id in chunk:
            item = by_id.get(item_id)
            outcome = comment_map.get(item_id)
            if item is None:
                message = next((text for failed_id, text in item_failures if failed_id == item_id), "Work Item inacessível.")
                issues.append(_failed_issue(client, project, item_id, message))
                failed_ids.append(item_id)
                failure_count += 1
            elif isinstance(outcome, Exception):
                issues.append(
                    _issue_from_work_item(client, project, item, [], error=str(outcome), field_mapping=field_mapping)
                )
                failed_ids.append(item_id)
                failure_count += 1
            else:
                comments = [comment for update in (outcome or []) if (comment := comment_from_update(update))]
                if comment_scope == "period":
                    comments = [comment for comment in comments if in_selected_year(comment, year)]
                comments.sort(key=lambda comment: comment.get("created_at") or "")
                comments_analyzed += len(comments)
                issues.append(_issue_from_work_item(client, project, item, comments, field_mapping=field_mapping))
            processed += 1
            if on_progress:
                on_progress(found, processed, comments_analyzed, failure_count)

    ambiguous, candidates = _ambiguity(issues, person)
    resolved = person
    if not ambiguous and not person.locked and len(candidates) == 1:
        chosen = candidates[0]
        resolved = PersonTarget(
            person.display_name,
            chosen.get("id"),
            chosen.get("unique_name"),
        )
        candidates = []
    elif not ambiguous:
        candidates = []
    status = "partial" if failure_count else "complete"
    if ambiguous:
        status = "ambiguous"
    return _payload(
        issues=issues,
        person=resolved,
        limitations=limitations,
        failed_ids=failed_ids,
        failure_count=failure_count,
        comments_analyzed=comments_analyzed,
        issues_found=found,
        status=status,
        ambiguous=ambiguous,
        candidates=candidates if ambiguous else [],
        **field_meta,
    )


def apply_identity(result: dict[str, Any], person: PersonTarget) -> dict[str, Any]:
    issues = []
    matched = 0
    for issue in result.get("issues") or []:
        source = issue.get("all_comments") if issue.get("all_comments") is not None else issue.get("comments") or []
        comments = [comment for comment in source if person_matches(comment, person)]
        copied = dict(issue)
        copied["comments"] = comments
        if issue.get("all_comments") is not None:
            copied["all_comments"] = issue["all_comments"]
        copied["person_comment_count"] = len(comments)
        copied["person_commented"] = bool(comments)
        matched += len(comments)
        issues.append(copied)
    updated = dict(result)
    updated["issues"] = issues
    updated["comments_matched"] = matched
    updated["ambiguous"] = False
    updated["candidates"] = []
    updated["person"] = {
        "display_name": person.display_name,
        "identity_id": person.identity_id,
        "unique_name": person.unique_name,
    }
    if updated.get("status") == "ambiguous":
        updated["status"] = "partial" if updated.get("failure_count") else "complete"
    return updated


def _ambiguity(issues: list[dict[str, Any]], person: PersonTarget) -> tuple[bool, list[dict[str, str | None]]]:
    if person.locked:
        return False, []
    found: dict[str, dict[str, str | None]] = {}
    for issue in issues:
        for comment in issue.get("comments") or []:
            if not name_matches(comment, person):
                continue
            key = author_key(comment)
            found.setdefault(key, candidate_from_comment(comment))
    if len(found) == 1:
        return False, list(found.values())
    if len(found) > 1:
        return True, list(found.values())
    return False, []


def _issue_from_work_item(
    client: AzureCollectionClient,
    project: str,
    item: dict[str, Any],
    comments: list[dict[str, Any]],
    error: str | None = None,
    field_mapping: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    fields = item.get("fields") or {}
    work_item_id = int(item["id"])
    planning = extract_planning_fields(fields, field_mapping or {})
    return {
        "id": work_item_id,
        "title": str(fields.get("System.Title") or ""),
        "description": str(fields.get("System.Description") or ""),
        **planning,
        "work_item_type": str(fields.get("System.WorkItemType") or ""),
        "state": str(fields.get("System.State") or ""),
        "assigned_to": display_identity(fields.get("System.AssignedTo")),
        "created_at": fields.get("System.CreatedDate"),
        "changed_at": fields.get("System.ChangedDate"),
        "url": work_item_url(client.base_url, client.organization, project, work_item_id),
        "comments": comments,
        "comment_count": None if error else len(comments),
        "error": error,
    }


def _failed_issue(client: AzureCollectionClient, project: str, work_item_id: int, message: str) -> dict[str, Any]:
    return {
        "id": work_item_id,
        "title": "",
        "description": "",
        "tags": "",
        "bucket": "",
        "areas_internas": "",
        "areas_externa": "",
        "work_item_type": "",
        "state": "",
        "assigned_to": "",
        "created_at": None,
        "changed_at": None,
        "url": work_item_url(client.base_url, client.organization, project, work_item_id),
        "comments": [],
        "comment_count": None,
        "error": message,
    }


def _payload(
    *,
    issues: list[dict[str, Any]],
    person: PersonTarget,
    limitations: list[str],
    failed_ids: list[int],
    failure_count: int,
    comments_analyzed: int,
    issues_found: int,
    status: str,
    ambiguous: bool,
    candidates: list[dict[str, str | None]],
    error_message: str | None = None,
    work_item_field_refs: list[str] | None = None,
    work_item_field_mapping: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    finalized: list[dict[str, Any]] = []
    matched_total = 0
    for issue in issues:
        comments = issue.get("comments") or []
        kept = comments if ambiguous or issue.get("error") else [comment for comment in comments if person_matches(comment, person)]
        if ambiguous and not issue.get("error"):
            kept = [comment for comment in comments if name_matches(comment, person)]
        person_count = len(kept) if not issue.get("error") else 0
        matched_total += person_count
        finalized.append(
            {
                **issue,
                "all_comments": list(comments),
                "comments": kept,
                "person_comment_count": person_count,
                "person_commented": person_count > 0,
            }
        )
    with_person = sum(1 for issue in finalized if issue["person_commented"])
    return {
        "status": status,
        "issues_found": issues_found,
        "issues_processed": len(finalized),
        "comments_analyzed": comments_analyzed,
        "comments_matched": matched_total,
        "failure_count": failure_count,
        "failed_ids": failed_ids,
        "limitations": limitations,
        "ambiguous": ambiguous,
        "candidates": candidates,
        "issues_with_person": with_person,
        "issues_without_person": sum(1 for issue in finalized if not issue.get("error") and not issue["person_commented"]),
        "person": {
            "display_name": person.display_name,
            "identity_id": person.identity_id,
            "unique_name": person.unique_name,
        },
        "error_message": error_message,
        "work_item_field_refs": work_item_field_refs or [],
        "work_item_field_mapping": work_item_field_mapping or {},
        "comments_storage_version": 1,
        "issues": finalized,
    }
