"""Front matter: a block of `key: value` lines between two `---` lines at the top of a post.

    ---
    title: Hello
    date: 2026-01-31
    tags: python, 日記
    draft: true
    ---
    body...

Keys are lower-cased.  `tags` becomes a list (comma separated, items stripped, empty items
dropped; a value in square brackets like `[a, b]` is accepted too).  `draft` becomes a bool.
"""


class FrontMatterError(ValueError):
    pass


TRUE = {"true", "yes", "1", "on"}
FALSE = {"false", "no", "0", "off", ""}


def parse(text):
    """(meta dict, body text)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1:])
            return _finish(meta), body
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise FrontMatterError(f"line {i + 1}: expected 'key: value'")
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip()
    raise FrontMatterError("front matter is not closed with '---'")


def _finish(meta):
    if "tags" in meta:
        v = meta["tags"]
        if v.startswith("[") and v.endswith("]"):
            v = v[1:-1]
        meta["tags"] = [t.strip() for t in v.split(",") if t.strip()]
    else:
        meta["tags"] = []
    d = meta.get("draft", "").lower()
    if d in TRUE:
        meta["draft"] = True
    elif d in FALSE:
        meta["draft"] = False
    else:
        raise FrontMatterError(f"draft: expected true/false, got {meta['draft']!r}")
    return meta
