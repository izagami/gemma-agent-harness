"""pwkit: tested helpers for Playwright (sync API, Python) automation of slow, changing web pages.

Copy next to your script and `from pwkit import *`. Every wait is on STATE (text, visibility, count), never on time,
and uses one generous timeout (TIMEOUT ms, 60 s by default) because real systems are slower than test ones.
`scope` below is a Page or a FrameLocator/Frame (forms inside an <iframe>: scope = page.frame_locator("iframe[...]")).

Discover
    inspect(page, scope_selector="body")  print every element with id / data-testid / name / aria-label / role
                                          (+ tag, type, text) - run it once before choosing selectors; old ids may be gone
    sel_testid(name) / sel_label(text)    '[data-testid="name"]' / '[aria-label="text"]'
Session
    open_browser()                        -> (playwright, browser, page) with page.on("dialog") accepting confirm()/alert()
    close_browser(pw, browser)            starts/stops Playwright itself: do NOT also use `with sync_playwright()`
                                          pw, browser, page = open_browser()
                                          try: ... finally: close_browser(pw, browser)
All helpers are plain functions taking the page/frame first: wait_attr(page, sel, ...), never page.wait_attr(...)
    login(page, url, user, password, user_sel, pass_sel, submit_sel, after_url_part=None)
Waiting
    wait_visible(scope, selector) / wait_hidden(scope, selector)
    wait_text(scope, selector, text)          until text_content() == text (exact, stripped)
    wait_text_change(scope, selector, old)    until text_content() != old
    wait_count(scope, selector, n)            until exactly n elements
    wait_attr(scope, selector, attr, value)   until the attribute equals value (e.g. aria-busy "false")
    wait_options(scope, select_selector)      until a <select> has a real (non-empty value) option
    click_and_wait_change(page, click_sel, watch_sel, scope=None)
                                              remembers watch_sel's text, clicks, waits until it changed: use for
                                              "next page", tabs, filters, search - anything that replaces content
                                              (a tab that is already selected: clicks and returns at once)
Reading
    text(scope, selector)                     exact text_content() ('' if missing)
    read_rows(scope, row_selector, cell_selector="td")  every row's cell texts in ONE call: list of lists
    open_and_read(page, click_locator, wait_sel, expect_text, read_sels)
                                              click (e.g. a row's 詳細), wait until wait_sel shows expect_text (the item
                                              you asked for, not the previous one), return {sel: text}
    collect_pages(page, read_page, next_sel, watch_sel)
                                              read_page() on every page; clicks next_sel and waits for watch_sel to change;
                                              stops when next is missing, hidden or disabled. Returns the concatenated list
Acting
    submit_once(scope, page, submit_sel, done_sel, error_sel=None)
                                              clicks ONCE and waits until done_sel is visible or error_sel has text;
                                              returns ("ok", text) / ("error", text). Never clicks again (no double records)
    fill_form(scope, {selector: value, ...}) / select_label(scope, selector, label)
Output
    write_csv(path, header, rows, encoding="utf-8", newline="\\n")
                                              quotes a value only if it contains , or " (doubling "), no BOM
    parse_int(s)                              '¥12,345' -> 12345, '¥-3,000' -> -3000, '▲1,234' -> -1234
"""
import os
import re
import time

TIMEOUT = int(os.environ.get("PWKIT_TIMEOUT", "60000"))


# ---------------------------------------------------------------- selectors / discovery
def sel_testid(name):
    return f'[data-testid="{name}"]'


def sel_label(text):
    return f'[aria-label="{text}"]'


