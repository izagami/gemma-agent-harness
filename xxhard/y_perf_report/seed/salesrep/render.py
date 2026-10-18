def yen(d):
    return f"{int(d):,}" if d == int(d) else f"{d:,}"


def render(meta, store_month, categories, skus, best, stats):
    out = ""
    out += "SALES REPORT\n"
    out += f"rows: {meta['rows']}  rejected: {meta['rejected']}  unique: {meta['unique']}  billable: {meta['billable']}\n"
    out += "\n[store x month]\n"
    stores = sorted({k[0] for k in store_month})
    months = sorted({k[1] for k in store_month})
    out += "store  " + " ".join(f"{m:>12}" for m in months) + f" {'total':>14}\n"
    for st in stores:
        cells = [store_month.get((st, m)) for m in months]
        total = sum(c for c in cells if c is not None)
        out += f"{st:<6} " + " ".join(f"{yen(c) if c is not None else '-':>12}" for c in cells) + f" {yen(total):>14}\n"
    out += "\n[categories]\n"
    for c, qty, total in categories:
        out += f"{c:<12}{qty:>9}{yen(total):>16}\n"
    out += "\n[top skus]\n"
    for i, (sku, total) in enumerate(skus, 1):
        out += f"{i:>2}. {sku} {yen(total):>14}\n"
    out += "\n[orders]\n"
    count, median, mean = stats
    out += f"count {count}  median {yen(median)}  mean {yen(mean)}\n"
    out += f"best day {best[0]} {yen(best[1])}\n"
    return out
