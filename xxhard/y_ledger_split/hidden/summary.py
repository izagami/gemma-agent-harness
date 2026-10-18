"""Print the household summary for data/journal.csv."""
import os
from datetime import date

import ledger

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ledger.set_rate("USD", "JPY", "151.37")
    ledger.set_rate("EUR", "JPY", "163.05")
    with open(os.path.join(HERE, "data", "journal.csv"), encoding="utf-8") as f:
        book = ledger.load_csv(f.read())
    print(ledger.balance_report(book))
    print(ledger.balance_report(book, until=date(2026, 2, 1)))
    print(ledger.monthly_report(book, "expenses", 2026))
    print(ledger.monthly_report(book, "Income", 2026, currency="USD"))
    posted = []
    book.on_post(posted.append)
    book.post(date(2026, 3, 20), "coffee", [("Expenses:Food", "480"), ("Assets:Bank", "-480")])
    print(len(posted), ledger.format_money(book.balance("Expenses")))
    print(ledger.dump_csv(book).splitlines()[-1])


if __name__ == "__main__":
    main()
