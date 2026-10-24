"""vbcompat: VBA runtime behaviour as Python functions, for porting Excel VBA macros byte for byte.

Standard library only. Copy this file next to your script and `from vbcompat import *`.
Each function behaves like the VBA function of the same name (Japanese Excel / Windows), including the cases where
VBA differs from Python. Strings are Python str; dates are datetime.date.

Numbers
    clng(x) / cint(x)          CLng / CInt: round half to EVEN (CLng(2.5)=2, CLng(3.5)=4); x may be a string
    vb_round(x, n=0)           Round(x, n): half to even
    vb_int(x) / vb_fix(x)      Int (floor) / Fix (toward zero)
    vb_idiv(a, b)              a \\ b : operands rounded half-even to integers, result truncated toward zero
    vb_mod(a, b)               a Mod b: sign follows a  (-7 Mod 12 = -7)
    val(s)                     Val: leading number only, spaces anywhere skipped ("  2 500" -> 2500, "1,200" -> 1)
    is_numeric(s)              IsNumeric (signs, thousands commas, decimals, exponents, full-width digits)
    cdbl(s)                    CDbl of a numeric string ("1,234.5" -> 1234.5)
    cstr(x)                    CStr: Long without leading space; Double with up to 15 significant digits, 1E+15 form
    vb_format(x, fmt)          Format for numbers: "0", "#,##0", "#,##0.00", "0.0%", "00000", "@" ... (half away from zero)
Strings
    vb_trim / vb_ltrim / vb_rtrim   only ASCII spaces
    vb_left / vb_right / vb_mid(s, start, length=None)   1-based Mid
    instr(s, sub, start=1) / instrrev(s, sub)            1-based, 0 when not found
    vb_replace(s, find, repl)  vb_ucase / vb_lcase (ASCII letters only, like VBA on full-width text)
    like(s, pattern)           Like with * ? # [abc] [!abc]  (binary compare)
    strconv_katakana / strconv_hiragana / strconv_narrow / strconv_wide
    lenb_sjis(s)               LenB(StrConv(s, vbFromUnicode)): byte length in cp932 (unmappable chars count 1)
    vb_split(s, delim)         Split ("" -> [])
Dates
    date_serial(y, m, d)       DateSerial with carry-over (day 0 = last day of previous month, month 13 = next Jan);
                               2-digit years: 0-29 -> 2000s, 30-99 -> 1900s
    date_add(interval, n, d)   "d", "ww" (7 days), "m" (clamps to month end), "yyyy", "q"
    date_diff(interval, a, b, first_day=1)   "d", "ww" (week starts crossed, 1 = Sunday), "m", "yyyy", "q"
    weekday(d, first_day=1)    Weekday: 1 = Sunday by default; first_day=2 (vbMonday) -> Monday = 1
    vb_format_date(d, fmt)     Format for dates: yyyy yy mm m dd d aaa aaaa ddd dddd hh nn ss (Japanese weekdays)
    is_date(s) / cdate(s)      IsDate / CDate for "yyyy/m/d" (and "yyyy-mm-dd") strings
    year / month / day         like VBA
Files
    read_sheet_csv(path, enc="cp932")      rows of an Excel "CSV (comma delimited)" file (list of lists of str)
    last_row(rows, col)        ws.Cells(ws.Rows.Count, col).End(xlUp).Row on those rows: 1-based index of the last
                               non-empty cell in column col (1-based), header row = 1
    PrintFile(path)            Open path For Output As #f + Print #f, ...: .print_line(s) writes s + CRLF in cp932;
                               use `with PrintFile(path) as f: f.print_line(...)`
Sorting
    bubble_sort_desc(idx, key)  the usual macro bubble sort: for i in 1..n-1, for j in 1..n-i: if key[idx[j]] <= key[idx[j+1]]: swap
                               (swaps equal neighbours, so ties end up reversed) - pass the comparison you see in the macro
                               via cmp=lambda a, b: ... returning True when the macro swaps
"""
import calendar
import csv
import datetime as _dt
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_FLOOR, ROUND_DOWN

__all__ = [n for n in dir() if not n.startswith("_")]  # refreshed at the end


# ---------------------------------------------------------------- numbers
def _dec(x):
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        return Decimal(int(x))
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        return Decimal(repr(x))
    if x is None:
        return Decimal(0)
    s = unicodedata.normalize("NFKC", str(x)).strip()
    if s == "":
        return Decimal(0)                # Empty -> 0
    return Decimal(s.replace(",", "").replace("d", "e").replace("D", "e"))


