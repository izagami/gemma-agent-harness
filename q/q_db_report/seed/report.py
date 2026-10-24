"""Run one report: python3 report.py DB NAME  -> CSV on stdout (header = column names).

NAME is a file queries/NAME.sql holding exactly one SELECT statement (see docs/REPORTS.md)."""
import csv, os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(db, name):
    with open(os.path.join(HERE, "queries", name + ".sql"), encoding="utf-8") as f:
        sql = f.read()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.execute(sql)
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        con.close()


def main(argv):
    if len(argv) != 2:
        print("usage: python3 report.py DB NAME", file=sys.stderr)
        return 2
    cols, rows = run(*argv)
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(cols)
    w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
