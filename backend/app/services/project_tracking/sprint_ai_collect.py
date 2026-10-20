from __future__ import annotations

import re
from typing import Any

from app.services.azure_devops import AzureDevOpsService
from app.services.azure_devops_errors import AzureDevOpsError
from app.services.project_tracking.azure_wit import (
    STORY_FIELDS,
    fetch_comments,
    fetch_revisions,
    fetch_work_items,
    wiql_child_work_item_ids,
    wiql_story_ids,
    work_item_web_url,
)
from app.services.project_tracking.catalog import ProjectScope
from app.services.project_tracking.revisions import _assignee_display
from app.services.project_tracking.sprint_analytics import decode_sprint_key, sprint_row_from_iteration

MAX_STORIES = 40
MAX_TASKS = 12
MAX_COMMENTS = 8
TEXT_LIMIT = 500

AI_FIELDS = [
    *STORY_FIELDS,
    "System.Tags",
]


def _plain(value: str | None, limit: int = TEXT_LIMIT) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(";") if part.strip()]


def _comments(service: AzureDevOpsService, work_item_id: int, limitations: list[str]) -> list[dict]:
    try:
        raw = fetch_comments(service, work_item_id, top=MAX_COMMENTS)
    except AzureDevOpsError:
        limitations.append(f"Comentários do item {work_item_id} indisponíveis.")
        return []
    rows: list[dict] = []
    for item in raw[:MAX_COMMENTS]:
        author = item.get("createdBy") or {}
        name = author.get("displayName") if isinstance(author, dict) else None
        rows.append(
            {
                "author": name,
                "text": _plain(item.get("text"), 280),
                "created_at": item.get("createdDate"),
            }
        )
    return [row for row in rows if row["text"]]


def _revisions(service: AzureDevOpsService, work_item_id: int, limitations: list[str]) -> list[dict]:
    try:
        raw = fetch_revisions(service, work_item_id)
    except AzureDevOpsError:
        limitations.append(f"História {work_item_id} sem revisões disponíveis.")
        return []
    rows: list[dict] = []
    for item in raw:
        fields = item.get("fields") or {}
        rows.append(
            {
                "revision": int(item.get("rev") or 0),
                "changed_at": fields.get("System.ChangedDate"),
                "state": str(fields.get("System.State") or "").strip() or None,
                "iteration_path": str(fields.get("System.IterationPath") or "").strip() or None,
                "area_path": str(fields.get("System.AreaPath") or "").strip() or None,
                "assignee": _assignee_display(fields.get("System.AssignedTo")),
            }
        )
    if not rows:
        limitations.append(f"História {work_item_id} sem revisões disponíveis.")
    return rows


def _feature_index(
    service: AzureDevOpsService,
    stories: list[dict],
    limitations: list[str],
) -> dict[int, dict]:
    pending: dict[int, int] = {}
    for story in stories:
        parent = story.get("parent_id")
        if isinstance(parent, int):
            pending[int(story["work_item_id"])] = parent
    resolved: dict[int, dict] = {}
    depth = 0
    while pending and depth < 4:
        depth += 1
        ids = sorted(set(pending.values()))
        try:
            items = fetch_work_items(
                service,
                ids,
                fields=["System.Id", "System.Title", "System.WorkItemType", "System.Parent"],
            )
        except AzureDevOpsError:
            limitations.append("Não foi possível ler Features/Epics relacionadas.")
            break
        by_id = {int(item["id"]): item for item in items if item.get("id") is not None}
        next_pending: dict[int, int] = {}
        for story_id, parent_id in pending.items():
            parent = by_id.get(parent_id)
            if not parent:
                continue
            fields = parent.get("fields") or {}
            kind = str(fields.get("System.WorkItemType") or "")
            if kind in {"Feature", "Epic"}:
                resolved[story_id] = {
                    "work_item_id": parent_id,
                    "title": fields.get("System.Title"),
                    "work_item_type": kind,
                }
                continue
            grand = fields.get("System.Parent")
            if isinstance(grand, int):
                next_pending[story_id] = grand
            elif str(grand).isdigit():
                next_pending[story_id] = int(grand)
        pending = next_pending
    return resolved


