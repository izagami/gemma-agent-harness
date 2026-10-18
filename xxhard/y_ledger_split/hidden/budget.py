"""Compare monthly expenses with a budget: python3 budget.py"""
import os
from datetime import date

from ledger import Money, convert, load_csv, parse_money, set_rate, LedgerError

HERE = os.path.dirname(os.path.abspath(__file__))

BUDGET = {
    "Expenses:Housing": "110,000",
    "Expenses:Food": "30,000",
    "Expenses:Software": "1,500",
    "Expenses:Books": "3,000",
}


def over_budget(book, year, month):
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    out = []
    for account, limit in BUDGET.items():
        spent = Money.zero("JPY")
        for _, p in book.postings(account, start=start, end=end):
            spent = spent + convert(p.amount, "JPY")
        limit = parse_money(limit, "JPY")
        if spent > limit:
            out.append((account, spent - limit))
    return out


def main():
    set_rate("USD", "JPY", "151.37")
    set_rate("JPY", "EUR", "0.006133")
    with open(os.path.join(HERE, "data", "journal.csv"), encoding="utf-8") as f:
        book = load_csv(f.read())
    for month in (1, 2, 3):
        rows = over_budget(book, 2026, month)
        print(f"2026-{month:02d}: " + (", ".join(f"{a} +{m}" for a, m in rows) or "ok"))
    try:
        convert(Money("GBP", 100), "JPY")
    except LedgerError as e:
        print("error:", e)


if __name__ == "__main__":
    main()
