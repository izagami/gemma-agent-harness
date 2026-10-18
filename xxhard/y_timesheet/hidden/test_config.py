import unittest

from ts.config import parse
from ts.errors import ConfigError


class ConfigTest(unittest.TestCase):
    def test_sections_and_override(self):
        c = parse('# c\ndata = a.tsv\n; c\n[project.alpha]\nrate = 6000\nname = "Alpha Corp"\nrate = 7000\n[x]\n')
        self.assertEqual(c.get("data"), "a.tsv")
        self.assertEqual(c.section("project.alpha"), {"rate": "7000", "name": "Alpha Corp"})
        self.assertEqual(c.get("rate", section="project.alpha"), "7000")

    def test_errors(self):
        for text, msg in [("[]\n", "line 1: bad section header"), ("a = 1\nbogus\n", "line 2: expected key = value"),
                          ("\n = 3\n", "line 2: empty key")]:
            with self.assertRaises(ConfigError) as cm:
                parse(text)
            self.assertEqual(str(cm.exception), msg)
