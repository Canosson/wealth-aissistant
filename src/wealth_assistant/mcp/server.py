"""Read-only MCP server exposing portfolio tools (T037).

Each tool call requires a `token` (JWT) argument; the server decodes it to
identify the investor, opens a DB session, and delegates to the same service
methods the REST API uses — no business logic here.

Run: python -m wealth_assistant.mcp.server  (stdio transport)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal

import jwt as pyjwt
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from wealth_assistant.config import get_settings
from wealth_assistant.persistence.db import AsyncSessionFactory
from wealth_assistant.services.portfolio_service import PortfolioService

_app = Server("wealth-assistant-portfolio")
_settings = get_settings()


def _investor_id(token: str) -> uuid.UUID:
    payload = pyjwt.decode(
        token,
        _settings.jwt_secret.get_secret_value(),
        algorithms=[_settings.jwt_algorithm],
    )
    return uuid.UUID(payload["sub"])


@_app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_portfolio",
            description="Return the investor's consolidated portfolio in reporting currency.",
            inputSchema={
                "type": "object",
                "properties": {"token": {"type": "string", "description": "Investor JWT"}},
                "required": ["token"],
            },
        ),
        Tool(
            name="get_allocation",
            description="Return portfolio allocation breakdown by asset_class, sector, or account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "Investor JWT"},
                    "by": {"type": "string", "enum": ["asset_class", "sector", "account"], "default": "asset_class"},
                },
                "required": ["token"],
            },
        ),
        Tool(
            name="get_performance",
            description="Return period return and gain/loss from portfolio snapshot history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "Investor JWT"},
                    "period": {"type": "string", "enum": ["1M", "3M", "6M", "1Y", "YTD", "ALL"], "default": "1M"},
                },
                "required": ["token"],
            },
        ),
        Tool(
            name="get_risk",
            description="Return concentration, HHI, volatility, and diversification summary.",
            inputSchema={
                "type": "object",
                "properties": {"token": {"type": "string", "description": "Investor JWT"}},
                "required": ["token"],
            },
        ),
    ]


@_app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in {"get_portfolio", "get_allocation", "get_performance", "get_risk"}:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    try:
        investor_id = _investor_id(arguments.get("token", ""))
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    if name == "get_allocation":
        return await _handle_allocation(investor_id, arguments)
    if name == "get_performance":
        return await _handle_performance(investor_id, arguments)
    if name == "get_risk":
        return await _handle_risk(investor_id)

    async with AsyncSessionFactory() as session:
        portfolio = await PortfolioService(session).get_portfolio(investor_id)

    out = {
        "reporting_currency": portfolio.reporting_currency,
        "total_value": {
            "amount": str(portfolio.total_value.quantize(Decimal("0.01"))),
            "currency": portfolio.reporting_currency,
        },
        "stale": portfolio.stale,
        "last_updated": portfolio.last_updated.isoformat() if portfolio.last_updated else None,
        "holdings": [
            {
                "security_id": str(h.security_id),
                "symbol": h.symbol,
                "name": h.name,
                "asset_class": h.asset_class,
                "quantity": str(h.quantity),
                "value": {
                    "amount": str(h.value_amount.quantize(Decimal("0.01"))),
                    "currency": portfolio.reporting_currency,
                } if h.price_available and h.value_amount is not None else None,
                "price_available": h.price_available,
                "accounts": h.accounts,
            }
            for h in portfolio.holdings
        ],
    }
    return [TextContent(type="text", text=json.dumps(out))]


async def _handle_allocation(investor_id: uuid.UUID, arguments: dict) -> list[TextContent]:
    from wealth_assistant.analytics.allocation import allocate
    async with AsyncSessionFactory() as session:
        portfolio = await PortfolioService(session).get_portfolio(investor_id)
    by = arguments.get("by", "asset_class")
    result = allocate(portfolio, by=by)
    currency = portfolio.reporting_currency
    out = {
        "by": result.by,
        "slices": [
            {
                "label": s.label,
                "weight_pct": str(s.weight_pct),
                "value": {"amount": str(s.value), "currency": currency},
            }
            for s in result.slices
        ],
    }
    return [TextContent(type="text", text=json.dumps(out))]


async def _handle_performance(investor_id: uuid.UUID, arguments: dict) -> list[TextContent]:
    import datetime
    from decimal import Decimal
    from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
    from wealth_assistant.persistence.repositories import SnapshotRepository
    from wealth_assistant.persistence.models import Investor
    period = arguments.get("period", "1M")
    async with AsyncSessionFactory() as session:
        snap_repo = SnapshotRepository(session)
        raw = await snap_repo.list_by_investor(investor_id)
        inv = await session.get(Investor, investor_id)
        currency = inv.reporting_currency if inv else "USD"
    points = [
        SnapshotPoint(
            as_of=s.as_of,
            total_value=Decimal(str(s.total_value_amount)),
            net_external_flow=Decimal(str(s.net_external_flow_amount)),
        )
        for s in raw
    ]
    result = compute_performance(points, period=period, reporting_currency=currency, as_of_date=datetime.date.today())
    def _money(amount: Decimal, cur: str) -> dict:
        return {"amount": str(amount), "currency": cur}

    out = {
        "period": result.period,
        "return_pct": str(result.return_pct),
        "gain_loss": _money(result.gain_loss, currency),
        "start_value": _money(result.start_value, currency),
        "end_value": _money(result.end_value, currency),
        "insufficient_history": result.insufficient_history,
    }
    return [TextContent(type="text", text=json.dumps(out))]


async def _handle_risk(investor_id: uuid.UUID) -> list[TextContent]:
    from wealth_assistant.analytics.risk import compute_risk
    from wealth_assistant.analytics.performance import SnapshotPoint
    from wealth_assistant.persistence.repositories import SnapshotRepository
    async with AsyncSessionFactory() as session:
        portfolio = await PortfolioService(session).get_portfolio(investor_id)
        snap_repo = SnapshotRepository(session)
        raw = await snap_repo.list_by_investor(investor_id)
    points = [
        SnapshotPoint(
            as_of=s.as_of,
            total_value=Decimal(str(s.total_value_amount)),
            net_external_flow=Decimal(str(s.net_external_flow_amount)),
        )
        for s in raw
    ]
    result = compute_risk(portfolio, points)
    out = {
        "hhi": str(result.hhi),
        "concentration": [
            {
                "security_id": str(f.security_id),
                "name": f.name,
                "weight_pct": str(f.weight_pct),
                "flagged": True,
            }
            for f in result.concentration_flags
        ],
        "annualized_volatility_pct": str(result.volatility_pct) if result.volatility_pct is not None else None,
        "insufficient_history": result.insufficient_history,
        "diversification": {
            "asset_class_count": result.asset_class_count,
            "sector_count": result.sector_count,
            "summary": result.diversification_summary,
        },
    }
    return [TextContent(type="text", text=json.dumps(out))]


if __name__ == "__main__":
    asyncio.run(stdio_server(_app))
