"""Consumption tax rate per item category (docs/SPEC.md)."""
from decimal import Decimal

STANDARD = Decimal("0.10")
RATES = {
    "food": Decimal("0.08"),     # reduced rate
    "exempt": Decimal("0"),      # stamps, postage, ...
}


def rate_for(category):
    """Tax rate for an item category (case and surrounding spaces ignored)."""
    return RATES.get(str(category).strip().lower(), STANDARD)
