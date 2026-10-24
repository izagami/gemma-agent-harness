#!/usr/bin/env python3
"""Port of vba/Module1.bas (顧客マスタ整形).  usage: customer_clean.py <顧客.csv> <出力ファイル>"""
import csv
import re
import sys

HIRA_TO_KATA = {c: c + 0x60 for c in range(0x3041, 0x3097)}

HALF = ("ｧｱｨｲｩｳｪｴｫｵｶｶﾞｷｷﾞｸｸﾞｹｹﾞｺｺﾞｻｻﾞｼｼﾞｽｽﾞｾｾﾞｿｿﾞﾀﾀﾞﾁﾁﾞｯﾂﾂﾞﾃﾃﾞﾄﾄﾞﾅﾆﾇﾈﾉﾊﾊﾞﾊﾟﾋﾋﾞﾋﾟﾌﾌﾞﾌﾟﾍﾍﾞﾍﾟﾎﾎﾞﾎﾟ"
        "ﾏﾐﾑﾒﾓｬﾔｭﾕｮﾖﾗﾘﾙﾚﾛﾜｦﾝ")
FULL = ("ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポ"
        "マミムメモャヤュユョヨラリルレロワヲン")


def _half_table():
    t, i = {}, 0
    for ch in FULL:
        h = HALF[i]
        if i + 1 < len(HALF) and HALF[i + 1] in "ﾞﾟ":
            h += HALF[i + 1]
            i += 1
        t[ord(ch)] = h
        i += 1
    t.update({ord("ヴ"): "ｳﾞ", ord("ー"): "ｰ", ord("・"): "･", ord("「"): "｢", ord("」"): "｣", ord("、"): "､",
              ord("。"): "｡", ord("゛"): "ﾞ", ord("゜"): "ﾟ", 0x3000: " "})
    t.update({c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)})
    return t


NARROW = _half_table()


def strconv_narrow(s):
    return s.translate(NARROW)


def vba_trim(s):
    return s.strip(" ")


def vba_val(s):
    s = re.sub(r"[ \t\n]", "", s)
    if s[:2] in ("&H", "&h"):
        m = re.match(r"[0-9a-fA-F]+", s[2:])
        return int(m.group(), 16) if m else 0
    if s[:2] in ("&O", "&o"):
        m = re.match(r"[0-7]+", s[2:])
        return int(m.group(), 8) if m else 0
    m = re.match(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eEdD][+-]?[0-9]+)?", s)
    return float(re.sub("[dD]", "e", m.group())) if m else 0


def vba_cstr(x):
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return str(x) if isinstance(x, int) else format(x, ".15g")


def main(src, dst):
    with open(src, encoding="cp932", newline="") as f:
        rows = list(csv.reader(f))[1:]
    lines = ["CODE\tNAME\tCORP\tKANA\tPREF\tADDR\tBLDG\tTEL\tPOINT"]
    for row in rows:
        row += [""] * (6 - len(row))
        code = vba_trim(row[0])
        if not re.fullmatch(r"C[0-9]{4}", code):           # Like "C####"
            lines.append(code + "\tERROR コード不正")
            continue
        nm = vba_trim(row[1].replace("　", " "))
        while "  " in nm:
            nm = nm.replace("  ", " ")
        corp = "1" if ("株式会社" in nm or "(株)" in nm or "（株）" in nm) else "0"
        while len(nm.encode("cp932")) > 20:                  # LenB(StrConv(nm, vbFromUnicode))
            nm = nm[:-1]
        kana = strconv_narrow(vba_trim(row[2]).translate(HIRA_TO_KATA))
        addr = vba_trim(row[3]).replace("　", " ")
        pref = addr[:4] if addr[3:4] == "県" else addr[:3]  # Mid(addr, 4, 1) is the 4th character
        rest = addr[len(pref):]
        sp = rest.rfind(" ")
        bldg = ""
        if sp >= 0:
            bldg, rest = vba_trim(rest[sp + 1:]), vba_trim(rest[:sp])
        rest = rest.replace("－", "-")
        d = "".join(c for c in strconv_narrow(row[4]) if c in "0123456789")
        if len(d) == 10 and d[:2] in ("03", "06"):
            tel = d[:2] + "-" + d[2:6] + "-" + d[6:]
        elif len(d) == 10:
            tel = d[:3] + "-" + d[3:6] + "-" + d[6:]
        elif len(d) == 11:
            tel = d[:3] + "-" + d[3:7] + "-" + d[7:]
        else:
            tel = ""
        lines.append("\t".join([code, nm, corp, kana, pref, rest, bldg, tel, vba_cstr(vba_val(row[5]))]))
    with open(dst, "w", encoding="cp932", newline="") as f:
        f.write("".join(l + "\r\n" for l in lines))


if __name__ == "__main__":
    main(*sys.argv[1:3])
