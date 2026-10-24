import os
import tempfile
import unittest

from salesrep.config import load_config, split_list

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigTest(unittest.TestCase):
    def test_split_list(self):
        self.assertEqual(split_list("A, B,\n  C # comment\n# only comment\nD"), ["A", "B", "C", "D"])

    def test_regions_loaded(self):
        cfg = load_config(os.path.join(HERE, "config"))
        self.assertEqual(sorted(cfg.regions), ["chubu", "kansai", "kanto"])
        self.assertEqual(cfg.regions["kanto"].label, "関東")
        self.assertIn("T01", cfg.regions["kanto"].stores)

    def test_override_order(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "regions.d"))
        with open(os.path.join(d, "base.ini"), "w") as f:
            f.write("[report]\ntitle = base\ncolumn_width = 9\n")
        with open(os.path.join(d, "regions.d", "b.ini"), "w") as f:
            f.write("[report]\ntitle = from b\n[region:x]\nstores = X1\n")
        cfg = load_config(d)
        self.assertEqual((cfg.title, cfg.column_width, cfg.regions["x"].stores), ("from b", 9, ["X1"]))
