"""Minimal synchronous event bus.

Handlers run immediately, in subscription order, inside emit().  Event names used in this package:
  customer.tier_changed   customer_id, old, new
  catalog.reloaded        version
  order.placed            order
"""
from collections import defaultdict


class Bus:
    def __init__(self):
        self._handlers = defaultdict(list)
        self.log = []          # (name, payload) of every event, for debugging

    def subscribe(self, name, fn):
        self._handlers[name].append(fn)
        return fn

    def emit(self, name, **payload):
        self.log.append((name, payload))
        for fn in list(self._handlers.get(name, ())):
            fn(**payload)
