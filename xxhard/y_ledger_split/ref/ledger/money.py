"""Money amounts, parsing/formatting, exchange rates and the default currency."""
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from ledger.errors import LedgerError

_DECIMALS = {"JPY": 0, "USD": 2, "EUR": 2, "GBP": 2}
_RATES = {}                     # (src, dst) -> Decimal
_DEFAULT_CURRENCY = "JPY"


def set_default_currency(code):
    global _DEFAULT_CURRENCY
    if code not in _DECIMALS:
        raise LedgerError(f"unknown currency {code}")
    _DEFAULT_CURRENCY = code


def get_default_currency():
    return _DEFAULT_CURRENCY


@dataclass(frozen=True, order=True)
class Money:
    """An amount in minor units (yen, cents) of one currency."""
    currency: str
    minor: int

    def __post_init__(self):
        if self.currency not in _DECIMALS:
            raise LedgerError(f"unknown currency {self.currency}")

    @classmethod
    def zero(cls, currency=None):
        return cls(currency or get_default_currency(), 0)

    def _check(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise LedgerError(f"currency mismatch: {self.currency} vs {other.currency}")
        return None

    def __add__(self, other):
        bad = self._check(other)
        return bad if bad is NotImplemented else Money(self.currency, self.minor + other.minor)

    def __sub__(self, other):
        bad = self._check(other)
        return bad if bad is NotImplemented else Money(self.currency, self.minor - other.minor)

    def __neg__(self):
        return Money(self.currency, -self.minor)

    def __mul__(self, k):
        if not isinstance(k, int):
            return NotImplemented
        return Money(self.currency, self.minor * k)

    def is_zero(self):
        return self.minor == 0

    def decimal(self):
        return Decimal(self.minor).scaleb(-_DECIMALS[self.currency])

    def __str__(self):
        return format_money(self)


_MONEY_RE = re.compile(r"^\s*(-)?\s*([0-9][0-9,]*)(?:\.([0-9]+))?\s*([A-Z]{3})?\s*$")


def parse_money(text, currency=None):
    """'1,234.50 USD', '-500', '12 JPY'. Without a code, `currency` or the default currency is used."""
    m = _MONEY_RE.match(text)
    if not m:
        raise LedgerError(f"bad amount {text!r}")
    sign, whole, frac, code = m.groups()
    code = code or currency or get_default_currency()
    if code not in _DECIMALS:
        raise LedgerError(f"unknown currency {code}")
    places = _DECIMALS[code]
    frac = frac or ""
    if len(frac) > places:
        raise LedgerError(f"too many decimals for {code}: {text!r}")
    minor = int(whole.replace(",", "") + frac.ljust(places, "0"))
    return Money(code, -minor if sign else minor)


def format_money(m):
    places = _DECIMALS[m.currency]
    sign = "-" if m.minor < 0 else ""
    whole, frac = divmod(abs(m.minor), 10 ** places)
    text = f"{whole:,}" + (f".{frac:0{places}d}" if places else "")
    return f"{sign}{text} {m.currency}"


def set_rate(src, dst, rate):
    """1 src = rate dst. The inverse direction is derived automatically."""
    rate = Decimal(str(rate))
    if rate <= 0:
        raise LedgerError("rate must be positive")
    _RATES[(src, dst)] = rate


def clear_rates():
    _RATES.clear()


def _rate(src, dst):
    if src == dst:
        return Decimal(1)
    if (src, dst) in _RATES:
        return _RATES[(src, dst)]
    if (dst, src) in _RATES:
        return 1 / _RATES[(dst, src)]
    raise LedgerError(f"no rate {src}->{dst}")


def convert(m, currency):
    value = m.decimal() * _rate(m.currency, currency)
    places = _DECIMALS[currency]
    minor = (value.scaleb(places)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    return Money(currency, int(minor))
