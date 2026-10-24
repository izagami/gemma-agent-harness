#!/usr/bin/env python3
"""購買申請の一括承認。

usage: python3 automation/approve.py <approve_list.csv>
環境変数: APP_URL(既定 http://127.0.0.1:8772)、APP_USER、APP_PASS
CSV の列: 申請番号,コメント(1行目は見出し。コメントは空でもよい)
CSV の順に、申請中のものは承認コメントを付けて承認し `APPROVED <申請番号>`、
申請中でないもの(承認済・差戻し)は承認せずに `SKIP <申請番号> <状態>` と表示する。
最後に `approved N skipped M` と表示する。
"""
import csv
import os
import sys

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8772").rstrip("/")
TIMEOUT = 60000


def read_list(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [(r["申請番号"].strip(), r["コメント"] or "") for r in csv.DictReader(f) if (r["申請番号"] or "").strip()]


def login(page):
    page.goto(URL + "/login")
    page.fill("#user", os.environ.get("APP_USER", ""))
    page.fill("#password", os.environ.get("APP_PASS", ""))
    page.click("#login")
    page.wait_for_url("**/requests")


def search(page, q):
    page.get_by_label("申請番号・件名で検索").fill(q)
    # the old result stays on screen until the new one arrives: wait for the table of exactly this query
    page.wait_for_function(
        """q => { const t = document.querySelector('[data-testid=req-table]');
                  return t.getAttribute('aria-busy') === 'false' && t.dataset.query === q; }""", arg=q, timeout=TIMEOUT)


def approve_one(page, no, comment):
    """returns None when approved, else the status of the request"""
    search(page, no)
    rows = page.get_by_test_id("req-row").filter(has=page.locator("td:first-child", has_text=no))
    row = None
    for i in range(rows.count()):
        if rows.nth(i).locator("td").first.inner_text().strip() == no:
            row = rows.nth(i)
            break
    if row is None:
        raise SystemExit(f"{no}: 申請が見つかりません")
    status = row.locator("td").nth(4).inner_text().strip()
    if status != "申請中":
        return status
    row.get_by_role("button", name=f"{no} を承認", exact=True).click()
    page.get_by_role("dialog").wait_for(state="visible")
    page.get_by_label("承認コメント").fill(comment)
    page.once("dialog", lambda d: d.accept())
    with page.expect_response(lambda r: r.url.endswith("/api/approve"), timeout=TIMEOUT) as info:
        page.get_by_role("button", name="承認する").click()     # exactly once: a second click is a second approval
    res = info.value.json()
    if not res.get("ok"):
        raise SystemExit(f"{no}: 承認できませんでした: {res.get('error')}")
    page.locator(".overlay").wait_for(state="hidden", timeout=TIMEOUT)
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    items = read_list(sys.argv[1])
    approved = skipped = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(TIMEOUT)
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
