"""Parsing durations such as `1h30m` or `1.5h` (docs/SPEC.md)."""
import re

from .units import SIZE

GROUP = re.compile(r"(\d+(?:\.\d+)?)([dhms])")
WHOLE = re.compile(r"\s*(?:\d+(?:\.\d+)?[dhms]\s*)+")


def parse_duration(text):
    """Return the duration in whole seconds; ValueError with the exact messages of docs/SPEC.md."""
    if not text.strip():
        raise ValueError("empty duration")
    if not WHOLE.fullmatch(text):
        raise ValueError(f"invalid duration: {text!r}")
    total = 0
    for number, unit in GROUP.findall(text):
        total += int(float(number) * SIZE[unit])
    return total
