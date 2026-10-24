"""Human readable sizes.  report.units: b | iec | si; report.decimals (default 1)."""
IEC = ["B", "KiB", "MiB", "GiB", "TiB"]
SI = ["B", "kB", "MB", "GB", "TB"]


def size(n, settings):
    units = settings.get("report.units", "iec").lower()
    if units == "b":
        return f"{n} B"
    if units not in ("iec", "si"):
        raise ValueError(f"setting report.units: unknown unit system: {units!r}")
    step, names = (1024, IEC) if units == "iec" else (1000, SI)
    decimals = settings.get_int("report.decimals", 1)
    value, i = float(n), 0
    while value >= step and i < len(names) - 1:
        value /= step
        i += 1
    if i == 0:
        return f"{n} B"
    return f"{value:.{decimals}f} {names[i]}"


def pad(text, width, align=None, *, settings):
    align = align or settings.get("report.align", "left")
    return text.rjust(width) if align == "right" else text.ljust(width)
