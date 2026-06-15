"""Contract tests: POST /auth/register and POST /auth/login vs OpenAPI (T017).

Written first (TDD RED). Will fail until T018/T019/T028 implement the auth
service, routes, and app factory.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_returns_201_with_token(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "supersecret1234",
            "reporting_currency": "USD",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "token" in body
    assert "investor_id" in body
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 0


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(auth_client: AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "supersecret1234",
        "reporting_currency": "USD",
    }
    r1 = await auth_client.post("/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await auth_client.post("/auth/register", json=payload)
    assert r2.status_code == 409
    body = r2.json()
    assert "code" in body
    assert "message" in body


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_200(auth_client: AsyncClient) -> None:
    email = "login@example.com"
    password = "supersecret1234"
    reg = await auth_client.post(
        "/auth/register",
        json={"email": email, "password": password, "reporting_currency": "EUR"},
    )
    assert reg.status_code == 201

    resp = await auth_client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "investor_id" in body


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(auth_client: AsyncClient) -> None:
    email = "badpass@example.com"
    await auth_client.post(
        "/auth/register",
        json={"email": email, "password": "supersecret1234", "reporting_currency": "USD"},
    )
    resp = await auth_client.post(
        "/auth/login", json={"email": email, "password": "wrongpassword1234"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert "code" in body
    assert "message" in body


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "supersecret1234"},
    )
    assert resp.status_code == 401
