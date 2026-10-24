#!/usr/bin/env python3
"""経費申請システムへの一括登録。

usage: python3 automation/submit.py <applications.csv>
環境変数: APP_URL(既定 http://127.0.0.1:8766)、APP_USER、APP_PASS
CSV の列: 氏名,メール,部署,金額,理由(部署は画面の表示名)
1件ごとに `OK <氏名> <申請番号>`、最後に `registered N` と表示する。
"""
import csv
import os
import sys

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8766").rstrip("/")
WAIT_RESULT_MS = 30000  # 申請の結果が出るまでの最大待ち(本番は遅い)


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows, 2):
        missing = [k for k in ("氏名", "メール", "部署", "金額", "理由") if not (r.get(k) or "").strip()]
        if missing:
            sys.exit(f"{path}:{i}: 空の列があります: {', '.join(missing)}")
    return rows


def login(page):
    page.goto(URL + "/login")
    page.fill("#user", os.environ.get("APP_USER", ""))
    page.fill("#password", os.environ.get("APP_PASS", ""))
    page.click("#login")
    page.wait_for_url("**/apply")


def submit_one(form, row):
    form.get_by_test_id("name").fill(row["氏名"])
    form.get_by_test_id("email").fill(row["メール"])
    form.get_by_test_id("dept").select_option(label=row["部署"])
    form.get_by_test_id("amount").fill(row["金額"].replace(",", ""))
    form.get_by_test_id("reason").fill(row["理由"])
    form.get_by_test_id("submit").click()  # confirm() は page の dialog ハンドラで OK を押す
    result = form.get_by_test_id("result")
    result.wait_for(state="visible", timeout=WAIT_RESULT_MS)
    text = result.inner_text()
    if "受け付けました" not in text:
        raise RuntimeError("想定外の結果: " + text)
    no = text.split()[1]
    form.get_by_test_id("again").click()
    form.get_by_test_id("form").wait_for(state="visible")
    return no


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rows = read_rows(sys.argv[1])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(15000)
        page.on("dialog", lambda d: d.accept())
        login(page)
        form = page.frame_locator('iframe[name="applyform"]')
        n = 0
        for row in rows:
            # やり直しはしない: 申請が通った後にやり直すと二重登録になる
            no = submit_one(form, row)
            print(f"OK {row['氏名']} {no}", flush=True)
            n += 1
        browser.close()
    print(f"registered {n}")


if __name__ == "__main__":
    main()
