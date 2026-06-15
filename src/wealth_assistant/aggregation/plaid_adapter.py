"""Plaid sandbox adapter (T022). Targets Plaid Investments product in sandbox.

Only used when AGGREGATION_PROVIDER=plaid. All tests use FakeAggregationProvider.
Requires PLAID_CLIENT_ID + PLAID_SECRET env vars.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products

from wealth_assistant.aggregation.port import (
    LinkToken,
    ProviderAccount,
    ProviderConnection,
    ProviderHolding,
    ProviderSecurity,
    ProviderUnavailableError,
)
from wealth_assistant.config import get_settings

_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
    # "development" was removed in plaid-python 40.0.0; unknown keys fall back to Sandbox via .get() default
}


def _make_client() -> plaid_api.PlaidApi:
    settings = get_settings()
    if not settings.plaid_client_id or not settings.plaid_secret:
        raise RuntimeError("PLAID_CLIENT_ID and PLAID_SECRET must be set.")
    configuration = plaid.Configuration(
        host=_ENV_MAP.get(settings.plaid_env, plaid.Environment.Sandbox),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret.get_secret_value(),
        },
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


class PlaidAdapter:
    """Plaid sandbox adapter — wraps the Plaid Python SDK."""

    def __init__(self) -> None:
        self._client = _make_client()

    async def create_link_token(self, investor_id: uuid.UUID) -> LinkToken:
        try:
            req = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=str(investor_id)),
                client_name="Wealth AIssistant",
                products=[Products("investments")],
                country_codes=[CountryCode("US")],
                language="en",
            )
            resp = self._client.link_token_create(req)
            return LinkToken(link_token=resp.link_token)
        except Exception as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    async def exchange_public_token(self, public_token: str) -> ProviderConnection:
        try:
            req = ItemPublicTokenExchangeRequest(public_token=public_token)
            resp = self._client.item_public_token_exchange(req)
            return ProviderConnection(
                provider_item_id=resp.item_id,
                institution_name="Unknown Institution",
                access_ref=resp.access_token,
            )
        except Exception as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    async def fetch_accounts(self, connection: ProviderConnection) -> list[ProviderAccount]:
        try:
            resp = self._client.accounts_get(
                AccountsGetRequest(access_token=connection.access_ref)
            )
            return [
                ProviderAccount(
                    provider_account_id=a.account_id,
                    name=a.name or a.official_name or "Unknown",
                    type=_map_account_type(str(a.type)),
                    currency=a.balances.iso_currency_code or "USD",
                    cash_balance=(
                        Decimal(str(a.balances.current))
                        if a.balances.current is not None
                        else None
                    ),
                )
                for a in resp.accounts
            ]
        except Exception as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    async def fetch_holdings(self, connection: ProviderConnection) -> list[ProviderHolding]:
        try:
            resp = self._client.investments_holdings_get(
                InvestmentsHoldingsGetRequest(access_token=connection.access_ref)
            )
            sec_map = {s.security_id: s for s in (resp.securities or [])}
            holdings: list[ProviderHolding] = []
            for h in resp.holdings or []:
                sec = sec_map.get(h.security_id)
                if sec is None:
                    continue
                holdings.append(
                    ProviderHolding(
                        provider_account_id=h.account_id,
                        security=ProviderSecurity(
                            symbol=sec.ticker_symbol,
                            name=sec.name or "Unknown",
                            asset_class=_map_asset_class(str(sec.type or "")),
                            sector=None,
                            currency=sec.iso_currency_code or "USD",
                        ),
                        quantity=Decimal(str(h.quantity)),
                        cost_basis=Decimal(str(h.cost_basis)) if h.cost_basis else None,
                        price=Decimal(str(h.institution_price)) if h.institution_price else None,
                        as_of=date.today(),
                    )
                )
            return holdings
        except Exception as exc:
            raise ProviderUnavailableError(str(exc)) from exc


def _map_account_type(plaid_type: str) -> str:
    return {"investment": "brokerage", "depository": "cash"}.get(plaid_type, "other")


def _map_asset_class(plaid_type: str) -> str:
    return {
        "equity": "equity",
        "etf": "etf",
        "mutual fund": "fund",
        "fixed income": "fixed_income",
        "cash": "cash",
        "cryptocurrency": "crypto",
    }.get(plaid_type.lower(), "other")