def clng(x):
    """CLng: round half to even"""
    return int(_dec(x).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


cint = clng


def vb_round(x, n=0):
    """Round(x, n): half to even. Returns int for n=0, float otherwise"""
    q = Decimal(1).scaleb(-n)
    r = _dec(x).quantize(q, rounding=ROUND_HALF_EVEN)
    return int(r) if n == 0 else float(r)


def vb_int(x):
    """Int: largest integer <= x"""
    return int(_dec(x).quantize(Decimal(1), rounding=ROUND_FLOOR))


def vb_fix(x):
    """Fix: toward zero"""
    return int(_dec(x).quantize(Decimal(1), rounding=ROUND_DOWN))


def vb_idiv(a, b):
    """a \\ b: both rounded half-even to integers, then truncated toward zero"""
    a, b = clng(a), clng(b)
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def vb_mod(a, b):
    """a Mod b: both rounded half-even to integers; the sign follows a"""
    a, b = clng(a), clng(b)
    return a - vb_idiv(a, b) * b


def val(s):
    """Val: reads the leading number; spaces, tabs and line feeds are skipped anywhere; &H / &O prefixes; "" -> 0"""
    if isinstance(s, (int, float)):
        return float(s)
    t = "".join(c for c in str(s or "") if c not in " \t\n\r")
    m = re.match(r"^&[hH]([0-9a-fA-F]+)", t)
    if m:
        v = int(m.group(1), 16)
        return float(v - 0x10000 if len(m.group(1)) <= 4 and v >= 0x8000 else v)
    m = re.match(r"^&[oO]?([0-7]+)", t)
    if m:
        return float(int(m.group(1), 8))
    m = re.match(r"^[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?", t)
    if not m:
        return 0.0
    v = float(m.group(0).replace("d", "e").replace("D", "e"))
    return v


_NUM_RE = re.compile(r"^\s*[+-]?\s*(\d[\d,]*\.?\d*|\.\d+)([eEdD][+-]?\d+)?\s*$")


def is_numeric(s):
    """IsNumeric for a cell value"""
    if isinstance(s, (int, float, Decimal)) and not isinstance(s, bool):
        return True
    t = unicodedata.normalize("NFKC", str(s or ""))
    if t.strip() == "":
        return False
    return bool(_NUM_RE.match(t)) or bool(re.match(r"^\s*&[hH][0-9a-fA-F]+\s*$|^\s*&[oO]?[0-7]+\s*$", t))


def cdbl(s):
    return float(_dec(s))


def cstr(x):
    """CStr: integers plainly; Double with 15 significant digits, no trailing zeros, exponent like 1E+15 / 1E-05"""
    if isinstance(x, bool):
        return "True" if x else "False"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, str):
        return x
    if x is None:
        return ""
    x = float(x)
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    s = "%.15G" % x
    if "E" in s:
        mant, exp = s.split("E")
        if "." in mant:
            mant = mant.rstrip("0").rstrip(".")
        sign, digits = exp[0], exp[1:].lstrip("0") or "0"
        return f"{mant}E{sign}{digits.zfill(2)}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _group(intpart):
    return f"{int(intpart):,}"


def vb_format(x, fmt):
    """Format(x, fmt) for numeric formats, rounding half away from zero: "0", "0.00", "#,##0", "#,##0.00", "0.0%",
    "00000", "#.##" (-> "5." like VBA). "pos;neg" sections: the second is used, without a sign, for negatives.
    A negative number keeps its "-" even when it rounds to 0 (Format(-0.4, "0") = "-0", as in VBA).
    A non-numeric string is returned unchanged."""
    if isinstance(x, str) and not is_numeric(x):
        return x
    d = _dec(x)
    secs = fmt.split(";")
    neg = d < 0
    if len(secs) > 1 and neg:
        f, sign = secs[1], ""
    else:
        f, sign = secs[0], "-" if neg else ""
    d = abs(d)
    if "%" in f:
        d = d * 100
    m = re.search(r"[0#][0#,]*(\.[0#]*)?|\.[0#]+", f)
    if not m:
        return sign + f
    num = m.group(0)
    int_spec, _, dec_spec = num.partition(".")
    has_dot = "." in num
    ndec = len(dec_spec)
    nmin = len(dec_spec) - len(dec_spec.lstrip("0"))
    r = d.quantize(Decimal(1).scaleb(-ndec), rounding=ROUND_HALF_UP)
    ip, _, fp = f"{r:f}".partition(".")
    fp = fp.ljust(ndec, "0")[:ndec]
    while len(fp) > nmin and fp.endswith("0"):
        fp = fp[:-1]
    zeros = int_spec.replace(",", "").count("0")
    if ip == "0" and zeros == 0:
        ip = ""
    if "," in int_spec and ip:
        ip = f"{int(ip):,}"
    ip = ip.zfill(zeros) if zeros and len(ip.replace(",", "")) < zeros else ip
    body = ip + ("." + fp if has_dot else "")
    return sign + f[:m.start()] + body + f[m.end():]


