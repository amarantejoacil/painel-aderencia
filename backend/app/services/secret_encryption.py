from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class SecretEncryptionError(ValueError):
    pass


def _derive_fallback_key() -> bytes:
    material = settings.database_url.encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    raw = settings.secret_encryption_key.strip()
    if raw:
        try:
            return Fernet(raw.encode("utf-8"))
        except ValueError as exc:
            raise SecretEncryptionError("SECRET_ENCRYPTION_KEY inválida.") from exc
    return Fernet(_derive_fallback_key())


def encrypt_secret(value: str) -> str:
    if not value:
        raise SecretEncryptionError("Valor vazio não pode ser criptografado.")
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value:
        raise SecretEncryptionError("Segredo ausente.")
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretEncryptionError("Não foi possível descriptografar o segredo.") from exc
