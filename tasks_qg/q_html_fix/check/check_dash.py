"""Hidden check for q_html_fix: drive the dashboard in Chromium (Asia/Tokyo) on the real data and on a second data set."""
import datetime, json, os, random, re, shutil, sys, unicodedata
from playwright.sync_api import sync_playwright

fails, n = [], [0]


def ok(cond, msg):
    n[0] += 1
    if not cond:
        fails.append(msg)


def load_rows(path):
    s = open(path, encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def norm(s):
    return unicodedata.normalize("NFKC", s).casefold()


def visible(rows, q, key, desc):
    q = norm(q.strip())
    out = [r for r in rows if q == "" or q in norm(r["name"]) or q in norm(r["region"])]
    if key:
        out.sort(key=lambda r: r["id"])
        out.sort(key=lambda r: r[key], reverse=desc)  # stable: ties keep id order in both directions
    return out


def utc_day(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")


def cells(r):
    return [r["name"], r["region"], f"{r['amount']:,}", utc_day(r["date"])]


def second_data():
    random.seed(11)
    rows = []
    for i in range(30):
        d = datetime.datetime(2025, 12, 28) + datetime.timedelta(minutes=random.randint(0, 60 * 24 * 10))
        rows.append({"id": i + 1, "name": random.choice(["Ａｂｅ", "abe", "ABE-trade", "Mori", "mori", "Ueda", "Oda"]),
                     "region": random.choice(["Sendai", "SENDAI", "Kobe", "Naha"]),
                     "amount": random.choice([5, 50, 500, 5000, 50000, 99, 1001, 10]), "date": d.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return rows


def run(pg, url, rows, tag):
    errs = []
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_load_state("load")
    pg.wait_for_timeout(100)

    def table():
        return pg.eval_on_selector_all("#tbl tbody tr", "trs => trs.map(tr => [...tr.cells].map(c => c.textContent.trim()))")

    def expect(q, key, desc, what):
        exp = visible(rows, q, key, desc)
        got = table()
        ok(got == [cells(r) for r in exp], f"[{tag}] {what}: table differs (first got {got[:2]}, want {[cells(r) for r in exp][:2]})")
        s = pg.text_content("#sum").strip()
        ok(s == f"合計: {sum(r['amount'] for r in exp):,}円", f"[{tag}] {what}: sum {s!r}")
        pg.click("#export-btn")
        csv = pg.input_value("#csv")
        want = "\n".join(["name,region,amount,date"] + [f"{r['name']},{r['region']},{r['amount']},{utc_day(r['date'])}" for r in exp])
        ok(csv == want, f"[{tag}] {what}: csv differs (got {csv[:80]!r})")

    expect("", None, False, "initial")
    pg.click("th[data-key=amount]"); expect("", "amount", False, "amount asc")
    pg.click("th[data-key=amount]"); expect("", "amount", True, "amount desc")
    pg.click("th[data-key=amount]"); expect("", "amount", False, "amount asc again")
    pg.click("th[data-key=date]"); expect("", "date", False, "date asc")
    queries = ["tokyo", "ＴＯＫＹＯ", " osaka ", "SATO", "ｓａ", "zzz"] if tag == "real" else ["abe", "ＡＢＥ", "sendai", " ｍｏｒｉ ", "Kobe"]
    for q in queries:
        pg.fill("#filter", q)
        expect(q, "date", False, f"filter {q!r}")
    pg.click("th[data-key=amount]")
    pg.fill("#filter", queries[0])
    expect(queries[0], "amount", False, "filter + amount asc")
    pg.fill("#filter", "")
    expect("", "amount", False, "filter cleared")
    ok(errs == [], f"[{tag}] console errors: {errs[:3]}")


def main():
    work = "/work"
    alt = "/tmp/dash-alt"
    shutil.rmtree(alt, ignore_errors=True)
    shutil.copytree(work, alt, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    rows2 = second_data()
    open(os.path.join(alt, "data.js"), "w", encoding="utf-8").write("window.SALES = " + json.dumps(rows2, ensure_ascii=False) + ";\n")
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        ctx = b.new_context(viewport={"width": 1200, "height": 900}, device_scale_factor=1, timezone_id="Asia/Tokyo", locale="ja-JP")
        # graded score (tasks_qg): a phase that crashes counts as one failed check and the others still run
        for url, rws, tag in (("file:///work/index.html", load_rows("/check/orig_data.js"), "real"),
                              (f"file://{alt}/index.html", rows2, "other data")):
            try:
                run(ctx.new_page(), url, rws, tag)
            except Exception as e:
                ok(False, f"[{tag}] crashed: {type(e).__name__}: {str(e)[:200]}")
        # phone width: no horizontal overflow of the page, table still shown
        try:
            phone(b)
        except Exception as e:
            ok(False, f"375px: crashed: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    if fails:
        print(f"FAIL {len(fails)} of {n[0]} checks:")
        for f in fails[:15]:
            print(" -", f)
        print(f"ITEMS {n[0] - len(fails)}/{n[0]}")
        sys.exit(1)
    print(f"ok {n[0]} checks")
    print(f"ITEMS {n[0]}/{n[0]}")


def phone(b):
    if True:
        m = b.new_context(viewport={"width": 375, "height": 740}, device_scale_factor=1, timezone_id="Asia/Tokyo", locale="ja-JP")
        pg = m.new_page()
        pg.goto("file:///work/index.html"); pg.wait_for_load_state("load"); pg.wait_for_timeout(100)
        sw, cw = pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        ok(sw <= cw, f"375px: page scrollWidth {sw} > clientWidth {cw}")
        bw = pg.evaluate("document.body.scrollWidth")
        ok(bw <= 375, f"375px: body scrollWidth {bw}")
        box = pg.locator("#tbl").bounding_box()
        ok(box is not None and box["height"] > 100, "375px: table not visible")
        ok(pg.locator("#tbl tbody tr").count() == len(load_rows("/check/orig_data.js")), "375px: rows missing")
        for sel in ("#filter", "#export-btn"):
            bb = pg.locator(sel).bounding_box()
            ok(bb is not None and bb["x"] >= 0 and bb["x"] + bb["width"] <= 375 + 0.5, f"375px: {sel} outside the screen {bb}")


main()
