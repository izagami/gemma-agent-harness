"""Consumption tax rate per item category (docs/SPEC.md)."""

STANDARD = 0.10
RATES = {
    "food": 0.08,     # reduced rate
    "exempt": 0.0,    # stamps, postage, ...
}


def rate_for(category):
    """Tax rate for an item category."""
    return RATES.get(category, STANDARD)
