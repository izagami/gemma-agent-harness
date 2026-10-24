import os
import tempfile
import unittest

from tests.test_cli import SAMPLE, run


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "e.json")
        run("--db", self.db, "import", SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_text(self):
        code, out, _ = run("--db", self.db, "report", "--month", "2026-09")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "Report 2026-09 (by category)")
        self.assertEqual(out.splitlines()[-1], "TOTAL           10,398  (6)")

    def test_invalid_month(self):
        self.assertEqual(run("--db", self.db, "report", "--month", "2026-13"), (2, "", "error: invalid month: 2026-13\n"))

    def test_reimport(self):
        self.assertEqual(run("--db", self.db, "import", SAMPLE)[1], "imported 0, skipped 7\n")
