import re

from ts.errors import UsageError

_HM = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")
_COLON = re.compile(r"^(\d+):([0-5]\d)$")
_DEC = re.compile(r"^(\d+)\.(\d+)h$")


def parse_duration(text):
    """'1h30m', '90m', '2h', '1:30', '1.5h' -> minutes (positive int)."""
    text = text.strip().lower()
    minutes = None
    m = _HM.match(text)
    if m and (m.group(1) or m.group(2)):
        minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    elif _COLON.match(text):
        h, mi = _COLON.match(text).groups()
        minutes = int(h) * 60 + int(mi)
    elif _DEC.match(text):
        whole, frac = _DEC.match(text).groups()
        total = (int(whole + frac) * 60)
        scale = 10 ** len(frac)
        if total % scale:
            raise UsageError(f"invalid duration: {text}")
        minutes = total // scale
    if not minutes:
        raise UsageError(f"invalid duration: {text}")
    return minutes


def format_minutes(minutes):
    """125 -> '2:05'."""
    return f"{minutes // 60}:{minutes % 60:02d}"
