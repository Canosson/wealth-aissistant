"""Contract tests for privacy/account-lifecycle endpoints (T024).

Covers:
  GET  /me/export  → 200 InvestorExport (FR-017)
  DELETE /me       → 204, then login yields 401 (FR-018, SC-009)
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

_REGISTER_PAYLOAD = {
    "email": "privacy@example.com",
    "password": "s3cure-passw0rd!",
    "reporting_currency": "USD",
}


async def _register_and_token(client: AsyncClient) -> str:
    resp = await client.post("/auth/register", json=_REGISTER_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["token"]


@pytest.mark.asyncio
async def test_export_returns_200_with_required_fields(auth_client: AsyncClient) -> None:
    token = await _register_and_token(auth_client)
    resp = await auth_client.get(
        "/me/export", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    for field in ("investor_id", "email", "reporting_currency", "created_at"):
        assert field in body, f"missing field: {field}"
    assert body["email"] == _REGISTER_PAYLOAD["email"]
    assert body["reporting_currency"] == _REGISTER_PAYLOAD["reporting_currency"]


@pytest.mark.asyncio
async def test_delete_me_returns_204(auth_client: AsyncClient) -> None:
    token = await _register_and_token(auth_client)
    resp = await auth_client.delete(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_me_then_login_returns_401(auth_client: AsyncClient) -> None:
    token = await _register_and_token(auth_client)
    await auth_client.delete("/me", headers={"Authorization": f"Bearer {token}"})

    login_resp = await auth_client.post(
        "/auth/login",
        json={"email": _REGISTER_PAYLOAD["email"], "password": _REGISTER_PAYLOAD["password"]},
    )
    assert login_resp.status_code == 401
