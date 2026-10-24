"""Time helpers for the library database."""


def jst_to_utc(s):
    """'YYYY-MM-DD HH:MM' in Japan time -> 'YYYY-MM-DDTHH:MM:00Z' in UTC."""
    day, hm = s.strip().split(" ")
    h, m = hm.split(":")
    return f"{day}T{(int(h) - 9) % 24:02d}:{m}:00Z"
