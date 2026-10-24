#!/usr/bin/env python3
"""受注管理の画面から全受注を out/orders.csv に書き出す(docs/SPEC.md)。"""
import csv, os, re
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8765").rstrip("/")


def main():
    orders = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(15000)
        page.goto(URL + "/login")
        page.fill("#user", os.environ["EXPORT_USER"])
        page.fill("#password", os.environ["EXPORT_PASS"])
        page.click("#login")
        page.wait_for_url("**/orders")
        n = 1
        while True:
            page.wait_for_function("t => document.querySelector('#pageinfo').textContent.startsWith(t)", arg=f"{n} / ")
            page.wait_for_selector("#loading", state="hidden")
            total = int(page.inner_text("#pageinfo").split("/")[1])
            for tr in page.query_selector_all("#orders tbody tr"):
                oid = tr.get_attribute("data-id")
                cells = [td.text_content() for td in tr.query_selector_all("td")]
                tr.query_selector("button.detail").click()
                page.wait_for_function("id => document.querySelector('#modal .oid').textContent === id", arg=oid)
                owner = page.text_content("#modal .owner")
                note = page.text_content("#modal .note")
                page.click("#modal .close")
                page.wait_for_selector("#modal", state="hidden")
                orders[oid] = [oid, cells[1], int(re.sub(r"[¥,]", "", cells[2])), cells[3], owner, note]
            if n >= total:
                break
            n += 1
            page.click("#next")
        browser.close()
    os.makedirs("out", exist_ok=True)
    with open("out/orders.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer", "amount", "status", "owner", "note"])
        for oid in sorted(orders):
            w.writerow(orders[oid])
    print(f"exported {len(orders)} orders")


if __name__ == "__main__":
    main()
