from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from app.config import azure_devops_configured_from_env, settings
from app.services.azure_devops_config import get_settings_row
from app.services.secret_encryption import uses_dedicated_encryption_key

logger = logging.getLogger(__name__)

_ENV_PAT = "AZURE_DEVOPS_PAT"


def reduce_env_pat_exposure(db: Session) -> None:
    """Evita manter PAT em texto claro no processo quando já existe cópia criptografada no banco."""
    row = get_settings_row(db)
    if not row or not row.encrypted_pat:
        return
    had_plaintext = bool(os.environ.get(_ENV_PAT) or settings.azure_devops_pat.strip())
    os.environ.pop(_ENV_PAT, None)
    settings.azure_devops_pat = ""
    if had_plaintext:
        logger.warning(
            "%s ignorado: o PAT já está armazenado criptografado no banco. "
            "Remova a variável do arquivo .env (local, não versionado) e do docker-compose.",
            _ENV_PAT,
        )


def log_startup_security_warnings(db: Session) -> None:
    if not uses_dedicated_encryption_key():
        logger.warning(
            "SECRET_ENCRYPTION_KEY não definida: PAT Azure e chave Gemini usam criptografia "
            "derivada da DATABASE_URL (apenas para desenvolvimento). "
            "Gere uma chave Fernet e configure SECRET_ENCRYPTION_KEY no ambiente."
        )

    row = get_settings_row(db)
    if row and row.encrypted_pat and azure_devops_configured_from_env():
        logger.warning(
            "Configuração duplicada: PAT no banco e também em variáveis de ambiente. "
            "Prefira somente Configurações na UI e remova %s do .env.",
            _ENV_PAT,
        )
