"""sqlkit: tested helpers for correct SQLite work with Python's sqlite3 (standard library only).

Copy next to your code and `from sqlkit import *` (or `from .sqlkit import *` inside a package).

    con = connect_existing(path)          opens an EXISTING file only (sqlite3.connect would create a new empty one),
                                          isolation_level=None so that only YOUR BEGIN/COMMIT control transactions
    with transaction(con):                BEGIN IMMEDIATE ... COMMIT; any exception -> ROLLBACK and re-raise.
        ...                               The file is then byte-identical to before (all or nothing).
    run_statements(con, sql)              runs a multi-statement SQL text one statement at a time INSIDE the current
                                          transaction. Use instead of con.executescript(), which COMMITs first and runs
                                          outside your transaction (a later ROLLBACK then fails: "no transaction is active")
    get_user_version(con) / set_user_version(con, n)
    table_names(con)                      user tables (sqlite_% excluded), sorted
    columns(con, table)                   column names in order
    fk_violations(con)                    PRAGMA foreign_key_check rows ([] = fine)
    enable_foreign_keys(con)              PRAGMA foreign_keys=ON (ON DELETE CASCADE only works on such a connection;
                                          must be set outside a transaction)
    like_escape(text, esc="\\\\")           escapes % _ and the escape char for  ... LIKE ? ESCAPE '\\'
    like_contains(text)                   -> pattern '%text%' already escaped; use with "LIKE ? ESCAPE '\\'"
    file_sha256(path)                     for your own test that a failed run left the file unchanged
    count(con, table, where="", params=())

Rules of thumb kept in these helpers: never commit() inside a loop; no executescript() inside a transaction;
parameters (?) for every value; a keyset cursor needs a total order (e.g. ORDER BY price DESC, id ASC).
"""
import contextlib
import hashlib
import os
import sqlite3


def connect_existing(path):
    """sqlite3 connection to an existing file (raises sqlite3.OperationalError if it does not exist);
    autocommit mode: transactions only where you open them (transaction())"""
    if not os.path.exists(path):
        raise sqlite3.OperationalError(f"unable to open database file: {path}")
    return sqlite3.connect(f"file:{path}?mode=rw", uri=True, isolation_level=None)


@contextlib.contextmanager
def transaction(con, mode="IMMEDIATE"):
    """BEGIN <mode> ... COMMIT; ROLLBACK and re-raise on any exception"""
    if con.in_transaction:
        raise RuntimeError("transaction(): a transaction is already open (did something commit implicitly?)")
    con.execute(f"BEGIN {mode}")
    try:
        yield con
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


def split_statements(sql):
    """split SQL text into complete statements at every ';' that ends one (string literals, quoted names and comments
    are respected via sqlite3.complete_statement); several statements on one line are split too"""
    out, cur = [], ""
    for ch in sql:
        cur += ch
        if ch == ";" and sqlite3.complete_statement(cur):
            st = cur.strip()
            if st.strip(";").strip():
                out.append(st)
            cur = ""
    rest = cur.strip()
    if rest and not all(l.strip().startswith("--") or not l.strip() for l in rest.splitlines()):
        out.append(rest)
    return out


def run_statements(con, sql):
    """execute every statement of sql with con.execute (stays inside the open transaction, unlike executescript)"""
    for st in split_statements(sql):
        con.execute(st)


def get_user_version(con):
    return con.execute("PRAGMA user_version").fetchone()[0]


def set_user_version(con, n):
    con.execute(f"PRAGMA user_version = {int(n)}")


def table_names(con):
    return sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))


def columns(con, table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def fk_violations(con):
    return con.execute("PRAGMA foreign_key_check").fetchall()


def enable_foreign_keys(con):
    con.execute("PRAGMA foreign_keys = ON")


def like_escape(text, esc="\\"):
    return str(text).replace(esc, esc + esc).replace("%", esc + "%").replace("_", esc + "_")


def like_contains(text, esc="\\"):
    return "%" + like_escape(text, esc) + "%"


def file_sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def count(con, table, where="", params=()):
    return con.execute(f'SELECT COUNT(*) FROM "{table}"' + (f" WHERE {where}" if where else ""), params).fetchone()[0]


__all__ = [n for n in list(globals()) if not n.startswith("_") and n not in ("contextlib", "hashlib", "os", "sqlite3")]
