"""Schema migrations: DIR/NNN_name.sql applied in numeric order, recorded in schema_migrations."""
import hashlib
import os
import re
import sqlite3

from notes import db

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")
PATTERN = re.compile(r"^([0-9]+)_([a-z0-9_]+)\.sql$")


class MigrationError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code


def scan(directory):
    found = []
    for f in sorted(os.listdir(directory)):
        m = PATTERN.fullmatch(f)
        if m and os.path.isfile(os.path.join(directory, f)):
            data = open(os.path.join(directory, f), "rb").read()
            found.append((int(m.group(1)), m.group(2), hashlib.sha256(data).hexdigest(), data.decode("utf-8")))
    found.sort(key=lambda x: x[0])
    return found


def applied_rows(conn):
    """{version: (name, checksum)}; None-conn = nothing. Old-init DBs report a virtual baseline."""
    if conn is None:
        return {}, False
    if db.table_exists(conn, "schema_migrations"):
        return {r[0]: (r[1], r[2]) for r in conn.execute("SELECT version, name, checksum FROM schema_migrations")}, False
    if db.table_exists(conn, "notes"):
        return None, True
    return {}, False


def plan(path, directory):
    migs = scan(directory)
    seen = set()
    for v, *_ in migs:
        if v in seen:
            raise MigrationError(f"error: duplicate migration version {v:03d}", 2)
        seen.add(v)
    for i in range(1, len(migs) + 1):
        if i not in seen:
            raise MigrationError(f"error: missing migration version {i:03d}", 2)
    by_v = {m[0]: m for m in migs}
    conn = db.connect(path) if os.path.exists(path) else None
    rows, baseline = applied_rows(conn)
    if baseline:
        if 1 not in by_v:
            raise MigrationError("error: missing migration version 001", 2)
        rows = {1: (by_v[1][1], by_v[1][2])}
    for v in sorted(rows):
        if v not in by_v:
            raise MigrationError(f"error: applied migration {v:03d} not found", 3)
    for v in sorted(rows):
        if rows[v][1] != by_v[v][2]:
            raise MigrationError(f"error: checksum mismatch for {v:03d} {by_v[v][1]}", 3)
    return conn, migs, set(rows), baseline


def status(path, directory, out):
    conn, migs, done, _ = plan(path, directory)
    if conn:
        conn.close()
    for v, name, *_ in migs:
        print(f"[{'x' if v in done else ' '}] {v:03d} {name}", file=out)
    print(f"current: {max(done):03d}" if done else "current: none", file=out)


def migrate(path, directory, out, dry_run=False, to=None):
    conn, migs, done, baseline = plan(path, directory)
    try:
        top = max((m[0] for m in migs), default=0)
        if to is not None and to > top:
            raise MigrationError(f"error: unknown target version {to:03d}", 2)
        pending = [m for m in migs if m[0] not in done and (to is None or m[0] <= to)]
        if not pending and not baseline:
            print("up to date", file=out)
            return
        if dry_run:
            if baseline:
                print(f"would baseline 001 {migs[0][1]}", file=out)
            for v, name, *_ in pending:
                print(f"would apply {v:03d} {name}", file=out)
            if not pending and not baseline:
                print("up to date", file=out)
            return
        if conn is None:
            conn = db.connect(path)
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                     "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL)")
        conn.commit()
        if baseline:
            v, name, chk, _ = migs[0]
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?, ?)", (v, name, chk))
            conn.commit()
            print(f"baseline {v:03d} {name}", file=out)
        for v, name, chk, sql in pending:
            try:
                conn.executescript("BEGIN;\n" + sql)
                conn.execute("INSERT INTO schema_migrations VALUES (?, ?, ?)", (v, name, chk))
                conn.commit()
            except sqlite3.Error as e:
                if conn.in_transaction:
                    conn.rollback()
                raise MigrationError(f"error: migration {v:03d} {name} failed: {e}", 1)
            print(f"apply {v:03d} {name}", file=out)
    finally:
        if conn:
            conn.close()
