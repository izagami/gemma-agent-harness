"""usage: python3 -m csvmerge OUT.csv IN1.csv [IN2.csv ...]"""
import sys

from .merge import merge
from .reader import read_table, write_table


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    out, inputs = argv[0], argv[1:]
    columns, rows = merge([read_table(p) for p in inputs])
    write_table(out, columns, rows)
    print(f"merged {len(rows)} rows from {len(inputs)} files -> {out}")
    return 0
