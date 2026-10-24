"""Build order (Kahn's algorithm)."""
import heapq


class CycleError(Exception):
    pass


def closure(graph, targets):
    """The targets and everything they need."""
    keep = set()
    stack = []
    for t in targets:
        if t not in graph.deps:
            raise KeyError(t)
        stack.append(t)
    while stack:
        n = stack.pop()
        if n in keep:
            continue
        keep.add(n)
        stack.extend(graph.deps[n])
    return keep


def cycle_path(graph, left):
    n = min(left)
    walk = []
    while n not in walk:
        walk.append(n)
        n = min(d for d in graph.deps[n] if d in left)
    return walk[walk.index(n):] + [n]


def build_order(graph, targets=None):
    nodes = set(graph.nodes()) if not targets else closure(graph, targets)
    pending = {n: len([d for d in graph.deps[n] if d in nodes]) for n in nodes}
    users = graph.dependents()
    ready = sorted(n for n in nodes if pending[n] == 0)
    order = []
    while ready:
        n = heapq.heappop(ready)
        order.append(n)
        for u in sorted(users[n]):
            if u in pending:
                pending[u] -= 1
                if pending[u] == 0:
                    heapq.heappush(ready, u)
    if len(order) < len(nodes):
        left = {n for n in nodes if n not in order}
        raise CycleError("cycle: " + " -> ".join(cycle_path(graph, left)))
    return order
