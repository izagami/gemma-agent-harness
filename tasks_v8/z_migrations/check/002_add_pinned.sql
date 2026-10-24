-- notes can be pinned to the top of `list`
ALTER TABLE notes ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0;