# ---------------------------------------------------------------- strings
def vb_trim(s):
    return str(s or "").strip(" ")


def vb_ltrim(s):
    return str(s or "").lstrip(" ")


def vb_rtrim(s):
    return str(s or "").rstrip(" ")


def vb_left(s, n):
    return str(s)[:max(0, int(n))]


def vb_right(s, n):
    n = max(0, int(n))
    return str(s)[-n:] if n else ""


def vb_mid(s, start, length=None):
    s = str(s)
    i = max(1, int(start)) - 1
    return s[i:] if length is None else s[i:i + max(0, int(length))]


def instr(s, sub, start=1):
    """InStr: 1-based position, 0 when not found ("" found at start)"""
    s, sub = str(s), str(sub)
    i = s.find(sub, max(1, int(start)) - 1)
    return i + 1


def instrrev(s, sub):
    i = str(s).rfind(str(sub))
    return i + 1


def vb_replace(s, find, repl):
    return str(s).replace(find, repl) if find else str(s)


def vb_ucase(s):
    return "".join(c.upper() if "a" <= c <= "z" else c for c in str(s))


def vb_lcase(s):
    return "".join(c.lower() if "A" <= c <= "Z" else c for c in str(s))


def vb_split(s, delim=" "):
    s = str(s)
    return [] if s == "" else s.split(delim)


def like(s, pattern):
    """VBA Like (Option Compare Binary): * ? # [chars] [!chars] [a-z]"""
    rx, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            rx += ".*"
        elif c == "?":
            rx += "."
        elif c == "#":
            rx += "[0-9]"
        elif c == "[":
            j = pattern.find("]", i + 1)
            if j < 0:
                rx += re.escape(c)
            else:
                body = pattern[i + 1:j]
                neg = body.startswith("!")
                if neg:
                    body = body[1:]
                rx += "[" + ("^" if neg else "") + "".join(re.escape(ch) if ch != "-" else "-" for ch in body) + "]"
                i = j
        else:
            rx += re.escape(c)
        i += 1
    return re.fullmatch(rx, str(s), re.S) is not None


def _narrow_table():
    half_of = {}
    for cp in range(0xFF61, 0xFFA0):
        h = chr(cp)
        f = unicodedata.normalize("NFKC", h)
        if len(f) == 1 and f not in half_of:
            half_of[f] = h
    t = dict(half_of)
    for cp in list(range(0x30A1, 0x30FB)) + [0x30FC, 0x30FB]:
        k = chr(cp)
        if k in t:
            continue
        d = unicodedata.normalize("NFD", k)
        if len(d) == 2 and d[0] in half_of and d[1] in ("゙", "゚"):
            t[k] = half_of[d[0]] + ("ﾞ" if d[1] == "゙" else "ﾟ")
    t["゛"] = "ﾞ"
    t["゜"] = "ﾟ"
    t["　"] = " "
    for cp in range(0xFF01, 0xFF5F):
        t[chr(cp)] = chr(cp - 0xFEE0)
    t.update({"￥": "\\", "￠": "¢", "￡": "£", "￢": "¬", "￣": "~", "￤": "¦"})
    return t


_NARROW = _narrow_table()
_WIDE = {}
for _f, _h in _NARROW.items():
    if len(_h) == 1 and _h not in _WIDE:
        _WIDE[_h] = _f
for _f, _h in _NARROW.items():
    if len(_h) == 2:
        _WIDE.setdefault(_h, _f)


def strconv_narrow(s):
    """StrConv(s, vbNarrow)"""
    return "".join(_NARROW.get(c, c) for c in str(s))


