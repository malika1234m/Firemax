"""Symmetric encryption for per-org secrets stored at rest (e.g. each
organization's Home Assistant long-lived token — effectively a key to their
building, so it must never sit in the DB in plaintext).

Uses Fernet (AES-128-CBC + HMAC) with a key from SECRETS_ENCRYPTION_KEY.
Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings


def encryption_available() -> bool:
    return bool(settings.SECRETS_ENCRYPTION_KEY)


def _fernet() -> Fernet:
    if not settings.SECRETS_ENCRYPTION_KEY:
        raise RuntimeError("SECRETS_ENCRYPTION_KEY is not configured")
    return Fernet(settings.SECRETS_ENCRYPTION_KEY.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str | None:
    """Returns the plaintext, or None if the value can't be decrypted (wrong/
    rotated key, tampering, or encryption not configured) — callers treat that
    the same as 'not configured' rather than crashing."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, RuntimeError, ValueError):
        return None