_INSPECT_JS = """root => {
  const out = [];
  for (const e of root.querySelectorAll('*')) {
    const a = {};
    for (const k of ['id', 'data-testid', 'name', 'aria-label', 'role', 'type', 'placeholder'])
      if (e.getAttribute(k)) a[k] = e.getAttribute(k);
    if (!Object.keys(a).length && !['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA', 'IFRAME', 'TABLE', 'FORM'].includes(e.tagName)) continue;
    const t = (e.innerText || e.value || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
    out.push(e.tagName.toLowerCase() + ' ' + JSON.stringify(a) + (e.hidden ? ' [hidden]' : '') + (e.disabled ? ' [disabled]' : '') + (t ? ' "' + t + '"' : ''));
    if (out.length > 200) break;
  }
  return out;
}"""


def inspect(page, scope_selector="body", frame=None):
    """print the elements you can select (id / data-testid / name / aria-label / role / buttons / inputs / iframes).
    For an iframe pass frame=page.frame(name=...) or the Frame object."""
    target = frame or page
    lines = target.eval_on_selector(scope_selector, _INSPECT_JS)
    for l in lines:
        print(l)
    return lines


# ---------------------------------------------------------------- session
def open_browser(headless=True):
    """-> (pw, browser, page); dialogs (confirm/alert/prompt) are accepted automatically"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    page = browser.new_page()
    page.set_default_timeout(TIMEOUT)
    page.on("dialog", lambda d: d.accept())
    return pw, browser, page


def close_browser(pw, browser):
    try:
        browser.close()
    finally:
        pw.stop()


def login(page, url, user, password, user_sel, pass_sel, submit_sel, after_url_part=None):
    page.goto(url)
    page.fill(user_sel, user)
    page.fill(pass_sel, password)
    page.click(submit_sel)
    if after_url_part:
        page.wait_for_url(re.compile(re.escape(after_url_part)), timeout=TIMEOUT)


# ---------------------------------------------------------------- waiting
def _loc(scope, selector):
    return scope.locator(selector)


def wait_visible(scope, selector):
    _loc(scope, selector).first.wait_for(state="visible", timeout=TIMEOUT)


def wait_hidden(scope, selector):
    _loc(scope, selector).first.wait_for(state="hidden", timeout=TIMEOUT)


def _poll(cond, what):
    end = time.time() + TIMEOUT / 1000
    last = None
    while time.time() < end:
        try:
            ok, last = cond()
            if ok:
                return last
        except Exception as e:      # element not there yet / detached during a re-render
            last = repr(e)
        time.sleep(0.05)
    raise TimeoutError(f"pwkit: timed out waiting for {what} (last seen: {last!r})")


def text(scope, selector):
    loc = _loc(scope, selector)
    if loc.count() == 0:
        return ""
    return (loc.first.text_content() or "").strip()


def wait_text(scope, selector, expected):
    expected = str(expected).strip()
    return _poll(lambda: (text(scope, selector) == expected, text(scope, selector)), f"{selector} == {expected!r}")


def wait_text_change(scope, selector, old):
    return _poll(lambda: ((t := text(scope, selector)) != old, t), f"{selector} to change from {old!r}")


def wait_count(scope, selector, n):
    return _poll(lambda: (_loc(scope, selector).count() == n, _loc(scope, selector).count()), f"{n} x {selector}")


def wait_attr(scope, selector, attr, value):
    def c():
        v = _loc(scope, selector).first.get_attribute(attr)
        return v == value, v
    return _poll(c, f"{selector}[{attr}={value!r}]")


def wait_options(scope, select_selector):
    """until the <select> has an option with a non-empty value (options often arrive later by fetch)"""
    _loc(scope, select_selector + " option[value]:not([value=''])").first.wait_for(state="attached", timeout=TIMEOUT)


def _content(scope, selector):
    loc = _loc(scope, selector)
    if loc.count() == 0:
        return None
    return loc.first.inner_html()


def click_and_wait_change(page, click_sel, watch_sel, scope=None):
    """click click_sel, then wait until watch_sel's HTML differs from before (content replaced, not just 'loading')"""
    scope = scope or page
    target = _loc(scope, click_sel).first
    if any(target.get_attribute(a) in ("true", "page") for a in ("aria-selected", "aria-current", "aria-pressed")):
        target.click()          # already the current tab / page: its content will not change, nothing to wait for
        return None
    before = _content(scope, watch_sel)
    target.click()
    return _poll(lambda: ((c := _content(scope, watch_sel)) is not None and c != before, None), f"{watch_sel} to change")


