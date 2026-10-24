"""Backup manifest: <outdir>/<backup.name>.manifest"""
import os

from tool import log


def render(entries, settings):
    name = settings.get("backup.name", "backup")
    total = sum(e.size for e in entries)
    lines = [f"# manifest {name} files={len(entries)} bytes={total}"]
    order = settings.get("backup.order", "path")
    if order == "size":
        entries = sorted(entries, key=lambda e: (-e.size, e.path))
    elif order == "path":
        entries = sorted(entries, key=lambda e: e.path)
    else:
        raise ValueError(f"setting backup.order: unknown order: {order!r}")
    lines += [f"{e.digest}  {e.size}  {e.path}" for e in entries]
    return "\n".join(lines) + "\n"


def write(entries, outdir, settings):
    name = settings.get("backup.name", "backup")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{name}.manifest")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(entries, settings))
    log.info(f"wrote {path}", settings)
    return path
