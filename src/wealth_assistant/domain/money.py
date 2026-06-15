"""Money and Currency value objects (Principle V — exact decimal, explicit currency)."""
from __future__ import annotations

from decimal import Decimal

# ISO-4217 uppercase codes accepted by the system
_VALID_CURRENCIES: frozenset[str] = frozenset({
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
    "BSD", "BTN", "BWP", "BZD", "CAD", "CDF", "CHF", "CLP", "CNY", "COP",
    "CRC", "CUC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP",
    "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP", "GMD",
    "GNF", "GTQ", "GYD", "HKD", "HNL", "HTG", "HUF", "IDR", "ILS", "INR",
    "IQD", "IRR", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KHR", "KMF",
    "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD", "LSL",
    "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MUR", "MVR",
    "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK", "NPR", "NZD",
    "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG", "QAR", "RON",
    "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK", "SGD", "SHP",
    "SLL", "SOS", "SRD", "STD", "SVC", "SYP", "SZL", "THB", "TJS", "TMT",
    "TND", "TOP", "TRY", "TTD", "TWD", "TZS", "UAH", "UGX", "USD", "UYU",
    "UZS", "VEF", "VND", "VUV", "WST", "XAF", "XCD", "XDR", "XOF", "XPF",
    "YER", "ZAR", "ZMW",
})


class CurrencyMismatchError(ValueError):
    """Raised when arithmetic is attempted between Money values of different currencies."""


class Currency:
    """Validated ISO-4217 alphabetic currency code."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        if code not in _VALID_CURRENCIES:
            raise ValueError(
                f"Unknown currency: {code!r}. Must be an uppercase ISO-4217 code."
            )
        self._code = code

    def __str__(self) -> str:
        return self._code

    def __repr__(self) -> str:
        return f"Currency({self._code!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Currency):
            return self._code == other._code
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._code)


class Money:
    """Exact-decimal monetary value with an explicit currency (Principle V)."""

    __slots__ = ("_amount", "_currency")

    def __init__(self, amount: Decimal, currency: Currency) -> None:
        if not isinstance(amount, Decimal):
            raise TypeError(
                f"Money.amount must be a Decimal, got {type(amount).__name__!r}."
            )
        object.__setattr__(self, "_amount", amount)
        object.__setattr__(self, "_currency", currency)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Money is immutable.")

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> Currency:
        return self._currency

    def _require_same_currency(self, other: Money) -> None:
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                f"Cannot mix {self._currency} and {other._currency}."
            )

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented  # type: ignore[return-value]
        self._require_same_currency(other)
        return Money(self._amount + other._amount, self._currency)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented  # type: ignore[return-value]
        self._require_same_currency(other)
        return Money(self._amount - other._amount, self._currency)

    def __mul__(self, scalar: Decimal | int) -> Money:
        if isinstance(scalar, int):
            scalar = Decimal(scalar)
        if not isinstance(scalar, Decimal):
            return NotImplemented  # type: ignore[return-value]
        return Money(self._amount * scalar, self._currency)

    def __rmul__(self, scalar: Decimal | int) -> Money:
        return self.__mul__(scalar)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._amount == other._amount and self._currency == other._currency
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._amount, self._currency))

    def __repr__(self) -> str:
        return f"Money({self._amount}, {self._currency})"
