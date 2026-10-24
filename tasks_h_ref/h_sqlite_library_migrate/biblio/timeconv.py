"""Time helpers for the library database."""
import re
from datetime import datetime, timedelta

_RE = re.compile(r"[0-9]{4}([-/])[0-9]{2}\1[0-9]{2} [0-9]{2}:[0-9]{2}")


def jst_to_utc(s):
    """'YYYY-MM-DD HH:MM' or 'YYYY/MM/DD HH:MM' in Japan time -> 'YYYY-MM-DDTHH:MM:00Z' in UTC; ValueError if invalid."""
    t = (s or "").strip(" ")
    if not _RE.fullmatch(t):
        raise ValueError(f"invalid time {s!r}")
    try:
        dt = datetime.strptime(t.replace("/", "-"), "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError(f"invalid time {s!r}") from None
    return (dt - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:00Z")
