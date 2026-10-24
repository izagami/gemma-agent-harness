"""Formatting seconds as a duration string (docs/SPEC.md)."""
from .units import UNITS


def format_duration(seconds):
    """`5430` -> `1h30m30s`: largest units first, no spaces."""
    if seconds < 0:
        raise ValueError("negative duration")
    parts = []
    for unit, size in UNITS:
        count, seconds = divmod(seconds, size)
        if count or parts:
            parts.append(f"{count}{unit}")
    return "".join(parts)
