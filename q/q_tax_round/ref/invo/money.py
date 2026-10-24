"""Yen amounts."""
from decimal import ROUND_HALF_UP, Decimal


def to_yen(x):
    """Round an amount to whole yen (docs/SPEC.md: half a yen and more rounds up)."""
    return int(Decimal(str(x)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def fmt(n):
    """1234567 -> '1,234,567'."""
    return f"{n:,}"
