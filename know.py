"""KNOW=1: domain pitfall sheets and a start-of-task brief, picked by what the task's files look like.

10-24: Claude solved the 6 q25 tasks Gemma never passes (db_migrate, browser_export, browser_fix, vba_sales,
vba_dates, vba_text) on the first try; Gemma's failures there matched, one for one, the domain facts Claude used
(VBA Mod sign, tie order, cp932/CRLF; a modal read before its content arrived; no rollback). The sheets below are
those facts as general knowledge of each domain - not answers to any task - so they must hold for any task of
the kind. Keep each line a checkable fact.
"""
import os
import re

SHEETS = {
    "vba": """\
Porting VBA to Python - VBA behaviours that differ from Python (reproduce them exactly; the output must match byte for byte):
- Trim/LTrim/RTrim remove ONLY ASCII spaces (not tabs, not full-width spaces U+3000).
- CLng/CInt and Round(x, n) round half to EVEN (banker's): CLng(2.5)=2, CLng(3.5)=4. Python round() does the same.
  Format(x, "0") / Format(x, "#,##0") / Format(x, "0.0%") round half AWAY from zero (use decimal ROUND_HALF_UP).
- Integer division a \\ b and a Mod b truncate toward zero: -7 \\ 12 = 0, -7 Mod 12 = -7. Python // and % floor: do not use them for negatives.
- Format(x, "#,##0") -> "1,234" / "-1,234"; Format(x, "0.0%") -> x*100 with one decimal + "%".
- CStr(Long) has no leading space; CStr(Double) gives up to 15 significant digits, no trailing zeros, exponent as 1E+15 / 1E-05.
- Val(s) reads only the leading number, skipping spaces even between digits ("  2 500" -> 2500, "1,200" -> 1, "350pt" -> 350, "1e2" -> 100, "" -> 0).
- IsNumeric accepts signs, thousands commas, decimals, exponents; Split("", "/") has NO elements.
- DateSerial(y, m, d) carries over: day 0 = last day of the previous month, month 13 = January next year, day 31 in a 30-day month = 1st of next month.
  Years 0-29 become 2000-2029 and 30-99 become 1900-1999 (so a 2-digit year fails a Year(dt) = y check).
- DateAdd("m", n, d) clamps to the month end (Jan 31 + 1 month = Feb 28). DateAdd("d", n, d) adds days.
- Weekday(d, vbMonday): Mon=1..Sun=7. DateDiff("ww", a, b) counts week starts (Sunday) crossed, not 7-day blocks.
- Format(d, "aaa") = Japanese short weekday 月火水木金土日; "yyyy/mm/dd" zero-pads.
- Like: * any string, ? one char, # one digit 0-9; binary compare (case-sensitive).
- Mid/Left/Len count UTF-16 units; LenB(StrConv(s, vbFromUnicode)) = byte length in Shift_JIS (cp932).
- StrConv(s, vbKatakana): hiragana -> katakana. StrConv(s, vbNarrow): full-width -> half-width; katakana with dakuten split
  (ガ -> ｶﾞ, パ -> ﾊﾟ, ヴ -> ｳﾞ), full-width ASCII/space -> ASCII; characters with no half-width form (ヰ ヱ ヮ ヵ ヶ, kanji) stay.
- A Scripting.Dictionary keeps insertion order. Reproduce the macro's own sort loop exactly (a bubble sort that swaps on <=
  reverses equal neighbours) - sorted() gives a different order for ties.
- Loops "For r = 2 To lastRow" visit EVERY row up to the last non-empty cell of the key column, including blank rows in
  between: keep whatever the macro prints for them (an error line, an empty field) - do not skip them.
- An empty cell read as a number is 0 (Empty). Excel "CSV (comma delimited)" on Japanese Windows is cp932 (Shift_JIS).
- Open ... For Output + Print # writes cp932 with CRLF after every line. Write bytes the same way (encoding="cp932", newline="").
- When the macro exits early (MsgBox + Exit Sub) it writes no file.
Method: before writing code, go through the macro line by line and write down, for each line, which behaviour above it uses.""",

    "browser": """\
Browser automation (Playwright, Python) on a slow page whose speed varies - facts that decide whether it works:
- Wait for STATE, never for time: no time.sleep for results. Use locator.wait_for(), page.wait_for_function(...) or
  expect-style checks on the exact condition (text equals X, element visible/hidden, "loading" gone, button enabled).
- Content that loads after something opens (a modal, a detail pane, a page of a table) shows OLD content first:
  wait until it shows the item you asked for (e.g. its id/number equals the row you clicked) before reading it.
- Paging: after clicking next, wait until the page indicator/rows change AND the loading marker is gone; stop when
  the next button is disabled or the last page number is reached. Collect by id so each item is taken exactly once.
- Read the current page/HTML before choosing selectors: forms may be inside an <iframe> (page.frame_locator(...)),
  elements may have data-testid instead of id, <select> options may be filled later by fetch (wait for a real option),
  submitting may open a confirm() dialog (page.on("dialog", lambda d: d.accept())).
- select_option(label=...) selects by the visible text; value=... by the option value.
- Never click a submit button twice for the same record: after the click, wait for the result or the error with a
  long timeout. Retry only steps before the submit (opening/filling the form); a retried submit double-registers.
- Use one generous timeout (e.g. 60 s) for every wait: the real system is slower than the test one.
- Read text with text_content() when exact characters matter; inner_text() may change whitespace.
- Output files: UTF-8 without BOM and "\\n" line ends unless told otherwise - open(path, "w", encoding="utf-8", newline="").
  CSV: quote a value only when it contains , or " (double the " inside), as the spec says.
- Credentials and URLs come from the environment variables named in the task; the test may use another user.
- Never change the provided app/server files: test against them as they are (cycle 48: a model edited app/server.py, which fails the task).""",

    "sqlite": """\
SQLite schema migration / data access in Python - facts that decide correctness:
- All or nothing: sqlite3.connect(path, isolation_level=None), then con.execute("BEGIN IMMEDIATE") ... COMMIT, and
  ROLLBACK on any exception. executescript() COMMITs first and runs outside your transaction - do not use it inside one.
  Never call commit() inside the loop. DDL (CREATE/ALTER/DROP) and PRAGMA user_version are transactional in SQLite.
- After a failed run the file must be byte-identical: check with a hash in your own test.
- Rename old tables first (ALTER TABLE t RENAME TO t_old), create the new ones with the final names, copy, drop the old ones.
- REFERENCES ... ON DELETE CASCADE only acts when PRAGMA foreign_keys=ON on the connection that deletes; PRAGMA
  foreign_key_check lists violations.
- sqlite3.connect() CREATES a missing file: use "file:path?mode=rw" with uri=True when the file must exist.
- Use parameters (?), never string formatting, for values; escape LIKE wildcards with ESCAPE when searching user text.
- Keyset pagination needs a total order (e.g. ORDER BY price DESC, id ASC with a (price, id) cursor) or rows repeat/vanish.
- Re-running on an already-migrated database must change nothing (check the version first).""",

    "firewall": """\
Firewall rule audits (nftables/iptables style, first match wins) - check every one of these, for EVERY address family:
- Every (family, hook) pair the policy covers needs a chain: with no chain for e.g. ip6/output, that traffic is not
  filtered at all. IPv4 and IPv6 get the same policy unless the policy says otherwise - compare the two rule lists line by line.
- Every chain with policy drop needs an established/related accept, in BOTH directions: replies to accepted incoming
  connections leave through the OUTPUT chain and are dropped without it.
- Shadowing: a broader accept earlier in the chain (no source limit, a port list that includes the restricted port, an
  unlimited accept before a rate-limited one) makes the later, narrower rule useless - remove or narrow the broad one.
- Address sets/CIDRs must be exactly as wide as the policy (a /16 where the policy says /24 is a violation).
- Temporary/debug/vendor rules not in the policy must go; comments like TEMP or a person's name are the hint.
- A rate-limited accept lets the excess fall through to the next rules: make sure nothing later accepts it (add an explicit drop).
- Check with the provided simulator/tool on a handful of packets (a disallowed SSH source, a reply ct=established on
  output, one ip6 output packet) - keep it small: fixing the rules matters more than a big test.""",

    "textout": """\
Exact output files - facts that decide a byte-for-byte match:
- Find out the expected encoding and line ends from a provided expected file (bytes: b"\\r\\n" vs b"\\n", BOM, cp932 vs
  UTF-8) and write exactly that: open(path, "w", encoding=..., newline="") and put the line ends in yourself.
- Compare your output with the provided expected file byte for byte (cmp / filecmp) - "looks the same" is not enough.
- Keep header texts, column order and number formats exactly as the spec/legacy code writes them.""",
}


