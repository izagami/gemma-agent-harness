"""Line breaking for Japanese text (docs/SPEC.md)."""
import unicodedata

from .width import text_width

# characters that must not start a line (they stay at the end of the previous line)
NO_START = set("。、，．・：；？！ー」』）］｝〕〉》】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ)]},.?!")
# characters that must not end a line (they move to the start of the next line)
NO_END = set("「『（［｛〔〈《【([{")


def units(text):
    """Base characters with their following combining marks."""
    out = []
    for ch in text:
        if out and unicodedata.combining(ch):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def wrap_paragraph(text, width):
    lines, cur = [], []
    w = 0
    for u in units(text):
        uw = text_width(u)
        if cur and w + uw > width:
            if u[0] in NO_START:
                cur.append(u)
                w += uw
                continue
            k = 0
            while k < len(cur) and cur[-1 - k][0] in NO_END:
                k += 1
            moved = cur[len(cur) - k:] if 0 < k < len(cur) else []  # never leave an empty line
            if moved:
                cur = cur[:len(cur) - k]
            lines.append("".join(cur))
            cur = moved
            w = sum(text_width(x) for x in cur)
        cur.append(u)
        w += uw
    lines.append("".join(cur))
    return lines


def wrap(text, width):
    """List of lines; every paragraph ("\\n"-separated) is wrapped on its own."""
    if width < 2:
        raise ValueError("width must be at least 2")
    out = []
    for para in text.split("\n"):
        out.extend(wrap_paragraph(para, width))
    return out
