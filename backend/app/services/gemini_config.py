from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import AI_PROVIDER_GOOGLE_GEMINI, AiSettings
from app.services.ai.errors import AiConfigError
from app.services.secret_encryption import SecretEncryptionError, decrypt_secret, encrypt_secret

AiConnectionStatus = Literal["not_configured", "configured", "error"]

PROVIDER_LABEL = "Google Gemini"


@dataclass
class AiConfigView:
    provider: str
    provider_label: str
    status: AiConnectionStatus
    api_key_configured: bool
    model_id: str | None
    enabled: bool
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_message: str | None


def get_settings_row(db: Session) -> AiSettings | None:
    return db.get(AiSettings, 1)


def _ensure_row(db: Session) -> AiSettings:
    row = get_settings_row(db)
    if row is None:
        row = AiSettings(id=1, provider=AI_PROVIDER_GOOGLE_GEMINI)
        db.add(row)
        db.flush()
    return row


def resolve_api_key(row: AiSettings | None) -> str | None:
    if row and row.encrypted_api_key:
        try:
            return decrypt_secret(row.encrypted_api_key)
        except SecretEncryptionError:
            return None
    return None


def _compute_status(row: AiSettings | None, *, key_ok: bool) -> AiConnectionStatus:
    if row is None or not row.encrypted_api_key or not key_ok:
        return "not_configured"
    if row.last_test_ok is False:
        return "error"
    if row.model_id:
        return "configured"
    return "not_configured"


def to_view(row: AiSettings | None) -> AiConfigView:
    key = resolve_api_key(row)
    key_ok = bool(key) if row and row.encrypted_api_key else False
    if row and row.encrypted_api_key and not key_ok:
        status: AiConnectionStatus = "error"
    else:
        status = _compute_status(row, key_ok=key_ok)

    return AiConfigView(
        provider=row.provider if row else AI_PROVIDER_GOOGLE_GEMINI,
        provider_label=PROVIDER_LABEL,
        status=status,
        api_key_configured=bool(row and row.encrypted_api_key and key_ok),
        model_id=row.model_id if row else None,
        enabled=bool(row.enabled) if row else False,
        last_test_at=row.last_test_at if row else None,
        last_test_ok=row.last_test_ok if row else None,
        last_test_message=row.last_test_message if row else None,
    )


def get_config_view(db: Session) -> AiConfigView:
    return to_view(get_settings_row(db))


def is_configured(db: Session) -> bool:
    view = get_config_view(db)
    return view.api_key_configured and bool(view.model_id)


def is_enabled_for_use(db: Session) -> bool:
    row = get_settings_row(db)
    if not row or not row.enabled:
        return False
    return is_configured(db)


def save_settings(
    db: Session,
    *,
    api_key: str | None,
    clear_api_key: bool,
    model_id: str | None,
    enabled: bool | None,
) -> AiConfigView:
    row = _ensure_row(db)

    if clear_api_key:
        row.encrypted_api_key = None

    if api_key and api_key.strip():
        row.encrypted_api_key = encrypt_secret(api_key.strip())

    if model_id is not None:
        cleaned = model_id.strip()
        row.model_id = cleaned or None

    if enabled is not None:
        row.enabled = enabled

    if not row.encrypted_api_key:
        row.enabled = False

    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return to_view(row)


def clear_api_key(db: Session) -> AiConfigView:
    return save_settings(db, api_key=None, clear_api_key=True, model_id=None, enabled=False)


def record_test_result(db: Session, *, ok: bool, message: str) -> None:
    row = _ensure_row(db)
    row.last_test_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.last_test_ok = ok
    row.last_test_message = message[:500]
    db.commit()


def require_api_key(db: Session) -> tuple[AiSettings, str]:
    row = get_settings_row(db)
    key = resolve_api_key(row)
    if not row or not key:
        raise AiConfigError("Chave da API não cadastrada.")
    return row, key


def require_model(row: AiSettings) -> str:
    if not row.model_id:
        raise AiConfigError("Selecione um modelo antes de continuar.")
    return row.model_id
