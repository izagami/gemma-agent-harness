"""Event log format, one event per line:

    <ISO-8601 timestamp with UTC offset>,<kind>,<user>[,<count>]

Blank lines and lines starting with '#' are ignored. kind is case-insensitive
(stored lower-case); count defaults to 1.
"""
from dataclasses import dataclass
from datetime import datetime


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Event:
    ts: datetime          # always timezone-aware
    kind: str
    user: str
    count: int = 1


def parse_line(line, lineno=0):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) not in (3, 4):
        raise ParseError(f"line {lineno}: expected 3 or 4 fields, got {len(parts)}")
    try:
        ts = datetime.fromisoformat(parts[0])
    except ValueError:
        raise ParseError(f"line {lineno}: bad timestamp {parts[0]!r}") from None
    if ts.tzinfo is None:
        raise ParseError(f"line {lineno}: timestamp {parts[0]!r} has no UTC offset")
    kind = parts[1].lower()
    if not kind or not parts[2]:
        raise ParseError(f"line {lineno}: empty kind or user")
    count = 1
    if len(parts) == 4:
        try:
            count = int(parts[3])
        except ValueError:
            raise ParseError(f"line {lineno}: bad count {parts[3]!r}") from None
        if count < 1:
            raise ParseError(f"line {lineno}: count must be positive")
    return Event(ts, kind, parts[2], count)


def parse_text(text):
    events = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        events.append(parse_line(line, n))
    return events


def parse_file(path):
    with open(path, encoding="utf-8") as f:
        return parse_text(f.read())
