"""Parsing durations such as `1h30m` or `1.5h` (docs/SPEC.md)."""
import re
from fractions import Fraction

from .units import SIZE, UNITS

GROUP = re.compile(r"\s*(\d+(?:\.\d+)?)\s*([dhms])\s*")
ORDER = [u for u, _ in UNITS]


def parse_duration(text):
    """Return the duration in whole seconds; ValueError with the exact messages of docs/SPEC.md."""
    if not text.strip():
        raise ValueError("empty duration")
    groups, pos = [], 0
    while pos < len(text):
        m = GROUP.match(text, pos)
        if not m:
            raise ValueError(f"invalid duration: {text!r}")
        groups.append(m.groups())
        pos = m.end()
    total, last = Fraction(0), -1
    for number, unit in groups:
        if ORDER.index(unit) <= last:
            raise ValueError(f"unit out of order: {unit}")
        last = ORDER.index(unit)
        total += Fraction(number) * SIZE[unit]
    if total.denominator != 1:
        raise ValueError("not a whole number of seconds")
    return int(total)
