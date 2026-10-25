import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.data = os.path.join(self.d, "inv.csv")
        shutil.copy(os.path.join(ROOT, "data", "inventory.csv"), self.data)
        shutil.copy(os.path.join(ROOT, "data", "inventory.csv.history"), self.data + ".history")

    def tearDown(self):
        shutil.rmtree(self.d)

    def run_cli(self, *args):
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, "-m", "invtool", "--data", self.data, *args],
                           capture_output=True, text=True, env=env, cwd=self.d)
        return r.returncode, r.stdout, r.stderr

    def test_help_lists_commands_alphabetically(self):
        code, out, _ = self.run_cli("help")
        names = [l.split()[0] for l in out.splitlines() if l.startswith("  ")]
        self.assertEqual(names, sorted(names))
        self.assertIn("adjust", names)

    def test_show(self):
        code, out, _ = self.run_cli("show", "b-200")
        self.assertEqual(out, "sku:      B-200\nname:     A4ノート\nqty:      40\nprice:    150.50\n"
                              "value:    6,020.00\nlocation: SHELF2\n")

    def test_add_and_list(self):
        self.assertEqual(self.run_cli("add", "z-1", "テープ", "7", "99.9", "--location", "back")[1],
                         "added Z-1 (7 x 99.90) at BACK\n")
        code, out, _ = self.run_cli("list", "--location", "BACK", "--sort", "value")
        self.assertEqual(out.splitlines()[-1], "2 item(s)")
        self.assertTrue(out.splitlines()[1].startswith("E-500"))

    def test_adjust_history(self):
        code, out, err = self.run_cli("adjust", "A-101", "-2", "--reason", "sold")
        self.assertEqual((code, out, err), (0, "A-101: 3 -> 1\n", "warning: A-101 is low on stock (1)\n"))
        self.assertEqual(self.run_cli("history", "a-101", "--limit", "2")[1], "#3        -2  sold\n#4        -2  sold\n")

    def test_errors(self):
        self.assertEqual(self.run_cli("show", "NOPE"), (1, "", "error: unknown SKU NOPE\n"))
        self.assertEqual(self.run_cli("frobnicate"), (2, "", "error: unknown command 'frobnicate' (try: invtool help)\n"))
        self.assertEqual(self.run_cli("move", "A-100"), (2, "", "error: usage: invtool move SKU LOCATION\n"))
        self.assertEqual(self.run_cli("remove", "A-100")[2], "error: A-100 still has 120 in stock (use --force)\n")

    def test_value(self):
        self.assertEqual(self.run_cli("value")[1], "total: 22,970.00 (180 units)\n")

    def test_export_json(self):
        out = self.run_cli("export", "--format=json")[1]
        self.assertIn('"price": 150.5', out)


if __name__ == "__main__":
    unittest.main()
