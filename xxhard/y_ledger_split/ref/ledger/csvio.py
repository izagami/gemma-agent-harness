"""CSV import/export."""
import csv
import io
from datetime import date

from ledger.book import Ledger
from ledger.errors import LedgerError
from ledger.models import normalize_account_name
from ledger.money import format_money, parse_money

CSV_FIELDS = ["txn", "date", "description", "account", "amount"]


def load_csv(text, accounts=None):
    """Rows with the same txn number form one transaction. accounts: {name: kind} to open first;
    unknown accounts are opened with a kind guessed from their first segment."""
    ledger = Ledger()
    for name, kind in (accounts or {}).items():
        ledger.open(name, kind)
    groups = {}
    order = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != CSV_FIELDS:
        raise LedgerError(f"bad header: {reader.fieldnames}")
    for n, row in enumerate(reader, 2):
        try:
            when = date.fromisoformat(row["date"])
        except ValueError:
            raise LedgerError(f"line {n}: bad date {row['date']!r}") from None
        key = row["txn"]
        if key not in groups:
            groups[key] = (when, row["description"], [])
            order.append(key)
        name = normalize_account_name(row["account"])
        if name not in ledger.accounts:
            ledger.open(name, _guess_kind(name))
        groups[key][2].append((name, parse_money(row["amount"])))
    for key in order:
        when, desc, postings = groups[key]
        ledger.post(when, desc, postings)
    return ledger


_KIND_GUESS = {"Assets": "asset", "Liabilities": "liability", "Equity": "equity",
               "Income": "income", "Expenses": "expense"}


def _guess_kind(name):
    top = name.split(":")[0]
    if top not in _KIND_GUESS:
        raise LedgerError(f"cannot guess kind of account {name}")
    return _KIND_GUESS[top]


def dump_csv(ledger):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(CSV_FIELDS)
    for i, txn in enumerate(ledger.transactions, 1):
        for p in txn.postings:
            w.writerow([i, txn.date.isoformat(), txn.description, p.account, format_money(p.amount)])
    return out.getvalue()