def strconv_wide(s):
    """StrConv(s, vbWide): ASCII and half-width katakana -> full-width (ｶﾞ -> ガ)"""
    s, out, i = str(s), [], 0
    while i < len(s):
        pair = s[i:i + 2]
        if len(pair) == 2 and pair in _WIDE:
            out.append(_WIDE[pair]); i += 2
            continue
        c = s[i]
        if c == " ":
            out.append("　")
        elif "!" <= c <= "~":
            out.append(chr(ord(c) + 0xFEE0))
        else:
            out.append(_WIDE.get(c, c))
        i += 1
    return "".join(out)


def strconv_katakana(s):
    """StrConv(s, vbKatakana): hiragana -> katakana"""
    return "".join(chr(ord(c) + 0x60) if (0x3041 <= ord(c) <= 0x3096 or ord(c) in (0x309D, 0x309E)) else c for c in str(s))


def strconv_hiragana(s):
    """StrConv(s, vbHiragana): katakana -> hiragana"""
    return "".join(chr(ord(c) - 0x60) if (0x30A1 <= ord(c) <= 0x30F6 or ord(c) in (0x30FD, 0x30FE)) else c for c in str(s))


_BEST_FIT = {"〜": "～", "‖": "∥", "−": "－", "¢": "￠", "£": "￡",
             "¬": "￢", "—": "―", "¥": "\\", "¦": "￤"}


def to_sjis(s):
    """Unicode -> cp932 bytes as Windows converts (unmappable characters become '?')"""
    out = []
    for c in str(s):
        c = _BEST_FIT.get(c, c)
        try:
            out.append(c.encode("cp932"))
        except UnicodeEncodeError:
            out.append(b"?")
    return b"".join(out)


def lenb_sjis(s):
    """LenB(StrConv(s, vbFromUnicode))"""
    return len(to_sjis(s))


# ---------------------------------------------------------------- dates
def _y2(y):
    if 0 <= y <= 29:
        return y + 2000
    if 30 <= y <= 99:
        return y + 1900
    return y


def date_serial(y, m, d):
    """DateSerial: month/day carry over; 2-digit years 0-29 -> 2000s, 30-99 -> 1900s"""
    y, m, d = _y2(clng(y)), clng(m), clng(d)
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return _dt.date(y, m, 1) + _dt.timedelta(days=d - 1)


def _add_months(d, n):
    t = d.month - 1 + n
    y, m = d.year + t // 12, t % 12 + 1
    return _dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def date_add(interval, n, d):
    """DateAdd: "d"/"y"/"w" days, "ww" weeks, "m" months (clamped to month end), "q" quarters, "yyyy" years"""
    n = clng(n)
    iv = interval.lower()
    if iv in ("d", "y", "w"):
        return d + _dt.timedelta(days=n)
    if iv == "ww":
        return d + _dt.timedelta(days=7 * n)
    if iv == "m":
        return _add_months(d, n)
    if iv == "q":
        return _add_months(d, 3 * n)
    if iv == "yyyy":
        return _add_months(d, 12 * n)
    raise ValueError("interval " + interval)


def weekday(d, first_day=1):
    """Weekday(d, firstdayofweek): default vbSunday=1 (Sunday=1 ... Saturday=7); first_day=2 means vbMonday"""
    sun0 = (d.weekday() + 1) % 7          # Sunday=0 ... Saturday=6
    return (sun0 - (first_day - 1)) % 7 + 1


def date_diff(interval, a, b, first_day=1):
    """DateDiff(interval, a, b): "d" days, "ww" week-start boundaries crossed (week starts on first_day, 1=Sunday),
    "w" whole 7-day blocks, "m" month boundaries, "q" quarter boundaries, "yyyy" year boundaries"""
    iv = interval.lower()
    if iv in ("d", "y"):
        return (b - a).days
    if iv == "w":
        return int((b - a).days / 7)
    if iv == "ww":
        sa = a - _dt.timedelta(days=weekday(a, first_day) - 1)
        sb = b - _dt.timedelta(days=weekday(b, first_day) - 1)
        return (sb - sa).days // 7
    if iv == "m":
        return (b.year - a.year) * 12 + b.month - a.month
    if iv == "q":
        return (b.year - a.year) * 4 + (b.month - 1) // 3 - (a.month - 1) // 3
    if iv == "yyyy":
        return b.year - a.year
    raise ValueError("interval " + interval)


