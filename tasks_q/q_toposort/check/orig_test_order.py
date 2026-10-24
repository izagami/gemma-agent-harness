import os
import subprocess
import sys
import tempfile
import unittest

from buildorder.graph import parse
from buildorder.order import CycleError, build_order


class OrderTest(unittest.TestCase):
    def test_chain(self):
        g = parse("c: b\nb: a\na:\n")
        self.assertEqual(build_order(g), ["a", "b", "c"])

    def test_spec_example(self):
        g = parse("app: lib util\nlib: base\nutil: base\n")
        self.assertEqual(build_order(g), ["base", "lib", "util", "app"])

    def test_comments(self):
        g = parse("# x\n\nb: a  # needs a\n")
        self.assertEqual(build_order(g), ["a", "b"])

    def test_cycle_detected(self):
        with self.assertRaises(CycleError):
            build_order(parse("a: b\nb: a\n"))

    def test_cli_exit_codes(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.deps")
        with open(p, "w") as f:
            f.write("a: b\nb: a\n")
        r = subprocess.run([sys.executable, "-m", "buildorder", p], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        r = subprocess.run([sys.executable, "-m", "buildorder", p, "zzz"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
