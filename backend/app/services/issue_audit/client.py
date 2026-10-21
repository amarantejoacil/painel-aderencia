from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.services.azure_devops_errors import (
    AzureDevOpsAuthError,
    AzureDevOpsConfigError,
    AzureDevOpsConnectionError,
    AzureDevOpsError,
)

API_VERSION = "7.1"
WIQL_PAGE_LIMIT = 20000
UPDATE_PAGE_SIZE = 200
WORK_ITEM_BATCH = 200
MAX_UPDATE_PAGES = 100

COMMENT_SOURCE_LIMITATION = (
    "Os comentários foram lidos do histórico do Work Item (campo System.History). "
    "Este Azure DevOps não publica a API de comentários. Revisões sem texto de histórico "
    "não entram na contagem, e o estado de exclusão do comentário não é informado."
)


class AuditPaginationError(AzureDevOpsError):
    pass


def _escape_wiql(value: str) -> str:
    return value.replace("'", "''")


def work_item_url(base_url: str, organization: str, project: str, work_item_id: int) -> str:
    return (
        f"{base_url.rstrip('/')}/{quote(organization.strip())}/"
        f"{quote(project.strip())}/_workitems/edit/{int(work_item_id)}"
    )


class AzureCollectionClient:
    """Cliente de uma coleção, usando a URL e o PAT já configurados, sem alterá-los."""

    def __init__(
        self,
        *,
        base_url: str,
        organization: str,
        pat: str,
        sleeper: Callable[[float], None] = time.sleep,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip() or not organization.strip() or not pat.strip():
            raise AzureDevOpsConfigError("Azure DevOps não configurado.")
        self.base_url = base_url.rstrip("/")
        self.organization = organization.strip()
        self._pat = pat
        self._sleeper = sleeper
        self._http = http_client or httpx.Client(timeout=60.0)

    @property
    def org_base(self) -> str:
        return f"{self.base_url}/{quote(self.organization)}"

    def project_base(self, project: str) -> str:
        return f"{self.org_base}/{quote(project.strip())}"

    def close(self) -> None:
        self._http.close()

    def request(self, method: str, url: str, *, json_body: dict[str, Any] | None = None) -> Any:
        delay = 1.0
        last_status = 0
        for attempt in range(4):
            try:
                response = self._http.request(
                    method,
                    url,
                    headers={"Accept": "application/json"},
                    auth=("", self._pat),
                    json=json_body,
                )
            except httpx.TimeoutException as exc:
                if attempt == 3:
                    raise AzureDevOpsConnectionError("Tempo esgotado ao consultar o Azure DevOps.") from exc
                self._sleeper(delay)
                delay *= 2
                continue
            except httpx.RequestError as exc:
                raise AzureDevOpsConnectionError("Não foi possível conectar ao Azure DevOps.") from exc

            last_status = response.status_code
            if response.status_code in {401, 403}:
                raise AzureDevOpsAuthError("PAT inválido ou sem permissão nesta coleção do Azure DevOps.")
            if response.status_code == 404:
                raise AzureDevOpsConnectionError("Projeto ou recurso não encontrado no Azure DevOps.")
            if response.status_code in {429, 503} or response.status_code >= 500:
                if attempt == 3:
                    raise AzureDevOpsConnectionError("Azure DevOps limitou ou ficou indisponível durante a consulta.")
                retry_after = response.headers.get("Retry-After")
                try:
                    wait = float(retry_after) if retry_after else delay
                except ValueError:
                    wait = delay
                self._sleeper(min(wait, 30))
                delay *= 2
                continue
            if response.status_code >= 400:
                raise AzureDevOpsConnectionError(_safe_error(response))
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError as exc:
                raise AzureDevOpsConnectionError("Resposta inválida do Azure DevOps.") from exc
        raise AzureDevOpsConnectionError(f"Falha ao consultar o Azure DevOps ({last_status}).")

    def ensure_project(self, project: str) -> None:
        url = f"{self.org_base}/_apis/projects/{quote(project.strip())}?api-version={API_VERSION}"
        self.request("GET", url)

    def ensure_collection(self) -> None:
        query = urlencode({"api-version": API_VERSION, "$top": 1, "stateFilter": "WellFormed"})
        self.request("GET", f"{self.org_base}/_apis/projects?{query}")

    def list_projects(self) -> list[str]:
        names: list[str] = []
        skip = 0
        while True:
            query = urlencode(
                {
                    "api-version": API_VERSION,
                    "$top": 100,
                    "$skip": skip,
                    "stateFilter": "WellFormed",
                }
            )
            payload = self.request("GET", f"{self.org_base}/_apis/projects?{query}")
            page = payload.get("value") or []
            for item in page:
                name = str(item.get("name") or "").strip()
                if name and name not in names:
                    names.append(name)
            if len(page) < 100:
                break
            skip += 100
            if skip > 5000:
                break
        return sorted(names, key=str.casefold)

    def search_identities(self, name: str) -> dict[str, Any]:
        query = urlencode(
            {
                "searchFilter": "General",
                "filterValue": name.strip(),
                "queryMembership": "None",
                "api-version": "6.0",
            }
        )
        try:
            payload = self.request("GET", f"{self.org_base}/_apis/identities?{query}")
        except AzureDevOpsAuthError:
            return {"status": "unavailable", "people": []}
        except AzureDevOpsConnectionError as exc:
            if "não encontrado" in str(exc).casefold():
                return {"status": "unavailable", "people": []}
            raise
        values = payload.get("value") if isinstance(payload, dict) else payload
        people = [_identity_from_directory(item) for item in values or []]
        people = [item for item in people if item["display_name"] or item["unique_name"]]
        return {"status": "ok", "people": people}

    def query_work_item_ids(
        self,
        *,
        project: str,
        work_item_type: str,
        date_field: str,
        start: date,
        end: date,
    ) -> tuple[list[int], list[str]]:
        ids, truncated = self._wiql_ids(project, work_item_type, date_field, start, end)
        limitations: list[str] = []
        if not truncated:
            return ids, limitations
        limitations.append(
            "A consulta do ano atingiu o limite da API e foi refeita mês a mês para não ficar restrita aos primeiros resultados."
        )
        seen: set[int] = set()
        ordered: list[int] = []
        cursor = start
        while cursor < end:
            month_end = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)
            if month_end > end:
                month_end = end
            part, part_truncated = self._wiql_ids(project, work_item_type, date_field, cursor, month_end)
            if part_truncated:
                limitations.append(
                    f"O período {cursor.isoformat()} a {month_end.isoformat()} ainda atingiu o limite de {WIQL_PAGE_LIMIT} itens."
                )
            for item_id in part:
                if item_id not in seen:
                    seen.add(item_id)
                    ordered.append(item_id)
            cursor = month_end
        return ordered, limitations

    def fetch_work_items(
        self,
        ids: list[int],
        *,
        field_refs: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[tuple[int, str]]]:
        found: list[dict[str, Any]] = []
        failed: list[tuple[int, str]] = []
        from app.services.issue_audit.field_refs import WORK_ITEM_BASE_FIELDS

        refs = list(field_refs or WORK_ITEM_BASE_FIELDS)
        seen: set[str] = set()
        ordered_refs: list[str] = []
        for ref in refs:
            name = str(ref).strip()
            if name and name not in seen:
                seen.add(name)
                ordered_refs.append(name)
        fields = ",".join(ordered_refs)

        def load(chunk: list[int]) -> None:
            if not chunk:
                return
            ids_param = ",".join(str(item) for item in chunk)
            url = (
                f"{self.org_base}/_apis/wit/workitems"
                f"?ids={ids_param}&fields={quote(fields, safe=',')}&api-version={API_VERSION}"
            )
            try:
                payload = self.request("GET", url)
            except AzureDevOpsAuthError:
                raise
            except AzureDevOpsError as exc:
                if len(chunk) == 1:
                    failed.append((chunk[0], str(exc)))
                    return
                middle = len(chunk) // 2
                load(chunk[:middle])
                load(chunk[middle:])
                return
            found.extend(payload.get("value") or [])

        for start in range(0, len(ids), WORK_ITEM_BATCH):
            load(ids[start : start + WORK_ITEM_BATCH])
        return found, failed

    def probe_comments_api(self, work_item_id: int) -> dict[str, Any]:
        """Verifica se a API de comentários existe neste servidor (somente leitura)."""
        versions = ("7.1-preview.4", "7.0-preview.3", "6.0-preview.3")
        for version in versions:
            query = urlencode({"$top": 200, "order": "asc", "api-version": version})
            url = f"{self.org_base}/_apis/wit/workItems/{int(work_item_id)}/comments?{query}"
            try:
                payload = self.request("GET", url)
            except AzureDevOpsAuthError:
                raise
            except AzureDevOpsConnectionError as exc:
                message = str(exc).casefold()
                if "não encontrado" in message or "404" in message:
                    continue
                return {"available": False, "error": str(exc), "api_version": version}
            comments = payload.get("comments") or []
            return {
                "available": True,
                "api_version": version,
                "count_on_page": len(comments),
                "total_count": payload.get("totalCount") or payload.get("count"),
                "has_continuation": bool(payload.get("continuationToken")),
            }
        return {"available": False, "reason": "comments_api_not_found"}

    def fetch_comment_updates(self, work_item_id: int) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        skip = 0
        for _page in range(MAX_UPDATE_PAGES):
            query = urlencode({"$top": UPDATE_PAGE_SIZE, "$skip": skip, "api-version": API_VERSION})
            url = f"{self.org_base}/_apis/wit/workItems/{int(work_item_id)}/updates?{query}"
            payload = self.request("GET", url)
            page = payload.get("value") or []
            collected.extend(page)
            if len(page) < UPDATE_PAGE_SIZE:
                return collected
            skip += UPDATE_PAGE_SIZE
        raise AuditPaginationError(
            f"A paginação do histórico da Issue {work_item_id} não terminou dentro do limite seguro."
        )

    def _wiql_ids(
        self,
        project: str,
        work_item_type: str,
        date_field: str,
        start: date,
        end: date,
    ) -> tuple[list[int], bool]:
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.TeamProject] = '{_escape_wiql(project.strip())}' "
                f"AND [System.WorkItemType] = '{_escape_wiql(work_item_type.strip())}' "
                f"AND [{date_field}] >= '{start.isoformat()}' "
                f"AND [{date_field}] < '{end.isoformat()}'"
            )
        }
        url = f"{self.project_base(project)}/_apis/wit/wiql?api-version={API_VERSION}"
        payload = self.request("POST", url, json_body=wiql)
        ids: list[int] = []
        for item in payload.get("workItems") or []:
            try:
                ids.append(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return ids, len(ids) >= WIQL_PAGE_LIMIT


def _safe_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        message = str(payload.get("message") or "").strip()
        if message and "token" not in message.casefold() and "pat" not in message.casefold():
            return message[:300]
    return "Não foi possível consultar o Azure DevOps."


def _property_value(item: dict[str, Any], key: str) -> str:
    raw = (item.get("properties") or {}).get(key)
    if isinstance(raw, dict):
        raw = raw.get("$value")
    return str(raw or "").strip()


def _identity_from_directory(item: dict[str, Any]) -> dict[str, str | None]:
    display = str(item.get("displayName") or item.get("providerDisplayName") or "").strip()
    if not display:
        display = _property_value(item, "Account")
    unique = str(item.get("uniqueName") or "").strip() or _property_value(item, "Mail") or None
    identity_id = str(item.get("id") or "").strip() or None
    descriptor = str(item.get("descriptor") or "").strip() or None
    return {
        "id": identity_id,
        "display_name": display,
        "unique_name": unique,
        "descriptor": descriptor,
    }
