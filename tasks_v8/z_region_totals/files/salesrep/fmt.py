"""Plain-text table formatting."""


def yen(n):
    """1234567 -> '1,234,567', -500 -> '-500'."""
    s = f"{abs(int(n)):,}"
    return "-" + s if n < 0 else s


def table(header, rows, width=12):
    """First column left-aligned (width 10), the others right-aligned to `width`."""
    def line(cells):
        first, rest = cells[0], cells[1:]
        return (f"{first:<10}" + "".join(f"{c:>{width}}" for c in rest)).rstrip()
    out = [line(header)]
    out += [line(r) for r in rows]
    return "\n".join(out)
