"""Assemble the HTML of a document (format: docs/SYNTAX.md)."""
import html

from docrender.blocks import Code, Heading, ListBlock, Paragraph, Rule
from docrender.context import RenderContext
from docrender.inline import render_inline
from docrender.parser import parse


def render_block(block, ctx):
    if isinstance(block, Heading):
        text = render_inline(block.text, ctx)
        hid = ctx.heading_id(block.text)
        num = ctx.heading_number(block.level)
        label = f"{num}. {text}" if num else text
        return [f'<h{block.level} id="{hid}">{label}</h{block.level}>']
    if isinstance(block, Paragraph):
        return [f"<p>{render_inline(block.text, ctx)}</p>"]
    if isinstance(block, ListBlock):
        tag = "ol" if block.ordered else "ul"
        return [f"<{tag}>", *(f"<li>{render_inline(it, ctx)}</li>" for it in block.items), f"</{tag}>"]
    if isinstance(block, Code):
        cls = f' class="lang-{block.lang}"' if block.lang else ""
        body = "\n".join(html.escape(l) for l in block.lines)
        return [f"<pre><code{cls}>{body}</code></pre>"]
    if isinstance(block, Rule):
        return ["<hr>"]
    raise TypeError(f"unknown block {block!r}")


def render(text):
    """Render one document to HTML (a string ending in a newline)."""
    doc = parse(text)
    ctx = RenderContext(doc)
    out = ["<article>"]
    for block in doc.blocks:
        out += render_block(block, ctx)
    out += ctx.footnotes.render_section(lambda t: render_inline(t, ctx))
    out.append("</article>")
    return "\n".join(out) + "\n"
