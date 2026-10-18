"""Plain-text reports.

    # 2026-03-02 (+09:00)
    login        12
    search        7
    TOTAL        19
    users: aoi, ren

Kinds are sorted by count (descending), then name. A day without events prints
"(no events)" instead of the table and the users line.
"""
from events.aggregate import active_users, daily_counts, weekly_counts
from events.tz import week_days, zone_name


def _with_total(counts):
    return dict(counts, TOTAL=sum(counts.values()))


def _table(counts):
    counts = _with_total(counts)
    rows = sorted(((k, n) for k, n in counts.items() if k != "TOTAL"), key=lambda kv: (-kv[1], kv[0]))
    rows.append(("TOTAL", counts["TOTAL"]))
    return [f"{kind:<10}{n:>5}" for kind, n in rows]


def daily_report(store, day, zone):
    lines = [f"# {day.isoformat()} ({zone_name(zone)})"]
    counts = daily_counts(store, day, zone)
    if not counts:
        lines.append("(no events)")
    else:
        lines += _table(counts)
        lines.append("users: " + ", ".join(active_users(store, day, zone)))
    return "\n".join(lines) + "\n"


def weekly_report(store, day, zone):
    days = week_days(day)
    lines = [f"# week {days[0].isoformat()}..{days[-1].isoformat()} ({zone_name(zone)})"]
    counts = weekly_counts(store, day, zone)
    if not counts:
        lines.append("(no events)")
    else:
        lines += _table(counts)
        users = set()
        for d in days:
            users.update(active_users(store, d, zone))
        lines.append("users: " + ", ".join(sorted(users)))
    return "\n".join(lines) + "\n"
