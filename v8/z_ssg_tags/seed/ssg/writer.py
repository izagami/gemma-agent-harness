"""Output helpers.  Files whose content did not change are not rewritten (keeps mtimes stable,
so the rsync deploy only uploads what changed)."""
import os
import shutil


def write_if_changed(path, text):
    """Write text (UTF-8) to path unless it already has exactly that content.  True if written."""
    data = text.encode("utf-8")
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True


def copy_static(src_dir, out_dir):
    """Copy every file under src_dir to out_dir (same relative paths), skipping unchanged files."""
    n = 0
    if not os.path.isdir(src_dir):
        return n
    for root, dirs, files in os.walk(src_dir):
        dirs.sort()
        for f in sorted(files):
            s = os.path.join(root, f)
            d = os.path.join(out_dir, os.path.relpath(s, src_dir))
            with open(s, "rb") as fh:
                data = fh.read()
            if os.path.exists(d):
                with open(d, "rb") as fh:
                    if fh.read() == data:
                        continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d)
            n += 1
    return n
