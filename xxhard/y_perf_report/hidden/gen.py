"""Deterministic test data: python3 gen.py [--rows N] [--seed S] OUT.csv

Columns: order_id,line,ts,store,sku,qty,unit_price,currency,status
Some rows are re-sent later with the same (order_id, line) (corrections) and a few are malformed.
"""
import argparse
import random
from datetime import datetime, timedelta

BASE = datetime(2025, 4, 1)


def generate(rows, seed, out):
    rnd = random.Random(seed)
    stores = [f"S{i:02d}" for i in range(1, 41)]
    out.write("order_id,line,ts,store,sku,qty,unit_price,currency,status\n")
    written, order, sent = 0, 100000, []
    while written < rows:
        order += 1
        store = rnd.choice(stores)
        ts = BASE + timedelta(seconds=rnd.randrange(365 * 86400))
        currency = rnd.choices(["JPY", "USD", "EUR"], [80, 12, 8])[0]
        for line in range(1, rnd.randint(1, 4) + 1):
            if written >= rows:
                break
            sku = f"P{rnd.randint(1, 2050):04d}"
            qty = rnd.randint(1, 5)
            if currency == "JPY":
                price = str(rnd.randint(1, 400) * 50)
            else:
                price = f"{rnd.randint(99, 25000) / 100:.2f}"
            status = rnd.choices(["ok", "cancel", "refund"], [90, 6, 4])[0]
            row = [str(order), str(line), ts.strftime("%Y-%m-%d %H:%M:%S"), store, sku, str(qty), price, currency, status]
            r = rnd.random()
            if r < 0.001:
                row[5] = rnd.choice(["", "x", "-1"])
            elif r < 0.002:
                row[6] = rnd.choice(["", "1,000", "abc"])
            out.write(",".join(row) + "\n")
            written += 1
            sent.append(row)
            if rnd.random() < 0.02 and written < rows:
                again = list(rnd.choice(sent[-5000:]))
                again[8] = rnd.choices(["ok", "cancel", "refund"], [50, 30, 20])[0]
                again[5] = str(rnd.randint(1, 5))
                out.write(",".join(again) + "\n")
                written += 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--rows", type=int, default=300000)
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        generate(a.rows, a.seed, f)


if __name__ == "__main__":
    main()
