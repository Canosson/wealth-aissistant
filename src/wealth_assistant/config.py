"""Environment-driven settings (Principle VI — no hardcoded values)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://localhost:5432/wealth",
        description="SQLAlchemy-compatible PostgreSQL URL",
    )

    # Aggregation provider
    aggregation_provider: str = Field(
        default="fake",
        description="Which provider adapter to use: 'fake' or 'plaid'",
    )

    # Plaid (only required when aggregation_provider == 'plaid')
    plaid_client_id: str | None = Field(default=None)
    plaid_secret: SecretStr | None = Field(default=None)
    plaid_env: str = Field(default="sandbox")

    # Auth
    jwt_secret: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        description="Secret key for signing JWTs — MUST be overridden in production",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60 * 8)  # 8 hours

    # Encryption-at-rest (AES-256 key, base64-encoded, 32 bytes decoded)
    encryption_key: SecretStr | None = Field(
        default=None,
        description="Base64-encoded 32-byte AES key for PII/credential encryption",
    )

    # Observability
    json_logs: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Scheduler — disabled until the snapshot pipeline is validated end-to-end
    snapshot_job_enabled: bool = Field(
        default=False,
        description="Register the weekly snapshot job. Keep False until snapshots are verified.",
    )

    # Analytics thresholds
    concentration_threshold_pct: int = Field(
        default=20,
        description="Holding weight >= this value triggers a concentration flag",
    )
    volatility_min_weeks: int = Field(
        default=30,
        description="Minimum weekly snapshots required to compute annualized volatility",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
