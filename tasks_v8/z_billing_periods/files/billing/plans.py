"""Plan catalogue (data/plans.csv: code,name,monthly)."""
import csv
import os
from typing import NamedTuple


class Plan(NamedTuple):
    code: str
    name: str
    monthly: int  # yen per full period


class PlanError(Exception):
    pass


def load_plans(path):
    plans = {}
    with open(path, newline="", encoding="utf-8") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            code = (row.get("code") or "").strip()
            if not code:
                raise PlanError(f"{os.path.basename(path)}:{n}: missing plan code")
            try:
                monthly = int(row["monthly"])
            except (KeyError, ValueError):
                raise PlanError(f"{os.path.basename(path)}:{n}: bad monthly price") from None
            if monthly < 0:
                raise PlanError(f"{os.path.basename(path)}:{n}: negative price")
            plans[code] = Plan(code, row.get("name", code).strip(), monthly)
    return plans


def get_plan(plans, code):
    try:
        return plans[code]
    except KeyError:
        raise PlanError(f"unknown plan: {code}") from None
