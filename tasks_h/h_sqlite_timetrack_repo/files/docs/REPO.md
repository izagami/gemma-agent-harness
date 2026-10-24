# tt.repo

Data access functions of the time-tracking web app (schema: data/schema.sql). Every function takes an open
`sqlite3.Connection` and returns plain Python values exactly as below (ints are Python `int`, never `float`).
Inputs come from users: any text (quotes, `%`, `_`, `\`) must work and is never part of the SQL text.

Terms: an entry is *running* when `minutes` is NULL (timer not stopped yet) and *finished* otherwise; a finished
entry may have `minutes = 0`. Usernames are compared exactly (case-sensitive, no wildcards). "Name order" means
ASCII-case-insensitive order of `name` (`alpha`, `Beta`, `gamma`), ties by id ascending.

* `project_summary(con)` -> one dict `{"id", "name", "entries", "minutes", "amount_yen"}` for EVERY project with
  `archived = 0`, including projects without entries. `entries` = number of its entries (running ones included),
  `minutes` = sum of its finished entries' minutes (0 if none), `amount_yen` = None when the project's `rate_yen` is
  NULL, otherwise `minutes * rate_yen // 60` computed once on the project's total minutes (rounded down to whole yen).
  Order: name order.
* `search_entries(con, text)` -> list of ids of the entries whose `note` contains `text` literally (ASCII letters
  case-insensitive; `%`, `_`, `\` and `'` are ordinary characters). A NULL note never matches; `''` matches every
  non-NULL note. Order: `started_at` descending, then id descending.
* `entries_page(con, username, size, after=None)` -> `(ids, cursor)`: the user's entries ordered by `started_at`
  descending, then id descending; at most `size` of them that come after `after` in this order. `cursor` is an
  opaque value to pass as `after` for the next page, or None when no entries are left after this page. Following the
  cursors lists every entry of the user exactly once, even when many entries share the same `started_at`.
* `daily_minutes(con, username, utc_offset_hours)` -> list of `(day, minutes)`: the user's finished entries grouped
  by the local calendar day of `started_at` in the time zone UTC+`utc_offset_hours` (an int, may be negative or 0),
  `day` as `'YYYY-MM-DD'`, minutes summed (a day whose entries all have 0 minutes appears with 0). Running entries
  are ignored completely. Order: day.
* `running_timers(con)` -> list of `(username, project name, started_at)` for every running entry (archived projects
  included). Order: `started_at`, then entry id.
* `user_report(con, username)` -> one dict `{"project_id", "project", "minutes", "entries"}` per project in which the
  user has at least one entry (archived projects included), in name order of the project; `minutes` = sum of the
  user's finished minutes in that project; `entries` = list of `{"id", "started_at", "minutes", "note"}` of the
  user's entries in that project ordered by `started_at`, then id. Must run at most 2 SQL statements in total,
  whatever the number of projects (the report page is slow otherwise).
* `delete_project(con, project_id)` -> deletes the project and all its entries, commits, and returns the number of
  entries deleted (0 and no change when there is no such project). The caller's connection may or may not have
  `PRAGMA foreign_keys` enabled; no entry of the project may be left behind either way, and entries of other
  projects are untouched.
