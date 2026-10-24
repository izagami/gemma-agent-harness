"""Formatting of yen amounts."""


def yen(n):
    """1234567 -> '1,234,567'"""
    sign = "-" if n < 0 else ""
    return f"{sign}{abs(n):,}"
