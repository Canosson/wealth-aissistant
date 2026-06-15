"""SQLAlchemy 2.0 session factory, declarative base, and unit-of-work (T012)."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from wealth_assistant.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _build_engine() -> object:
    settings = get_settings()
    # psycopg3 async: driver string is already correct for async use
    return create_async_engine(str(settings.database_url), echo=False, pool_pre_ping=True)


_engine = _build_engine()

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,  # type: ignore[arg-type]
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def unit_of_work() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager providing a transactional unit-of-work session."""
    async with AsyncSessionFactory() as session, session.begin():
        yield session
