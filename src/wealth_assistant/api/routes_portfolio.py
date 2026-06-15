"""Connection + portfolio routes (T036 US1, T045 US2)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from wealth_assistant.aggregation.port import ProviderUnavailableError
from wealth_assistant.analytics.allocation import allocate
from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
from wealth_assistant.analytics.risk import ConcentrationFlag, compute_risk
from wealth_assistant.api.deps import InvestorDep, SessionDep
from wealth_assistant.api.schemas import (
    ConnectionResponse,
    ExchangeRequest,
    HoldingResponse,
    LinkTokenResponse,
    MoneySchema,
    PortfolioResponse,
)
from wealth_assistant.domain.errors import NotFoundError
from wealth_assistant.persistence.repositories import SnapshotRepository
from wealth_assistant.services.connection_service import ConnectionService
from wealth_assistant.services.portfolio_service import PortfolioService


# ── US2 response schemas ─────────────────────────────────────────────────────

class AllocationSliceSchema(BaseModel):
    label: str
    weight_pct: str
    value: MoneySchema


class AllocationSchema(BaseModel):
    by: str
    slices: list[AllocationSliceSchema]


class PerformanceSchema(BaseModel):
    period: str
    return_pct: str
    gain_loss: MoneySchema
    start_value: MoneySchema
    end_value: MoneySchema
    insufficient_history: bool


class ConcentrationItemSchema(BaseModel):
    security_id: str
    name: str | None
    weight_pct: str
    flagged: bool


class DiversificationSchema(BaseModel):
    asset_class_count: int
    sector_count: int
    summary: str


class RiskSchema(BaseModel):
    hhi: str
    concentration: list[ConcentrationItemSchema]
    annualized_volatility_pct: str | None
    insufficient_history: bool
    diversification: DiversificationSchema


router = APIRouter(tags=["portfolio"])


def _conn_schema(conn) -> ConnectionResponse:
    return ConnectionResponse(
        id=conn.id,
        provider=conn.provider,
        institution_name=conn.institution_name,
        status=conn.status.value,
        last_synced_at=conn.last_synced_at,
        error_detail=conn.error_detail,
    )


@router.post("/connections/link-token", response_model=LinkTokenResponse)
async def create_link_token(investor: InvestorDep, session: SessionDep) -> LinkTokenResponse:
    svc = ConnectionService(session)
    token = await svc.create_link_token(investor.id)
    return LinkTokenResponse(link_token=token)


@router.post("/connections", status_code=status.HTTP_201_CREATED, response_model=ConnectionResponse)
async def exchange_connection(
    body: ExchangeRequest, investor: InvestorDep, session: SessionDep
) -> ConnectionResponse:
    svc = ConnectionService(session)
    conn = await svc.exchange_and_link(investor.id, body.public_token)
    return _conn_schema(conn)


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections(investor: InvestorDep, session: SessionDep) -> list[ConnectionResponse]:
    svc = ConnectionService(session)
    return [_conn_schema(c) for c in await svc.list_connections(investor.id)]


@router.post("/connections/{connection_id}/refresh", response_model=ConnectionResponse)
async def refresh_connection(
    connection_id: uuid.UUID, investor: InvestorDep, session: SessionDep
) -> ConnectionResponse:
    svc = ConnectionService(session)
    try:
        conn = await svc.refresh_connection(connection_id, investor.id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Connection not found"})
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=409, detail={"code": "provider_unavailable", "message": str(exc)})
    return _conn_schema(conn)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID, investor: InvestorDep, session: SessionDep
) -> Response:
    svc = ConnectionService(session)
    try:
        await svc.unlink(connection_id, investor.id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Connection not found"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(investor: InvestorDep, session: SessionDep) -> PortfolioResponse:
    svc = PortfolioService(session)
    portfolio = await svc.get_portfolio(investor.id)
    holdings = [
        HoldingResponse(
            security_id=h.security_id,
            symbol=h.symbol,
            name=h.name,
            asset_class=h.asset_class,
            sector=h.sector,
            quantity=str(h.quantity),
            value=MoneySchema(
                amount=str(h.value_amount.quantize(Decimal("0.01"))),
                currency=portfolio.reporting_currency,
            ) if h.price_available and h.value_amount is not None else None,
            price_available=h.price_available,
            accounts=h.accounts,
        )
        for h in portfolio.holdings
    ]
    total = portfolio.total_value.quantize(Decimal("0.01"))
    return PortfolioResponse(
        reporting_currency=portfolio.reporting_currency,
        total_value=MoneySchema(amount=str(total), currency=portfolio.reporting_currency),
        last_updated=portfolio.last_updated,
        stale=portfolio.stale,
        holdings=holdings,
    )


@router.get("/portfolio/allocation", response_model=AllocationSchema)
async def get_allocation(
    investor: InvestorDep,
    session: SessionDep,
    by: Literal["asset_class", "sector", "account"] = Query(default="asset_class"),
) -> AllocationSchema:
    portfolio = await PortfolioService(session).get_portfolio(investor.id)
    result = allocate(portfolio, by=by)
    return AllocationSchema(
        by=result.by,
        slices=[
            AllocationSliceSchema(
                label=s.label,
                weight_pct=str(s.weight_pct),
                value=MoneySchema(amount=str(s.value), currency=portfolio.reporting_currency),
            )
            for s in result.slices
        ],
    )


@router.get("/portfolio/performance", response_model=PerformanceSchema)
async def get_performance(
    investor: InvestorDep,
    session: SessionDep,
    period: Literal["1M", "3M", "6M", "1Y", "YTD", "ALL"] = Query(default="1M"),
) -> PerformanceSchema:
    snap_repo = SnapshotRepository(session)
    raw_snaps = await snap_repo.list_by_investor(investor.id)
    investor_obj = await session.get(
        __import__("wealth_assistant.persistence.models", fromlist=["Investor"]).Investor,
        investor.id,
    )
    currency = investor_obj.reporting_currency if investor_obj else "USD"

    points = [
        SnapshotPoint(
            as_of=s.as_of,
            total_value=Decimal(str(s.total_value_amount)),
            net_external_flow=Decimal(str(s.net_external_flow_amount)),
        )
        for s in raw_snaps
    ]
    result = compute_performance(points, period=period, reporting_currency=currency, as_of_date=date.today())

    money = MoneySchema(amount="0.00", currency=currency)
    return PerformanceSchema(
        period=result.period,
        return_pct=str(result.return_pct),
        gain_loss=MoneySchema(amount=str(result.gain_loss), currency=currency),
        start_value=MoneySchema(amount=str(result.start_value), currency=currency),
        end_value=MoneySchema(amount=str(result.end_value), currency=currency),
        insufficient_history=result.insufficient_history,
    )


@router.get("/portfolio/risk", response_model=RiskSchema)
async def get_risk(investor: InvestorDep, session: SessionDep) -> RiskSchema:
    portfolio = await PortfolioService(session).get_portfolio(investor.id)
    snap_repo = SnapshotRepository(session)
    raw_snaps = await snap_repo.list_by_investor(investor.id)
    points = [
        SnapshotPoint(
            as_of=s.as_of,
            total_value=Decimal(str(s.total_value_amount)),
            net_external_flow=Decimal(str(s.net_external_flow_amount)),
        )
        for s in raw_snaps
    ]
    result = compute_risk(portfolio, points)
    return RiskSchema(
        hhi=str(result.hhi),
        concentration=[
            ConcentrationItemSchema(
                security_id=str(f.security_id),
                name=f.name,
                weight_pct=str(f.weight_pct),
                flagged=True,
            )
            for f in result.concentration_flags
        ],
        annualized_volatility_pct=str(result.volatility_pct) if result.volatility_pct is not None else None,
        insufficient_history=result.insufficient_history,
        diversification=DiversificationSchema(
            asset_class_count=result.asset_class_count,
            sector_count=result.sector_count,
            summary=result.diversification_summary,
        ),
    )
