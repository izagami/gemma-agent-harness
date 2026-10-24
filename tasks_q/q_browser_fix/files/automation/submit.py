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
import time

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8766").rstrip("/")
RETRIES = 2          # 画面が重いときのやり直し回数
WAIT_RESULT = 1.0    # 申請ボタンを押してから結果を読むまでの待ち(秒)


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


def fill_form(page, row):
    page.fill("#name", row["氏名"])
    page.fill("#email", row["メール"])
    page.select_option("#dept", row["部署"])
    page.fill("#amount", row["金額"].replace(",", ""))
    page.fill("#reason", row["理由"])


def submit_one(page, row):
    fill_form(page, row)
    page.click("#submit")
    time.sleep(WAIT_RESULT)
    text = page.inner_text("#result", timeout=2000)
    if "受け付けました" not in text:
        raise RuntimeError("想定外の結果: " + text)
    no = text.split()[1]
    page.click("#again")
    return no


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rows = read_rows(sys.argv[1])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(5000)
        login(page)
        n = 0
        for row in rows:
            for attempt in range(RETRIES + 1):
                try:
                    no = submit_one(page, row)
                    break
                except PWTimeout:
                    if attempt == RETRIES:
                        raise
                    print(f"retry {row['氏名']} ({attempt + 1})", file=sys.stderr)
                    page.goto(URL + "/apply")
            print(f"OK {row['氏名']} {no}", flush=True)
            n += 1
        browser.close()
    print(f"registered {n}")


if __name__ == "__main__":
    main()
