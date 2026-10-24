# Invoice format

```
INVOICE <customer> <name>
period <start>..<end> (<N> days)
- <plan code> <start>..<end> <days>d <amount>
TOTAL <sum of amounts> JPY
```

* Dates are `YYYY-MM-DD`; all ranges are inclusive (`2026-03-10..2026-04-09` is 31 days).
* One `-` line per plan used in the period, in date order.
* Amounts are whole yen with `,` thousands separators.

## Periods

Period k of a subscription starts on the date k months after the contract start
(clamped to the last day of the month when that month is shorter) and ends the day
before period k+1 starts.  E.g. start 2026-01-31: 2026-01-31..2026-02-27,
2026-02-28..2026-03-30, 2026-03-31..2026-04-29, 2026-04-30..2026-05-30, ...

## Plan changes

If the plan changes on day c inside a period, the old plan is billed for start..c-1
and the new plan for c..end.  Each line is `monthly * line days / period days`,
rounded to whole yen (0.5 rounds up).  A line covering the whole period is exactly
the monthly price.
