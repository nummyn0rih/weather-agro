"""Fernet helpers for at-rest encryption of secrets in `settings.value` (task 6.3).

The Fernet key is derived from ``settings.SECRET_KEY`` via HKDF-SHA256 (32-byte
output, urlsafe-base64 encoded). This keeps a single root secret in `.env`
(`SECRET_KEY`) and avoids managing a second key while still allowing future
domain separation through the HKDF ``info`` parameter.
"""

from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

_HKDF_INFO = b"weather-agro.settings.v1"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    settings = get_settings()
    raw = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(settings.SECRET_KEY.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt(plain: str) -> str:
    """Encrypt a plaintext secret. Returns a urlsafe-b64 fernet token (str)."""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token previously produced by :func:`encrypt`."""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("invalid encryption token") from exc


def reset_cache() -> None:
    """Drop the cached Fernet instance. Test-only — call after monkeypatching SECRET_KEY."""
    _fernet.cache_clear()
