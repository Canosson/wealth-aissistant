"""Shared pytest fixtures for contract and integration tests."""
from __future__ import annotations

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

import wealth_assistant.persistence.models  # noqa: F401 — registers all ORM models with Base
from wealth_assistant.persistence.db import Base

# Allow crypto to work in tests without a real 32-byte AES key
os.environ.setdefault("_ALLOW_MISSING_ENCRYPTION_KEY", "1")

# Default to in-memory SQLite (offline, fast). Set TEST_DATABASE_URL to point the
# suite at a real engine, e.g. the docker-compose Postgres:
#   postgresql+psycopg://wealth:wealth@localhost:5432/wealth_test
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
)
_IS_SQLITE = TEST_DATABASE_URL.startswith("sqlite")


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    if _IS_SQLITE:
        # StaticPool ensures all sessions share the same in-memory SQLite
        # connection, so data inserted via db_session is visible to auth_client.
        engine = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # Real server-backed engine (Postgres). NullPool gives each function-scoped
        # fixture a clean connection and avoids cross-test pool reuse.
        engine = create_async_engine(
            TEST_DATABASE_URL, echo=False, poolclass=NullPool
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def auth_client(db_engine):
    """ASGI test client backed by an isolated in-memory SQLite database."""
    from wealth_assistant.api import deps
    from wealth_assistant.api.app import create_app

    factory = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)
    app = create_app()

    async def _override_session():
        async with factory() as session, session.begin():
            yield session

    app.dependency_overrides[deps.get_session] = _override_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
