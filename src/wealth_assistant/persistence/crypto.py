"""AES-256-GCM encryption-at-rest for PII and provider access tokens (T016, FR-019).

Key is a base64-encoded 32-byte value from ENCRYPTION_KEY env var.
In production, missing ENCRYPTION_KEY raises at first use.
Set _ALLOW_MISSING_ENCRYPTION_KEY=1 only in test environments.
"""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12
_SEPARATOR = b":"
_TEST_KEY: bytes | None = None  # cached for test round-trips


def _in_test_env() -> bool:
    """Return True only when running under pytest. Prevents the bypass from working in prod."""
    import sys  # noqa: PLC0415

    return "pytest" in sys.modules


def _load_key() -> bytes:
    global _TEST_KEY
    raw = os.environ.get("ENCRYPTION_KEY")
    if raw:
        return base64.b64decode(raw)
    if os.environ.get("_ALLOW_MISSING_ENCRYPTION_KEY") == "1" and _in_test_env():
        if _TEST_KEY is None:
            _TEST_KEY = secrets.token_bytes(32)
        return _TEST_KEY
    raise RuntimeError(
        "ENCRYPTION_KEY is not set. Provide a base64-encoded 32-byte AES key."
    )


def encrypt(plaintext: str) -> str:
    """Return 'base64(nonce):base64(ciphertext)' suitable for DB storage."""
    key = _load_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    encoded = base64.b64encode(nonce) + _SEPARATOR + base64.b64encode(ciphertext)
    return encoded.decode()


def decrypt(token: str) -> str:
    """Reverse of encrypt(). Raises ValueError on bad or tampered ciphertext."""
    key = _load_key()
    aesgcm = AESGCM(key)
    try:
        nonce_b64, ct_b64 = token.encode().split(_SEPARATOR, 1)
        plaintext = aesgcm.decrypt(
            base64.b64decode(nonce_b64), base64.b64decode(ct_b64), None
        )
        return plaintext.decode()
    except Exception as exc:
        raise ValueError(
            "Decryption failed — token is invalid or was tampered with."
        ) from exc
