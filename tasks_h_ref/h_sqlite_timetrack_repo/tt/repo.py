"""Data access functions of the time-tracking app (docs/REPO.md)."""


def project_summary(con):
    rows = con.execute("""
        SELECT p.id, p.name, COUNT(e.id), COALESCE(SUM(e.minutes), 0), p.rate_yen
        FROM projects p LEFT JOIN entries e ON e.project_id = p.id
        WHERE p.archived = 0
        GROUP BY p.id
        ORDER BY p.name COLLATE NOCASE, p.id""").fetchall()
    return [{"id": r[0], "name": r[1], "entries": r[2], "minutes": r[3],
             "amount_yen": None if r[4] is None else r[3] * r[4] // 60} for r in rows]


def _like_escape(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_entries(con, text):
    rows = con.execute("SELECT id FROM entries WHERE note LIKE ? ESCAPE '\\' ORDER BY started_at DESC, id DESC",
                       ("%" + _like_escape(text) + "%",)).fetchall()
    return [r[0] for r in rows]


def entries_page(con, username, size, after=None):
    if after is None:
        rows = con.execute("SELECT id, started_at FROM entries WHERE username = ? "
                           "ORDER BY started_at DESC, id DESC LIMIT ?", (username, size + 1)).fetchall()
    else:
        at, aid = after
        rows = con.execute("SELECT id, started_at FROM entries WHERE username = ? "
                           "AND (started_at < ? OR (started_at = ? AND id < ?)) "
                           "ORDER BY started_at DESC, id DESC LIMIT ?", (username, at, at, aid, size + 1)).fetchall()
    more = len(rows) > size
    rows = rows[:size]
    cursor = (rows[-1][1], rows[-1][0]) if more else None
    return [r[0] for r in rows], cursor


def daily_minutes(con, username, utc_offset_hours):
    mod = f"{int(utc_offset_hours):+d} hours"
    rows = con.execute("""
        SELECT date(started_at, ?) AS day, SUM(minutes)
        FROM entries WHERE username = ? AND minutes IS NOT NULL
        GROUP BY day ORDER BY day""", (mod, username)).fetchall()
    return [(d, m) for d, m in rows]


def running_timers(con):
    rows = con.execute("""
        SELECT e.username, p.name, e.started_at
        FROM entries e JOIN projects p ON p.id = e.project_id
        WHERE e.minutes IS NULL
        ORDER BY e.started_at, e.id""").fetchall()
    return [tuple(r) for r in rows]


def user_report(con, username):
    rows = con.execute("""
        SELECT p.id, p.name, e.id, e.started_at, e.minutes, e.note
        FROM entries e JOIN projects p ON p.id = e.project_id
        WHERE e.username = ?
        ORDER BY p.name COLLATE NOCASE, p.id, e.started_at, e.id""", (username,)).fetchall()
    out = []
    for pid, name, eid, at, mins, note in rows:
        if not out or out[-1]["project_id"] != pid:
            out.append({"project_id": pid, "project": name, "minutes": 0, "entries": []})
        out[-1]["entries"].append({"id": eid, "started_at": at, "minutes": mins, "note": note})
        out[-1]["minutes"] += mins or 0
    return out


def delete_project(con, project_id):
    try:
        n = con.execute("DELETE FROM entries WHERE project_id = ?", (project_id,)).rowcount
        con.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        con.commit()
    except BaseException:
        con.rollback()
        raise
    return n
