"""Build the monthly report text."""
from salesrep.aggregate import Totals, region_totals, unassigned
from salesrep.fmt import table, yen
from salesrep.loaders import load_refunds, load_sales
from salesrep.stores import StoreDirectory


def build_report(cfg, data_dir, month, detail_region=None):
    directory = StoreDirectory.load(data_dir, cfg)
    sales = load_sales(data_dir, cfg, month, directory)
    refunds = load_refunds(data_dir, cfg, month)
    regions, detail = region_totals(cfg, directory, sales, refunds)
    lines = [f"{cfg.title} {month} ({cfg.currency})", ""]
    rows = []
    grand = Totals()
    for name, t in regions.items():
        rows.append([name, yen(t.sales), yen(-t.refunds), yen(t.net)])
        grand.add(t)
    rows.append(["TOTAL", yen(grand.sales), yen(-grand.refunds), yen(grand.net)])
    lines.append(table(["region", "sales", "refunds", "net"], rows, cfg.column_width))
    missing = unassigned(cfg, directory, sales, refunds)
    if missing:
        lines += ["", "warning: stores without region: " + ", ".join(missing)]
    if detail_region:
        if detail_region not in detail:
            raise KeyError(detail_region)
        lines += ["", f"[{detail_region}] {cfg.regions[detail_region].label}"]
        lines.append(table(["store", "sales", "refunds", "net"],
                           [[sid, yen(t.sales), yen(-t.refunds), yen(t.net)] for sid, t in detail[detail_region]],
                           cfg.column_width))
    return "\n".join(lines) + "\n"
