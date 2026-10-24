import re


def split_name(full):
    """'  山田　太郎 ' -> ('山田', '太郎')  (family name first; ASCII or full-width space)."""
    s = full.strip(" 　\t")
    m = re.search(r"[ 　]", s)
    if not m:
        return s, ""
    return s[:m.start()], s[m.end():].strip(" 　\t")


def split_tags(text):
    out = []
    for t in (text or "").split(","):
        t = t.strip().lower()
        if t and t not in out:
            out.append(t)
    return out
