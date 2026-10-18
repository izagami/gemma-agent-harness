"""Monthly exchange rates to JPY (1 unit of currency = rate JPY)."""
from decimal import Decimal

RATES_TABLE = """
month,USD,EUR
2025-04,143.10,162.35
2025-05,144.85,163.02
2025-06,144.20,165.70
2025-07,146.55,170.12
2025-08,147.40,171.88
2025-09,148.05,173.40
2025-10,150.62,175.09
2025-11,152.31,176.40
2025-12,154.08,179.95
2026-01,153.77,178.21
2026-02,151.92,176.66
2026-03,149.38,174.50
"""


def parse_rates(text=RATES_TABLE):
    lines = [l for l in text.strip().splitlines() if l.strip()]
    header = lines[0].split(",")
    table = {}
    for line in lines[1:]:
        cells = line.split(",")
        for cur, value in zip(header[1:], cells[1:]):
            table[(cells[0], cur)] = Decimal(value)
    return table


_TABLE = parse_rates()
_ONE = Decimal(1)


def rate_for(month, currency):
    if currency == "JPY":
        return _ONE
    return _TABLE[(month, currency)]
