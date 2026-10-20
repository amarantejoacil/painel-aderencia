from __future__ import annotations

from dataclasses import dataclass

from app.services.azure_devops import AzureDevOpsService
from app.services.azure_devops_config import resolve_projects


@dataclass(frozen=True)
class ProjectScope:
    key: str
    label: str
    team_project: str
    area_path: str | None


def _scope_key(team_project: str, area_path: str | None) -> str:
    return f"{team_project}::{area_path or '*'}"


def list_project_scopes(service: AzureDevOpsService, configured_projects: list[str]) -> list[ProjectScope]:
    scopes: list[ProjectScope] = []
    for team_project in configured_projects:
        scopes.append(
            ProjectScope(
                key=_scope_key(team_project, None),
                label=team_project,
                team_project=team_project,
                area_path=None,
            )
        )
        if team_project.casefold() == "hannah":
            continue
        areas = _list_area_paths(service, team_project)
        for area in areas:
            if area == team_project:
                continue
            leaf = area.split("\\")[-1]
            scopes.append(
                ProjectScope(
                    key=_scope_key(team_project, area),
                    label=leaf,
                    team_project=team_project,
                    area_path=area,
                )
            )
    return scopes


def _list_area_paths(service: AzureDevOpsService, team_project: str) -> list[str]:
    from urllib.parse import quote

    from app.services.azure_devops import API_VERSION

    url = (
        f"{service.project_base(team_project)}/_apis/wit/classificationnodes/Areas"
        f"?$depth=3&api-version={API_VERSION}"
    )
    payload = service._request("GET", url)
    paths: list[str] = []

    def walk(node: dict, prefix: str = "") -> None:
        name = str(node.get("name") or "")
        path = f"{prefix}\\{name}" if prefix else name
        paths.append(path)
        for child in node.get("children") or []:
            walk(child, path)

    walk(payload)
    return paths


def resolve_scope(
    scopes: list[ProjectScope],
    *,
    team_project: str | None,
    area_path: str | None,
    scope_key: str | None,
) -> ProjectScope | None:
    if scope_key:
        for item in scopes:
            if item.key == scope_key:
                return item
    if team_project:
        for item in scopes:
            if item.team_project == team_project and item.area_path == area_path:
                return item
        for item in scopes:
            if item.team_project == team_project and area_path is None and item.area_path is None:
                return item
    return None


def configured_team_projects(db) -> list[str]:
    from app.services.azure_devops_config import get_settings_row

    row = get_settings_row(db)
    return resolve_projects(row)
