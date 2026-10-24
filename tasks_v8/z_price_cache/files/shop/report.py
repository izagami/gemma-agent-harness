"""Daily sales report.

Format (one line per customer who ordered that day, sorted by customer id):

    # <day>
    <customer id>  <name padded to 12>  orders=<n>  items=<n>  total=<yen with , separators>
    TOTAL  orders=<n>  items=<n>  total=<yen>

A day without orders prints the header and "TOTAL  orders=0  items=0  total=0".
"""


def daily_report(book, customers, day):
    per = {}
    for o in book.on_day(day):
        n, items, total = per.get(o.customer_id, (0, 0, 0))
        per[o.customer_id] = (n + 1, items + o.items, total + o.total)
    out = [f"# {day}"]
    for cid in sorted(per):
        n, items, total = per[cid]
        name = customers.get(cid).name
        out.append(f"{cid}  {name:<12}  orders={n}  items={items}  total={total:,}")
    n = sum(v[0] for v in per.values())
    items = sum(v[1] for v in per.values())
    total = sum(v[2] for v in per.values())
    out.append(f"TOTAL  orders={n}  items={items}  total={total:,}")
    return "\n".join(out)
