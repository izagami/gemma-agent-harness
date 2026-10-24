"""Line-based block parser.

Recognised blocks (see docs/SYNTAX.md):
  # Title / ## Section / ### Subsection
  paragraphs (consecutive non-blank lines)
  - unordered items / 1. ordered items
  ``` fenced code ```
  --- horizontal rule
  [^id]: footnote definition        (removed from the flow)
  [name]: https://url               (link reference definition, removed from the flow)
"""
import re

from docrender import inline
from docrender.blocks import Code, Document, Heading, ListBlock, Paragraph, Rule

HEADING = re.compile(r"^(#{1,3})\s+(.*?)\s*#*\s*$")
UL_ITEM = re.compile(r"^[-*]\s+(.*)$")
OL_ITEM = re.compile(r"^\d+[.)]\s+(.*)$")
FOOTDEF = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.*)$")
LINKDEF = re.compile(r"^\[([^\]^][^\]]*)\]:\s*(\S+)\s*$")
FENCE = re.compile(r"^```\s*(\w*)\s*$")


def parse(text):
    blocks, footnotes, links = [], {}, {}
    para, lst = [], None
    lines = text.replace("\r\n", "\n").split("\n")

    def flush():
        nonlocal para, lst
        if para:
            blocks.append(Paragraph(" ".join(para)))
            para = []
        if lst is not None:
            blocks.append(lst)
            lst = None

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        m = FENCE.match(line)
        if m:
            flush()
            code = Code(m.group(1))
            while i < len(lines) and not FENCE.match(lines[i].rstrip()):
                code.lines.append(lines[i])
                i += 1
            i += 1  # closing fence (or EOF)
            blocks.append(code)
            continue
        if not line.strip():
            flush()
            continue
        m = FOOTDEF.match(line)
        if m:
            flush()
            body = [m.group(2)]
            while i < len(lines) and lines[i].startswith("    ") and lines[i].strip():
                body.append(lines[i].strip())
                i += 1
            footnotes.setdefault(m.group(1), " ".join(body))
            continue
        m = LINKDEF.match(line)
        if m:
            flush()
            name = m.group(1).strip().lower()
            links.setdefault(name, m.group(2))
            inline.define_link(name, m.group(2))
            continue
        m = HEADING.match(line)
        if m:
            flush()
            blocks.append(Heading(len(m.group(1)), m.group(2)))
            continue
        if line.strip() == "---":
            flush()
            blocks.append(Rule())
            continue
        mu, mo = UL_ITEM.match(line), OL_ITEM.match(line)
        if mu or mo:
            if para:
                flush()
            ordered = mo is not None
            if lst is None or lst.ordered != ordered:
                flush()
                lst = ListBlock(ordered=ordered)
            lst.items.append((mo or mu).group(1))
            continue
        if lst is not None and lines[i - 1].startswith("  "):
            lst.items[-1] += " " + line.strip()
            continue
        if lst is not None:
            flush()
        para.append(line.strip())
    flush()
    return Document(blocks, footnotes, links)
