import unittest

from tests.helpers import Workspace


class CliTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_add_list_total(self):
        self.assertEqual(self.ws.run("add", "2026-09-02", "beta", "45m"), (0, "added: 2026-09-02 beta 0:45\n", ""))
        self.ws.run("add", "2026-09-01", "alpha", "1h30m", "design", "review")
        self.ws.run("add", "2026-09-02", "alpha", "1:00")
        code, out, _ = self.ws.run("list")
        self.assertEqual(out, "2026-09-01  alpha  1:30  design review\n2026-09-02  beta  0:45\n2026-09-02  alpha  1:00\n")
        code, out, _ = self.ws.run("total")
        self.assertEqual(out, "alpha  2:30\nbeta  0:45\nTOTAL  3:15\n")
        self.assertEqual(self.ws.run("list", "--project", "zzz")[1], "no entries\n")

    def test_config_data_path(self):
        self.ws.write("conf/my.conf", "data = ../d/work.tsv\n")
        self.ws.write("d/work.tsv", "2026-09-01\talpha\t30\t\n")
        self.assertEqual(self.ws.run("--config", "conf/my.conf", "total")[1], "alpha  0:30\nTOTAL  0:30\n")

    def test_default_config(self):
        self.ws.write("ts.conf", "data = x.tsv\n")
        self.ws.run("add", "2026-09-01", "a", "1h")
        self.assertEqual(self.ws.run("--config", "ts.conf", "list")[1], "2026-09-01  a  1:00\n")

    def test_errors(self):
        self.assertEqual(self.ws.run("add", "2026-13-01", "a", "1h"), (2, "", "error: invalid date: 2026-13-01\n"))
        self.assertEqual(self.ws.run("add", "2026-01-01", "A", "1h"), (2, "", "error: invalid project: A\n"))
        self.assertEqual(self.ws.run("--config", "nope.conf", "list"), (2, "", "error: config: not found: nope.conf\n"))
        self.ws.write("bad.conf", "[a]\nnope\n")
        self.assertEqual(self.ws.run("--config", "bad.conf", "list")[2], "error: config: line 2: expected key = value\n")
        self.ws.write("entries.tsv", "garbage\n")
        self.assertEqual(self.ws.run("list"), (1, "", "error: entries.tsv: line 1: corrupt entry\n"))
