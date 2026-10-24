"""python3 -m invo INVOICE.csv  -> one line per item, then SUBTOTAL / TAX / TOTAL."""
import sys

from .invoice import load_csv, summarize
from .money import fmt


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python3 -m invo INVOICE.csv", file=sys.stderr)
        return 2
    rows, sub, tax, total = summarize(load_csv(argv[0]))
    for item, net, t, line_total in rows:
        print(f"{item} {fmt(net)} {fmt(t)} {fmt(line_total)}")
    print(f"SUBTOTAL {fmt(sub)}")
    print(f"TAX {fmt(tax)}")
    print(f"TOTAL {fmt(total)}")
    return 0
