"""Version precedence (docs/SPEC.md)."""
import functools

from .parse import parse


def key(v):
    """Sort key: releases sort after their pre-releases."""
    pre = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in v.pre)
    return (v.major, v.minor, v.patch, not v.pre, pre)


def compare(a, b):
    """-1, 0 or 1 (a and b are strings or Versions)."""
    a = parse(a) if isinstance(a, str) else a
    b = parse(b) if isinstance(b, str) else b
    ka, kb = key(a), key(b)
    return (ka > kb) - (ka < kb)


def sort_versions(versions, reverse=False):
    """Sorted list of Versions; versions of equal precedence keep their input order."""
    return sorted(versions, key=functools.cmp_to_key(compare), reverse=reverse)
