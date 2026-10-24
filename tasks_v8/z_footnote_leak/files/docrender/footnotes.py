"""Footnotes: numbered in the order of their first reference in the document."""
import html


class FootnoteRegistry:
    # id -> number, assigned on first reference
    numbers = {}

    def __init__(self, definitions):
        self.definitions = dict(definitions)
        self.counts = {}

    def reference(self, fid):
        """Number of footnote `fid` (assigning the next one on first use); None if undefined."""
        if fid not in self.definitions:
            return None
        if fid not in self.numbers:
            self.numbers[fid] = len(self.numbers) + 1
        self.counts[fid] = self.counts.get(fid, 0) + 1
        return self.numbers[fid]

    def ref_count(self, fid):
        return self.counts.get(fid, 0)

    def used(self):
        """[(number, id)] of the footnotes referenced in this document, by number."""
        return sorted((n, fid) for fid, n in self.numbers.items() if fid in self.counts)

    def render_section(self, render_text):
        used = self.used()
        if not used:
            return []
        out = ['<section class="footnotes">', "<ol>"]
        for n, fid in used:
            body = render_text(self.definitions[fid])
            out.append(f'<li id="fn-{n}">{body} <a href="#fnref-{n}">&#8617;</a></li>')
        out += ["</ol>", "</section>"]
        return out


def footnote_title(fid):
    return html.escape(fid)
