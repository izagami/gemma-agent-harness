# Task suite changes

- 2026-10-18: h_dupes instruction said "in order of first appearance" but the original function (and the
  check) use the order in which the second occurrence appears. Fixed the wording. Results for h_dupes from
  runs before this change are not comparable.
- 2026-10-18: h_access did not say whether blank lines count as bad lines (the check expects they do not). Added "空行は数えない". Earlier h_access results are not comparable.
