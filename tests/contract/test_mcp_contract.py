"""T054: MCP contract tests — all tool outputs validate vs OpenAPI component schemas.

Validates the JSON structure that the MCP server emits for each tool against the
Portfolio, Allocation, Performance, and Risk component schemas in openapi.yaml.
Uses jsonschema for full structural + type checking (not just field presence).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import warnings
import yaml
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from jsonschema import RefResolver, validate, ValidationError

OPENAPI_PATH = (
    Path(__file__).parents[2] / "specs" / "001-portfolio-analytics" / "contracts" / "openapi.yaml"
)


@pytest.fixture(scope="module")
def spec() -> dict:
    with OPENAPI_PATH.open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def resolver(spec: dict) -> RefResolver:
    return RefResolver.from_schema(spec)


def _validate(instance: dict, schema_name: str, spec: dict, resolver: RefResolver) -> None:
    schema = spec["components"]["schemas"][schema_name]
    validate(instance=instance, schema=schema, resolver=resolver)


# ── get_portfolio ─────────────────────────────────────────────────────────────

def test_mcp_portfolio_full_holding_validates(spec, resolver):
    sample = {
        "reporting_currency": "USD",
        "total_value": {"amount": "10000.00", "currency": "USD"},
        "stale": False,
        "last_updated": "2026-06-12T00:00:00",
        "holdings": [
            {
                "security_id": "00000000-0000-0000-0000-000000000001",
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_class": "equity",
                "sector": "Technology",
                "quantity": "10",
                "value": {"amount": "1750.00", "currency": "USD"},
                "price_available": True,
                "accounts": ["Fidelity 401k"],
            }
        ],
    }
    _validate(sample, "Portfolio", spec, resolver)


def test_mcp_portfolio_no_price_holding_validates(spec, resolver):
    """Holdings with price_available=False omit the value field."""
    sample = {
        "reporting_currency": "USD",
        "total_value": {"amount": "0.00", "currency": "USD"},
        "stale": False,
        "last_updated": None,
        "holdings": [
            {
                "security_id": "00000000-0000-0000-0000-000000000002",
                "symbol": None,
                "name": "Illiquid Fund",
                "asset_class": "fund",
                "sector": None,
                "quantity": "100",
                "price_available": False,
                "accounts": ["Schwab"],
            }
        ],
    }
    _validate(sample, "Portfolio", spec, resolver)


def test_mcp_portfolio_empty_holdings_validates(spec, resolver):
    sample = {
        "reporting_currency": "EUR",
        "total_value": {"amount": "0.00", "currency": "EUR"},
        "stale": False,
        "last_updated": None,
        "holdings": [],
    }
    _validate(sample, "Portfolio", spec, resolver)


# ── get_allocation ────────────────────────────────────────────────────────────

def test_mcp_allocation_asset_class_validates(spec, resolver):
    """Allocation slices use Money objects (not plain strings) for value."""
    sample = {
        "by": "asset_class",
        "slices": [
            {
                "label": "equity",
                "weight_pct": "75.00",
                "value": {"amount": "7500.00", "currency": "USD"},
            },
            {
                "label": "Unclassified",
                "weight_pct": "25.00",
                "value": {"amount": "2500.00", "currency": "USD"},
            },
        ],
    }
    _validate(sample, "Allocation", spec, resolver)


def test_mcp_allocation_empty_slices_validates(spec, resolver):
    sample = {"by": "sector", "slices": []}
    _validate(sample, "Allocation", spec, resolver)


# ── get_performance ───────────────────────────────────────────────────────────

def test_mcp_performance_normal_validates(spec, resolver):
    """Performance Money fields are objects with amount+currency, not plain strings."""
    sample = {
        "period": "1M",
        "return_pct": "5.23",
        "gain_loss": {"amount": "523.00", "currency": "USD"},
        "start_value": {"amount": "10000.00", "currency": "USD"},
        "end_value": {"amount": "10523.00", "currency": "USD"},
        "insufficient_history": False,
    }
    _validate(sample, "Performance", spec, resolver)


def test_mcp_performance_insufficient_history_validates(spec, resolver):
    sample = {
        "period": "1Y",
        "return_pct": "0.00",
        "gain_loss": {"amount": "0.00", "currency": "USD"},
        "start_value": {"amount": "0.00", "currency": "USD"},
        "end_value": {"amount": "0.00", "currency": "USD"},
        "insufficient_history": True,
    }
    _validate(sample, "Performance", spec, resolver)


def test_mcp_performance_negative_return_validates(spec, resolver):
    sample = {
        "period": "3M",
        "return_pct": "-12.50",
        "gain_loss": {"amount": "-1250.00", "currency": "EUR"},
        "start_value": {"amount": "10000.00", "currency": "EUR"},
        "end_value": {"amount": "8750.00", "currency": "EUR"},
        "insufficient_history": False,
    }
    _validate(sample, "Performance", spec, resolver)


# ── get_risk ──────────────────────────────────────────────────────────────────

def test_mcp_risk_with_flags_validates(spec, resolver):
    """Risk uses 'concentration' (not 'concentration_flags'), nested diversification,
    and 'annualized_volatility_pct' (not 'volatility_pct')."""
    sample = {
        "hhi": "3025.00",
        "concentration": [
            {
                "security_id": "00000000-0000-0000-0000-000000000001",
                "name": "Apple Inc.",
                "weight_pct": "55.00",
                "flagged": True,
            }
        ],
        "annualized_volatility_pct": "18.50",
        "diversification": {
            "asset_class_count": 2,
            "sector_count": 3,
            "summary": "Moderately diversified across 2 asset classes.",
        },
    }
    _validate(sample, "Risk", spec, resolver)


def test_mcp_risk_insufficient_history_validates(spec, resolver):
    """Null annualized_volatility_pct is valid when history is insufficient."""
    sample = {
        "hhi": "0.00",
        "concentration": [],
        "annualized_volatility_pct": None,
        "diversification": {
            "asset_class_count": 0,
            "sector_count": 0,
            "summary": "No priced holdings to assess.",
        },
    }
    _validate(sample, "Risk", spec, resolver)


def test_mcp_risk_no_concentration_flags_validates(spec, resolver):
    sample = {
        "hhi": "1250.00",
        "concentration": [],
        "annualized_volatility_pct": "12.30",
        "diversification": {
            "asset_class_count": 4,
            "sector_count": 6,
            "summary": "Diversified across 4 asset classes.",
        },
    }
    _validate(sample, "Risk", spec, resolver)


# ── Negative: old MCP format must FAIL validation ─────────────────────────────

def test_old_mcp_allocation_string_value_is_invalid(spec, resolver):
    """Old format used plain string for value — must not pass schema."""
    old_format = {
        "by": "asset_class",
        "slices": [{"label": "equity", "weight_pct": "100.00", "value": "10000.00"}],
    }
    with pytest.raises(ValidationError):
        _validate(old_format, "Allocation", spec, resolver)


def test_old_mcp_risk_concentration_flags_key_is_invalid(spec, resolver):
    """Old format used 'concentration_flags' key — 'concentration' is required."""
    old_format = {
        "hhi": "3025.00",
        "concentration_flags": [{"security_id": "x", "symbol": "AAPL", "weight_pct": "55.00"}],
        "diversification": {"asset_class_count": 1, "sector_count": 1, "summary": "test"},
    }
    with pytest.raises(ValidationError):
        _validate(old_format, "Risk", spec, resolver)
