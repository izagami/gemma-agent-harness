"""Discount rules (percent, integers).

  tier discount          standard 0, silver 5, gold 10, platinum 15
  category adjustment    "sale" items: tier discount is halved (rounded down)
                         "bulk" items: +3 for gold and platinum
  never more than MAX_DISCOUNT percent in total.
Quantity discounts are applied per order line in orders.py, not here.
"""

TIER_DISCOUNT = {"standard": 0, "silver": 5, "gold": 10, "platinum": 15}
MAX_DISCOUNT = 20


def discount_percent(tier, category):
    pct = TIER_DISCOUNT[tier]
    if category == "sale":
        pct //= 2
    elif category == "bulk" and tier in ("gold", "platinum"):
        pct += 3
    return min(pct, MAX_DISCOUNT)


def apply_percent(amount, pct):
    """amount * (100 - pct) / 100, rounded half up to whole yen."""
    return (amount * (100 - pct) + 50) // 100
