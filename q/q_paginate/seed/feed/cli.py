"""python3 -m feed POSTS.jsonl [--author NAME] [--limit N] [--cursor C]"""
import argparse
import sys

from .paginate import page
from .store import load


def main(argv):
    ap = argparse.ArgumentParser(prog="feed")
    ap.add_argument("posts")
    ap.add_argument("--author")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--cursor")
    a = ap.parse_args(argv)
    try:
        res = page(load(a.posts), a.limit, a.cursor, a.author)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for p in res["items"]:
        print(f"{p['id']}\t{p['created_at']}\t{p['author']}\t{p['title']}")
    print(f"next: {res['next'] or '-'}")
    return 0
