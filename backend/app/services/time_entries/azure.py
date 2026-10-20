from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.services.azure_devops import API_VERSION, AzureDevOpsService
from app.services.azure_devops_errors import (
    AzureDevOpsAuthError,
    AzureDevOpsConnectionError,
    AzureDevOpsError,
)
from app.services.project_tracking.azure_wit import fetch_work_items, work_item_web_url
from app.services.time_entries.errors import TimeEntryError, TimeEntryRejected, TimeEntryTransportError
from app.services.time_entries.payload import (
    CLOSED_TASK_STATE,
    DEFAULT_ATIVIDADE,
    DEFAULT_IMPEDIMENTO,
    DEFAULT_TIPO_TAREFA,
    FIELD_ATIVIDADE,
    FIELD_HORAS_ESTIMADA,
    FIELD_HORAS_EXECUTADAS,
    FIELD_IMPEDIMENTO,
    FIELD_TIPO_TAREFA,
    build_task_document,
)

STORY_READ_FIELDS = [
    "System.Id",
    "System.Title",
    "System.State",
    "System.WorkItemType",
    "System.TeamProject",
    "System.AreaPath",
    "System.IterationPath",
]

_SECRET_PATTERN = re.compile(r"(?i)(pat|password|authorization)\s*[:=]\s*\S+")


def _identity_unique_name_resolvable(unique: str | None) -> bool:
    """Azure só resolve Assigned To com e-mail ou domínio\\conta — CPF puro falha."""
    text = (unique or "").strip()
    if not text:
        return False
    if "@" in text or "\\" in text:
        return True
    if text.isdigit():
        return False
    return False


@dataclass(frozen=True)
class AzureIdentity:
    display_name: str
    unique_name: str | None
    identity_id: str | None

    @property
    def assigned_to(self) -> str:
        if self.unique_name and _identity_unique_name_resolvable(self.unique_name):
            return f"{self.display_name} <{self.unique_name}>"
        return self.display_name


@dataclass(frozen=True)
class StoryInfo:
    id: int
    title: str
    state: str
    work_item_type: str
    project: str
    area_path: str
    iteration_path: str
    url: str


@dataclass(frozen=True)
class CreatedTask:
    id: int
    title: str
    state: str
    url: str


@dataclass(frozen=True)
class AzureTaskHit:
    id: int
    title: str
    state: str
    estimated_hours: Decimal | None
    executed_hours: Decimal | None
    url: str


def sanitize_message(value: str) -> str:
    cleaned = _SECRET_PATTERN.sub("[redigido]", value or "")
    return " ".join(cleaned.split())[:500]


def month_task_wiql(project: str, work_date_field: str, start: date, end: date) -> str:
    project_name = project.replace("'", "''")
    return (
        "SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.TeamProject] = '{project_name}' "
        "AND [System.WorkItemType] = 'Task' "
        "AND [System.State] <> 'Removed' "
        f"AND [{work_date_field}] >= '{start.isoformat()}' "
        f"AND [{work_date_field}] <= '{end.isoformat()}'"
    )


