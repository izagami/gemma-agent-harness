# ttlcache

`TTLCache(capacity, ttl, clock=time.monotonic)`: at most `capacity` entries; each entry lives `ttl`
seconds (or its own `ttl` given to `set`). `clock()` returns the current time (tests use `FakeClock`).

## Rules

* An entry set at time `t` with time-to-live `ttl` is **expired from time `t + ttl` on** (at exactly
  `t + ttl` it is already expired). Example: `set("a", 1)` at 0 with ttl 10 → `get("a")` at 9.99 hits,
  at 10 misses.
* `get(key, default=None)`: a live entry is a hit (`hits += 1`), becomes the most recently used, and
  returns its value. Reading does **not** extend its life. Missing or expired → `misses += 1`, returns
  `default`; an expired entry found this way is removed (`expirations += 1`).
* `set(key, value, ttl=None)`: a key that is already stored (even if expired) is replaced in place: new
  value, new start time and ttl, becomes most recently used; this never evicts anything and does not
  count as an expiration. For a new key when the cache already holds `capacity` entries: first every
  expired entry is removed (`expirations += 1` each); only if it is still full, the least recently used
  entry is removed (`evictions += 1`). `ttl <= 0` → `ValueError`.
* `delete(key)` → True if the key was stored (expired or not), else False. Not counted in the stats.
* `len(cache)`: number of live entries; expired entries are removed (`expirations += 1` each).
* `key in cache`: True for a live entry; changes nothing (no stats, no recency).
* `stats()` → `{"hits", "misses", "evictions", "expirations"}` (a copy).
* "Most/least recently used" is by `set` and successful `get` only.
