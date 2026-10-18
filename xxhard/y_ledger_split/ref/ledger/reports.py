"""Reports."""
from datetime import date

from ledger.models import ACCOUNT_KINDS, normalize_account_name
from ledger.money import Money, convert, format_money, get_default_currency

def trial_balance(ledger, currency=None, until=None):
    """{account name: Money} for every account with postings, sorted by name."""
    currency = currency or get_default_currency()
    names = sorted({p.account for _, p in ledger.postings(end=until)})
    return {n: _own_balance(ledger, n, currency, until) for n in names}


def _own_balance(ledger, name, currency, until):
    total = Money.zero(currency)
    for _, p in ledger.postings(name, end=until):
        if p.account == name:
            total = total + convert(p.amount, currency)
    return total


def balance_report(ledger, currency=None, until=None):
    """One line per account (sign flipped for credit-normal kinds), grouped by kind."""
    currency = currency or get_default_currency()
    tb = trial_balance(ledger, currency, until)
    lines = []
    for kind in ACCOUNT_KINDS:
        rows = [(n, m) for n, m in tb.items() if ledger.accounts[n].kind == kind]
        if not rows:
            continue
        lines.append(f"[{kind}]")
        sub = Money.zero(currency)
        for n, m in rows:
            shown = m if ledger.accounts[n].debit_normal else -m
            sub = sub + shown
            lines.append(f"  {n:<28}{format_money(shown):>18}")
        lines.append(f"  {'total':<28}{format_money(sub):>18}")
    return "\n".join(lines) + "\n"


def monthly_report(ledger, account, year, currency=None):
    """Net movement of `account` (and sub-accounts) per month of `year`; months without postings are 0."""
    account = normalize_account_name(account)
    currency = currency or get_default_currency()
    sums = [Money.zero(currency) for _ in range(12)]
    for txn, p in ledger.postings(account, start=date(year, 1, 1), end=date(year + 1, 1, 1)):
        sums[txn.date.month - 1] = sums[txn.date.month - 1] + convert(p.amount, currency)
    lines = [f"{account} {year} ({currency})"]
    for i, m in enumerate(sums, 1):
        lines.append(f"{year}-{i:02d} {format_money(m):>18}")
    return "\n".join(lines) + "\n"
