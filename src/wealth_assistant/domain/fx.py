"""FX conversion utilities (Principle V — recorded rate, reproducible; R3)."""
from __future__ import annotations

from decimal import Decimal

from wealth_assistant.domain.money import Currency, Money


class FxConversionError(ValueError):
    """Raised when an FX conversion cannot be completed."""


def convert(source: Money, target_currency: Currency, rate: Decimal) -> Money:
    """Convert *source* to *target_currency* using a caller-supplied *rate*.

    The rate is base→quote: 1 unit of source.currency = rate units of target_currency.
    The caller must record the rate alongside any snapshot for reproducibility (R3).

    Raises FxConversionError when rate is zero or negative.
    """
    if rate <= Decimal("0"):
        raise FxConversionError(f"FX rate must be positive, got {rate!r}.")
    return Money(source.amount * rate, target_currency)
