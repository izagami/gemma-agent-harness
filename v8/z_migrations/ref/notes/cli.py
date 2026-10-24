"""Command line: python3 -m notes [--db PATH] COMMAND ..."""
import argparse
import os
import sys

import io

from notes import db, migrate, models


def build_parser():
    p = argparse.ArgumentParser(prog="notes")
    p.add_argument("--db", help="database file (default: $NOTES_DB or ./notes.db)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create / upgrade the database")
    m = sub.add_parser("migrate", help="apply schema migrations")
    m.add_argument("action", nargs="?", choices=["status"])
    m.add_argument("--dir", default=migrate.DEFAULT_DIR)
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--to", type=int)
    a = sub.add_parser("add", help="add a note")
    a.add_argument("title")
    a.add_argument("--body", default="")
    a.add_argument("--tag", action="append", default=[])
    a.add_argument("--date", default=os.environ.get("NOTES_TODAY", "1970-01-01"))
    l = sub.add_parser("list", help="list notes")
    l.add_argument("--tag")
    s = sub.add_parser("show", help="show one note")
    s.add_argument("id", type=int)
    d = sub.add_parser("delete", help="delete a note")
    d.add_argument("id", type=int)
    return p


def fmt_line(n):
    tags = (" [" + ", ".join(n.tags) + "]") if n.tags else ""
    return f"{n.id:>4}  {n.created}  {n.title}{tags}"


def main(argv=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args = build_parser().parse_args(argv)
    path = db.db_path(args.db)
    if args.cmd in ("init", "migrate"):
        try:
            if args.cmd == "init":
                migrate.migrate(path, migrate.DEFAULT_DIR, io.StringIO())
                print(f"initialized {path}", file=out)
            elif args.action == "status":
                migrate.status(path, args.dir, out)
            else:
                migrate.migrate(path, args.dir, out, args.dry_run, args.to)
        except migrate.MigrationError as e:
            print(e, file=err)
            return e.code
        return 0
    if not os.path.exists(path):
        print(f"error: no database at {path} (run init first)", file=err)
        return 1
    conn = db.connect(path)
    try:
        if args.cmd == "add":
            try:
                n = models.add(conn, args.title, args.body, args.tag, args.date)
            except ValueError as e:
                print(f"error: {e}", file=err)
                return 1
            print(f"added {n.id}", file=out)
        elif args.cmd == "list":
            for n in models.list_notes(conn, args.tag):
                print(fmt_line(n), file=out)
        elif args.cmd == "show":
            try:
                n = models.get(conn, args.id)
            except models.NotFound:
                print(f"error: note {args.id} not found", file=err)
                return 1
            print(fmt_line(n), file=out)
            if n.body:
                print("", file=out)
                print(n.body, file=out)
        elif args.cmd == "delete":
            try:
                models.delete(conn, args.id)
            except models.NotFound:
                print(f"error: note {args.id} not found", file=err)
                return 1
            print(f"deleted {args.id}", file=out)
    finally:
        conn.close()
    return 0