def detect(root, task):
    """-> list of sheet keys that apply to the task's files"""
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        files += [os.path.relpath(os.path.join(dp, f), root) for f in fns]
    low = task.lower()
    keys = []
    if any(f.lower().endswith((".bas", ".cls", ".frm")) for f in files) or "vba" in low or "マクロ" in task:
        keys.append("vba")
    html = any(f.endswith(".html") for f in files)
    if "playwright" in low or (html and any(re.search(r"(^|/)server\.py$", f) for f in files)):   # automation, not page fixes
        keys.append("browser")
    if "sqlite" in low or any(f.endswith((".db", ".sqlite", ".sqlite3", ".sql")) for f in files):
        keys.append("sqlite")
    if any(f.endswith((".nft", ".rules")) for f in files) or re.search(r"firewall|iptables|nftables|ファイアウォール", task, re.I):
        keys.append("firewall")
    if any("expected" in os.path.basename(f).lower() for f in files) or "1 バイト" in task or "byte" in low:
        keys.append("textout")
    return keys


def facts_of(path):
    b = open(path, "rb").read()
    enc = "utf-8"
    try:
        b.decode("utf-8")
    except UnicodeDecodeError:
        enc = "cp932 (Shift_JIS)"
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    return (f"{len(b)} bytes, encoding {enc}{', starts with a BOM' if b.startswith(b'\xef\xbb\xbf') else ''}, "
            f"line ends: {crlf} CRLF / {lf} LF-only, ends with a newline: {b.endswith(b'\n')}")