def _story_payload(
    service: AzureDevOpsService,
    team_project: str,
    item: dict,
    limitations: list[str],
) -> dict:
    fields = item.get("fields") or {}
    work_item_id = int(item["id"])
    parent = fields.get("System.Parent")
    parent_id = int(parent) if str(parent or "").isdigit() else None
    return {
        "work_item_id": work_item_id,
        "title": fields.get("System.Title"),
        "description": _plain(fields.get("System.Description")),
        "acceptance": _plain(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")),
        "state_current": fields.get("System.State"),
        "assignee_current": _assignee_display(fields.get("System.AssignedTo")),
        "created_at": fields.get("System.CreatedDate"),
        "tags": _tags(fields.get("System.Tags")),
        "area_path": fields.get("System.AreaPath"),
        "iteration_current": fields.get("System.IterationPath"),
        "parent_id": parent_id,
        "impediment_field": str(fields.get("Custom.TemouTeveimpedimentoUS") or "").strip() or None,
        "azure_url": work_item_web_url(service, team_project, work_item_id),
        "comments": _comments(service, work_item_id, limitations),
        "revisions": _revisions(service, work_item_id, limitations),
        "tasks": [],
    }


def _attach_tasks(
    service: AzureDevOpsService,
    team_project: str,
    stories: list[dict],
    limitations: list[str],
) -> None:
    if not stories:
        return
    parent_ids = [int(story["work_item_id"]) for story in stories]
    try:
        child_ids = wiql_child_work_item_ids(service, team_project, parent_ids)
    except AzureDevOpsError:
        limitations.append("Não foi possível ler as Tasks vinculadas às histórias.")
        return
    if not child_ids:
        return
    try:
        items = fetch_work_items(
            service,
            child_ids,
            fields=["System.Id", "System.Title", "System.State", "System.WorkItemType", "System.AssignedTo", "System.Description", "System.Parent"],
        )
    except AzureDevOpsError:
        limitations.append("Não foi possível ler o detalhe das Tasks vinculadas.")
        return
    tasks_by_parent: dict[int, list[dict]] = {parent: [] for parent in parent_ids}
    for item in items:
        if item.get("id") is None:
            continue
        fields = item.get("fields") or {}
        if str(fields.get("System.WorkItemType") or "") not in {"Task", "Bug"}:
            continue
        parent_raw = fields.get("System.Parent")
        if not str(parent_raw or "").isdigit():
            continue
        parent_id = int(parent_raw)
        if parent_id not in tasks_by_parent:
            continue
        task_id = int(item["id"])
        tasks_by_parent[parent_id].append(
            {
                "work_item_id": task_id,
                "title": fields.get("System.Title"),
                "state": fields.get("System.State"),
                "assignee": _assignee_display(fields.get("System.AssignedTo")),
                "description": _plain(fields.get("System.Description"), 280),
                "azure_url": work_item_web_url(service, team_project, task_id),
                "comments": _comments(service, task_id, limitations),
            }
        )
    for story in stories:
        parent_id = int(story["work_item_id"])
        tasks = tasks_by_parent.get(parent_id, [])
        if len(tasks) > MAX_TASKS:
            limitations.append(
                f"História {parent_id} tem mais de {MAX_TASKS} Tasks; a análise usa as primeiras."
            )
        story["tasks"] = tasks[:MAX_TASKS]


def collect_sprint(
    service: AzureDevOpsService,
    sprint_key: str,
    scope: ProjectScope,
) -> tuple[dict, list[str]]:
    from app.services.project_tracking.azure_wit import list_dated_iterations

    team_project, path = decode_sprint_key(sprint_key)
    if team_project != scope.team_project:
        raise ValueError("A Sprint não pertence ao projeto do escopo selecionado.")
    sprint = None
    for candidate in list_dated_iterations(service, team_project):
        if candidate.path == path:
            sprint = candidate
            break
    if sprint is None:
        raise ValueError("Sprint não encontrada no Azure DevOps.")
    base = sprint_row_from_iteration(sprint)
    limitations: list[str] = []
    story_ids = wiql_story_ids(service, team_project, iteration_path=path)
    if scope.area_path:
        area_ids = set(wiql_story_ids(service, team_project, area_path=scope.area_path))
        story_ids = [item for item in story_ids if item in area_ids]
    if len(story_ids) > MAX_STORIES:
        limitations.append(
            f"Sprint {base.get('name')} tem {len(story_ids)} histórias; a análise usa as primeiras {MAX_STORIES}."
        )
        story_ids = story_ids[:MAX_STORIES]
    items = fetch_work_items(service, story_ids, fields=AI_FIELDS) if story_ids else []
    stories = [_story_payload(service, team_project, item, limitations) for item in items if item.get("id")]
    _attach_tasks(service, team_project, stories, limitations)
    features = _feature_index(service, stories, limitations)
    for story in stories:
        story["feature"] = features.get(int(story["work_item_id"]))
        story.pop("parent_id", None)
    return (
        {
            **base,
            "sprint_key": sprint_key,
            "area_label": scope.label,
            "area_path": scope.area_path,
            "stories": stories,
        },
        limitations,
    )


def collect_sprints(
    service: AzureDevOpsService,
    sprint_keys: list[str],
    scope: ProjectScope,
) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    limitations: list[str] = []
    for key in sprint_keys:
        sprint, notes = collect_sprint(service, key, scope)
        rows.append(sprint)
        limitations.extend(notes)
    rows.sort(key=lambda item: (item.get("start_date") or "", item.get("name") or ""))
    return rows, limitations
