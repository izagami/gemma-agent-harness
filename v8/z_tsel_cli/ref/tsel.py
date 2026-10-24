#!/usr/bin/env python3
"""tsel: select columns and filter rows of TSV/CSV files."""
import csv
import getopt
import io
import re
import sys

USAGE = """usage: tsel.py [-d C] [-H] [-f LIST] [-w EXPR ...] [-n] [FILE ...]
  -d, --delimiter C   field delimiter (default: tab; ',' uses CSV quoting)
  -H, --no-header     input has no header line
  -f, --fields LIST   columns to output: names, 1-based numbers, ranges N-M
  -w, --where EXPR    COL=VAL, COL!=VAL or COL~RE (repeatable, AND)
  -n, --count         print the number of matching rows only
  -h, --help          show this help
"""


class Fail(Exception):
    pass


def read_rows(data, delim):
    text = data.decode("utf-8")
    if text.startswith("﻿"):
        text = text[1:]
    if delim == ",":
        return [r for r in csv.reader(io.StringIO(text, newline=""))]
    rows = []
    for line in text.split("\n"):
        rows.append(line[:-1].split(delim) if line.endswith("\r") else line.split(delim))
    if text.endswith("\n") or text == "":
        rows.pop()
    return rows


def resolve(item, header, ncols, allow_range=True):
    if re.fullmatch(r"\d+", item):
        n = int(item)
        if ncols is not None and not 1 <= n <= ncols:
            raise Fail(f"field index out of range: {item}")
        return [n - 1]
    m = re.fullmatch(r"(\d+)-(\d+)", item) if allow_range else None
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            raise Fail(f"invalid range: {item}")
        for n in (a, b):
            if ncols is not None and not 1 <= n <= ncols:
                raise Fail(f"field index out of range: {n}")
        return list(range(a - 1, b))
    if header is None:
        raise Fail(f"field names require a header: {item}")
    if item not in header:
        raise Fail(f"unknown field: {item}")
    return [header.index(item)]


def parse_expr(e):
    for i, ch in enumerate(e):
        if e.startswith("!=", i):
            col, op, val = e[:i], "!=", e[i + 2:]
            break
        if ch in "=~":
            col, op, val = e[:i], ch, e[i + 1:]
            break
    else:
        raise Fail(f"invalid expression: {e}")
    if not col:
        raise Fail(f"invalid expression: {e}")
    if op == "~":
        try:
            val = re.compile(val)
        except re.error:
            raise Fail(f"invalid regex: {e[len(col) + 1:]}")
    return col, op, val


def run(argv, stdin):
    try:
        opts, files = getopt.gnu_getopt(argv, "d:Hf:w:nh",
                                        ["delimiter=", "no-header", "fields=", "where=", "count", "help"])
    except getopt.GetoptError as e:
        name = ("-" if len(e.opt) == 1 else "--") + e.opt
        raise Fail(("option requires an argument: " if "requires argument" in e.msg else "unknown option: ") + name)
    delim, header_mode, fields, wheres, count = "\t", True, None, [], False
    for o, a in opts:
        if o in ("-h", "--help"):
            return USAGE, 0
        if o in ("-d", "--delimiter"):
            if len(a) != 1:
                raise Fail("delimiter must be a single character")
            delim = a
        elif o in ("-H", "--no-header"):
            header_mode = False
        elif o in ("-f", "--fields"):
            fields = a
        elif o in ("-w", "--where"):
            wheres.append(a)
        elif o in ("-n", "--count"):
            count = True
    exprs = [parse_expr(w) for w in wheres]
    files = files or ["-"]
    header, data = None, []
    for f in files:
        if f == "-":
            raw = stdin.read()
        else:
            try:
                with open(f, "rb") as fh:
                    raw = fh.read()
            except OSError:
                raise Fail(f"cannot open: {f}")
        rows = read_rows(raw, delim)
        if header_mode and rows:
            h, rows = rows[0], rows[1:]
            if header is None:
                header = h
            elif h != header:
                raise Fail(f"header mismatch: {f}")
        data.extend(rows)
    if header_mode:
        ncols = len(header) if header is not None else None
    else:
        ncols = len(data[0]) if data else None
    hdr = header if header_mode else None
    if header_mode and header is None:  # empty input: nothing to check against
        return "", 1
    idx = list(range(ncols or 0)) if fields is None else \
        [i for item in fields.split(",") for i in resolve(item, hdr, ncols)]
    conds = [(resolve(c, hdr, ncols, False)[0], op, v) for c, op, v in exprs]

    def get(r, i):
        return r[i] if i < len(r) else ""

    def ok(r):
        for i, op, v in conds:
            x = get(r, i)
            if op == "=" and x != v or op == "!=" and x == v or op == "~" and not v.search(x):
                return False
        return True

    if fields is None and not header_mode:
        idx = None
    out_rows = [r for r in data if ok(r)]
    code = 0 if out_rows else 1
    if count:
        return f"{len(out_rows)}\n", code
    sel = (lambda r: r if idx is None else [get(r, i) for i in idx])
    lines = ([[get(header, i) for i in idx]] if header_mode else []) + [sel(r) for r in out_rows]
    buf = io.StringIO()
    if delim == ",":
        csv.writer(buf, lineterminator="\n").writerows(lines)
    else:
        for l in lines:
            buf.write(delim.join(l) + "\n")
    return buf.getvalue(), code


def main():
    try:
        out, code = run(sys.argv[1:], sys.stdin.buffer)
    except Fail as e:
        sys.stderr.write(f"tsel: error: {e}\n")
        sys.exit(2)
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.exit(code)


if __name__ == "__main__":
    main()
