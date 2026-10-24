#!/usr/bin/env python3
"""購買申請の一括承認。

usage: python3 automation/approve.py <approve_list.csv>
環境変数: APP_URL(既定 http://127.0.0.1:8772)、APP_USER、APP_PASS
CSV の列: 申請番号,コメント(1行目は見出し。コメントは空でもよい)
CSV の順に、申請中のものは承認コメントを付けて承認し `APPROVED <申請番号>`、
申請中でないもの(承認済・差戻し)は承認せずに `SKIP <申請番号> <状態>` と表示する。
最後に `approved N skipped M` と表示する。
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8772").rstrip("/")
WAIT = 0.8        # 検索や承認のあと、画面が更新されるまでの待ち(秒)
RETRIES = 2       # 承認の完了表示が出ないときに押し直す回数


def read_list(path):
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f.read().splitlines()[1:]:
            if not line.strip():
                continue
            no, comment = line.split(",", 1)
            items.append((no.strip(), comment))
    return items


def login(page):
    page.goto(URL + "/login")
    page.fill("#user", os.environ.get("APP_USER", ""))
    page.fill("#password", os.environ.get("APP_PASS", ""))
    page.click("#login")
    page.wait_for_url("**/requests")


def approve_one(page, no, comment):
    """returns None when approved, else the status of the request"""
    page.fill("#search", no)
    time.sleep(WAIT)
    row = page.locator("#results tr").first
    status = row.locator("td").nth(4).inner_text().strip()
    if status != "申請中":
        return status
    row.locator("button.approve").click()
    page.fill("#comment", comment)
    for _ in range(RETRIES + 1):
        page.click("#ok")
        time.sleep(WAIT)
        if page.is_visible("#toast"):
            break
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    items = read_list(sys.argv[1])
    approved = skipped = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(5000)
        login(page)
        for no, comment in items:
            status = approve_one(page, no, comment)
            if status is None:
                print(f"APPROVED {no}", flush=True)
                approved += 1
            else:
                print(f"SKIP {no} {status}", flush=True)
                skipped += 1
        browser.close()
    print(f"approved {approved} skipped {skipped}")


if __name__ == "__main__":
    main()
