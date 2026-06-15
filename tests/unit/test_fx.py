"""Unit tests for FX conversion — written first (TDD RED)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from wealth_assistant.domain.fx import FxConversionError, convert
from wealth_assistant.domain.money import Currency, Money


class TestConvert:
    def test_usd_to_eur(self) -> None:
        usd = Money(Decimal("100.00"), Currency("USD"))
        result = convert(usd, Currency("EUR"), Decimal("0.9200"))
        assert result.currency == Currency("EUR")
        assert result.amount == Decimal("92.0000")

    def test_same_currency_rate_one(self) -> None:
        usd = Money(Decimal("100.00"), Currency("USD"))
        result = convert(usd, Currency("USD"), Decimal("1"))
        assert result == Money(Decimal("100.00"), Currency("USD"))

    def test_reproducible_same_rate(self) -> None:
        usd = Money(Decimal("1234.5678"), Currency("USD"))
        rate = Decimal("1.08500")
        r1 = convert(usd, Currency("EUR"), rate)
        r2 = convert(usd, Currency("EUR"), rate)
        assert r1 == r2

    def test_result_is_exact_decimal(self) -> None:
        usd = Money(Decimal("1.00"), Currency("USD"))
        rate = Decimal("1.234567890")
        result = convert(usd, Currency("EUR"), rate)
        assert isinstance(result.amount, Decimal)

    def test_zero_rate_raises(self) -> None:
        usd = Money(Decimal("100.00"), Currency("USD"))
        with pytest.raises((ZeroDivisionError, FxConversionError, ValueError)):
            convert(usd, Currency("EUR"), Decimal("0"))

    def test_negative_rate_raises(self) -> None:
        usd = Money(Decimal("100.00"), Currency("USD"))
        with pytest.raises((ValueError, FxConversionError)):
            convert(usd, Currency("EUR"), Decimal("-1"))

    def test_known_gbp_to_usd(self) -> None:
        gbp = Money(Decimal("200.00"), Currency("GBP"))
        rate = Decimal("1.25")
        result = convert(gbp, Currency("USD"), rate)
        assert result.amount == Decimal("250.00")
        assert result.currency == Currency("USD")

    def test_fractional_result_is_decimal(self) -> None:
        usd = Money(Decimal("1.00"), Currency("USD"))
        rate = Decimal("3")
        result = convert(usd, Currency("JPY"), rate)
        assert isinstance(result.amount, Decimal)
        assert result.amount == Decimal("3")
