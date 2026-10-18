import random, sys
sys.path.insert(0, "/work")
from datetime import date, datetime, timedelta, timezone
from events import cache
from events.aggregate import daily_counts
from events.parse import parse_text
from events.report import daily_report, weekly_report
from events.store import EventStore
from events.tz import parse_zone

rnd = random.Random(20261018)
OFFS = ["+09:00", "-05:00", "+00:00", "+05:30", "-08:00", "+14:00", "-11:00", "+12:45"]
KINDS = ["login", "search", "upload", "share"]
USERS = ["aoi", "ren", "yui", "kai", "mia", "leo"]
base = datetime(2026, 3, 1, tzinfo=timezone.utc)

def gen(n):
    lines = []
    for _ in range(n):
        t = base + timedelta(minutes=rnd.randrange(0, 14 * 24 * 60))
        off = OFFS[rnd.randrange(len(OFFS))]
        local = t.astimezone(parse_zone(off)).replace(tzinfo=None)
        lines.append(f"{local.isoformat()}{off},{rnd.choice(KINDS)},{rnd.choice(USERS)},{rnd.randint(1, 4)}")
    return lines

def counts(evs, days, zone):
    c = {}
    for e in evs:
        if e.ts.astimezone(zone).date() in days:
            c[e.kind] = c.get(e.kind, 0) + e.count
    return c

def render(title, evs, days, zone):
    c = counts(evs, days, zone)
    lines = [title]
    if not c:
        lines.append("(no events)")
    else:
        for k, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"{k:<10}{n:>5}")
        lines.append(f"{'TOTAL':<10}{sum(c.values()):>5}")
        users = sorted({e.user for e in evs if e.ts.astimezone(zone).date() in days})
        lines.append("users: " + ", ".join(users))
    return "\n".join(lines) + "\n"

def zname(z):
    m = int(z.utcoffset(None).total_seconds() // 60); s = "-" if m < 0 else "+"; m = abs(m)
    return f"{s}{m // 60:02d}:{m % 60:02d}"

cache.clear()
all_lines = gen(400)
evs = parse_text("\n".join(all_lines[:250]))
store = EventStore(evs)
for step in range(300):
    if step in (100, 200):
        more = parse_text("\n".join(all_lines[250:325] if step == 100 else all_lines[325:]))
        store.extend(more); evs = evs + more
    zone = parse_zone(rnd.choice(OFFS + ["UTC"]))
    day = date(2026, 2, 27) + timedelta(days=rnd.randrange(0, 19))
    if rnd.random() < 0.6:
        got = daily_report(store, day, zone)
        exp = render(f"# {day.isoformat()} ({zname(zone)})", evs, {day}, zone)
    else:
        mon = day - timedelta(days=day.weekday())
        days = {mon + timedelta(days=i) for i in range(7)}
        got = weekly_report(store, day, zone)
        exp = render(f"# week {mon.isoformat()}..{(mon + timedelta(days=6)).isoformat()} ({zname(zone)})", evs, days, zone)
    assert got == exp, (step, day, zname(zone), got, exp)

# cache still used: repeated query without changes is a hit
z = parse_zone("-05:00")
d = date(2026, 3, 4)
daily_counts(store, d, z)
h = cache.stats()["hits"]
r1 = daily_counts(store, d, z)
assert cache.stats()["hits"] == h + 1, cache.stats()
r1["bogus"] = 99
assert "bogus" not in daily_report(store, d, z)
print("ok")
