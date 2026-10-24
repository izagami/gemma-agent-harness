import contextlib
import io
import json
import os
import tempfile
import unittest

from exp.cli import main

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "data", "sample.csv")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "e.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_and_list(self):
        self.assertEqual(run("--db", self.db, "add", "2026-09-02", "1,200", " Food ", "--note", "x")[:2], (0, "added #1\n"))
        self.assertEqual(run("--db", self.db, "add", "2026-09-01", "3.50", "books", "--currency", "usd")[1], "added #2\n")
        code, out, _ = run("--db", self.db, "list")
        self.assertEqual(out.splitlines(), ["   2  2026-09-01        3.50 USD  books",
                                            "   1  2026-09-02        1200 JPY  food         x"])

    def test_validation(self):
        code, out, err = run("--db", self.db, "add", "2026-02-30", "10", "food")
        self.assertEqual((code, out, err), (1, "", "error: invalid date: 2026-02-30\n"))
        self.assertEqual(run("--db", self.db, "add", "2026-02-03", "-1", "food")[2], "error: invalid amount: -1\n")
        self.assertFalse(os.path.exists(self.db))

    def test_import_and_month_filter(self):
        self.assertEqual(run("--db", self.db, "import", SAMPLE)[:2], (0, "imported 7\n"))
        _, out, _ = run("--db", self.db, "list", "--month", "2026-09", "--category", "food")
        self.assertEqual(len(out.splitlines()), 4)
        with open(self.db) as f:
            self.assertEqual(json.load(f)["next_id"], 8)

    def test_env_db(self):
        os.environ["EXP_DB"] = self.db
        try:
            run("add", "2026-09-02", "5", "misc")
        finally:
            del os.environ["EXP_DB"]
        self.assertTrue(os.path.exists(self.db))
