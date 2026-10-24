"""Line breaking for Japanese text (docs/SPEC.md)."""
from .width import char_width

# characters that must not start a line (they stay at the end of the previous line)
NO_START = set("。、")


def wrap_paragraph(text, width):
    lines, cur, w = [], "", 0
    for ch in text:
        cw = char_width(ch)
        if cur and w + cw > width:
            if ch in NO_START:
                cur += ch
                w += cw
                continue
            lines.append(cur)
            cur, w = "", 0
        cur += ch
        w += cw
    lines.append(cur)
    return lines


def wrap(text, width):
    """List of lines; every paragraph ("\\n"-separated) is wrapped on its own."""
    if width < 2:
        raise ValueError("width must be at least 2")
    out = []
    for para in text.split("\n"):
        out.extend(wrap_paragraph(para, width))
    return out
