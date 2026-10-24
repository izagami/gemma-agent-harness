"""Text formatting helpers."""


def table(rows, widths, aligns):
    """rows of strings -> lines; aligns is a string of '<' / '>' per column."""
    out = []
    for r in rows:
        out.append("  ".join(f"{c:{a}{w}}" for c, w, a in zip(r, widths, aligns)).rstrip())
    return out


def expense_line(e):
    return f"{e.id:>4}  {e.date}  {e.amount:>10} {e.currency}  {e.category:<12} {e.note}".rstrip()
