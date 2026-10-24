"""pwkit: tested helpers for Playwright (sync API, Python) automation of slow, changing web pages.

Copy next to your script and `from pwkit import *`. Every wait is on STATE (text, visibility, count), never on time,
with one timeout (TIMEOUT ms, 15 s by default: pages answer within a few seconds, and a wait that runs out means the
selector or the page is wrong - the error then says which URL the page is on and what it has, so read it and fix that).
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
                                          returns only when the login page is gone (raises with the page's error
                                          message if the login failed) - only then page.goto() another page
Waiting
    wait_visible(scope, selector) / wait_hidden(scope, selector)
    wait_text(scope, selector, text)          until text_content() == text (exact, stripped)
    wait_text_change(scope, selector, old)    until text_content() != old
    wait_count(scope, selector, n)            until exactly n elements
    wait_attr(scope, selector, attr, value=None)  until the attribute equals value (e.g. aria-busy "false");
                                              no value: until the element has the attribute (e.g. "hidden")
    wait_options(scope, select_selector)      until a <select> has a real (non-empty value) option
    click_and_wait_change(page, click_sel, watch_sel, scope=None)   click_sel: a selector or a Locator (tabs.nth(i))
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
    search_and_wait(scope, input_sel, query, rows_sel, table_sel=None)
                                              types query into a search box and waits until the result is for THIS query
                                              (table not aria-busy, its data-query == query if it has one, every row
                                              contains the query); returns the rows Locator. The old result stays on
                                              screen while the new one loads - never read right after typing
    find_row(scope, rows_sel, key, col=0)     the row whose cell col is exactly key (not R-12 for R-125), or None
Acting
    modal_submit(page, values, submit_sel, dialog_sel='[role="dialog"]', done_sel=None)
                                              for a form that opens in a dialog after a click: waits for the dialog,
                                              fill_form(values) inside it, clicks submit_sel ONCE (a confirm() is accepted
                                              by open_browser's handler), waits until the dialog is gone. Click the row's
                                              button only after the previous dialog is gone (an open overlay eats clicks)
    submit_once(scope, page, submit_sel, done_sel, error_sel=None)
                                              clicks ONCE and waits until done_sel is visible or error_sel has text;
                                              returns ("ok", text) / ("error", text). Never clicks again (no double records)
    fill_form(scope, {selector: value, ...})  text inputs are filled; a <select> gets the option whose label (or value)
                                              is the value; a checkbox/radio is checked when the value is true
    select_label(scope, selector, label)
Output
    write_csv(path, header, rows, encoding="utf-8", newline="\\n")   rows: lists, or dicts keyed by the header names
                                              quotes a value only if it contains , or " (doubling "), no BOM
    parse_int(s)                              '¥12,345' -> 12345, '¥-3,000' -> -3000, '▲1,234' -> -1234
"""
import os
import re
import time

# 15 s: cycle 68 scripts that waited on a wrong selector (or on a page they had been redirected away from) sat in a
# 60 s wait past the checker's 22-42 s limit -> score 0 and no error message to learn from
TIMEOUT = int(os.environ.get("PWKIT_TIMEOUT", "15000"))


def _where(scope):
    """'page is at URL; it has: ...' for timeout messages"""
    try:
        page = scope if hasattr(scope, "goto") else getattr(scope, "page", None)
        if page is None:
            return ""
        have = page.eval_on_selector("body", _INSPECT_JS)[:15]
        return f" - the page is at {page.url}; it has: " + "; ".join(have)
    except Exception:
        return ""


# ---------------------------------------------------------------- selectors / discovery
def sel_testid(name, *rest):
    """'[data-testid="name"]'; called as sel_testid(page, name) it returns page.locator(that) (cycle 69 did so)"""
    if rest:
        return name.locator(f'[data-testid="{rest[0]}"]')
    return f'[data-testid="{name}"]'


def sel_label(text, *rest):
    """'[aria-label="text"]'; called as sel_label(page, text) it returns page.locator(that)"""
    if rest:
        return text.locator(f'[aria-label="{rest[0]}"]')
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


def close_browser(pw, browser, *_):
    try:
        browser.close()
    finally:
        pw.stop()


