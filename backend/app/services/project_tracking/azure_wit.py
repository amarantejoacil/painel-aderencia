from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.services.azure_devops import AzureDevOpsService, API_VERSION

STORY_WIQL_TYPE = "User Story"
STORY_FIELDS = [
    "System.Id",
    "System.Title",
    "System.State",
    "System.WorkItemType",
    "System.AssignedTo",
    "System.CreatedDate",
    "System.ChangedDate",
    "System.AreaPath",
    "System.IterationPath",
    "System.Parent",
    "System.Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "Microsoft.VSTS.Common.ClosedDate",
    "Microsoft.VSTS.Common.StateChangeDate",
    "Custom.TemouTeveimpedimentoUS",
    "System.CommentCount",
]


@dataclass(frozen=True)
class DatedIteration:
    team_project: str
    path: str
    name: str
    start: str | None
    finish: str | None


def _escape_wiql(value: str) -> str:
    return value.replace("'", "''")


def list_dated_iterations(service: AzureDevOpsService, team_project: str) -> list[DatedIteration]:
    project = team_project.strip()
    url = (
        f"{service.project_base(project)}/_apis/wit/classificationnodes/Iterations"
        f"?$depth=10&api-version={API_VERSION}"
    )
    payload = service._request("GET", url)
    flat: list[DatedIteration] = []

    def walk(node: dict, prefix: str = "") -> None:
        name = str(node.get("name") or "")
        path = f"{prefix}\\{name}" if prefix else name
        attrs = node.get("attributes") or {}
        start = attrs.get("startDate")
        finish = attrs.get("finishDate")
        if start or finish:
            flat.append(
                DatedIteration(
                    team_project=project,
                    path=path,
                    name=name,
                    start=start,
                    finish=finish,
                )
            )
        for child in node.get("children") or []:
            walk(child, path)

    walk(payload)
    return flat


def wiql_story_ids(
    service: AzureDevOpsService,
    team_project: str,
    *,
    iteration_path: str | None = None,
    area_path: str | None = None,
) -> list[int]:
    project = _escape_wiql(team_project.strip())
    clauses = [
        f"[System.TeamProject] = '{project}'",
        f"[System.WorkItemType] = '{STORY_WIQL_TYPE}'",
    ]
    if iteration_path:
        escaped = _escape_wiql(iteration_path)
        clauses.append(f"[System.IterationPath] UNDER '{escaped}'")
    if area_path:
        escaped = _escape_wiql(area_path)
        clauses.append(f"[System.AreaPath] UNDER '{escaped}'")
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE {' AND '.join(clauses)}"}
    url = f"{service.project_base(team_project)}/_apis/wit/wiql?api-version={API_VERSION}"
    payload = service._request("POST", url, json=wiql)
    ids: list[int] = []
    for item in payload.get("workItems") or []:
        try:
            ids.append(int(item["id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ids


def fetch_work_items(
    service: AzureDevOpsService,
    ids: list[int],
    *,
    fields: list[str] | None = None,
    expand_relations: bool = False,
) -> list[dict[str, Any]]:
    if not ids:
        return []
    field_list = fields or STORY_FIELDS
    items: list[dict[str, Any]] = []
    batch = 200
    for start in range(0, len(ids), batch):
        chunk = ids[start : start + batch]
        ids_param = ",".join(str(item) for item in chunk)
        fields_param = ",".join(field_list)
        expand_part = "&$expand=Relations" if expand_relations else ""
        url = (
            f"{service.org_base}/_apis/wit/workitems"
            f"?ids={ids_param}&fields={quote(fields_param, safe=',')}"
            f"{expand_part}&api-version={API_VERSION}"
        )
        payload = service._request("GET", url)
        items.extend(payload.get("value") or [])
    return items


def fetch_revisions(service: AzureDevOpsService, work_item_id: int) -> list[dict[str, Any]]:
    url = f"{service.org_base}/_apis/wit/workitems/{work_item_id}/revisions?api-version={API_VERSION}"
    payload = service._request("GET", url)
    return payload.get("value") or []


def fetch_comments(service: AzureDevOpsService, work_item_id: int, *, top: int = 15) -> list[dict[str, Any]]:
    from app.services.azure_devops_errors import AzureDevOpsConnectionError, AzureDevOpsError

    url = (
        f"{service.org_base}/_apis/wit/workItems/{work_item_id}/comments"
        f"?$top={top}&order=desc&api-version=7.1-preview.4"
    )
    try:
        payload = service._request("GET", url)
    except AzureDevOpsConnectionError:
        return []
    except AzureDevOpsError:
        return []
    return payload.get("comments") or []


def wiql_child_work_item_ids(
    service: AzureDevOpsService,
    team_project: str,
    parent_ids: list[int],
    *,
    work_item_types: tuple[str, ...] = ("Task", "Bug"),
) -> list[int]:
    if not parent_ids:
        return []
    project = _escape_wiql(team_project.strip())
    type_list = ", ".join(f"'{_escape_wiql(item)}'" for item in work_item_types)
    matched: list[int] = []
    chunk_size = 40
    for start in range(0, len(parent_ids), chunk_size):
        chunk = parent_ids[start : start + chunk_size]
        parents = ", ".join(str(item) for item in chunk)
        wiql = {
            "query": (
                f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project}' "
                f"AND [System.WorkItemType] IN ({type_list}) "
                f"AND [System.Parent] IN ({parents})"
            )
        }
        url = f"{service.project_base(team_project)}/_apis/wit/wiql?api-version={API_VERSION}"
        payload = service._request("POST", url, json=wiql)
        for item in payload.get("workItems") or []:
            try:
                matched.append(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                continue
    return matched


def work_item_web_url(service: AzureDevOpsService, team_project: str, work_item_id: int) -> str:
    return (
        f"{service.base_url}/{quote(service.organization)}/"
        f"{quote(team_project)}/_workitems/edit/{work_item_id}"
    )
