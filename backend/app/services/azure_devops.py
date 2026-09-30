from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.services.azure_devops_errors import (
    AzureDevOpsAuthError,
    AzureDevOpsConfigError,
    AzureDevOpsConnectionError,
    AzureDevOpsError,
)

logger = logging.getLogger(__name__)

API_VERSION = "7.1"
BATCH_SIZE = 200

SYSTEM_FIELDS = [
    "System.Id",
    "System.Title",
    "System.AssignedTo",
    "System.State",
    "System.WorkItemType",
    "System.TeamProject",
    "System.AreaPath",
    "Microsoft.VSTS.Scheduling.CompletedWork",
    "Microsoft.VSTS.Scheduling.OriginalEstimate",
]

WORK_DATE_NAME_PATTERNS = (
    re.compile(r"data\s*refer[eê]ncia", re.IGNORECASE),
    re.compile(r"data\s*de\s*refer[eê]ncia", re.IGNORECASE),
)
ACTIVITY_NAME_PATTERNS = (
    re.compile(r"^atividade$", re.IGNORECASE),
    re.compile(r"^activity$", re.IGNORECASE),
    re.compile(r"categoria\s*de\s*atividade", re.IGNORECASE),
)
COMPLETED_HOURS_PATTERNS = (
    re.compile(r"horas\s*executadas", re.IGNORECASE),
    re.compile(r"^completed\s*work$", re.IGNORECASE),
)

TJMT_EXTRA_WORK_ITEM_FIELDS = (
    "Custom.Atividade",
    "Custom.Horasexecutadas",
    "Custom.Horasestimada",
)


