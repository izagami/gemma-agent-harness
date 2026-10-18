"""Double-entry bookkeeping: money, accounts, transactions, a ledger, CSV I/O and reports.

Everything lives in this one module and it has become hard to work with.
"""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

__all__ = [
    "LedgerError", "Money", "parse_money", "format_money", "set_rate", "clear_rates", "convert",
    "set_default_currency", "get_default_currency", "ACCOUNT_KINDS", "Account", "Posting",
    "Transaction", "normalize_account_name", "Ledger", "load_csv", "dump_csv",
    "balance_report", "monthly_report", "trial_balance",
]


class LedgerError(Exception):
    """Any error raised by this library."""


# ---------------------------------------------------------------- money

_DECIMALS = {"JPY": 0, "USD": 2, "EUR": 2, "GBP": 2}
_RATES = {}                     # (src, dst) -> Decimal
_DEFAULT_CURRENCY = "JPY"


def set_default_currency(code):
    global _DEFAULT_CURRENCY
    if code not in _DECIMALS:
        raise LedgerError(f"unknown currency {code}")
    _DEFAULT_CURRENCY = code


def get_default_currency():
    return _DEFAULT_CURRENCY


@dataclass(frozen=True, order=True)
class Money:
    """An amount in minor units (yen, cents) of one currency."""
    currency: str
    minor: int

    def __post_init__(self):
        if self.currency not in _DECIMALS:
            raise LedgerError(f"unknown currency {self.currency}")

    @classmethod
    def zero(cls, currency=None):
        return cls(currency or get_default_currency(), 0)

    def _check(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise LedgerError(f"currency mismatch: {self.currency} vs {other.currency}")
        return None

    def __add__(self, other):
        bad = self._check(other)
        return bad if bad is NotImplemented else Money(self.currency, self.minor + other.minor)

    def __sub__(self, other):
        bad = self._check(other)
        return bad if bad is NotImplemented else Money(self.currency, self.minor - other.minor)

    def __neg__(self):
        return Money(self.currency, -self.minor)

    def __mul__(self, k):
        if not isinstance(k, int):
            return NotImplemented
        return Money(self.currency, self.minor * k)

    def is_zero(self):
        return self.minor == 0

    def decimal(self):
        return Decimal(self.minor).scaleb(-_DECIMALS[self.currency])

    def __str__(self):
        return format_money(self)


_MONEY_RE = re.compile(r"^\s*(-)?\s*([0-9][0-9,]*)(?:\.([0-9]+))?\s*([A-Z]{3})?\s*$")


def parse_money(text, currency=None):
    """'1,234.50 USD', '-500', '12 JPY'. Without a code, `currency` or the default currency is used."""
    m = _MONEY_RE.match(text)
    if not m:
        raise LedgerError(f"bad amount {text!r}")
    sign, whole, frac, code = m.groups()
    code = code or currency or get_default_currency()
    if code not in _DECIMALS:
        raise LedgerError(f"unknown currency {code}")
    places = _DECIMALS[code]
    frac = frac or ""
    if len(frac) > places:
        raise LedgerError(f"too many decimals for {code}: {text!r}")
    minor = int(whole.replace(",", "") + frac.ljust(places, "0"))
    return Money(code, -minor if sign else minor)


def format_money(m):
    places = _DECIMALS[m.currency]
    sign = "-" if m.minor < 0 else ""
    whole, frac = divmod(abs(m.minor), 10 ** places)
    text = f"{whole:,}" + (f".{frac:0{places}d}" if places else "")
    return f"{sign}{text} {m.currency}"


def set_rate(src, dst, rate):
    """1 src = rate dst. The inverse direction is derived automatically."""
    rate = Decimal(str(rate))
    if rate <= 0:
        raise LedgerError("rate must be positive")
    _RATES[(src, dst)] = rate


def clear_rates():
    _RATES.clear()


def _rate(src, dst):
    if src == dst:
        return Decimal(1)
    if (src, dst) in _RATES:
        return _RATES[(src, dst)]
    if (dst, src) in _RATES:
        return 1 / _RATES[(dst, src)]
    raise LedgerError(f"no rate {src}->{dst}")


def convert(m, currency):
    value = m.decimal() * _rate(m.currency, currency)
    places = _DECIMALS[currency]
    minor = (value.scaleb(places)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    return Money(currency, int(minor))


# ---------------------------------------------------------------- accounts & transactions

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


# ---------------------------------------------------------------- ledger

class Ledger:
    def __init__(self):
        self.accounts = {}          # name -> Account
        self.transactions = []      # kept sorted by date (stable)
        self._listeners = []

    def open(self, name, kind):
        name = normalize_account_name(name)
        if name in self.accounts:
            raise LedgerError(f"account exists: {name}")
        self.accounts[name] = Account(name, kind)
        return self.accounts[name]

    def on_post(self, callback):
        self._listeners.append(callback)

    def post(self, when, description, postings):
        """postings: [(account name, Money or amount text), ...]"""
        items = []
        for name, amount in postings:
            name = normalize_account_name(name)
            if name not in self.accounts:
                raise LedgerError(f"unknown account {name}")
            if isinstance(amount, str):
                amount = parse_money(amount)
            items.append(Posting(name, amount))
        txn = Transaction(when, description, items)
        txn.validate()
        i = len(self.transactions)
        while i > 0 and self.transactions[i - 1].date > when:
            i -= 1
        self.transactions.insert(i, txn)
        for cb in self._listeners:
            cb(txn)
        return txn

    def postings(self, account=None, start=None, end=None):
        """(transaction, posting) pairs; account matches itself and its sub-accounts; end is exclusive."""
        for txn in self.transactions:
            if start and txn.date < start or end and txn.date >= end:
                continue
            for p in txn.postings:
                if account is None or p.account == account or p.account.startswith(account + ":"):
                    yield txn, p

    def balance(self, account, currency=None, until=None):
        """Sum of the account's postings before `until`, converted to `currency` (default currency if None)."""
        account = normalize_account_name(account)
        currency = currency or get_default_currency()
        total = Money.zero(currency)
        for _, p in self.postings(account, end=until):
            total = total + convert(p.amount, currency)
        return total


# ---------------------------------------------------------------- CSV

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


# ---------------------------------------------------------------- reports

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
