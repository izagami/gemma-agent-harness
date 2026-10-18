"""Fixed-offset time zones ('+09:00', '-0500', 'UTC+05:30', 'UTC', 'Z')."""
import re
from datetime import datetime, time, timedelta, timezone

_OFFSET = re.compile(r"^(?:UTC)?([+-])(\d{2}):?(\d{2})$")


def parse_zone(text):
    text = text.strip().upper()
    if text in ("UTC", "Z"):
        return timezone.utc
    m = _OFFSET.match(text)
    if not m:
        raise ValueError(f"bad zone {text!r}")
    sign, hours, minutes = m.group(1), int(m.group(2)), int(m.group(3))
    if hours > 14 or minutes >= 60:
        raise ValueError(f"bad zone {text!r}")
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(-delta if sign == "-" else delta)


def zone_name(zone):
    """'+09:00', '-05:00', '+00:00'."""
    minutes = int(zone.utcoffset(None).total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def local_day(ts, zone):
    return ts.astimezone(zone).date()


def day_bounds(day, zone):
    """[start, end) of the local calendar day `day` in `zone`, as UTC datetimes."""
    start = datetime.combine(day, time(0), tzinfo=zone)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def week_days(day):
    """The 7 dates (Monday..Sunday) of the week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=i) for i in range(7)]
