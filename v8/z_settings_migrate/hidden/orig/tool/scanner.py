"""Walk a directory tree and collect the files to back up."""
import fnmatch
import hashlib
import os
from dataclasses import dataclass

from tool import legacy_settings, log


@dataclass(frozen=True)
class Entry:
    path: str      # relative, "/"-separated
    size: int
    digest: str    # sha1 hex, or "-" when backup.checksums is off


def _excluded(rel, patterns):
    base = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatchcase(rel, p) or fnmatch.fnmatchcase(base, p) for p in patterns)


def _digest(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root):
    patterns = legacy_settings.get_list("backup.exclude")
    hidden = legacy_settings.get_bool("backup.include_hidden", False)
    max_size = legacy_settings.get_int("backup.max_size", 0)
    checksums = legacy_settings.get_bool("backup.checksums", True)
    out = []
    for dirpath, dirs, files in os.walk(root):
        dirs.sort()
        if not hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        dirs[:] = [d for d in dirs if not _excluded(d if rel_dir == "." else f"{rel_dir}/{d}", patterns)]
        for name in sorted(files):
            if not hidden and name.startswith("."):
                continue
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or _excluded(rel, patterns):
                log.info(f"skip {rel}")
                continue
            size = os.path.getsize(full)
            if max_size and size > max_size:
                log.info(f"too big {rel} ({size})")
                continue
            out.append(Entry(rel, size, _digest(full) if checksums else "-"))
    log.info(f"scanned {len(out)} files")
    return out
