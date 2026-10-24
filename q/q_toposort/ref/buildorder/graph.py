"""Reading dependency files into a graph."""


class Graph:
    """deps[name] = the names `name` depends on. Every name that appears anywhere is a node."""

    def __init__(self):
        self.deps = {}

    def add(self, target, deps=()):
        self.deps.setdefault(target, [])
        for d in deps:
            self.deps.setdefault(d, [])
            if d not in self.deps[target]:
                self.deps[target].append(d)

    def nodes(self):
        return sorted(self.deps)

    def dependents(self):
        """name -> set of nodes that depend on it."""
        out = {n: set() for n in self.deps}
        for t, ds in self.deps.items():
            for d in ds:
                out[d].add(t)
        return out


def parse(text):
    g = Graph()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"bad line: {raw!r}")
        target, rest = line.split(":", 1)
        g.add(target.strip(), rest.split())
    return g


def load(path):
    with open(path, encoding="utf-8") as f:
        return parse(f.read())
