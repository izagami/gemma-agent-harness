"""Hidden check for q_wrap_cjk: an independent implementation of docs/SPEC.md."""
import os, random, subprocess, sys, unicodedata
sys.path.insert(0, "/work")
from jwrap.width import text_width
from jwrap.wrap import wrap

HEAD = "。、，．・：；？！ー」』）］｝〕〉》】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ)]},.?!"
TAIL = "「『（［｛〔〈《【([{"


def cw(c):
    if unicodedata.combining(c):
        return 0
    return 2 if unicodedata.east_asian_width(c) in "WF" else 1


def ref_para(t, width):
    us, i = [], 0
    while i < len(t):
        j = i + 1
        while j < len(t) and unicodedata.combining(t[j]):
            j += 1
        us.append(t[i:j]); i = j
    out, line = [], []
    for u in us:
        size = sum(cw(c) for x in line for c in x)
        uw = sum(cw(c) for c in u)
        if not line or size + uw <= width or u[0] in HEAD:
            line.append(u); continue
        n = 0
        for x in reversed(line):
            if x[0] in TAIL:
                n += 1
            else:
                break
        if n == len(line):
            n = 0
        out.append("".join(line[:len(line) - n]))
        line = line[len(line) - n:] + [u]
    out.append("".join(line))
    return out


def ref(t, width):
    return [l for p in t.split("\n") for l in ref_para(p, width)]


V = "゙"
fixed = [
    ("あいうえおかきくけこ。さし", 10), ("ＡＢＣＤＥＦ", 10), ("あいうえ「かきくけ", 10), ("あいうえお」」。かき", 10),
    ("か" + V + "き" + V + "く" + V + "け" + V + "こ" + V + "さ" + V, 6), ("café au lait", 5), ("ａｂｃｄ（ｅｆ）ｇ", 8),
    ("あいう「「えお", 8), ("「「「「", 4), ("お知らせ：来週の定例会は、会議室Ｂ（３階）で行います。", 12),
    ("ちょっとまって、きゃっきゃっ", 7), ("abc(def) ghi.jkl", 4), ("ア" * 9 + "ァ", 18), ("あ" + "、" * 5 + "い", 4),
    ("x" + V * 3 + "yz", 2), ("ＡＰＩ（内線２０４）", 9), ("ab\n\nあいうえお", 4), ("", 10),
]
rng = random.Random(2026)
pool = list("あいうえおかきくけこアイウエオabcde ＡＢＣ１２３") + list(HEAD[:20]) + list(TAIL[:6]) + ["か" + V, "é"]
for _ in range(60):
    fixed.append(("".join(rng.choice(pool) for _ in range(rng.randrange(5, 40))), rng.randrange(2, 16)))
bad = []
for t, w in fixed:
    try:
        got = wrap(t, w)
    except Exception as e:
        bad.append(f"wrap({t!r}, {w}) raised {e!r}"); continue
    if got != ref(t, w):
        bad.append(f"wrap({t!r}, {w})\n   got  {got}\n   want {ref(t, w)}")
for s, n in [("ＡＢ", 4), ("か" + V, 2), ("é", 1), ("ｱ", 1), ("ａ１", 4)]:
    if text_width(s) != n:
        bad.append(f"text_width({s!r}) = {text_width(s)}, want {n}")
if bad:
    print(f"{len(bad)} of {len(fixed) + 5} cases wrong:"); print("\n".join(bad[:6])); sys.exit(1)

text = open("/work/data/notice.txt", encoding="utf-8").read()
for w in (10, 16, 23, 40):
    r = subprocess.run([sys.executable, "-m", "jwrap", "-w", str(w), "data/notice.txt"], cwd="/work", capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout == "".join(l + "\n" for l in ref(text[:-1], w)), (w, r.stdout, r.stderr)
r = subprocess.run([sys.executable, "-m", "jwrap", "-w", "6"], cwd="/work", input="あいうえお」\n", capture_output=True, text=True)
assert r.stdout == "あいう\nえお」\n", r.stdout
r = subprocess.run([sys.executable, "-m", "jwrap", "-w", "1", "-"], cwd="/work", input="a\n", capture_output=True, text=True)
assert r.returncode == 2 and r.stderr.startswith("error:"), (r.returncode, r.stderr)
print(f"ok: {len(fixed)} wraps + CLI")
