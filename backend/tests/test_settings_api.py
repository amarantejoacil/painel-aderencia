from app.models import AzureDevOpsSettings
from app.services.azure_devops_config import get_config_view, is_configured, save_settings
from tests.conftest import TestingSession


def test_save_settings_encrypts_pat_and_never_returns_it(client) -> None:
    db = TestingSession()
    try:
        view = save_settings(
            db,
            base_url="https://azure-devops.example.test",
            organization="NucleoIA",
            project="Inteligência Artificial",
            pat="secret-pat-value",
            pat_expires_at=None,
        )
        assert view.configured is True
        assert view.pat_configured is True

        row = db.get(AzureDevOpsSettings, 1)
        assert row is not None
        assert row.encrypted_pat is not None
        assert "secret-pat-value" not in row.encrypted_pat

        public = get_config_view(db)
        assert public.pat_configured is True
        assert is_configured(db) is True
    finally:
        db.close()


def test_update_settings_keeps_pat_when_not_provided(client) -> None:
    db = TestingSession()
    try:
        save_settings(
            db,
            base_url="https://azure-devops.example.test",
            organization="NucleoIA",
            project="Projeto A",
            pat="first-pat",
            pat_expires_at=None,
        )
        before = db.get(AzureDevOpsSettings, 1)
        assert before is not None
        encrypted_before = before.encrypted_pat

        save_settings(
            db,
            base_url="https://azure-devops.example.test",
            organization="NucleoIA",
            project="Projeto B",
            pat=None,
            pat_expires_at=None,
        )
        after = db.get(AzureDevOpsSettings, 1)
        assert after is not None
        assert after.encrypted_pat == encrypted_before
        assert after.project == "Projeto B"
    finally:
        db.close()


def test_get_settings_endpoint_masks_pat(client) -> None:
    db = TestingSession()
    try:
        save_settings(
            db,
            base_url="https://azure-devops.example.test",
            organization="NucleoIA",
            project="Projeto",
            pat="hidden-pat",
            pat_expires_at=None,
        )
    finally:
        db.close()

    response = client.get("/api/settings/azure-devops")
    assert response.status_code == 200
    body = response.json()
    assert body["pat_configured"] is True
    assert "hidden-pat" not in str(body)
    assert "encrypted" not in str(body).lower()
