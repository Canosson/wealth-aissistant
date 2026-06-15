"""FastAPI dependency injection: DB session and authenticated investor (T019)."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.config import get_settings
from wealth_assistant.persistence.db import AsyncSessionFactory
from wealth_assistant.persistence.models import Investor
from wealth_assistant.persistence.repositories import InvestorRepository

_bearer = HTTPBearer()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async DB session. Overridden in tests."""
    async with AsyncSessionFactory() as session, session.begin():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_investor(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Investor:
    """Decode JWT and return the authenticated Investor (FR-013)."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        investor_id = uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid or expired token."},
        )

    repo = InvestorRepository(session)
    investor = await repo.get_by_id(investor_id)
    if investor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "investor_not_found", "message": "Investor not found."},
        )
    return investor


InvestorDep = Annotated[Investor, Depends(get_current_investor)]
