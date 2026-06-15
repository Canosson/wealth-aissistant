"""Unit tests for Money / Currency value objects — written first (TDD RED)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from wealth_assistant.domain.money import Currency, CurrencyMismatchError, Money


class TestCurrency:
    def test_valid_currency_usd(self) -> None:
        c = Currency("USD")
        assert str(c) == "USD"

    def test_valid_currency_eur(self) -> None:
        c = Currency("EUR")
        assert str(c) == "EUR"

    def test_invalid_currency_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown currency"):
            Currency("XYZ")

    def test_lowercase_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown currency"):
            Currency("usd")

    def test_currency_equality(self) -> None:
        assert Currency("USD") == Currency("USD")
        assert Currency("USD") != Currency("EUR")

    def test_currency_hashable(self) -> None:
        s = {Currency("USD"), Currency("EUR"), Currency("USD")}
        assert len(s) == 2

    def test_currency_repr(self) -> None:
        assert "USD" in repr(Currency("USD"))


class TestMoney:
    def test_construction(self) -> None:
        m = Money(Decimal("100.00"), Currency("USD"))
        assert m.amount == Decimal("100.00")
        assert m.currency == Currency("USD")

    def test_float_rejected(self) -> None:
        with pytest.raises(TypeError, match="Decimal"):
            Money(100.0, Currency("USD"))  # type: ignore[arg-type]

    def test_int_rejected(self) -> None:
        with pytest.raises(TypeError, match="Decimal"):
            Money(100, Currency("USD"))  # type: ignore[arg-type]

    def test_addition_same_currency(self) -> None:
        a = Money(Decimal("10.00"), Currency("USD"))
        b = Money(Decimal("20.00"), Currency("USD"))
        assert a + b == Money(Decimal("30.00"), Currency("USD"))

    def test_subtraction_same_currency(self) -> None:
        a = Money(Decimal("50.00"), Currency("USD"))
        b = Money(Decimal("20.00"), Currency("USD"))
        assert a - b == Money(Decimal("30.00"), Currency("USD"))

    def test_addition_mixed_currency_raises(self) -> None:
        a = Money(Decimal("10.00"), Currency("USD"))
        b = Money(Decimal("10.00"), Currency("EUR"))
        with pytest.raises(CurrencyMismatchError):
            _ = a + b

    def test_subtraction_mixed_currency_raises(self) -> None:
        a = Money(Decimal("10.00"), Currency("USD"))
        b = Money(Decimal("10.00"), Currency("EUR"))
        with pytest.raises(CurrencyMismatchError):
            _ = a - b

    def test_multiply_by_decimal(self) -> None:
        m = Money(Decimal("10.00"), Currency("USD"))
        assert m * Decimal("1.5") == Money(Decimal("15.00"), Currency("USD"))

    def test_multiply_by_int(self) -> None:
        m = Money(Decimal("10.00"), Currency("USD"))
        assert m * 3 == Money(Decimal("30.00"), Currency("USD"))

    def test_rmul(self) -> None:
        m = Money(Decimal("10.00"), Currency("USD"))
        assert 3 * m == Money(Decimal("30.00"), Currency("USD"))

    def test_equality(self) -> None:
        a = Money(Decimal("100.00"), Currency("USD"))
        b = Money(Decimal("100.00"), Currency("USD"))
        assert a == b

    def test_inequality_amount(self) -> None:
        a = Money(Decimal("100.00"), Currency("USD"))
        b = Money(Decimal("200.00"), Currency("USD"))
        assert a != b

    def test_inequality_currency(self) -> None:
        a = Money(Decimal("100.00"), Currency("USD"))
        b = Money(Decimal("100.00"), Currency("EUR"))
        assert a != b

    def test_zero(self) -> None:
        m = Money(Decimal("0.00"), Currency("USD"))
        assert m.amount == Decimal("0.00")

    def test_repr_contains_amount_and_currency(self) -> None:
        m = Money(Decimal("42.50"), Currency("GBP"))
        r = repr(m)
        assert "42.50" in r
        assert "GBP" in r

    def test_hashable(self) -> None:
        m1 = Money(Decimal("10.00"), Currency("USD"))
        m2 = Money(Decimal("10.00"), Currency("USD"))
        assert hash(m1) == hash(m2)
        d = {m1: "value"}
        assert d[m2] == "value"

    def test_immutable_amount(self) -> None:
        m = Money(Decimal("100.00"), Currency("USD"))
        with pytest.raises(AttributeError):
            m._amount = Decimal("200.00")  # type: ignore[misc]
