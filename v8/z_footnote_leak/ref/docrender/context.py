"""Per-document rendering state: section numbering, heading ids, footnotes."""
import re
import unicodedata

from docrender.footnotes import FootnoteRegistry


def slugify(text):
    """'Getting Started!' -> 'getting-started' (non-ASCII letters are kept)."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-") or "section"


class RenderContext:
    def __init__(self, document, counters=None, used_ids=None):
        self.document = document
        self.footnotes = FootnoteRegistry(document.footnotes)
        self.counters = list(counters) if counters is not None else [0, 0]   # [h2 number, h3 number]
        self.used_ids = set(used_ids) if used_ids is not None else set()

    def heading_number(self, level):
        """'1', '1.2', ... for ## and ### headings; None for the # title."""
        if level == 1:
            return None
        if level == 2:
            self.counters[0] += 1
            self.counters[1] = 0
            return f"{self.counters[0]}"
        self.counters[1] += 1
        return f"{self.counters[0]}.{self.counters[1]}"

    def heading_id(self, text):
        """Unique id for a heading: slug, then slug-2, slug-3, ... within the document."""
        base = slugify(text)
        hid, k = base, 1
        while hid in self.used_ids:
            k += 1
            hid = f"{base}-{k}"
        self.used_ids.add(hid)
        return hid
