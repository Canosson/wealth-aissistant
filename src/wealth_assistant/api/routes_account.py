"""Account lifecycle routes: data export + self-deletion (T026, FR-017/018)."""
from __future__ import annotations

from fastapi import APIRouter, Response, status

from wealth_assistant.api.deps import InvestorDep, SessionDep
from wealth_assistant.services.account_service import AccountService

router = APIRouter(tags=["account"])


@router.get("/me/export")
async def export_investor_data(
    investor: InvestorDep,
    session: SessionDep,
) -> dict:
    svc = AccountService(session)
    return await svc.export_investor_data(investor)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    investor: InvestorDep,
    session: SessionDep,
) -> Response:
    svc = AccountService(session)
    await svc.delete_investor(investor.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
