"""Database access: where the DB lives, how to open it, how to create the schema."""
import os
import sqlite3

DEFAULT_DB = "notes.db"

# NOTE: keep in sync with migrations/001_initial.sql
SCHEMA = """
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
CREATE TABLE tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (note_id, tag)
);
CREATE INDEX tags_by_tag ON tags(tag);
"""


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


def init(conn):
    """Create the schema if the DB is empty."""
    if not table_exists(conn, "notes"):
        conn.executescript(SCHEMA)
    conn.commit()
