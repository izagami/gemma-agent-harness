"""Build order (Kahn's algorithm)."""


class CycleError(Exception):
    pass


def closure(graph, targets):
    """The targets and everything they need."""
    keep = set()
    for t in targets:
        if t not in graph.deps:
            raise KeyError(t)
        keep.add(t)
        keep.update(graph.deps[t])
    return keep


def build_order(graph, targets=None):
    nodes = set(graph.nodes()) if not targets else closure(graph, targets)
    pending = {n: len([d for d in graph.deps[n] if d in nodes]) for n in nodes}
    users = graph.dependents()
    ready = sorted(n for n in nodes if pending[n] == 0)
    order = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for u in sorted(users[n]):
            if u in pending:
                pending[u] -= 1
                if pending[u] == 0:
                    ready.append(u)
    if len(order) < len(nodes):
        left = sorted(n for n in nodes if n not in order)
        raise CycleError("cycle: " + ", ".join(left))
    return order
