"""Connection service: link-token, exchange, list, refresh, unlink (T034)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.aggregation.factory import get_provider
from wealth_assistant.aggregation.port import ProviderConnection, ProviderUnavailableError
from wealth_assistant.persistence.crypto import decrypt, encrypt
from wealth_assistant.persistence.models import (
    Account,
    AccountType,
    AssetClass,
    ConnectionStatus,
    Holding,
    LinkedAccountConnection,
    Price,
    Security,
)
from wealth_assistant.persistence.repositories import (
    AccountRepository,
    ConnectionRepository,
    HoldingRepository,
    PriceRepository,
    SecurityRepository,
)


class ConnectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._provider = get_provider()

    async def create_link_token(self, investor_id: uuid.UUID) -> str:
        link = await self._provider.create_link_token(investor_id)
        return link.link_token

    async def exchange_and_link(
        self, investor_id: uuid.UUID, public_token: str
    ) -> LinkedAccountConnection:
        provider_conn = await self._provider.exchange_public_token(public_token)
        provider_name = "plaid" if "fake" not in provider_conn.provider_item_id else "fake"
        conn = LinkedAccountConnection(
            investor_id=investor_id,
            provider=provider_name,
            provider_item_id=provider_conn.provider_item_id,
            institution_name=provider_conn.institution_name,
            status=ConnectionStatus.pending,
            encrypted_access_token=encrypt(provider_conn.access_ref),
        )
        self._session.add(conn)
        await self._session.flush()
        await self._do_sync(conn, provider_conn)
        return conn

    async def list_connections(
        self, investor_id: uuid.UUID
    ) -> list[LinkedAccountConnection]:
        repo = ConnectionRepository(self._session)
        return list(await repo.list_by_investor(investor_id))

    async def refresh_connection(
        self, connection_id: uuid.UUID, investor_id: uuid.UUID
    ) -> LinkedAccountConnection:
        repo = ConnectionRepository(self._session)
        conn = await repo.get_by_id(connection_id, investor_id)
        if conn is None:
            from wealth_assistant.domain.errors import NotFoundError
            raise NotFoundError(entity="connection", entity_id=connection_id)

        access_ref = decrypt(conn.encrypted_access_token or "")
        provider_conn = ProviderConnection(
            provider_item_id=conn.provider_item_id,
            institution_name=conn.institution_name or "",
            access_ref=access_ref,
        )
        try:
            await self._do_sync(conn, provider_conn)
        except ProviderUnavailableError:
            conn.status = ConnectionStatus.error
            raise
        return conn

    async def unlink(self, connection_id: uuid.UUID, investor_id: uuid.UUID) -> None:
        repo = ConnectionRepository(self._session)
        conn = await repo.get_by_id(connection_id, investor_id)
        if conn is None:
            from wealth_assistant.domain.errors import NotFoundError
            raise NotFoundError(entity="connection", entity_id=connection_id)
        hold_repo = HoldingRepository(self._session)
        await hold_repo.delete_by_connection(connection_id)
        await repo.delete(conn)

    async def _do_sync(
        self, conn: LinkedAccountConnection, provider_conn: ProviderConnection
    ) -> None:
        acct_repo = AccountRepository(self._session)
        sec_repo = SecurityRepository(self._session)
        hold_repo = HoldingRepository(self._session)
        price_repo = PriceRepository(self._session)

        provider_accounts = await self._provider.fetch_accounts(provider_conn)
        provider_holdings = await self._provider.fetch_holdings(provider_conn)

        acct_map: dict[str, Account] = {}
        for pa in provider_accounts:
            acct = await acct_repo.get_by_provider_account_id(conn.id, pa.provider_account_id)
            if acct is None:
                acct = Account(
                    connection_id=conn.id,
                    provider_account_id=pa.provider_account_id,
                    name=pa.name,
                    type=(
                        AccountType(pa.type)
                        if pa.type in AccountType._value2member_map_
                        else AccountType.other
                    ),
                    currency=pa.currency,
                    cash_balance_amount=pa.cash_balance,
                    cash_balance_currency=pa.currency,
                )
                self._session.add(acct)
                await self._session.flush()
            acct_map[pa.provider_account_id] = acct

        await hold_repo.delete_by_connection(conn.id)
        await self._session.flush()

        prices_queued: set[tuple[uuid.UUID, object]] = set()
        for ph in provider_holdings:
            ps = ph.security
            symbol = ps.symbol or ""
            sec = await sec_repo.get_by_symbol_and_currency(symbol, ps.currency)
            if sec is None:
                asset_cls = (
                    AssetClass(ps.asset_class)
                    if ps.asset_class in AssetClass._value2member_map_
                    else AssetClass.unclassified
                )
                sec = Security(
                    symbol=ps.symbol,
                    name=ps.name,
                    asset_class=asset_cls,
                    sector=ps.sector,
                    currency=ps.currency,
                )
                self._session.add(sec)
                await self._session.flush()

            acct = acct_map.get(ph.provider_account_id)
            if acct is None:
                continue

            holding = Holding(
                account_id=acct.id,
                security_id=sec.id,
                quantity=ph.quantity,
                cost_basis_amount=ph.cost_basis,
                cost_basis_currency=ps.currency if ph.cost_basis else None,
                as_of=datetime.combine(ph.as_of, datetime.min.time()).replace(tzinfo=UTC),
            )
            self._session.add(holding)

            if ph.price is not None:
                price_key = (sec.id, ph.as_of)
                if price_key not in prices_queued:
                    existing = await price_repo.get_latest(sec.id)
                    if existing is None or existing.as_of < ph.as_of:
                        self._session.add(Price(
                            security_id=sec.id,
                            price_amount=ph.price,
                            price_currency=ps.currency,
                            as_of=ph.as_of,
                        ))
                        prices_queued.add(price_key)

        conn.status = ConnectionStatus.active
        conn.last_synced_at = datetime.now(UTC)
