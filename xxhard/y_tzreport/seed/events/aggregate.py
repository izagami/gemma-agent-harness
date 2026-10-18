from collections import Counter

from events.cache import memoize
from events.tz import day_bounds, week_days


@memoize
def daily_counts(store, day, zone):
    """{kind: summed count} over the events of local day `day` in `zone`."""
    start, end = day_bounds(day, zone)
    counts = Counter()
    for ev in store.between(start, end):
        counts[ev.kind] += ev.count
    return dict(counts)


def weekly_counts(store, day, zone):
    """Like daily_counts, summed over the Monday..Sunday week containing `day`."""
    total = {}
    for d in week_days(day):
        for kind, n in daily_counts(store, d, zone).items():
            total[kind] = total.get(kind, 0) + n
    return total


def active_users(store, day, zone):
    start, end = day_bounds(day, zone)
    return sorted({ev.user for ev in store.between(start, end)})
