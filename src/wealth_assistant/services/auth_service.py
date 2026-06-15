"""Auth service: Argon2id password hashing + JWT issue/verify (T018)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.config import get_settings
from wealth_assistant.domain.errors import ConflictError, ValidationError
from wealth_assistant.persistence.models import Investor
from wealth_assistant.persistence.repositories import InvestorRepository

_ph = PasswordHasher()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def register(
        self, email: str, password: str, reporting_currency: str
    ) -> tuple[Investor, str]:
        """Create a new investor and return (investor, token). Raises ConflictError if email taken."""
        repo = InvestorRepository(self._session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            raise ConflictError(message=f"Email already registered: {email}")

        password_hash = _ph.hash(password)
        investor = Investor(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            reporting_currency=reporting_currency.upper(),
        )
        await repo.add(investor)
        token = self._issue_token(investor)
        return investor, token

    async def login(self, email: str, password: str) -> tuple[Investor, str]:
        """Verify credentials and return (investor, token). Raises ValidationError on failure."""
        repo = InvestorRepository(self._session)
        investor = await repo.get_by_email(email)
        if investor is None:
            raise ValidationError(message="Invalid credentials.")
        try:
            _ph.verify(investor.password_hash, password)
        except VerifyMismatchError:
            raise ValidationError(message="Invalid credentials.")
        token = self._issue_token(investor)
        return investor, token

    def _issue_token(self, investor: Investor) -> str:
        settings = self._settings
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=settings.jwt_expire_minutes
        )
        payload = {"sub": str(investor.id), "exp": expire}
        return jwt.encode(
            payload,
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
