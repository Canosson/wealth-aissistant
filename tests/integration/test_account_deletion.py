"""Integration test: account deletion erases all investor data (T027, SC-009).

Verifies:
  1. DELETE /me succeeds (204)
  2. Data is fully erased — re-registration with the same email works (proves
     no soft-delete / unique-email constraint collision)
  3. The old JWT is rejected after deletion
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

_EMAIL = "erasure@example.com"
_PASSWORD = "s3cure-passw0rd!"
_PAYLOAD = {"email": _EMAIL, "password": _PASSWORD, "reporting_currency": "USD"}


@pytest.mark.asyncio
async def test_account_deletion_erases_all_data(auth_client: AsyncClient) -> None:
    # Register
    reg = await auth_client.post("/auth/register", json=_PAYLOAD)
    assert reg.status_code == 201
    token = reg.json()["token"]

    # Delete
    del_resp = await auth_client.delete("/me", headers={"Authorization": f"Bearer {token}"})
    assert del_resp.status_code == 204

    # Re-register same email → must succeed (no uniqueness collision)
    re_reg = await auth_client.post("/auth/register", json=_PAYLOAD)
    assert re_reg.status_code == 201, (
        "Re-registration should succeed after full erasure; "
        "got conflict which indicates soft-delete or incomplete cascade"
    )

    # Old JWT rejected
    old_export = await auth_client.get("/me/export", headers={"Authorization": f"Bearer {token}"})
    assert old_export.status_code == 401
