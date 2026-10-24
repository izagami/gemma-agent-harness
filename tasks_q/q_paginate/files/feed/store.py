"""Loading posts from a JSON Lines file."""
import json


def load(path):
    posts = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))
    return posts


def sort_key(p):
    return (p["created_at"], p["id"])


def ordered(posts):
    """Newest first; equal times: larger id first."""
    return sorted(posts, key=sort_key, reverse=True)
