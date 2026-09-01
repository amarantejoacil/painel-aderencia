from unittest.mock import patch

from app.services.azure_devops import AzureDevOpsService


def test_azure_status_when_not_configured(client) -> None:
    with patch("app.routers.azure_devops.is_configured", return_value=False):
        response = client.get("/api/azure-devops/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["last_sync_at"] is None


def test_test_connection_success(client) -> None:
    with patch("app.routers.azure_devops.is_configured", return_value=True):
        with patch("app.routers.azure_devops.build_service") as build_mock:
            build_mock.return_value = AzureDevOpsService(
                base_url="https://dev.azure.com",
                organization="Org",
                project="Proj",
                pat="pat",
                work_date_field="Custom.DataReferencia",
            )
            with patch.object(AzureDevOpsService, "test_connection", return_value=None):
                response = client.post("/api/azure-devops/test-connection")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_sync_creates_merged_batch(client) -> None:
    from datetime import date

    from app.services.activity_normalization import NormalizedActivity

    mapped = [
        NormalizedActivity(
            task_id="9001",
            title="Task Azure",
            azure_assignee="Ana Souza <PJMT\\1001>",
            assignee_name="Ana Souza",
            work_date=date(2026, 8, 3),
            source="azure_api",
        )
    ]

    with patch("app.routers.azure_devops.is_configured", return_value=True):
        with patch("app.routers.azure_devops.build_service") as build_mock:
            service = AzureDevOpsService(
                base_url="https://dev.azure.com",
                organization="Org",
                project="Proj",
                pat="pat",
                work_date_field="Custom.DataReferencia",
            )
            build_mock.return_value = service
            with patch.object(AzureDevOpsService, "discover_field_mapping", return_value={
                "work_date_field": "Custom.DataReferencia",
                "activity_field": "Custom.Atividade",
            }):
                with patch.object(AzureDevOpsService, "query_task_ids", return_value=[9001]):
                    with patch.object(AzureDevOpsService, "fetch_work_items", return_value=[{"id": 9001, "fields": {}}]):
                        with patch("app.routers.azure_devops.map_work_items", return_value=(mapped, 0)):
                            response = client.post("/api/azure-devops/sync", json={"year": 2026, "month": 8})

    assert response.status_code == 200
    body = response.json()
    assert body["tasks_found"] == 1
    assert body["created"] == 1
    assert body["import_id"] > 0

    listed = client.get("/api/imports")
    assert listed.json()[0]["source"] == "azure_api"
