# Schema v1 -> v2

`python3 -m crm.migrate DB` upgrades a contacts database in place. `PRAGMA user_version` holds the schema version
(v1 databases have 0 or 1).

## v1
    contacts(id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, tags TEXT)   -- tags: comma separated
    notes(id INTEGER PRIMARY KEY, contact_id INTEGER, body TEXT)               -- no foreign key

## v2 (exactly these tables, user_version = 2, v1 tables gone)
    contacts(id INTEGER PRIMARY KEY, last_name TEXT NOT NULL, first_name TEXT NOT NULL, email TEXT)
    tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)
    contact_tags(contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                 tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                 PRIMARY KEY (contact_id, tag_id))
    notes(id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, body TEXT)
    orphan_notes(id INTEGER PRIMARY KEY, contact_id INTEGER, body TEXT)

## Rules
* Contact ids, emails, note ids and bodies are kept as they are.
* Names are written family name first. Trim the name; the part before the first space (ASCII space or the
  full-width space U+3000) is `last_name`, the rest (trimmed, may contain spaces) is `first_name`. No space:
  the whole name is `last_name` and `first_name` is ''. Example: '  山田　太郎 ' -> ('山田', '太郎').
* Tags: split on ',', trim, lower-case; empty entries are dropped; the same tag twice on a contact counts once.
  One `tags` row per distinct name over the whole database.
* Notes whose contact_id is NULL or not an existing contact go to `orphan_notes` (same id, contact_id, body).
* A contact whose full_name is NULL or blank makes the whole migration fail.
* All or nothing: on any failure the database is left exactly as it was (still v1), the command prints
  `migration failed: <reason>` to stderr and exits with status 1.
* On success it prints `migrated to v2: C contacts, T tags, N notes, O orphan notes` and exits 0. Running it on a
  v2 database changes nothing, prints `already at v2` and exits 0.
* Afterwards `PRAGMA foreign_key_check` reports nothing.
