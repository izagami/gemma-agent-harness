"""Database access: where the DB lives and how to open it (the schema lives in migrations/)."""
import os
import sqlite3

DEFAULT_DB = "notes.db"


def db_path(arg=None):
    """--db wins, then $NOTES_DB, then ./notes.db."""
    return arg or os.environ.get("NOTES_DB") or DEFAULT_DB


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_exists(conn, name):
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return row is not None
