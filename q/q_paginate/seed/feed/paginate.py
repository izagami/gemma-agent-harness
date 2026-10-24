"""Cursor pagination."""
import base64
import json

from .store import ordered

MAX_LIMIT = 100


def encode_cursor(post):
    raw = json.dumps({"t": post["created_at"]}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor):
    pad = "=" * (-len(cursor) % 4)
    try:
        d = json.loads(base64.urlsafe_b64decode(cursor + pad))
        return d["t"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("bad cursor") from None


def visible(post, author):
    return not post.get("deleted") and (author is None or post["author"] == author)


def page(posts, limit=20, cursor=None, author=None):
    """One page: {"items": [post, ...], "next": cursor or None}."""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be 1..{MAX_LIMIT}")
    rows = ordered(posts)
    if cursor is not None:
        t = decode_cursor(cursor)
        rows = [p for p in rows if p["created_at"] < t]
    chunk = [p for p in rows[:limit] if visible(p, author)]
    nxt = encode_cursor(chunk[-1]) if len(chunk) == limit else None
    return {"items": chunk, "next": nxt}
