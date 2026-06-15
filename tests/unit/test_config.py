"""Unit tests for Settings validation (security hardening A1).

The JWT signing secret must be at least 32 bytes so HS256 tokens cannot be
brute-forced. Settings must refuse to construct with a weaker secret.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from wealth_assistant.config import Settings


def _build(secret: str) -> Settings:
    # _env_file=None isolates from the project .env; the explicit kwarg takes
    # precedence over any JWT_SECRET in the environment.
    return Settings(jwt_secret=secret, _env_file=None)


def test_rejects_jwt_secret_shorter_than_32_bytes():
    with pytest.raises(ValidationError):
        _build("x" * 31)


def test_rejects_empty_jwt_secret():
    with pytest.raises(ValidationError):
        _build("")


def test_accepts_jwt_secret_of_exactly_32_bytes():
    settings = _build("x" * 32)
    assert settings.jwt_secret.get_secret_value() == "x" * 32
