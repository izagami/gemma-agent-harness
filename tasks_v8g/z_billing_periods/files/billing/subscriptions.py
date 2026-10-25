"""Subscriptions (data/subscriptions.csv).

Columns: customer,name,plan,start,change_on,change_to
  start      contract start date = billing anchor
  change_on  optional date from which the customer is on plan `change_to`
"""
import csv
import os
from typing import NamedTuple, Optional

from billing.dates import parse_date


class Subscription(NamedTuple):
    customer: str
    name: str
    plan: str
    start: object
    change_on: Optional[object] = None
    change_to: Optional[str] = None

    def plan_on(self, d):
        """Plan code in force on date d."""
        if self.change_on is not None and d >= self.change_on:
            return self.change_to
        return self.plan


class SubscriptionError(Exception):
    pass


def load_subscriptions(path):
    subs = {}
    with open(path, newline="", encoding="utf-8") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            where = f"{os.path.basename(path)}:{n}"
            cust = row["customer"].strip()
            if cust in subs:
                raise SubscriptionError(f"{where}: duplicate customer {cust}")
            try:
                start = parse_date(row["start"])
                change_on = parse_date(row["change_on"]) if (row.get("change_on") or "").strip() else None
            except ValueError as e:
                raise SubscriptionError(f"{where}: {e}") from None
            change_to = (row.get("change_to") or "").strip() or None
            if (change_on is None) != (change_to is None):
                raise SubscriptionError(f"{where}: change_on and change_to go together")
            if change_on is not None and change_on < start:
                raise SubscriptionError(f"{where}: plan change before start")
            subs[cust] = Subscription(cust, row["name"].strip(), row["plan"].strip(), start, change_on, change_to)
    return subs
