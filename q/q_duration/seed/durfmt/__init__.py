"""durfmt: parse and format human-readable durations (docs/SPEC.md)."""
from .fmt import format_duration
from .parse import parse_duration

__all__ = ["format_duration", "parse_duration"]
