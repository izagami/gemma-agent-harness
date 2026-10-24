"""Expense records and their validation."""
import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

CURRENCY = re.compile(r"^[A-Z]{3}$")


class ValidationError(ValueError):
    pass


@dataclass
class Expense:
    id: int
    date: str        # YYYY-MM-DD
    amount: str      # decimal string in `currency`, e.g. "12.50"
    currency: str    # ISO code, upper case
    category: str    # lower case, stripped
    note: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: d[k] for k in ("id", "date", "amount", "currency", "category", "note")})

    @property
    def decimal_amount(self):
        return Decimal(self.amount)


def clean_date(s):
    s = (s or "").strip()
    try:
        date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"invalid date: {s}") from None
    if len(s) != 10:
        raise ValidationError(f"invalid date: {s}")
    return s


def clean_amount(s):
    s = (s or "").strip().replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValidationError(f"invalid amount: {s}") from None
    if not d.is_finite() or d <= 0:
        raise ValidationError(f"invalid amount: {s}")
    return format(d.normalize(), "f") if d == d.to_integral() else format(d, "f")


def clean_currency(s):
    s = (s or "JPY").strip().upper() or "JPY"
    if not CURRENCY.match(s):
        raise ValidationError(f"invalid currency: {s}")
    return s


def clean_category(s):
    s = (s or "").strip().lower()
    if not s:
        raise ValidationError("category is required")
    return s


def make_expense(id, date, amount, currency, category, note=""):
    return Expense(id, clean_date(date), clean_amount(amount), clean_currency(currency),
                   clean_category(category), (note or "").strip())
