CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,      -- 1 = archived
    rate_yen INTEGER                          -- hourly rate in yen; NULL = not billable
);
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    started_at TEXT NOT NULL,                 -- UTC, 'YYYY-MM-DDTHH:MM:SSZ'
    minutes INTEGER,                          -- NULL while the timer is still running
    note TEXT
);
