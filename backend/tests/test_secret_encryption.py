import pytest

from app.services.secret_encryption import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_roundtrip() -> None:
    original = "my-secret-pat-token"
    encrypted = encrypt_secret(original)
    assert encrypted != original
    assert decrypt_secret(encrypted) == original


def test_decrypt_invalid_token_raises() -> None:
    from app.services.secret_encryption import SecretEncryptionError

    with pytest.raises(SecretEncryptionError):
        decrypt_secret("not-a-valid-token")
