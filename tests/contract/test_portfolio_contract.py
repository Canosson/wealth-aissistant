"""Contract tests for connection + portfolio endpoints (T030).

Verifies HTTP status codes and response shapes against openapi.yaml for:
  POST /connections/link-token   → 200 {link_token}
  POST /connections              → 201 Connection
  GET  /connections              → 200 [Connection]
  POST /connections/{id}/refresh → 200 Connection
  DELETE /connections/{id}       → 204
  GET  /portfolio                → 200 Portfolio
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

_REG = {
    "email": "portfolio_contract@example.com",
    "password": "s3cure-passw0rd!",
    "reporting_currency": "USD",
}


async def _token(client: AsyncClient) -> str:
    r = await client.post("/auth/register", json=_REG)
    assert r.status_code == 201
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_link_token_returns_200_with_link_token(auth_client: AsyncClient) -> None:
    token = await _token(auth_client)
    r = await auth_client.post("/connections/link-token", headers=_auth(token))
    assert r.status_code == 200
    assert "link_token" in r.json()


@pytest.mark.asyncio
async def test_exchange_returns_201_connection_schema(auth_client: AsyncClient) -> None:
    token = await _token(auth_client)
    r = await auth_client.post(
        "/connections",
        json={"public_token": "fake-public-token"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    for field in ("id", "provider", "institution_name", "status"):
        assert field in body, f"missing field: {field}"


@pytest.mark.asyncio
async def test_list_connections_returns_200_list(auth_client: AsyncClient) -> None:
    token = await _token(auth_client)
    await auth_client.post(
        "/connections", json={"public_token": "fake-public-token"}, headers=_auth(token)
    )
    r = await auth_client.get("/connections", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_refresh_connection_returns_200(auth_client: AsyncClient) -> None:
    token = await _token(auth_client)
    conn = await auth_client.post(
        "/connections", json={"public_token": "fake-public-token"}, headers=_auth(token)
    )
    conn_id = conn.json()["id"]
    r = await auth_client.post(f"/connections/{conn_id}/refresh", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_delete_connection_returns_204(auth_client: AsyncClient) -> None:
    token = await _token(auth_client)
    conn = await auth_client.post(
        "/connections", json={"public_token": "fake-public-token"}, headers=_auth(token)
    )
    conn_id = conn.json()["id"]
    r = await auth_client.delete(f"/connections/{conn_id}", headers=_auth(token))
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_get_portfolio_returns_200_portfolio_schema(auth_client: AsyncClient) -> None:
    token = await _token(auth_client)
    await auth_client.post(
        "/connections", json={"public_token": "fake-public-token"}, headers=_auth(token)
    )
    r = await auth_client.get("/portfolio", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    for field in ("reporting_currency", "total_value", "holdings", "stale"):
        assert field in body, f"missing field: {field}"
    assert isinstance(body["holdings"], list)
    tv = body["total_value"]
    assert "amount" in tv and "currency" in tv
