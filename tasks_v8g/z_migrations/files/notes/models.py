"""Note CRUD on an open connection."""
from dataclasses import dataclass, field


class NotFound(Exception):
    pass


@dataclass
class Note:
    id: int
    title: str
    body: str
    created: str
    tags: list = field(default_factory=list)


def _tags(conn, note_id):
    return [r["tag"] for r in conn.execute("SELECT tag FROM tags WHERE note_id = ? ORDER BY tag", (note_id,))]


def add(conn, title, body="", tags=(), created="1970-01-01"):
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")
    cur = conn.execute("INSERT INTO notes (title, body, created) VALUES (?, ?, ?)", (title, body, created))
    nid = cur.lastrowid
    for t in sorted({t.strip().lower() for t in tags if t.strip()}):
        conn.execute("INSERT INTO tags (note_id, tag) VALUES (?, ?)", (nid, t))
    conn.commit()
    return get(conn, nid)


def get(conn, note_id):
    r = conn.execute("SELECT id, title, body, created FROM notes WHERE id = ?", (note_id,)).fetchone()
    if r is None:
        raise NotFound(note_id)
    return Note(r["id"], r["title"], r["body"], r["created"], _tags(conn, r["id"]))


def list_notes(conn, tag=None):
    if tag:
        rows = conn.execute("SELECT n.id FROM notes n JOIN tags t ON t.note_id = n.id WHERE t.tag = ? ORDER BY n.id",
                            (tag.lower(),))
    else:
        rows = conn.execute("SELECT id FROM notes ORDER BY id")
    return [get(conn, r["id"]) for r in rows.fetchall()]


def delete(conn, note_id):
    cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise NotFound(note_id)
