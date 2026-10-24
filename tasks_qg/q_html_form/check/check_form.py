"""Hidden check for q_html_form: drive /work/index.html with Playwright and compare with the spec."""
import json, sys, unicodedata
from playwright.sync_api import sync_playwright

PRICE = {"A": 480, "B": 120, "C": 330}
FIELDS = ["name", "email", "product", "qty", "coupon"]
fails, n = [], [0]


def ok(cond, msg):
    n[0] += 1
    if not cond:
        fails.append(msg)


def yen(v):
    return f"{v:,}円"


def expect_money(subtotal, coupon_ok):
    disc = subtotal // 10 if coupon_ok else 0
    tax = (subtotal - disc) // 10
    return subtotal, disc, tax, subtotal - disc + tax


def _main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        ctx = b.new_context(viewport={"width": 1000, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        errs = []
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.on("pageerror", lambda e: errs.append(str(e)))

        def load():
            pg.goto("file:///work/index.html")
            pg.wait_for_load_state("load")

        def txt(sel):
            loc = pg.locator(sel)
            return loc.text_content().strip() if loc.count() else None

        def money():
            return [txt(s) for s in ("#subtotal", "#discount", "#tax", "#total")]

        def blur(sel):
            pg.locator(sel).blur()

        load()
        # structure
        for f in FIELDS:
            ok(pg.locator(f"#{f}").count() == 1, f"#{f} missing")
            ok(pg.locator(f"#{f}-error").count() == 1, f"#{f}-error missing")
            ok(pg.locator(f"label[for={f}]").count() == 1, f"label for {f} missing")
        if fails:
            return report(errs)
        ok(pg.locator("label[for=name]").text_content().strip() == "お名前", "label name text")
        ok(pg.locator("label[for=qty]").text_content().strip() == "数量", "label qty text")
        ok(pg.get_attribute("#qty", "type") == "text", "qty must be type=text")
        ok(sorted(pg.eval_on_selector_all("#product option", "os => os.map(o => o.value)")) == ["", "A", "B", "C"], "product options")
        # initial state
        ok(all(txt(f"#{f}-error") == "" for f in FIELDS), "errors not empty initially")
        ok(pg.is_disabled("#submit"), "submit enabled initially")
        ok(money() == ["0円"] * 4, f"initial money {money()}")

        # errors appear only after blur
        pg.fill("#name", "")
        ok(txt("#name-error") == "", "name error before blur")
        blur("#name")
        ok(txt("#name-error") == "お名前を入力してください", f"name empty error: {txt('#name-error')!r}")
        pg.fill("#name", "あ" * 21)
        ok(txt("#name-error") == "お名前は20文字以内で入力してください", f"name long error (live after blur): {txt('#name-error')!r}")
        pg.fill("#name", "  " + "い" * 20 + " ")
        ok(txt("#name-error") == "", "20 chars with spaces must be valid")
        pg.fill("#name", "   ")
        ok(txt("#name-error") == "お名前を入力してください", "spaces only = empty")
        pg.fill("#name", "  山田 太郎  ")

        pg.fill("#email", "abc")
        ok(txt("#email-error") == "", "email error before blur")
        blur("#email")
        ok(txt("#email-error") == "メールアドレスの形式が正しくありません", f"email format: {txt('#email-error')!r}")
        pg.fill("#email", "")
        ok(txt("#email-error") == "メールアドレスを入力してください", "email empty")
        pg.fill("#email", "a b@c.jp")
        ok(txt("#email-error") == "メールアドレスの形式が正しくありません", "email with space")
        pg.fill("#email", " taro@example.co.jp ")
        ok(txt("#email-error") == "", "valid email with spaces")

        pg.focus("#product"); blur("#product")
        ok(txt("#product-error") == "商品を選択してください", f"product empty: {txt('#product-error')!r}")
        pg.select_option("#product", "A")
        ok(txt("#product-error") == "", "product chosen")

        # qty: live money update before blur
        pg.fill("#qty", "3")
        ok(money() == [yen(v) for v in expect_money(1440, False)], f"A x3 money {money()}")
        ok(txt("#qty-error") == "", "qty error before blur")
        blur("#qty")
        for bad in ["0", "100", "2.5", "-1", "3a", "１００"]:
            pg.fill("#qty", bad)
            ok(txt("#qty-error") == "数量は1〜99の整数で入力してください", f"qty {bad!r}: {txt('#qty-error')!r}")
            ok(money()[0] == "0円", f"qty {bad!r} subtotal must be 0")
        pg.fill("#qty", "")
        ok(txt("#qty-error") == "数量を入力してください", "qty empty")
        pg.fill("#qty", "１２")
        ok(txt("#qty-error") == "", "full-width 12 valid")
        ok(money() == [yen(v) for v in expect_money(480 * 12, False)], f"A x12 money {money()}")
        ok(not pg.is_disabled("#submit"), "submit should be enabled when all valid")

        # coupon
        pg.fill("#coupon", "XYZ"); blur("#coupon")
        ok(txt("#coupon-error") == "クーポンコードが無効です", f"coupon invalid: {txt('#coupon-error')!r}")
        ok(pg.is_disabled("#submit"), "invalid coupon must disable submit")
        ok(money() == [yen(v) for v in expect_money(480 * 12, False)], "invalid coupon: no discount")
        pg.fill("#coupon", " save10 ")
        ok(txt("#coupon-error") == "", "coupon case-insensitive")
        for prod, q in [("A", 12), ("B", 7), ("C", 99), ("C", 1), ("B", 13)]:
            pg.select_option("#product", prod)
            pg.fill("#qty", str(q))
            ok(money() == [yen(v) for v in expect_money(PRICE[prod] * q, True)], f"{prod}x{q} SAVE10 money {money()}")
        pg.fill("#coupon", "")
        pg.select_option("#product", "C"); pg.fill("#qty", "99")
        ok(money() == [yen(v) for v in expect_money(32670, False)], f"C x99 money {money()}")

        # product back to empty -> totals 0, submit disabled
        pg.select_option("#product", "")
        ok(money()[0] == "0円" and txt("#product-error") == "商品を選択してください", "product cleared")
        ok(pg.is_disabled("#submit"), "submit disabled with empty product")

        # submit
        pg.select_option("#product", "B"); pg.fill("#qty", "７"); pg.fill("#coupon", "Save10")
        ok(not pg.is_disabled("#submit"), "submit enabled for B x7")
        url = pg.url
        if not pg.is_disabled("#submit"):
            pg.click("#submit", timeout=3000)
        pg.wait_for_timeout(300)
        ok(pg.url == url, "page navigated on submit")
        raw = txt("#result") or ""
        exp = {"name": "山田 太郎", "email": "taro@example.co.jp", "product": "B", "qty": 7, "coupon": "SAVE10",
               "total": expect_money(840, True)[3]}
        ok(raw == json.dumps(exp, ensure_ascii=False, separators=(",", ":")), f"result JSON {raw!r} != {exp}")

        # fresh load: blur order independence, untouched fields show no error
        load()
        pg.fill("#qty", "5"); blur("#qty")
        ok(txt("#name-error") == "" and txt("#email-error") == "", "untouched fields must not show errors")
        ok(txt("#qty-error") == "", "qty 5 valid")
        ok(errs == [], f"console errors: {errs[:3]}")
        b.close()
    report([])


def report(errs):
    if errs:
        fails.append(f"console errors: {errs[:3]}")
    if fails:
        print(f"FAIL {len(fails)} of {n[0]} checks:")
        for f in fails[:15]:
            print(" -", f)
        print(f"ITEMS {max(n[0] - len(fails), 0)}/{max(n[0], len(fails))}")
        sys.exit(1)
    print(f"ok {n[0]} checks")
    print(f"ITEMS {n[0]}/{n[0]}")
    sys.exit(0)


def main():
    # graded score (tasks_qg): a crash (a missing element, a timeout) counts as one failed check, so the checks that
    # ran before it still score; the verdict is unchanged
    try:
        _main()
    except SystemExit:
        raise
    except Exception as e:
        ok(False, f"crashed: {type(e).__name__}: {str(e)[:200]}")
        report([])


main()