def brief(root, task, keys):
    """start-of-task brief: the docs and the code to port/fix, in full, plus byte facts of provided expected files,
    so the model does not spend its first steps reading them (and does not skip one)"""
    parts, size = [], 0
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        files += [os.path.relpath(os.path.join(dp, f), root) for f in sorted(fns)]
    files.sort()

    def text(p, limit):
        b = open(os.path.join(root, p), "rb").read()[:limit]
        for enc in ("utf-8", "cp932"):
            try:
                return b.decode(enc)
            except UnicodeDecodeError:
                pass
        return b.decode("utf-8", "replace")

    order = [f for f in files if f.lower().endswith((".md", ".txt", ".rst")) and "expected" not in f.lower()]
    order += [f for f in files if f.lower().endswith((".bas", ".cls", ".frm"))]
    order += [f for f in files if f.endswith(".py") and not f.startswith("tests/") and f not in order][:6]
    order += [f for f in files if f.endswith((".html", ".js")) and "lib/" not in f][:4]
    for f in order:
        t = text(f, 12000)
        if size + len(t) > 30000:
            parts.append(f"=== {f} === (not shown: brief size limit; read it yourself)")
            continue
        size += len(t)
        parts.append(f"=== {f} ===\n{t}")
    for f in files:
        if "expected" in os.path.basename(f).lower():
            parts.append(f"=== {f} === provided expected output: {facts_of(os.path.join(root, f))}\n" + text(f, 1500))
        elif f.startswith("data/") and f.lower().endswith((".csv", ".txt", ".json", ".jsonl")):
            parts.append(f"=== {f} === input sample ({facts_of(os.path.join(root, f))}):\n" + text(f, 800))
    return "\n\n".join(parts)


def message(root, task):
    keys = detect(root, task)
    if not keys:
        # cycle 44: tasks with no sheet (cad_*, paginate) lost with the long brief + "list every rule first" alone;
        # the gains came where a sheet applied (browser_fix first pass, vba_sales 0.57 -> 0.95)
        return keys, ""
    sheets = "\n\n".join(SHEETS[k] for k in keys)
    out = ("[harness] Before you start: the project's documents and code are below in full (you do not need to read them "
           "again), followed by facts about this kind of task that decide whether the result is right.\n\n" + brief(root, task, keys))
    if sheets:
        out += "\n\n" + sheets
    out += ("\n\nFirst write a think that lists every rule of the task and documents (and, when porting or fixing code, every "
            "behaviour of the existing code) that the result must keep, with the facts above that apply to each. Then implement "
            "all of them. Keep your own test small: one check for each rule that is easy to get wrong (negative numbers, ties, "
            "blank rows, encoding and line ends, slow responses) - a long test costs more time than it saves.")
    return keys, out


# ---------------------------------------------------------------- LINT=1: the sheets as checks on written code
# cycle 45 db_migrate: the sqlite sheet said "executescript() commits first - do not use it inside a transaction";
# Gemma wrote BEGIN IMMEDIATE and then executescript inside it anyway (every case: "cannot rollback - no transaction
# is active"). Telling is not enough; a cheap check right after each write points at the line.
def _open_w_calls(text):
    """open(..., 'w'/'wb'...) calls in Python source -> list of the call texts (one line each)"""
    return [m.group(0) for m in re.finditer(r"open\([^\n]*?[\"'][wa]b?\+?[\"'][^\n]*", text)]


