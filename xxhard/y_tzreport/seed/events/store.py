"""In-memory event store, bucketed by calendar day so range queries only scan a few buckets."""
from collections import defaultdict
from datetime import timedelta


class EventStore:
    def __init__(self, events=()):
        self._buckets = defaultdict(list)
        self.size = 0
        self.version = 0          # bumped on every change
        self.extend(events)

    @staticmethod
    def _bucket_key(ts):
        return ts.date()

    def add(self, event):
        self._buckets[self._bucket_key(event.ts)].append(event)
        self.size += 1
        self.version += 1

    def extend(self, events):
        for ev in events:
            self.add(ev)

    def between(self, start, end):
        """Events with start <= ts < end (aware datetimes), ordered by timestamp."""
        out = []
        day = start.date()
        while day <= end.date():
            out.extend(ev for ev in self._buckets.get(day, ()) if start <= ev.ts < end)
            day += timedelta(days=1)
        out.sort(key=lambda ev: ev.ts)
        return out

    def __len__(self):
        return self.size
