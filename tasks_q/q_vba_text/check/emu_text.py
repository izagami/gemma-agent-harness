"""Independent emulation of vba/Module1.bas (顧客マスタ整形) with VBA string semantics.
rows: lists of cell texts (A..F) as the CSV export shows them. Returns the output file bytes (cp932, CRLF)."""
import re

# --- StrConv(vbKatakana): hiragana -> katakana
def to_katakana(s):
    return "".join(chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch for ch in s)

# --- StrConv(vbNarrow)
_H = "｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ"
_F = "。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜"
NARROW = dict(zip(_F, _H))
for base, voiced in zip("カキクケコサシスセソタチツテトハヒフヘホ", "ガギグゲゴザジズゼゾダヂヅデドバビブベボ"):
    NARROW[voiced] = NARROW[base] + "ﾞ"
for base, semi in zip("ハヒフヘホ", "パピプペポ"):
    NARROW[semi] = NARROW[base] + "ﾟ"
NARROW["ヴ"] = "ｳﾞ"
NARROW["　"] = " "


def narrow(s):
    out = []
    for ch in s:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        else:
            out.append(NARROW.get(ch, ch))
    return "".join(out)


def vtrim(s):
    return s.strip(" ")


def lenb_sjis(s):
    return len(s.encode("cp932"))


def like(s, pattern):
    """VBA Like (binary compare) for the patterns used here: * ? # and literal characters."""
    rx = "".join(".*" if c == "*" else "." if c == "?" else "[0-9]" if c == "#" else re.escape(c) for c in pattern)
    return re.fullmatch(rx, s, re.S) is not None


def val(s):
    """VBA Val(): blanks, tabs and linefeeds are removed first; reads &H/&O integers or a decimal number."""
    s = "".join(ch for ch in s if ch not in " \t\n")
    if s[:2].upper() == "&H":
        m = re.match(r"[0-9A-Fa-f]*", s[2:]).group(0)
        return int(m, 16) if m else 0
    if s[:2].upper() == "&O":
        m = re.match(r"[0-7]*", s[2:]).group(0)
        return int(m, 8) if m else 0
    m = re.match(r"[+-]?([0-9]*\.?[0-9]*)([EeDd][+-]?[0-9]+)?", s)
    txt = m.group(0) if m and re.search(r"[0-9]", m.group(1) or "") else ""
    if not txt:
        return 0
    return float(txt.replace("D", "E").replace("d", "e"))


def cstr_num(x):
    if isinstance(x, int):
        return str(x)
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return "%.15g" % x


def convert(rows):
    out = ["\t".join(["CODE", "NAME", "CORP", "KANA", "PREF", "ADDR", "BLDG", "TEL", "POINT"])]
    for row in rows:
        row = (row + [""] * 6)[:6]
        code = vtrim(row[0])
        if not like(code, "C####"):
            out.append(code + "\tERROR コード不正")
            continue
        nm = vtrim(row[1].replace("　", " "))
        while "  " in nm:
            nm = nm.replace("  ", " ")
        corp = "1" if any(like(nm, p) for p in ("*株式会社*", "*(株)*", "*（株）*")) else "0"
        while lenb_sjis(nm) > 20:
            nm = nm[:-1]
        kana = narrow(to_katakana(vtrim(row[2])))
        addr = vtrim(row[3]).replace("　", " ")
        pref = addr[:4] if addr[3:4] == "県" else addr[:3]
        rest = addr[len(pref):]
        sp = rest.rfind(" ")
        if sp >= 0:
            bldg, rest = vtrim(rest[sp + 1:]), vtrim(rest[:sp])
        else:
            bldg = ""
        rest = rest.replace("－", "-")
        digits = "".join(ch for ch in narrow(row[4]) if "0" <= ch <= "9")
        if len(digits) == 10 and digits[:2] in ("03", "06"):
            tel = f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        elif len(digits) == 10:
            tel = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11:
            tel = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        else:
            tel = ""
        out.append("\t".join([code, nm, corp, kana, pref, rest, bldg, tel, cstr_num(val(row[5]))]))
    return "".join(l + "\r\n" for l in out).encode("cp932")
