import os
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.config import settings
from app.services import credentials_security
from app.services.credentials_security import reduce_env_pat_exposure
from app.services.secret_encryption import uses_dedicated_encryption_key


def test_uses_dedicated_encryption_key_false_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "secret_encryption_key", "")
    assert uses_dedicated_encryption_key() is False
    monkeypatch.setattr(settings, "secret_encryption_key", "x" * 10)
    assert uses_dedicated_encryption_key() is True


def test_reduce_env_pat_exposure_clears_env_and_settings(monkeypatch) -> None:
    row = SimpleNamespace(encrypted_pat="gAAAAABfake")
    monkeypatch.setattr(
        credentials_security,
        "get_settings_row",
        MagicMock(return_value=row),
    )
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "pat-from-env")
    monkeypatch.setattr(settings, "azure_devops_pat", "pat-from-env")

    reduce_env_pat_exposure(MagicMock())

    assert os.environ.get("AZURE_DEVOPS_PAT") is None
    assert settings.azure_devops_pat == ""
