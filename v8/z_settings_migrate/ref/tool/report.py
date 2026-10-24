"""Size report grouped by extension or top-level directory."""
from tool import fmt


def _group(path, by):
    if by == "dir":
        return path.split("/", 1)[0] + "/" if "/" in path else "./"
    name = path.rsplit("/", 1)[-1]
    return "." + name.rsplit(".", 1)[1].lower() if "." in name.lstrip(".") else "(none)"


def groups(entries, settings):
    by = settings.get("report.group_by", "ext")
    if by not in ("ext", "dir"):
        raise ValueError(f"setting report.group_by: unknown grouping: {by!r}")
    acc = {}
    for e in entries:
        g = acc.setdefault(_group(e.path, by), [0, 0])
        g[0] += 1
        g[1] += e.size
    return sorted(acc.items(), key=lambda kv: (-kv[1][1], kv[0]))


def render(entries, settings):
    top = settings.get_int("report.top", 5)
    title = settings.get("report.title", "Report")
    total = sum(e.size for e in entries)
    lines = [f"{title}: {len(entries)} files, {fmt.size(total, settings)}"]
    gs = groups(entries, settings)
    shown = gs[:top] if top > 0 else gs
    for name, (count, size) in shown:
        lines.append(f"  {fmt.pad(name, 10, settings=settings)} {count:>4}  {fmt.pad(fmt.size(size, settings), 10, 'right', settings=settings)}")
    rest = gs[len(shown):]
    if rest:
        lines.append(f"  {fmt.pad('(other)', 10, settings=settings)} {sum(c for _, (c, _) in rest):>4}  "
                     f"{fmt.pad(fmt.size(sum(s for _, (_, s) in rest), settings), 10, 'right', settings=settings)}")
    if settings.get_bool("report.show_largest", False) and entries:
        big = max(entries, key=lambda e: (e.size, e.path))
        lines.append(f"largest: {big.path} ({fmt.size(big.size, settings)})")
    return "\n".join(lines) + "\n"
