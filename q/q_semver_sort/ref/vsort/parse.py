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


def _idents(part, what, text, numeric_no_zero=False):
    ids = tuple(part.split("."))
    for i in ids:
        if not IDENT.match(i) or (numeric_no_zero and i.isdigit() and len(i) > 1 and i[0] == "0"):
            raise InvalidVersion(f"invalid {what} in {text!r}")
    return ids


def parse(text):
    """'v1.2.3-rc.1+build.5' -> Version. A leading 'v' is allowed. Raises InvalidVersion."""
    s = text.strip()
    if s[:1] in ("v", "V"):
        s = s[1:]
    rest, sep2, build = s.partition("+")
    core, sep, pre = rest.partition("-")
    nums = core.split(".")
    if len(nums) != 3 or not all(n.isascii() and n.isdigit() and (n == "0" or n[0] != "0") for n in nums):
        raise InvalidVersion(f"invalid version: {text.strip()!r}")
    major, minor, patch = (int(n) for n in nums)
    pre_ids = _idents(pre, "pre-release", text, True) if sep else ()
    build_ids = _idents(build, "build metadata", text) if sep2 else ()
    return Version(major, minor, patch, pre_ids, build_ids, text.strip())
