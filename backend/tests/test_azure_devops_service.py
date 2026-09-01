from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.azure_devops import AzureDevOpsService
from app.services.azure_devops_errors import AzureDevOpsAuthError, AzureDevOpsConnectionError


@pytest.fixture
def service() -> AzureDevOpsService:
    return AzureDevOpsService(
        base_url="https://dev.azure.com",
        organization="NucleoIA",
        project="Inteligência Artificial",
        pat="secret-pat",
        work_date_field="Custom.DataReferencia",
        activity_field="Custom.Atividade",
    )


def test_query_task_ids_uses_wiql(service: AzureDevOpsService) -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"workItems": [{"id": 10}, {"id": 11}]}

    with patch("app.services.azure_devops.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.request.return_value = response
        ids = service.query_task_ids(2026, 8)

    assert ids == [10, 11]
    call_args = client.request.call_args
    assert call_args[0][0] == "POST"
    assert "wiql" in call_args[0][1]
    body = call_args[1]["json"]["query"]
    assert "Custom.DataReferencia" in body
    assert "2026-08-01" in body
    assert "2026-08-31" in body


def test_test_connection_raises_auth_error(service: AzureDevOpsService) -> None:
    response = MagicMock()
    response.status_code = 401
    response.json.return_value = {}

    with patch("app.services.azure_devops.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.request.return_value = response
        with pytest.raises(AzureDevOpsAuthError):
            service.test_connection()


def test_request_raises_connection_error_on_network_failure(service: AzureDevOpsService) -> None:
    with patch("app.services.azure_devops.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.request.side_effect = httpx.ConnectError("offline", request=MagicMock())
        with pytest.raises(AzureDevOpsConnectionError):
            service._request("GET", "https://example.test")


def test_discover_field_mapping_uses_overrides(service: AzureDevOpsService) -> None:
    mapping = service.discover_field_mapping()
    assert mapping["work_date_field"] == "Custom.DataReferencia"
    assert mapping["activity_field"] == "Custom.Atividade"