def login(page, url, user, password, user_sel, pass_sel, submit_sel, after_url_part=None):
    page.goto(url)
    page.fill(user_sel, user)
    page.fill(pass_sel, password)
    login_url = page.url
    page.click(submit_sel)
    if after_url_part:
        page.wait_for_url(re.compile(re.escape(after_url_part)), timeout=TIMEOUT)
        return

    # cycle 68 h_browser_inventory: page.goto(next page) right after the click raced the login -> redirected back to
    # the login page, then a 60 s wait for an element of the next page. Wait until the login form is gone.
    def c():
        if page.url != login_url or page.locator(pass_sel).count() == 0 or not page.locator(pass_sel).first.is_visible():
            return True, None
        msg = page.locator('[role="alert"], .error, #error').all_text_contents()
        msg = " ".join(m.strip() for m in msg if m.strip())
        if msg:
            raise RuntimeError(f"pwkit login: the login page says {msg!r} (user {user!r})")
        return False, None
    try:
        _poll(c, "the login page to go away")
    except TimeoutError:
        raise TimeoutError(f"pwkit login: still on the login page after {TIMEOUT // 1000} s{_where(page)}") from None


# ---------------------------------------------------------------- waiting
def _loc(scope, selector):
    return scope.locator(selector)


def _wait_state(scope, selector, state):
    try:
        _loc(scope, selector).first.wait_for(state=state, timeout=TIMEOUT)
    except Exception as e:
        if "Timeout" not in type(e).__name__ and "Timeout" not in str(e)[:200]:
            raise
        raise TimeoutError(f"pwkit: {selector} not {state} after {TIMEOUT // 1000} s{_where(scope)}") from None


def wait_visible(scope, selector):
    _wait_state(scope, selector, "visible")


def wait_hidden(scope, selector):
    _wait_state(scope, selector, "hidden")


def _poll(cond, what, scope=None):
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
    raise TimeoutError(f"pwkit: timed out after {TIMEOUT // 1000} s waiting for {what} (last seen: {last!r})"
                       + (_where(scope) if scope is not None else ""))


def text(scope, selector):
    loc = _loc(scope, selector)
    if loc.count() == 0:
        return ""
    return (loc.first.text_content() or "").strip()


def wait_text(scope, selector, expected):
    expected = str(expected).strip()
    return _poll(lambda: (text(scope, selector) == expected, text(scope, selector)), f"{selector} == {expected!r}", scope)


def wait_text_change(scope, selector, old):
    return _poll(lambda: ((t := text(scope, selector)) != old, t), f"{selector} to change from {old!r}", scope)


def wait_count(scope, selector, n):
    return _poll(lambda: (_loc(scope, selector).count() == n, _loc(scope, selector).count()), f"{n} x {selector}", scope)


def wait_attr(scope, selector, attr, value=None):
    """until the attribute equals value; without value: until the element HAS the attribute (e.g. 'hidden')"""
    def c():
        v = _loc(scope, selector).first.get_attribute(attr)
        return (v is not None if value is None else v == value), v
    return _poll(c, f"{selector}[{attr}{'' if value is None else '=' + repr(value)}]", scope)


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
    # click_sel may also be a Locator (e.g. tabs.nth(i)); cycle 68 passed the tab as scope= and a selector inside it
    if not isinstance(click_sel, str):
        target, scope = click_sel.first, page if scope is click_sel else scope
    elif hasattr(scope, "click") and not hasattr(scope, "goto"):     # scope is an element Locator: it is the target
        target, scope = scope, page
    else:
        target = _loc(scope, click_sel).first
    if any(target.get_attribute(a) in ("true", "page") for a in ("aria-selected", "aria-current", "aria-pressed")):
        target.click()          # already the current tab / page: its content will not change, nothing to wait for
        return None
    before = _content(scope, watch_sel)
    target.click()
    return _poll(lambda: ((c := _content(scope, watch_sel)) is not None and c != before, None), f"{watch_sel} to change", scope)


# ---------------------------------------------------------------- reading
_ROWS_JS = """(rows, cellSel) => rows.map(r => Array.from(r.querySelectorAll(cellSel)).map(c => c.textContent))"""


def read_rows(scope, row_selector, cell_selector="td"):
    """every row's cell texts (exact text_content) in one round trip"""
    loc = _loc(scope, row_selector)
    return loc.evaluate_all(_ROWS_JS, cell_selector)