def normalize_project_names(
    projects: list[str] | None = None,
    project: str | None = None,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for source in projects or []:
        label = source.strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(label)
    if not names and project and project.strip():
        names.append(project.strip())
    return names


class AzureDevOpsService:
    def __init__(
        self,
        *,
        base_url: str,
        organization: str,
        pat: str,
        work_date_field: str = "",
        activity_field: str = "",
        completed_hours_field: str = "",
        project: str | None = None,
        projects: list[str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.organization = organization.strip()
        self.pat = pat
        self.work_date_field = work_date_field.strip()
        self.activity_field = activity_field.strip()
        self.completed_hours_field = completed_hours_field.strip()
        self.projects = normalize_project_names(projects, project)
        if not self.projects:
            raise AzureDevOpsConfigError("Informe ao menos um projeto do Azure DevOps.")
        self.project = self.projects[0]
        self._resolved_work_date_field: str | None = None
        self._resolved_activity_field: str | None = None
        self._resolved_completed_hours_field: str | None = None
        self._field_catalog: list[dict[str, Any]] | None = None

    @classmethod
    def from_settings(cls) -> AzureDevOpsService:
        if not settings.azure_devops_url.strip():
            raise AzureDevOpsConfigError("Azure DevOps não configurado.")
        if not settings.azure_devops_organization.strip():
            raise AzureDevOpsConfigError("Azure DevOps não configurado.")
        if not settings.azure_devops_project.strip():
            raise AzureDevOpsConfigError("Azure DevOps não configurado.")
        if not settings.azure_devops_pat.strip():
            raise AzureDevOpsConfigError("Azure DevOps não configurado.")
        env_projects = [
            item.strip()
            for item in settings.azure_devops_project.split(",")
            if item.strip()
        ]
        return cls(
            base_url=settings.azure_devops_url,
            organization=settings.azure_devops_organization,
            pat=settings.azure_devops_pat,
            projects=env_projects,
            work_date_field=settings.azure_devops_field_work_date,
            activity_field=settings.azure_devops_field_activity,
        )

    @property
    def org_base(self) -> str:
        return f"{self.base_url}/{quote(self.organization)}"

    def project_base(self, project: str | None = None) -> str:
        label = (project or self.project).strip()
        return f"{self.org_base}/{quote(label)}"

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _auth(self) -> tuple[str, str]:
        return ("", self.pat)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(),
                    auth=self._auth(),
                    **kwargs,
                )
        except httpx.RequestError as exc:
            logger.warning("Azure DevOps request failed: %s", type(exc).__name__)
            raise AzureDevOpsConnectionError("Não foi possível conectar ao Azure DevOps.") from exc

        if response.status_code in {401, 403}:
            raise AzureDevOpsAuthError("Não foi possível autenticar no Azure DevOps.")
        if response.status_code == 404:
            raise AzureDevOpsConnectionError("Projeto ou recurso não encontrado no Azure DevOps.")
        if response.status_code >= 500:
            raise AzureDevOpsConnectionError("Azure DevOps indisponível no momento.")
        if response.status_code >= 400:
            raise AzureDevOpsConnectionError("Não foi possível conectar ao Azure DevOps.")

        try:
            return response.json()
        except ValueError as exc:
            raise AzureDevOpsConnectionError("Resposta inválida do Azure DevOps.") from exc

    def list_team_projects(self) -> list[str]:
        url = f"{self.org_base}/_apis/projects?api-version={API_VERSION}&$top=200&stateFilter=WellFormed"
        payload = self._request("GET", url)
        names: list[str] = []
        for item in payload.get("value") or []:
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
        return sorted(names, key=str.casefold)

    def test_connection(self) -> None:
        for project in self.projects:
            project_url = f"{self.org_base}/_apis/projects/{quote(project)}?api-version={API_VERSION}"
            self._request("GET", project_url)
        wiql = {
            "query": (
                f"SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.TeamProject] = '{self._escape_wiql(self.project)}' "
                f"AND [System.WorkItemType] = 'Task'"
            )
        }
        wiql_url = f"{self.project_base(self.project)}/_apis/wit/wiql?api-version={API_VERSION}"
        self._request("POST", wiql_url, json=wiql)
        self._load_field_catalog()

    def _escape_wiql(self, value: str) -> str:
        return value.replace("'", "''")

    def _load_field_catalog(self) -> list[dict[str, Any]]:
        if self._field_catalog is not None:
            return self._field_catalog
        url = f"{self.org_base}/_apis/wit/fields?api-version={API_VERSION}"
        payload = self._request("GET", url)
        self._field_catalog = payload.get("value", [])
        return self._field_catalog

    def _match_field(
        self,
        patterns: tuple[re.Pattern[str], ...],
        *,
        prefer_custom: bool = False,
    ) -> str | None:
        matches: list[str] = []
        for field in self._load_field_catalog():
            name = str(field.get("name") or "")
            reference = str(field.get("referenceName") or "")
            if not reference:
                continue
            for pattern in patterns:
                if pattern.search(name) or pattern.search(reference):
                    matches.append(reference)
                    break
        if not matches:
            return None
        if prefer_custom:
            for reference in matches:
                if reference.startswith("Custom."):
                    return reference
        return matches[0]

    def resolve_work_date_field(self) -> str:
        if self._resolved_work_date_field:
            return self._resolved_work_date_field
        if self.work_date_field:
            self._resolved_work_date_field = self.work_date_field
            return self._resolved_work_date_field
        discovered = self._match_field(WORK_DATE_NAME_PATTERNS)
        if not discovered:
            raise AzureDevOpsError(
                "Campo 'Data referência' não encontrado. Configure AZURE_DEVOPS_FIELD_WORK_DATE."
            )
        self._resolved_work_date_field = discovered
        return self._resolved_work_date_field

    def resolve_activity_field(self) -> str | None:
        if self._resolved_activity_field is not None:
            return self._resolved_activity_field or None
        discovered: str | None = None
        try:
            discovered = self._match_field(ACTIVITY_NAME_PATTERNS, prefer_custom=True)
        except AzureDevOpsError:
            discovered = None
        configured = self.activity_field
        if configured.startswith("Custom."):
            self._resolved_activity_field = configured
            return configured
        if discovered:
            self._resolved_activity_field = discovered
            return discovered
        if configured:
            self._resolved_activity_field = configured
            return configured
        self._resolved_activity_field = ""
        return None

    def resolve_completed_hours_field(self) -> str:
        if self._resolved_completed_hours_field:
            return self._resolved_completed_hours_field
        discovered: str | None = None
        try:
            discovered = self._match_field(COMPLETED_HOURS_PATTERNS, prefer_custom=True)
        except AzureDevOpsError:
            pass
        configured = self.completed_hours_field
        if configured.startswith("Custom."):
            self._resolved_completed_hours_field = configured
            return configured
        if discovered:
            self._resolved_completed_hours_field = discovered
            return discovered
        if configured:
            self._resolved_completed_hours_field = configured
            return configured
        self._resolved_completed_hours_field = (
            discovered or "Microsoft.VSTS.Scheduling.CompletedWork"
        )
        return self._resolved_completed_hours_field

    def discover_field_mapping(self) -> dict[str, str | None]:
        work_date = self.resolve_work_date_field()
        activity = self.resolve_activity_field()
        return {
            "work_date_field": work_date,
            "activity_field": activity,
            "completed_hours_field": self.resolve_completed_hours_field(),
            "task_id_field": "System.Id",
            "title_field": "System.Title",
            "assignee_field": "System.AssignedTo",
            "state_field": "System.State",
            "work_item_type_field": "System.WorkItemType",
        }

    def probe_field_names(self) -> dict[str, list[str]]:
        catalog = self._load_field_catalog()
        custom = [
            str(item.get("referenceName"))
            for item in catalog
            if str(item.get("referenceName", "")).startswith("Custom.")
        ]
        selected = self.discover_field_mapping()
        return {
            "custom_field_references": custom[:100],
            "selected_mapping": selected,
        }

    def _query_task_ids_for_project(self, project: str, year: int, month: int) -> list[int]:
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        work_date_field = self.resolve_work_date_field()
        wiql = {
            "query": (
                f"SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.TeamProject] = '{self._escape_wiql(project)}' "
                f"AND [System.WorkItemType] = 'Task' "
                f"AND [{work_date_field}] >= '{start.isoformat()}' "
                f"AND [{work_date_field}] <= '{end.isoformat()}'"
            )
        }
        wiql_url = f"{self.project_base(project)}/_apis/wit/wiql?api-version={API_VERSION}"
        payload = self._request("POST", wiql_url, json=wiql)
        ids: list[int] = []
        for item in payload.get("workItems") or []:
            try:
                ids.append(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return ids

    def query_task_ids(self, year: int, month: int) -> list[int]:
        seen: set[int] = set()
        ordered: list[int] = []
        for project in self.projects:
            for task_id in self._query_task_ids_for_project(project, year, month):
                if task_id in seen:
                    continue
                seen.add(task_id)
                ordered.append(task_id)
        return ordered

    def fetch_work_items(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        work_date_field = self.resolve_work_date_field()
        activity_field = self.resolve_activity_field()
        completed_hours_field = self.resolve_completed_hours_field()
        fields = list(SYSTEM_FIELDS)
        if work_date_field not in fields:
            fields.append(work_date_field)
        if activity_field and activity_field not in fields:
            fields.append(activity_field)
        if completed_hours_field not in fields:
            fields.append(completed_hours_field)
        for extra in TJMT_EXTRA_WORK_ITEM_FIELDS:
            if extra not in fields:
                fields.append(extra)

        items: list[dict[str, Any]] = []
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start : start + BATCH_SIZE]
            ids_param = ",".join(str(item) for item in chunk)
            fields_param = ",".join(fields)
            url = (
                f"{self.org_base}/_apis/wit/workitems"
                f"?ids={ids_param}&fields={quote(fields_param, safe=',')}"
                f"&api-version={API_VERSION}"
            )
            payload = self._request("GET", url)
            items.extend(payload.get("value") or [])
        return items
