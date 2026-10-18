"""python3 report.py SALES.csv  -> report on stdout"""
import sys

from salesrep.aggregate import best_day, by_category, by_store_month, order_stats, top_skus
from salesrep.clean import dedupe, drop_cancelled
from salesrep.enrich import enrich
from salesrep.load import read_rows
from salesrep.render import render


def build_report(path):
    rows, rejected = read_rows(path)
    unique = dedupe(rows)
    billable = drop_cancelled(unique)
    sales = enrich(billable)
    meta = {"rows": len(rows) + rejected, "rejected": rejected, "unique": len(unique), "billable": len(billable)}
    return render(meta, by_store_month(sales), by_category(sales), top_skus(sales), best_day(sales), order_stats(sales))


if __name__ == "__main__":
    sys.stdout.write(build_report(sys.argv[1]))
