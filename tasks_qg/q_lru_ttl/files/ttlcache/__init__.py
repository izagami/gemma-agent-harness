"""ttlcache: an LRU cache whose entries also expire (see docs/SPEC.md)."""
from .cache import TTLCache
from .clock import FakeClock

__all__ = ["TTLCache", "FakeClock"]
