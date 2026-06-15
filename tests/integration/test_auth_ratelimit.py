"""Integration tests for auth endpoint rate limiting (security hardening A3).

Both POST /auth/register and POST /auth/login must reject the 6th request
within a minute with HTTP 429.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

_PASSWORD = "s3cure-passw0rd!"
_EMAIL = "ratelimit@example.com"


@pytest.mark.asyncio
async def test_login_rate_limited_after_5_requests(auth_client: AsyncClient) -> None:
    """The 6th login attempt within a sliding window must return 429."""
    # Register so valid credentials exist
    await auth_client.post(
        "/auth/register",
        json={"email": _EMAIL, "password": _PASSWORD, "reporting_currency": "USD"},
    )

    for attempt in range(5):
        resp = await auth_client.post(
            "/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
        )
        assert resp.status_code == 200, f"Expected 200 on attempt {attempt + 1}, got {resp.status_code}"

    sixth = await auth_client.post(
        "/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
    )
    assert sixth.status_code == 429


@pytest.mark.asyncio
async def test_register_rate_limited_after_5_requests(auth_client: AsyncClient) -> None:
    """The 6th register attempt within a sliding window must return 429."""
    for attempt in range(5):
        resp = await auth_client.post(
            "/auth/register",
            json={
                "email": f"user{attempt}@example.com",
                "password": _PASSWORD,
                "reporting_currency": "USD",
            },
        )
        assert resp.status_code in (201, 409), f"Unexpected {resp.status_code} on attempt {attempt + 1}"

    sixth = await auth_client.post(
        "/auth/register",
        json={"email": "sixth@example.com", "password": _PASSWORD, "reporting_currency": "USD"},
    )
    assert sixth.status_code == 429
