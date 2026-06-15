"""Config-driven aggregation provider factory (T023)."""
from __future__ import annotations

from wealth_assistant.aggregation.port import AggregationProvider
from wealth_assistant.config import get_settings


def get_provider() -> AggregationProvider:
    """Return the configured AggregationProvider adapter."""
    settings = get_settings()
    provider = settings.aggregation_provider.lower()
    if provider == "fake":
        from wealth_assistant.aggregation.fake import FakeAggregationProvider
        return FakeAggregationProvider()  # type: ignore[return-value]
    if provider == "plaid":
        from wealth_assistant.aggregation.plaid_adapter import PlaidAdapter
        return PlaidAdapter()  # type: ignore[return-value]
    raise ValueError(
        f"Unknown aggregation provider {provider!r}. Valid values: 'fake', 'plaid'."
    )
