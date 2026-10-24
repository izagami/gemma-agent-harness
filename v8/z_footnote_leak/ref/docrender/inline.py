"""Inline markup: escaping, `code`, **strong**, *em*, links and footnote references."""
import html
import re

CODE = re.compile(r"`([^`]+)`")
STRONG = re.compile(r"\*\*(.+?)\*\*")
EM = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])")
INLINE_LINK = re.compile(r"\[([^\]^][^\]]*)\]\(([^)\s]+)\)")
REF_LINK = re.compile(r"\[([^\]^][^\]]*)\]\[([^\]]*)\]")
FOOTREF = re.compile(r"\[\^([^\]\s]+)\]")


def resolve_link(name, ctx):
    """URL of a link reference definition of the current document (None if undefined)."""
    return ctx.document.links.get(name.lower())


def render_inline(text, ctx):
    """Render one line/paragraph of inline markup to HTML.  `ctx` is the RenderContext."""
    stash = []

    def keep(s):
        stash.append(s)
        return f"\x00{len(stash) - 1}\x00"

    # code spans first: nothing inside them is markup
    text = CODE.sub(lambda m: keep(f"<code>{html.escape(m.group(1))}</code>"), text)

    def footref(m):
        n = ctx.footnotes.reference(m.group(1))
        if n is None:
            return keep(html.escape(m.group(0)))
        first = ctx.footnotes.ref_count(m.group(1)) == 1
        rid = f' id="fnref-{n}"' if first else ""
        return keep(f'<sup{rid}><a href="#fn-{n}">{n}</a></sup>')

    text = FOOTREF.sub(footref, text)

    def inline_link(m):
        return keep(f'<a href="{html.escape(m.group(2))}">{render_inline(m.group(1), ctx)}</a>')

    def ref_link(m):
        label, name = m.group(1), m.group(2) or m.group(1)
        url = resolve_link(name, ctx)
        if url is None:
            return keep(html.escape(m.group(0)))
        return keep(f'<a href="{html.escape(url)}">{render_inline(label, ctx)}</a>')

    text = INLINE_LINK.sub(inline_link, text)
    text = REF_LINK.sub(ref_link, text)
    text = html.escape(text, quote=False)
    text = STRONG.sub(r"<strong>\1</strong>", text)
    text = EM.sub(r"<em>\1</em>", text)
    return re.sub("\x00(\\d+)\x00", lambda m: stash[int(m.group(1))], text)
