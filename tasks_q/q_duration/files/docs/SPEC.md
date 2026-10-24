# durfmt

Durations are written as groups `<number><unit>`, units `d` (86400 s), `h` (3600 s), `m` (60 s), `s` (1 s).

## parse_duration(text) / `python3 -m durfmt parse TEXT` -> whole seconds
* `<number>` is digits with an optional fraction (`1`, `90`, `1.5`, `0.25`); no sign, no exponent.
* Units are lower case. Each unit may appear at most once and units must come largest first
  (`2d4h`, `1h30m`, `90s`; `30m1h` and `1h1h` are errors).
* Spaces (and tabs) are allowed anywhere between the parts: before/after the text, between groups and
  between a number and its unit (`1h30m`, `1h 30m`, ` 1 h 30 m `).
* The total must be a whole number of seconds (`1.5h` = 5400, `0.5m` = 30, `1.5s` is an error).
  Compute exactly (no floating-point rounding): `0.1h` = 360.
* Errors (`ValueError`, exact messages; the CLI prints `error: <message>` to stderr, exit code 2):
  * only spaces or nothing: `empty duration`
  * anything that does not match the syntax: `invalid duration: '<text>'` (the original text, Python repr)
  * a unit repeated or out of order: `unit out of order: <unit>` (the first offending unit)
  * not whole seconds: `not a whole number of seconds`

## format_duration(seconds) / `python3 -m durfmt format SECONDS`
* Largest units first, units with a zero count are left out, no spaces: `5430` -> `1h30m30s`,
  `3600` -> `1h`, `86460` -> `1d1m`. `0` -> `0s`. Negative: `ValueError("negative duration")`.
* Round trip: `parse_duration(format_duration(n)) == n` for every n >= 0.
