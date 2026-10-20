from unittest.mock import MagicMock, patch

from app.models import AiSettings
from app.services.gemini_config import get_config_view, save_settings
from tests.conftest import TestingSession


def test_save_gemini_settings_encrypts_key_and_never_returns_it(client) -> None:
    db = TestingSession()
    try:
        view = save_settings(
            db,
            api_key="secret-gemini-key",
            clear_api_key=False,
            model_id="gemini-2.0-flash",
            enabled=True,
        )
        assert view.api_key_configured is True
        assert view.model_id == "gemini-2.0-flash"
        assert view.enabled is True

        row = db.get(AiSettings, 1)
        assert row is not None
        assert row.encrypted_api_key is not None
        assert "secret-gemini-key" not in row.encrypted_api_key

        public = get_config_view(db)
        assert public.api_key_configured is True
    finally:
        db.close()


def test_update_gemini_keeps_key_when_not_provided(client) -> None:
    db = TestingSession()
    try:
        save_settings(
            db,
            api_key="first-key",
            clear_api_key=False,
            model_id="gemini-2.0-flash",
            enabled=True,
        )
        before = db.get(AiSettings, 1)
        assert before is not None
        encrypted_before = before.encrypted_api_key

        save_settings(
            db,
            api_key=None,
            clear_api_key=False,
            model_id="gemini-2.5-flash",
            enabled=False,
        )
        after = db.get(AiSettings, 1)
        assert after is not None
        assert after.encrypted_api_key == encrypted_before
        assert after.model_id == "gemini-2.5-flash"
        assert after.enabled is False
    finally:
        db.close()


def test_get_gemini_settings_endpoint_masks_key(client) -> None:
    db = TestingSession()
    try:
        save_settings(
            db,
            api_key="hidden-gemini",
            clear_api_key=False,
            model_id="gemini-2.0-flash",
            enabled=True,
        )
    finally:
        db.close()

    response = client.get("/api/settings/gemini")
    assert response.status_code == 200
    body = response.json()
    assert body["api_key_configured"] is True
    assert "hidden-gemini" not in str(body)
    assert "encrypted" not in str(body).lower()


def test_delete_gemini_api_key(client) -> None:
    db = TestingSession()
    try:
        save_settings(
            db,
            api_key="to-remove",
            clear_api_key=False,
            model_id="gemini-2.0-flash",
            enabled=True,
        )
    finally:
        db.close()

    response = client.delete("/api/settings/gemini/api-key")
    assert response.status_code == 200
    body = response.json()
    assert body["api_key_configured"] is False
    assert body["enabled"] is False


@patch("app.routers.settings.GeminiClient")
def test_test_gemini_connection_success(mock_client_cls, client) -> None:
    db = TestingSession()
    try:
        save_settings(
            db,
            api_key="valid-key",
            clear_api_key=False,
            model_id="gemini-2.0-flash",
            enabled=True,
        )
    finally:
        db.close()

    instance = MagicMock()
    mock_client_cls.return_value = instance

    response = client.post("/api/settings/gemini/test-connection")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    instance.test_connection.assert_called_once_with("gemini-2.0-flash")


@patch("app.routers.settings.GeminiClient")
def test_test_gemini_connection_auth_error(mock_client_cls, client) -> None:
    from app.services.ai.errors import AiAuthError

    db = TestingSession()
    try:
        save_settings(
            db,
            api_key="bad-key",
            clear_api_key=False,
            model_id="gemini-2.0-flash",
            enabled=True,
        )
    finally:
        db.close()

    instance = MagicMock()
    instance.test_connection.side_effect = AiAuthError("Chave inválida.")
    mock_client_cls.return_value = instance

    response = client.post("/api/settings/gemini/test-connection")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["message"] == "Chave inválida."
