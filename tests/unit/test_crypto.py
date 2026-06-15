"""Unit tests for the encryption helpers (security hardening A2).

The _ALLOW_MISSING_ENCRYPTION_KEY bypass must only work when pytest is running.
A production process that has the flag set (accidentally or maliciously) must
still get a RuntimeError rather than silently using a random ephemeral key.
"""
from __future__ import annotations

import pytest

from wealth_assistant.persistence import crypto
from wealth_assistant.persistence.crypto import decrypt, encrypt


def test_in_test_env_returns_true_when_under_pytest():
    """_in_test_env() must return True inside a running pytest session."""
    from wealth_assistant.persistence.crypto import _in_test_env  # noqa: PLC0415

    assert _in_test_env() is True


def test_load_key_raises_when_not_in_pytest_even_with_bypass_flag(monkeypatch):
    """The bypass flag alone is not enough — pytest must also be running."""
    monkeypatch.setattr(crypto, "_in_test_env", lambda: False)
    monkeypatch.setenv("_ALLOW_MISSING_ENCRYPTION_KEY", "1")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    crypto._TEST_KEY = None  # reset cached test key

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        crypto._load_key()


def test_load_key_works_in_pytest_with_bypass_flag(monkeypatch):
    """In a real pytest run, the bypass flag should still mint a 32-byte key."""
    monkeypatch.setenv("_ALLOW_MISSING_ENCRYPTION_KEY", "1")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    crypto._TEST_KEY = None

    key = crypto._load_key()
    assert len(key) == 32


def test_encrypt_decrypt_round_trip():
    plaintext = "super-secret-access-token"
    assert decrypt(encrypt(plaintext)) == plaintext