def _parse_hours(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _parse_reference_day(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


class TimeEntryAzure:
    def __init__(self, service: AzureDevOpsService) -> None:
        self._service = service

    def projects(self) -> list[str]:
        return list(self._service.projects)

    def identity(self) -> AzureIdentity:
        url = f"{self._service.org_base}/_apis/connectionData?api-version=5.0-preview"
        try:
            payload = self._service._request("GET", url)
        except AzureDevOpsAuthError as exc:
            raise TimeEntryError("Não foi possível autenticar no Azure DevOps.", status_code=401) from exc
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível identificar o usuário do PAT.") from exc
        user = payload.get("authenticatedUser") or {}
        props = user.get("properties") or {}
        account = props.get("Account")
        if isinstance(account, dict):
            account = account.get("$value")
        display = str(user.get("providerDisplayName") or user.get("customDisplayName") or "").strip()
        if not display:
            raise TimeEntryError("O Azure DevOps não informou o usuário autenticado.")
        unique = str(user.get("uniqueName") or "").strip() or None
        if not unique and account:
            unique = str(account).strip() or None
        identity_id = str(user.get("id") or "").strip() or None
        return AzureIdentity(display_name=display, unique_name=unique or None, identity_id=identity_id)

    def get_story(self, story_id: int) -> StoryInfo:
        url = f"{self._service.org_base}/_apis/wit/workitems/{int(story_id)}?api-version={API_VERSION}"
        try:
            payload = self._service._request("GET", url)
        except AzureDevOpsAuthError as exc:
            raise TimeEntryError("Não foi possível autenticar no Azure DevOps.", status_code=401) from exc
        except AzureDevOpsConnectionError as exc:
            if "não encontrado" in str(exc).casefold():
                raise TimeEntryError(f"User Story {story_id} não encontrada no Azure DevOps.", status_code=404) from exc
            raise TimeEntryTransportError("Não foi possível consultar a User Story.") from exc
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível consultar a User Story.") from exc
        return self._story_from_payload(payload, fallback_id=story_id)

    def search_stories(self, project: str, query: str) -> list[StoryInfo]:
        self._require_project(project)
        text = query.replace("'", "''")
        project_name = project.replace("'", "''")
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.TeamProject] = '{project_name}' "
                "AND [System.WorkItemType] = 'User Story' "
                f"AND [System.Title] CONTAINS '{text}' "
                "AND [System.State] <> 'Removed' "
                "ORDER BY [System.ChangedDate] DESC"
            )
        }
        url = f"{self._service.project_base(project)}/_apis/wit/wiql?$top=20&api-version={API_VERSION}"
        try:
            payload = self._service._request("POST", url, json=wiql)
        except AzureDevOpsAuthError as exc:
            raise TimeEntryError("Não foi possível autenticar no Azure DevOps.", status_code=401) from exc
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível pesquisar User Stories.") from exc
        ids: list[int] = []
        for item in payload.get("workItems") or []:
            try:
                ids.append(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                continue
        if not ids:
            return []
        try:
            raw_items = fetch_work_items(self._service, ids, fields=STORY_READ_FIELDS)
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível ler as User Stories encontradas.") from exc
        stories = [self._story_from_payload(item, fallback_id=int(item.get("id") or 0)) for item in raw_items]
        return stories[:20]

    def assert_task_defaults(self, project: str) -> None:
        self._require_project(project)
        expected = {
            FIELD_TIPO_TAREFA: DEFAULT_TIPO_TAREFA,
            FIELD_ATIVIDADE: DEFAULT_ATIVIDADE,
            FIELD_IMPEDIMENTO: DEFAULT_IMPEDIMENTO,
        }
        for reference, value in expected.items():
            allowed = self._allowed_values(project, reference)
            if allowed and value not in allowed:
                raise TimeEntryError(
                    f"O valor '{value}' não é permitido no campo {reference} do projeto {project}."
                )

    def work_date_field(self) -> str:
        try:
            return self._service.resolve_work_date_field()
        except AzureDevOpsError as exc:
            raise TimeEntryError("O campo Data referência não está configurado.") from exc

    def create_task(
        self,
        *,
        project: str,
        title: str,
        description: str,
        reference_date: date,
        estimated_hours: Decimal,
        assignee: str,
        area_path: str,
        iteration_path: str,
        parent_id: int,
    ) -> CreatedTask:
        document = build_task_document(
            title=title,
            description=description,
            reference_date=reference_date,
            estimated_hours=estimated_hours,
            assignee=assignee,
            area_path=area_path,
            iteration_path=iteration_path,
            work_date_field=self.work_date_field(),
            parent_url=f"{self._service.org_base}/_apis/wit/workItems/{int(parent_id)}",
        )
        url = f"{self._service.project_base(project)}/_apis/wit/workitems/$Task?api-version={API_VERSION}"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json-patch+json",
                    },
                    auth=self._service._auth(),
                    json=document,
                )
        except httpx.TimeoutException as exc:
            raise TimeEntryTransportError("Tempo esgotado ao criar a Task no Azure DevOps.") from exc
        except httpx.RequestError as exc:
            raise TimeEntryTransportError("Não foi possível conectar ao Azure DevOps.") from exc

        if response.status_code in {401, 403}:
            raise TimeEntryRejected("O PAT não tem permissão para criar Work Items.")
        if response.status_code >= 400:
            raise TimeEntryRejected(_azure_error_message(response))
        try:
            body = response.json()
        except ValueError as exc:
            raise TimeEntryTransportError("Resposta inválida do Azure DevOps.") from exc
        task_id = body.get("id")
        try:
            numeric_id = int(task_id)
        except (TypeError, ValueError) as exc:
            raise TimeEntryTransportError("O Azure DevOps não confirmou o identificador da Task.") from exc
        if numeric_id <= 0:
            raise TimeEntryTransportError("O Azure DevOps não confirmou o identificador da Task.")
        fields = body.get("fields") or {}
        title_value = str(fields.get("System.Title") or title)
        task_url = work_item_web_url(self._service, project, numeric_id)
        try:
            state = self._set_task_state(project, numeric_id, CLOSED_TASK_STATE)
        except TimeEntryRejected as exc:
            raise TimeEntryRejected(
                f"A Task #{numeric_id} foi criada, mas não foi possível alterar o estado para "
                f"{CLOSED_TASK_STATE}. {exc.message}"
            ) from exc
        return CreatedTask(
            id=numeric_id,
            title=title_value,
            state=state,
            url=task_url,
        )

    def _set_task_state(self, project: str, task_id: int, state: str) -> str:
        document = [{"op": "replace", "path": "/fields/System.State", "value": state}]
        url = (
            f"{self._service.project_base(project)}/_apis/wit/workitems/{int(task_id)}"
            f"?api-version={API_VERSION}"
        )
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.patch(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json-patch+json",
                    },
                    auth=self._service._auth(),
                    json=document,
                )
        except httpx.TimeoutException as exc:
            raise TimeEntryTransportError("Tempo esgotado ao atualizar o estado da Task no Azure DevOps.") from exc
        except httpx.RequestError as exc:
            raise TimeEntryTransportError("Não foi possível conectar ao Azure DevOps.") from exc

        if response.status_code in {401, 403}:
            raise TimeEntryRejected("O PAT não tem permissão para alterar Work Items.")
        if response.status_code >= 400:
            raise TimeEntryRejected(_azure_error_message(response))
        try:
            body = response.json()
        except ValueError as exc:
            raise TimeEntryTransportError("Resposta inválida do Azure DevOps.") from exc
        fields = body.get("fields") or {}
        return str(fields.get("System.State") or state)

    def tasks_between(
        self,
        *,
        project: str,
        story_id: int,
        start: date,
        end: date,
    ) -> list[tuple[date | None, AzureTaskHit]]:
        self._require_project(project)
        work_date_field = self.work_date_field()
        project_name = project.replace("'", "''")
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.TeamProject] = '{project_name}' "
                "AND [System.WorkItemType] = 'Task' "
                f"AND [System.Parent] = {int(story_id)} "
                f"AND [{work_date_field}] >= '{start.isoformat()}' "
                f"AND [{work_date_field}] <= '{end.isoformat()}'"
            )
        }
        url = f"{self._service.project_base(project)}/_apis/wit/wiql?api-version={API_VERSION}"
        try:
            payload = self._service._request("POST", url, json=wiql)
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível consultar as Tasks do Azure DevOps.") from exc
        ids: list[int] = []
        for item in payload.get("workItems") or []:
            try:
                ids.append(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                continue
        if not ids:
            return []
        fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.Parent",
            work_date_field,
            FIELD_HORAS_ESTIMADA,
            FIELD_HORAS_EXECUTADAS,
        ]
        try:
            raw_items = fetch_work_items(self._service, ids, fields=fields)
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível ler as Tasks consultadas.") from exc
        hits: list[tuple[date | None, AzureTaskHit]] = []
        for item in raw_items:
            item_fields = item.get("fields") or {}
            try:
                task_id = int(item.get("id") or item_fields.get("System.Id"))
            except (TypeError, ValueError):
                continue
            hit = AzureTaskHit(
                id=task_id,
                title=str(item_fields.get("System.Title") or "").strip(),
                state=str(item_fields.get("System.State") or "").strip(),
                estimated_hours=_parse_hours(item_fields.get(FIELD_HORAS_ESTIMADA)),
                executed_hours=_parse_hours(item_fields.get(FIELD_HORAS_EXECUTADAS)),
                url=work_item_web_url(self._service, project, task_id),
            )
            hits.append((_parse_reference_day(item_fields.get(work_date_field)), hit))
        return hits

    def raw_tasks_in_period(self, start: date, end: date) -> list[dict[str, Any]]:
        work_date_field = self.work_date_field()
        seen: set[int] = set()
        ordered: list[int] = []
        for project in self._service.projects:
            wiql = {"query": month_task_wiql(project, work_date_field, start, end)}
            url = f"{self._service.project_base(project)}/_apis/wit/wiql?api-version={API_VERSION}"
            try:
                payload = self._service._request("POST", url, json=wiql)
            except AzureDevOpsError as exc:
                raise TimeEntryTransportError(
                    "Não foi possível consultar as Tasks do mês no Azure DevOps."
                ) from exc
            for item in payload.get("workItems") or []:
                try:
                    task_id = int(item["id"])
                except (KeyError, TypeError, ValueError):
                    continue
                if task_id in seen:
                    continue
                seen.add(task_id)
                ordered.append(task_id)
        if not ordered:
            return []
        try:
            return self._service.fetch_work_items(ordered)
        except AzureDevOpsError as exc:
            raise TimeEntryTransportError("Não foi possível ler as Tasks consultadas.") from exc

    def mapping_fields(self) -> tuple[str, str | None, str]:
        return (
            self.work_date_field(),
            self._service.resolve_activity_field(),
            self._service.resolve_completed_hours_field(),
        )

    def task_url(self, project: str, task_id: int) -> str:
        return work_item_web_url(self._service, project, task_id)

    def executed_hours_on(self, day: date, names: list[str]) -> Decimal:
        from app.services.time_entries.conference import sum_executed_hours

        return sum_executed_hours(self, self.raw_tasks_in_period(day, day), names)

    def _require_project(self, project: str) -> None:
        known = {item.casefold(): item for item in self._service.projects}
        if project.casefold() not in known:
            raise TimeEntryError("O projeto informado não está na configuração do Azure DevOps.")

    def _allowed_values(self, project: str, reference: str) -> list[str]:
        url = (
            f"{self._service.project_base(project)}/_apis/wit/workitemtypes/Task/fields/{reference}"
            f"?$expand=allowedValues&api-version={API_VERSION}"
        )
        try:
            payload = self._service._request("GET", url)
        except AzureDevOpsError as exc:
            raise TimeEntryError(
                f"Não foi possível ler os valores permitidos de {reference} no projeto {project}."
            ) from exc
        values = payload.get("allowedValues") or []
        return [str(item) for item in values]

    def _story_from_payload(self, payload: dict[str, Any], *, fallback_id: int) -> StoryInfo:
        fields = payload.get("fields") or {}
        try:
            work_item_id = int(payload.get("id") or fields.get("System.Id") or fallback_id)
        except (TypeError, ValueError) as exc:
            raise TimeEntryError("Resposta inválida do Azure DevOps.") from exc
        project = str(fields.get("System.TeamProject") or "").strip()
        if not project:
            raise TimeEntryError("A User Story não informou o projeto do Azure DevOps.")
        self._require_project(project)
        return StoryInfo(
            id=work_item_id,
            title=str(fields.get("System.Title") or "").strip() or f"User Story {work_item_id}",
            state=str(fields.get("System.State") or "").strip(),
            work_item_type=str(fields.get("System.WorkItemType") or "").strip(),
            project=project,
            area_path=str(fields.get("System.AreaPath") or "").strip(),
            iteration_path=str(fields.get("System.IterationPath") or "").strip(),
            url=work_item_web_url(self._service, project, work_item_id),
        )


def _azure_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "O Azure DevOps recusou a criação da Task."
    if not isinstance(body, dict):
        return "O Azure DevOps recusou a criação da Task."
    custom = body.get("customProperties") or {}
    rules = custom.get("RuleValidationErrors") if isinstance(custom, dict) else None
    messages: list[str] = []
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and rule.get("errorMessage"):
                messages.append(str(rule["errorMessage"]))
    if not messages and body.get("message"):
        messages.append(str(body["message"]))
    if not messages:
        return "O Azure DevOps recusou a criação da Task."
    return sanitize_message(" ".join(messages))