# ---------------------------------------------------------------- reading
_ROWS_JS = """(rows, cellSel) => rows.map(r => Array.from(r.querySelectorAll(cellSel)).map(c => c.textContent))"""


def read_rows(scope, row_selector, cell_selector="td"):
    """every row's cell texts (exact text_content) in one round trip"""
    loc = _loc(scope, row_selector)
    return loc.evaluate_all(_ROWS_JS, cell_selector)


def open_and_read(page, click_locator, wait_sel, expect_text, read_sels, scope=None):
    """click_locator (a Locator, e.g. row.locator('button.detail')), wait until wait_sel shows expect_text (content
    that loads after opening shows the PREVIOUS item first), then read every selector in read_sels"""
    scope = scope or page
    click_locator.click()
    wait_text(scope, wait_sel, expect_text)
    return {s: (_loc(scope, s).first.text_content() or "") for s in read_sels}


def collect_pages(page, read_page, next_sel, watch_sel, scope=None, max_pages=10000):
    """read_page() -> list for the current page; then click next_sel while it is visible and enabled, waiting each
    time until watch_sel's content changes. Returns the concatenated list"""
    scope = scope or page
    out = []
    for _ in range(max_pages):
        out += list(read_page())
        nxt = _loc(scope, next_sel)
        if nxt.count() == 0 or not nxt.first.is_visible() or nxt.first.is_disabled():
            break
        click_and_wait_change(page, next_sel, watch_sel, scope)
    return out


# ---------------------------------------------------------------- acting
def fill_form(scope, values):
    for sel, v in values.items():
        _loc(scope, sel).first.fill(str(v))


def select_label(scope, selector, label):
    wait_options(scope, selector)
    _loc(scope, selector).first.select_option(label=label)


def submit_once(scope, page, submit_sel, done_sel, error_sel=None):
    """click ONCE; wait until done_sel is visible (-> ("ok", its text)) or error_sel shows a message (-> ("error", text)).
    Never clicks again: a second click can register the same record twice."""
    err_before = text(scope, error_sel) if error_sel else ""
    _loc(scope, submit_sel).first.click()

    def c():
        d = _loc(scope, done_sel)
        if d.count() and d.first.is_visible():
            return True, ("ok", (d.first.text_content() or "").strip())
        if error_sel:
            t = text(scope, error_sel)
            if t and t != err_before and not t.endswith("…") and "中" not in t[-3:]:
                return True, ("error", t)
        return False, None
    return _poll(c, f"{done_sel} or an error")


# ---------------------------------------------------------------- output
def csv_field(v):
    v = "" if v is None else str(v)
    return '"' + v.replace('"', '""') + '"' if ("," in v or '"' in v) else v


def write_csv(path, header, rows, encoding="utf-8", newline="\n"):
    """exact CSV: quote only values with , or " ; no BOM; the given line end after every line"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding=encoding, newline="") as f:
        for r in [header] + list(rows):
            f.write(",".join(csv_field(x) for x in r) + newline)


def parse_int(s):
    """'¥12,345' -> 12345, '¥-3,000' -> -3000, '▲1,234' / '△1,234' -> -1234, '(1,234)' -> -1234"""
    t = str(s).strip()
    neg = t.startswith(("▲", "△", "-", "−")) or "-" in t or (t.startswith("(") and t.endswith(")"))
    digits = re.sub(r"[^\d]", "", t)
    return -int(digits) if neg and digits else int(digits or 0)


__all__ = [n for n in list(globals()) if not n.startswith("_") and n not in ("os", "re", "time")]
