import io
import os
import shutil
import sqlite3
import tempfile
import unittest

from notes.cli import main


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "t.db")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = main(["--db", self.db, *argv], out, err)
        return code, out.getvalue(), err.getvalue()

    def test_init_and_add(self):
        self.assertEqual(self.run_cli("init"), (0, f"initialized {self.db}\n", ""))
        self.assertEqual(self.run_cli("add", "buy milk", "--tag", "Home", "--date", "2026-01-02")[:2], (0, "added 1\n"))
        self.assertEqual(self.run_cli("add", "call bob")[1], "added 2\n")
        code, out, _ = self.run_cli("list")
        self.assertEqual(out, "   1  2026-01-02  buy milk [home]\n   2  1970-01-01  call bob\n")
        self.assertEqual(self.run_cli("list", "--tag", "HOME")[1], "   1  2026-01-02  buy milk [home]\n")

    def test_init_twice_keeps_data(self):
        self.run_cli("init")
        self.run_cli("add", "x")
        self.assertEqual(self.run_cli("init")[0], 0)
        self.assertEqual(self.run_cli("list")[1], "   1  1970-01-01  x\n")

    def test_needs_init(self):
        code, out, err = self.run_cli("list")
        self.assertEqual(code, 1)
        self.assertIn("run init first", err)

    def test_show_delete(self):
        self.run_cli("init")
        self.run_cli("add", "t", "--body", "hello")
        self.assertEqual(self.run_cli("show", "1")[1], "   1  1970-01-01  t\n\nhello\n")
        self.assertEqual(self.run_cli("delete", "1")[1], "deleted 1\n")
        self.assertEqual(self.run_cli("show", "1")[:3], (1, "", "error: note 1 not found\n"))

    def test_empty_title(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli("add", "  ")[2], "error: title must not be empty\n")

    def test_tag_cascade(self):
        self.run_cli("init")
        self.run_cli("add", "t", "--tag", "a")
        self.run_cli("delete", "1")
        con = sqlite3.connect(self.db)
        self.assertEqual(con.execute("SELECT count(*) FROM tags").fetchone()[0], 0)
        con.close()


if __name__ == "__main__":
    unittest.main()