def search_and_wait(scope, input_sel, query, rows_sel, table_sel=None):
    """fill the search box, then wait until the shown result belongs to this query (cycle 70 h_browser_approve: scripts
    read the previous query's rows, or clicked before the table reloaded)"""
    query = str(query)
    _loc(scope, input_sel).first.fill(query)
    q = query.lower()

    t0 = time.time()

    def c():
        # without table_sel: any busy element / any data-query on the page counts (cycle 71 passed only 'tbody tr' and
        # got 0 rows - the table was still loading - which looked like "every row matches")
        tsel = table_sel or "[aria-busy], [data-query]"
        for t in _loc(scope, tsel).all():
            if t.get_attribute("aria-busy") == "true":
                return False, "table busy"
            dq = t.get_attribute("data-query")
            if dq is not None and dq != query:
                return False, f"table shows query {dq!r}"
        texts = [x.lower() for x in _loc(scope, rows_sel).all_text_contents()]
        if not texts and time.time() - t0 < 2:
            return False, "no rows yet"
        return all(q in x for x in texts), f"{len(texts)} rows"
    _poll(c, f"rows of {rows_sel} for search {query!r}", scope)
    time.sleep(0.2)                 # one more look: a slow older response may still overwrite the table
    _poll(c, f"rows of {rows_sel} for search {query!r}", scope)
    return _loc(scope, rows_sel)


def find_row(scope, rows_sel, key, col=0):
    """the row Locator whose cell number col (td/th) is exactly key, else None"""
    rows = _loc(scope, rows_sel)
    cells = rows.evaluate_all("(rs, col) => rs.map(r => { const c = r.querySelectorAll('td,th')[col]; "
                              "return c ? c.textContent.trim() : null; })", col)
    for i, t in enumerate(cells):
        if t == str(key).strip():
            return rows.nth(i)
    return None


def modal_submit(page, values, submit_sel, dialog_sel='[role="dialog"]', done_sel=None, **_):
    """dialog form: wait for it, fill it, click submit ONCE, wait until it is gone; returns the dialog's last text"""
    dlg = page.locator(dialog_sel).first
    _wait_state(page, dialog_sel, "visible")
    fill_form(dlg, values)
    last = (dlg.text_content() or "").strip()
    dlg.locator(submit_sel).first.click()

    def c():
        if page.locator(dialog_sel).count() == 0 or not page.locator(dialog_sel).first.is_visible():
            return True, None
        return False, (page.locator(dialog_sel).first.text_content() or "").strip()[:200]
    _poll(c, f"the dialog {dialog_sel} to close after clicking {submit_sel} once", page)
    if done_sel:                    # optional: also wait for a confirmation element (toast) to show
        wait_visible(page, done_sel)
    return last


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
    # cycle 68 q_browser_fix: fill() on a <select> waits for an editable element until the timeout
    for sel, v in values.items():
        el = _loc(scope, sel).first
        el.wait_for(state="attached", timeout=TIMEOUT)
        tag, typ = el.evaluate("e => [e.tagName.toLowerCase(), (e.type || '').toLowerCase()]")
        if tag == "select":
            wait_options(scope, sel)
            try:
                el.select_option(label=str(v), timeout=3000)
            except Exception:
                el.select_option(value=str(v))
        elif typ in ("checkbox", "radio"):
            el.set_checked(bool(v) and str(v).lower() not in ("0", "false", "no", "off", ""))
        else:
            el.fill(str(v))


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
    return _poll(c, f"{done_sel} or an error", scope)


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
            if isinstance(r, dict):     # cycle 68: rows given as dicts wrote their keys on every line
                r = [r.get(h, "") for h in header]
            f.write(",".join(csv_field(x) for x in r) + newline)


def parse_int(s):
    """'¥12,345' -> 12345, '¥-3,000' -> -3000, '▲1,234' / '△1,234' -> -1234, '(1,234)' -> -1234"""
    t = str(s).strip()
    neg = t.startswith(("▲", "△", "-", "−")) or "-" in t or (t.startswith("(") and t.endswith(")"))
    digits = re.sub(r"[^\d]", "", t)
    return -int(digits) if neg and digits else int(digits or 0)


__all__ = [n for n in list(globals()) if not n.startswith("_") and n not in ("os", "re", "time")]
