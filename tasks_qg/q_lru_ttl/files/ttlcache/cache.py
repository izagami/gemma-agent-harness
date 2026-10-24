"""LRU cache with per-entry time to live."""
import time
from collections import OrderedDict


class Entry:
    __slots__ = ("value", "born", "ttl")

    def __init__(self, value, born, ttl):
        self.value, self.born, self.ttl = value, born, ttl

    def expired(self, now):
        return now > self.born + self.ttl


class TTLCache:
    def __init__(self, capacity, ttl, clock=time.monotonic):
        if capacity < 1 or ttl <= 0:
            raise ValueError("capacity must be >= 1 and ttl > 0")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self._data = OrderedDict()   # oldest use first
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "expirations": 0}

    def _expire(self, key):
        del self._data[key]
        self._stats["expirations"] += 1

    def get(self, key, default=None):
        now = self.clock()
        e = self._data.get(key)
        if e is None:
            self._stats["misses"] += 1
            return default
        if e.expired(now):
            self._expire(key)
            self._stats["misses"] += 1
            return default
        self._data.move_to_end(key)
        e.born = now
        self._stats["hits"] += 1
        return e.value

    def set(self, key, value, ttl=None):
        ttl = self.ttl if ttl is None else ttl
        if ttl <= 0:
            raise ValueError("ttl must be > 0")
        now = self.clock()
        if len(self._data) >= self.capacity:
            self._make_room(now)
        self._data[key] = Entry(value, now, ttl)
        self._data.move_to_end(key)

    def _make_room(self, now):
        oldest = next(iter(self._data))
        del self._data[oldest]
        self._stats["evictions"] += 1
        for k in [k for k, e in self._data.items() if e.expired(now)]:
            self._expire(k)

    def delete(self, key):
        return self._data.pop(key, None) is not None

    def __len__(self):
        now = self.clock()
        for k in [k for k, e in self._data.items() if e.expired(now)]:
            self._expire(k)
        return len(self._data)

    def __contains__(self, key):
        e = self._data.get(key)
        return e is not None and not e.expired(self.clock())

    def stats(self):
        return dict(self._stats)
