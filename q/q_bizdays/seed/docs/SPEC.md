# bizcal

The office is closed on Saturdays, Sundays and on every date listed in `data/holidays.txt`
(`YYYY-MM-DD name` per line, `#` starts a comment). Every other day is a business day.
A holiday that falls on a Saturday or Sunday changes nothing: there are no substitute days
unless the file lists them, and the file is the only source of holidays (all years in it apply).

## add_business_days(cal, start, n) / `python3 -m bizcal add START N`
* n > 0: step forward one day at a time from `start`; the n-th business day reached is the result.
  `start` itself is never counted, even when it is a business day.
* n < 0: the same, backwards (the |n|-th business day before `start`).
* n = 0: `start` if it is a business day, otherwise the next business day after it.
* The CLI prints the date as `YYYY-MM-DD`.

## count_business_days(cal, first, last) / `python3 -m bizcal count FIRST LAST`
* The number of business days d with first <= d <= last (both ends included).
* first > last raises `ValueError("first is after last")`; the CLI prints `error: first is after last`
  to stderr and exits with code 2 (the same for any invalid argument).

## Examples (with data/holidays.txt)
* `add 2026-04-28 3` -> `2026-05-07` (04-29 and 05-04..05-06 are holidays, 05-02/03 a weekend)
* `add 2026-05-11 -1` -> `2026-05-08`
* `count 2026-05-01 2026-05-08` -> `3`
