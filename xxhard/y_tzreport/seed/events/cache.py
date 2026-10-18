"""Memoization for expensive aggregate queries.

Arguments are used as the cache key; unhashable arguments are keyed by identity.
stats() reports hits/misses over all memoized functions.
"""
import functools

_stats = {"hits": 0, "misses": 0}
_caches = []


def _key_part(arg):
    try:
        hash(arg)
        return arg
    except TypeError:
        return ("id", id(arg))


def memoize(fn):
    cache = {}
    _caches.append(cache)

    @functools.wraps(fn)
    def wrapper(*args):
        key = tuple(_key_part(a) for a in args)
        if key in cache:
            _stats["hits"] += 1
            return cache[key]
        _stats["misses"] += 1
        value = fn(*args)
        cache[key] = value
        return value

    wrapper.cache = cache
    return wrapper


def stats():
    return dict(_stats)


def clear():
    for c in _caches:
        c.clear()
    _stats.update(hits=0, misses=0)
