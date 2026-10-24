"""usage: python3 -m durfmt parse TEXT | python3 -m durfmt format SECONDS"""
import sys

from .fmt import format_duration
from .parse import parse_duration


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("parse", "format"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        if argv[0] == "parse":
            print(parse_duration(argv[1]))
        else:
            print(format_duration(int(argv[1])))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0
