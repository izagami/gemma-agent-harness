"""The Ledger."""
from ledger.errors import LedgerError
from ledger.models import Account, Posting, Transaction, normalize_account_name
from ledger.money import Money, convert, get_default_currency, parse_money

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
