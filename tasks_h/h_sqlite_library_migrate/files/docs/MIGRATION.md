# Library database: schema v1 -> v2

`python3 -m biblio.migrate DB` upgrades a library loan database in place. `PRAGMA user_version` holds the schema
version: v1 databases have 0 or 1, migrated databases have 2.

## v1
    books(id INTEGER PRIMARY KEY, title TEXT, author TEXT)
    loans(id INTEGER PRIMARY KEY, book_id INTEGER, member TEXT, loaned_at TEXT, returned_at TEXT, fine REAL)

* `member` is the member card code as typed at the counter (e.g. ` m-0012 `).
* `loaned_at` / `returned_at` are Japan local time (JST, UTC+9, no daylight saving) written as
  `YYYY-MM-DD HH:MM` or, from the old counter client, `YYYY/MM/DD HH:MM`, possibly with spaces around.
  `returned_at` is NULL, '' or only spaces while the book is still out.
* `fine` is the overdue fine in yen stored as a float by an old calculation (e.g. `99.99999999`), or NULL (no fine).

## v2 (exactly these tables, user_version = 2, no other tables left)
    books(id INTEGER PRIMARY KEY, title TEXT, author TEXT)                       -- unchanged, same rows
    members(id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE)
    loans(id INTEGER PRIMARY KEY,
          book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
          member_id INTEGER NOT NULL REFERENCES members(id),
          loaned_at TEXT NOT NULL,
          returned_at TEXT,
          fine_yen INTEGER NOT NULL)

## Rules
* Books are kept as they are. Loan ids and book ids are kept.
* Member code = `member` with surrounding spaces removed and ASCII letters upper-cased (` m-0012 ` -> `M-0012`).
  One `members` row per distinct code; ids are 1, 2, 3, ... in ascending order of the code (plain string order).
  `loans.member_id` points to the loan's member.
* Times are stored in UTC as `YYYY-MM-DDTHH:MM:00Z`; e.g. `2026/03/01 08:30` (JST) -> `2026-02-28T23:30:00Z`.
  A time is valid only in one of the two formats above with exactly 4/2/2 digit year/month/day (one separator
  kind, not mixed), exactly 2/2 digit hour/minute, a real calendar date and a time 00:00-23:59.
  A `returned_at` that is NULL/''/only spaces becomes NULL.
* `fine_yen` = `fine` rounded to the nearest integer (stored fines are never halfway between two integers);
  NULL becomes 0.
* The migration fails if a loan has a NULL or blank member, a `book_id` that is NULL or not an existing book,
  a `loaned_at` that is not a valid time, or a `returned_at` that is neither empty nor a valid time.
  It also fails if `user_version` is not 0, 1 or 2 (`unknown schema version N`).
* All or nothing: on any failure the database file is left exactly as it was (byte for byte), the command prints
  `migration failed: <reason>` to stderr and exits with status 1.
* On success it prints `migrated to v2: B books, M members, L loans` and exits 0.
* Running it on a v2 database changes nothing (the file stays byte-identical), prints `already at v2` and exits 0.
* Afterwards, with `PRAGMA foreign_keys = ON`: `PRAGMA foreign_key_check` reports nothing, deleting a book deletes
  its loans, and deleting a member who still has loans is refused.
