# Task suite changes

- 2026-10-18: h_dupes instruction said "in order of first appearance" but the original function (and the
  check) use the order in which the second occurrence appears. Fixed the wording. Results for h_dupes from
  runs before this change are not comparable.
- 2026-10-18: h_access did not say whether blank lines count as bad lines (the check expects they do not). Added "空行は数えない". Earlier h_access results are not comparable.
- 2026-10-18: audit of all 40 tasks (spec vs hidden check). Wording fixed for stats_cli (rounding), robust
  (null amounts), h_money (string prices), h_sqlite (only departments with employees, rounding), wordcount
  (chars include newlines), log_errors (final newline), h_sync (sort copy/delete together, one line per deleted
  folder, no copy lines for folders), h_clean_csv (numeric id sort), csv_sum (rounding), x_cache_bug (do not
  mutate caller's params), x_write_tests (one assert per line; check no longer hides failing tests behind
  `| tail`). Results before this change are not comparable for these tasks.
