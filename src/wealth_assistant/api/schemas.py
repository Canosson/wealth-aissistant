"""Pydantic request/response schemas matching openapi.yaml contracts."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    reporting_currency: str = Field(min_length=3, max_length=3)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    investor_id: uuid.UUID


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    code: str
    message: str
    correlation_id: str | None = None


# ── Privacy ───────────────────────────────────────────────────────────────────

class ExportResponse(BaseModel):
    investor_id: uuid.UUID
    email: str
    reporting_currency: str
    created_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


# ── Connections ───────────────────────────────────────────────────────────────

class ConnectionResponse(BaseModel):
    id: uuid.UUID
    provider: str
    institution_name: str | None
    status: str
    last_synced_at: datetime | None = None
    error_detail: str | None = None


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangeRequest(BaseModel):
    public_token: str


# ── Portfolio (US1) ───────────────────────────────────────────────────────────

class MoneySchema(BaseModel):
    amount: str
    currency: str


class HoldingResponse(BaseModel):
    security_id: uuid.UUID
    symbol: str | None = None
    name: str
    asset_class: str
    sector: str | None = None
    quantity: str
    value: MoneySchema | None = None
    price_available: bool
    accounts: list[str] = Field(default_factory=list)


class PortfolioResponse(BaseModel):
    reporting_currency: str
    total_value: MoneySchema
    last_updated: datetime | None = None
    stale: bool = False
    holdings: list[HoldingResponse] = Field(default_factory=list)


# ── Allocation (US2) ──────────────────────────────────────────────────────────

class AllocationSlice(BaseModel):
    label: str
    weight_pct: str
    value: MoneySchema


class AllocationResponse(BaseModel):
    by: str
    slices: list[AllocationSlice] = Field(default_factory=list)


# ── Performance (US2) ─────────────────────────────────────────────────────────

class PerformanceResponse(BaseModel):
    period: str
    return_pct: str
    gain_loss: MoneySchema
    start_value: MoneySchema
    end_value: MoneySchema
    insufficient_history: bool = False


# ── Risk (US3) ────────────────────────────────────────────────────────────────

class ConcentrationItem(BaseModel):
    security_id: uuid.UUID
    name: str
    weight_pct: str
    flagged: bool


class DiversificationSummary(BaseModel):
    asset_class_count: int
    sector_count: int
    summary: str


class RiskResponse(BaseModel):
    concentration: list[ConcentrationItem] = Field(default_factory=list)
    hhi: str
    annualized_volatility_pct: str | None = None
    diversification: DiversificationSummary
