#!/usr/bin/env python3
"""Export all stock of all warehouses to out/inventory.csv (reference solution)."""
import csv, os, re, sys
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8770").rstrip("/")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "inventory.csv")
T = 60000


def wait_loaded(page, wh):
    page.wait_for_function(
        """wh => { const t = document.querySelector('[data-testid=stock-table]');
                   return t.getAttribute('aria-busy') === 'false' && t.dataset.wh === wh; }""", arg=wh, timeout=T)


def parse_qty(s):
    s = s.strip().replace(",", "")
    return -int(s[1:]) if s.startswith("▲") else int(s)


def main():
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_default_timeout(T)
        page.goto(URL + "/login")
        page.get_by_label("ユーザー名").fill(os.environ.get("STOCK_USER", ""))
        page.get_by_label("パスワード").fill(os.environ.get("STOCK_PASS", ""))
        page.get_by_role("button", name="ログイン").click()
        page.wait_for_url("**/stock")
        page.wait_for_selector("[role=tab]")
        tabs = page.locator("[role=tab]")
        codes = [tabs.nth(i).get_attribute("data-wh") for i in range(tabs.count())]
        wait_loaded(page, codes[0])
        cb = page.get_by_test_id("instock-only")
        if cb.is_checked():
            cb.uncheck()
            wait_loaded(page, codes[0])
        for code in codes:
            page.locator(f"[role=tab][data-wh='{code}']").click()
            wait_loaded(page, code)
            while page.get_by_test_id("load-more").is_visible():
                n = page.get_by_test_id("stock-row").count()
                page.get_by_test_id("load-more").click()
                page.wait_for_function(
                    """n => { const t = document.querySelector('[data-testid=stock-table]');
                              return t.getAttribute('aria-busy') === 'false' &&
                                     t.querySelectorAll('[data-testid=stock-row]').length > n; }""", arg=n, timeout=T)
            data = page.eval_on_selector_all(
                "[data-testid=stock-row]",
                "rs => rs.map(r => ({sku: r.querySelector('[data-col=sku]').textContent,"
                " name: r.querySelector('[data-col=name]').textContent, qty: r.querySelector('[data-col=qty]').textContent}))")
            total = int(re.search(r"全\s*(\d+)", page.get_by_test_id("count").inner_text()).group(1))
            seen = {}
            for d in data:
                seen.setdefault(d["sku"], d)
            if len(seen) != total:
                sys.exit(f"{code}: got {len(seen)} items, page says {total}")
            rows += [(code, d["sku"], d["name"], parse_qty(d["qty"])) for d in seen.values()]
        b.close()
    rows.sort(key=lambda r: (r[0], r[1]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["warehouse", "sku", "name", "qty"])
        w.writerows(rows)
    print(f"exported {len(rows)} items")


if __name__ == "__main__":
    main()
