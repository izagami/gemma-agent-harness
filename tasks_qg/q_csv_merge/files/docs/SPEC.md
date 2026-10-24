# csvmerge

`python3 -m csvmerge OUT.csv IN1.csv [IN2.csv ...]` merges CSV exports into one table and prints
`merged <N> rows from <M> files -> OUT.csv`.

## Input
* UTF-8, with or without a BOM (Excel writes one). Line ends may be `\n` or `\r\n`.
* Standard CSV quoting: a quoted field may contain `,`, `"` (written `""`) and line breaks.
* The first record is the header. Header names are matched case-insensitively after stripping
  surrounding spaces: ` Name `, `NAME` and `name` are the same column, written as `name`.
* Rows shorter than the header are padded with empty fields. Empty lines between records are ignored.

## Merging
* The key column is `id`. Rows with an empty `id` are ignored.
* Columns: the normalised names in first-seen order (all columns of IN1, then new ones of IN2, ...).
* Rows: one per `id`, in order of first appearance.
* Files are applied in command-line order (a repeated `id` inside one file is applied in row order).
  A later value replaces an earlier one only if it is non-empty: an empty field never erases data.
* Missing values are written as empty fields.

## Output
UTF-8 without BOM, `\n` line ends, minimal quoting (Python `csv` defaults).

Example: `a.csv` = `id,name\n1,Ann\n2,Bob` and `b.csv` = `ID, City \n2,Kyoto\n3,Nara`
give `id,name,city\n1,Ann,\n2,Bob,Kyoto\n3,,Nara\n`.
