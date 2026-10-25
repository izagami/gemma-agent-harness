# notes

    python3 -m notes --db my.db init
    python3 -m notes --db my.db add "buy milk" --tag home
    python3 -m notes --db my.db list

The schema lives in `migrations/` (`NNN_name.sql`). `db.SCHEMA` is a copy of 001 used by `init`
until the migration runner exists.

Tests: `python3 -m unittest discover -s tests`