_JA_SHORT = "日月火水木金土"        # by Sunday=0
_JA_LONG = ["日曜日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日"]
_EN_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_EN_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def vb_format_date(d, fmt):
    """Format(date, fmt): yyyy yy mm m dd d aaaa aaa dddd ddd hh h nn n ss s; other characters are copied.
    In VBA "mm" after h/hh means minutes; use "nn" for minutes to be safe."""
    if isinstance(d, _dt.datetime):
        dt = d
    else:
        dt = _dt.datetime(d.year, d.month, d.day)
    sun0 = (dt.weekday() + 1) % 7
    tokens = [("yyyy", f"{dt.year:04d}"), ("aaaa", _JA_LONG[sun0]), ("dddd", _EN_LONG[sun0]), ("aaa", _JA_SHORT[sun0]),
              ("ddd", _EN_SHORT[sun0]), ("yy", f"{dt.year % 100:02d}"), ("mm", f"{dt.month:02d}"), ("dd", f"{dt.day:02d}"),
              ("hh", f"{dt.hour:02d}"), ("nn", f"{dt.minute:02d}"), ("ss", f"{dt.second:02d}"), ("m", str(dt.month)),
              ("d", str(dt.day)), ("h", str(dt.hour)), ("n", str(dt.minute)), ("s", str(dt.second))]
    out, i = "", 0
    while i < len(fmt):
        for t, v in tokens:
            if fmt.startswith(t, i):
                out += v
                i += len(t)
                break
        else:
            out += fmt[i]
            i += 1
    return out


def cdate(s):
    """CDate for 'yyyy/m/d' or 'yyyy-mm-dd' (optional ' hh:nn[:ss]'). Raises ValueError otherwise"""
    t = unicodedata.normalize("NFKC", str(s)).strip()
    m = re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", t)
    if not m:
        raise ValueError("not a date: " + repr(s))
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if m.group(4):
        return _dt.datetime(y, mo, d, int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
    return _dt.date(y, mo, d)


def is_date(s):
    if isinstance(s, (_dt.date, _dt.datetime)):
        return True
    try:
        cdate(s)
        return True
    except (ValueError, TypeError):
        return False


def year(d):
    return d.year


def month(d):
    return d.month


def day(d):
    return d.day


# ---------------------------------------------------------------- files
def read_sheet_csv(path, enc="cp932"):
    """rows of an Excel 'CSV (comma delimited)' file; every cell is a str ('' for empty)"""
    with open(path, encoding=enc, newline="") as f:
        return [list(r) for r in csv.reader(f)]


def last_row(rows, col=1):
    """ws.Cells(ws.Rows.Count, col).End(xlUp).Row: 1-based row number of the last non-empty cell in column col
    (rows[0] is row 1). Rows after it are not visited by a `For r = 2 To lastRow` loop; blank rows before it are."""
    last = 0
    for i, r in enumerate(rows):
        if len(r) >= col and str(r[col - 1]) != "":
            last = i + 1
    return last


def cell(rows, r, c):
    """ws.Cells(r, c).Value as str ('' when the row is short or missing); r, c are 1-based"""
    if r - 1 >= len(rows) or r < 1:
        return ""
    row = rows[r - 1]
    return row[c - 1] if 0 < c <= len(row) else ""


class PrintFile:
    """Open path For Output As #f ... Print #f, s ... Close #f  -> cp932 bytes, CRLF after every line"""

    def __init__(self, path):
        self.path, self.buf = path, []

    def print_line(self, s=""):
        self.buf.append(to_sjis(s) + b"\r\n")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is None:
            with open(self.path, "wb") as f:
                f.write(b"".join(self.buf))
        return False


# ---------------------------------------------------------------- sorting
def bubble_sort_desc(idx, key, cmp=None):
    """The common macro sort:
        For i = 1 To n - 1: For j = 1 To n - i: If key(idx(j)) <= key(idx(j + 1)) Then swap
    idx: list of indexes (0-based Python list), key: list/dict of values. Returns a new list. Ties are swapped, so
    their order is reversed relative to a stable sort - exactly like the macro. Give cmp(a, b) -> True-to-swap when
    the macro's condition differs (e.g. cmp=lambda a, b: key[a] < key[b])."""
    idx = list(idx)
    n = len(idx)
    swap = cmp or (lambda a, b: key[a] <= key[b])
    for i in range(1, n):
        for j in range(0, n - i):
            if swap(idx[j], idx[j + 1]):
                idx[j], idx[j + 1] = idx[j + 1], idx[j]
    return idx


__all__ = [n for n in list(globals()) if not n.startswith("_") and n not in (
    "calendar", "csv", "re", "unicodedata", "Decimal", "ROUND_HALF_EVEN", "ROUND_HALF_UP", "ROUND_FLOOR", "ROUND_DOWN")]
