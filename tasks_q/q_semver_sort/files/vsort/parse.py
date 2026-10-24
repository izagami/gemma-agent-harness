"""Parse version strings."""
import re
from dataclasses import dataclass

IDENT = re.compile(r"^[0-9A-Za-z-]+$")


class InvalidVersion(ValueError):
    pass


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    pre: tuple = ()      # pre-release identifiers, as strings
    build: tuple = ()    # build metadata identifiers, as strings
    text: str = ""       # the string as given

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += "-" + ".".join(self.pre)
        if self.build:
            s += "+" + ".".join(self.build)
        return s


def _idents(part, what, text):
    ids = tuple(part.split("."))
    for i in ids:
        if not IDENT.match(i):
            raise InvalidVersion(f"invalid {what} in {text!r}")
    return ids


def parse(text):
    """'v1.2.3-rc.1+build.5' -> Version. A leading 'v' is allowed. Raises InvalidVersion."""
    s = text.strip()
    if s[:1] in ("v", "V"):
        s = s[1:]
    core, sep, pre = s.partition("-")
    pre, sep2, build = pre.partition("+")
    nums = core.split(".")
    if len(nums) != 3 or not all(n.isdigit() for n in nums):
        raise InvalidVersion(f"invalid version: {text.strip()!r}")
    major, minor, patch = (int(n) for n in nums)
    pre_ids = _idents(pre, "pre-release", text) if sep else ()
    build_ids = _idents(build, "build metadata", text) if sep2 else ()
    return Version(major, minor, patch, pre_ids, build_ids, text.strip())
