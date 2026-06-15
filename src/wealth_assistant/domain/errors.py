"""Base domain error types (Principle VI — explicit errors, no silent failure)."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainError(Exception):
    """Root for all domain-level errors. Always carry a correlation_id."""

    message: str
    correlation_id: UUID = field(default_factory=uuid4)

    def __str__(self) -> str:
        return f"[{self.correlation_id}] {self.message}"


@dataclass(frozen=True)
class NotFoundError(DomainError):
    """Raised when a requested resource does not exist."""


@dataclass(frozen=True)
class AuthorizationError(DomainError):
    """Raised when an investor attempts to access another investor's resource."""


@dataclass(frozen=True)
class ValidationError(DomainError):
    """Raised when domain validation fails (distinct from HTTP-layer validation)."""


@dataclass(frozen=True)
class ConflictError(DomainError):
    """Raised when a state conflict prevents the requested operation."""
