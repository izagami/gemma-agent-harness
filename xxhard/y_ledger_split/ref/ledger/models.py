"""Accounts, postings and transactions."""
from dataclasses import dataclass, field
from datetime import date

from ledger.errors import LedgerError
from ledger.money import Money

ACCOUNT_KINDS = ("asset", "liability", "equity", "income", "expense")


def normalize_account_name(name):
    """'assets : Bank' -> 'Assets:Bank' (segments trimmed, first letter upper-cased)."""
    parts = [p.strip() for p in name.split(":")]
    if not all(parts):
        raise LedgerError(f"bad account name {name!r}")
    return ":".join(p[0].upper() + p[1:] for p in parts)


@dataclass(frozen=True)
class Account:
    name: str
    kind: str

    def __post_init__(self):
        if self.kind not in ACCOUNT_KINDS:
            raise LedgerError(f"unknown account kind {self.kind}")

    @property
    def debit_normal(self):
        return self.kind in ("asset", "expense")


@dataclass(frozen=True)
class Posting:
    account: str
    amount: Money


@dataclass
class Transaction:
    date: date
    description: str
    postings: list = field(default_factory=list)

    def validate(self):
        if len(self.postings) < 2:
            raise LedgerError(f"{self.description}: needs at least two postings")
        sums = {}
        for p in self.postings:
            sums[p.amount.currency] = sums.get(p.amount.currency, 0) + p.amount.minor
        unbalanced = sorted(c for c, s in sums.items() if s != 0)
        if unbalanced:
            raise LedgerError(f"{self.description}: unbalanced in {', '.join(unbalanced)}")
