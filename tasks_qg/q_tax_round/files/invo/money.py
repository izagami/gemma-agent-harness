"""Yen amounts."""


def to_yen(x):
    """Round an amount to whole yen (docs/SPEC.md: fractions of a yen are rounded)."""
    return int(round(x))


def fmt(n):
    """1234567 -> '1,234,567'."""
    return f"{n:,}"
