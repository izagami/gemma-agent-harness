"""Data access functions of the time-tracking app (docs/REPO.md)."""


def project_summary(con):
    rows = con.execute("""
        SELECT p.id, p.name, COUNT(*), SUM(e.minutes), SUM(e.minutes * p.rate_yen / 60)
        FROM projects p LEFT JOIN entries e ON e.project_id = p.id
        WHERE p.archived = 0
        GROUP BY p.id
        ORDER BY p.name""").fetchall()
    return [{"id": r[0], "name": r[1], "entries": r[2], "minutes": r[3], "amount_yen": r[4]} for r in rows]


def search_entries(con, text):
    rows = con.execute(f"SELECT id FROM entries WHERE note LIKE '%{text}%' ORDER BY started_at DESC").fetchall()
    return [r[0] for r in rows]


def entries_page(con, username, size, after=None):
    if after is None:
        rows = con.execute("SELECT id, started_at FROM entries WHERE username LIKE ? "
                           "ORDER BY started_at DESC, id DESC LIMIT ?", (username, size)).fetchall()
    else:
        rows = con.execute("SELECT id, started_at FROM entries WHERE username LIKE ? AND started_at < ? "
                           "ORDER BY started_at DESC, id DESC LIMIT ?", (username, after, size)).fetchall()
    cursor = rows[-1][1] if len(rows) == size else None
    return [r[0] for r in rows], cursor


def daily_minutes(con, username, utc_offset_hours):
    rows = con.execute("""
        SELECT substr(started_at, 1, 10) AS day, SUM(minutes)
        FROM entries WHERE username = ?
        GROUP BY day ORDER BY day""", (username,)).fetchall()
    return [(d, m) for d, m in rows]


def running_timers(con):
    # minutes stays empty while the timer runs
    rows = con.execute("""
        SELECT e.username, p.name, e.started_at
        FROM entries e JOIN projects p ON p.id = e.project_id
        WHERE NOT e.minutes
        ORDER BY e.started_at, e.id""").fetchall()
    return [tuple(r) for r in rows]


def user_report(con, username):
    projects = con.execute("""
        SELECT DISTINCT p.id, p.name FROM projects p JOIN entries e ON e.project_id = p.id
        WHERE e.username = ? ORDER BY p.name""", (username,)).fetchall()
    out = []
    for pid, name in projects:
        entries = [{"id": r[0], "started_at": r[1], "minutes": r[2], "note": r[3]} for r in con.execute(
            "SELECT id, started_at, minutes, note FROM entries WHERE project_id = ? AND username = ? "
            "ORDER BY started_at, id", (pid, username))]
        out.append({"project_id": pid, "project": name, "minutes": sum(e["minutes"] or 0 for e in entries),
                    "entries": entries})
    return out


def delete_project(con, project_id):
    n = con.execute("SELECT COUNT(*) FROM entries WHERE project_id = ?", (project_id,)).fetchone()[0]
    con.execute("DELETE FROM projects WHERE id = ?", (project_id,))   # entries go with it (ON DELETE CASCADE)
    con.commit()
    return n