def lint(keys, path, text):
    """-> list of (rule id, message) for Python code written under the sheets in keys"""
    if not path.endswith(".py") or path.startswith((".agent/", "app/")) or "/tests/" in "/" + path:
        return []
    out = []
    if "sqlite" in keys:
        if re.search(r"\bBEGIN\b", text) and "executescript" in text:
            out.append(("sq-execscript", "executescript() COMMITs any open transaction and runs its statements outside it, so a "
                        "later ROLLBACK fails ('no transaction is active') and the database is left half-migrated. Inside "
                        "BEGIN ... COMMIT/ROLLBACK run each statement with con.execute()."))
        if re.search(r"\bBEGIN\b", text) and "sqlite3.connect" in text and "isolation_level=None" not in text:
            out.append(("sq-isolation", "you issue BEGIN yourself, but sqlite3.connect() without isolation_level=None also "
                        "opens/commits transactions on its own; connect with isolation_level=None."))
        lines = text.split("\n")
        for i, l in enumerate(lines):
            if ".commit()" in l:
                ind = len(l) - len(l.lstrip())
                for j in range(i - 1, max(-1, i - 40), -1):
                    lj = lines[j]
                    if lj.strip() and len(lj) - len(lj.lstrip()) < ind and re.match(r"\s*(for|while)\b", lj):
                        out.append(("sq-commit-loop", f"line {i + 1}: commit() inside a loop makes the change permanent "
                                    "row by row - a later failure cannot be rolled back. Commit once at the end."))
                        break
                    if lj.strip() and len(lj) - len(lj.lstrip()) < ind and re.match(r"\s*(def|class)\b", lj):
                        break
    if "vba" in keys or "textout" in keys:
        if re.search(r"newline\s*=\s*[\"']\\r\\n[\"']", text) and "\\r\\n" in re.sub(r"newline\s*=\s*[\"']\\r\\n[\"']", "", text):
            # cycle 48 h_vba_kintai: opened with newline='\r\n' and wrote '\r\n' -> b'\r\r\n' on every line
            out.append(("tx-crcr", "the file is opened with newline='\\r\\n' AND the text already contains '\\r\\n': every line "
                        "then ends in \\r\\r\\n. Use one of the two: newline='' and write '\\r\\n' yourself."))
        for call in _open_w_calls(text):
            if "newline=" not in call and "b'" not in call and 'b"' not in call and "'wb'" not in call and '"wb"' not in call:
                out.append(("tx-newline", f"{call.strip()[:80]}: text mode without newline='' rewrites line ends; write the "
                            "exact line ends yourself with newline='' (Print # writes CRLF)."))
                break
    if "vba" in keys:
        for call in _open_w_calls(text):
            if not re.search(r"cp932|shift_jis|sjis|ms932", call, re.I) and "b'" not in call and '"wb"' not in call and "'wb'" not in call:
                out.append(("vba-enc", f"{call.strip()[:80]}: the macro's Print # writes cp932 (Shift_JIS); open the output "
                            "with encoding='cp932' (or write cp932 bytes)."))
                break
        if re.search(r"\.strip\(\s*\)", text):
            out.append(("vba-trim", "a bare .strip() also removes tabs, newlines and full-width spaces; VBA Trim removes only "
                        "ASCII spaces: .strip(' ')."))
        if re.search(r"[\w\)\]]\s*//\s*[\w\(]", text) or re.search(r"[\w\)\]]\s*%\s*\d", text):
            out.append(("vba-intdiv", "Python // and % floor (-7 // 12 = -1, -7 % 12 = 5); VBA \\ and Mod truncate toward "
                        "zero (-7 \\ 12 = 0, -7 Mod 12 = -7). Use a truncating helper wherever a value can be negative."))
        if re.search(r"\bstr\(\s*(val|cdbl|float|vb_round)\(|f[\"'][^\"']*\{\s*(val|cdbl|float)\(", text):
            # cycle 50 h_vba_kintai: str(val("45")) -> "45.0" where the macro's "& Val(...)" prints "45"
            out.append(("vba-cstr", "str() / f-strings print a float as '45.0'; VBA's string concatenation of a number "
                        "prints '45' (and 1E+15 style for big ones). Use cstr(x) from vbcompat (or the same rule)."))
        if re.search(r"\bsorted\(|\.sort\(", text):
            out.append(("vba-sort", "sorted()/.sort() order ties differently from the macro's own sort loop (a bubble sort "
                        "that swaps on <= reverses equal neighbours). Reproduce the macro's loop."))
    if "browser" in keys:
        if re.search(r"\btime\.sleep\(|wait_for_timeout\(", text):
            out.append(("br-sleep", "a fixed wait (time.sleep / wait_for_timeout) breaks when the system is slower: wait for "
                        "the state instead (locator.wait_for, page.wait_for_function on the exact text/visibility)."))
        if "inner_text(" in text:
            out.append(("br-innertext", "inner_text() may change whitespace; use text_content() when the exact text matters."))
    return out


def vbc_api():
    """the docstring of vbcompat.py (its API list), for the start message"""
    import vbcompat
    return vbcompat.__doc__.split("\n", 3)[-1].strip()
