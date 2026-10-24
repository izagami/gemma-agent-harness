import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

from tool.cli import main


def wr(p, data):
    with open(p, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)


def rd(p):
    with open(p) as f:
        return f.read()


def run(*argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    clean = {k: v for k, v in os.environ.items() if not k.startswith("TOOL_")}
    clean.update(env or {})
    with mock.patch.dict(os.environ, clean, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ToolTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = os.path.join(self.d, "src")
        for rel, size in [("a.py", 10), ("b.py", 2000), ("docs/readme.md", 5000), ("docs/.hidden", 7), ("big.bin", 9000)]:
            p = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            wr(p, b"x" * size)
        self.ini = os.path.join(self.d, "t.ini")

    def tearDown(self):
        shutil.rmtree(self.d)

    def write_ini(self, text):
        wr(self.ini, text)

    def test_scan_defaults(self):
        code, out, err = run("--config", self.ini if os.path.exists(self.ini) else os.devnull, "scan", self.root)
        self.assertEqual(code, 0)
        self.assertEqual(out.split(), ["10", "a.py", "2000", "b.py", "9000", "big.bin", "5000", "docs/readme.md"])

    def test_exclude_and_max_size(self):
        self.write_ini("[backup]\nexclude = *.bin, ,docs/*\nmax_size = 1_999\n")
        self.assertEqual(run("--config", self.ini, "scan", self.root)[1].split(), ["10", "a.py"])

    def test_report_iec(self):
        self.write_ini("[report]\ntop = 2\n")
        code, out, _ = run("--config", self.ini, "report", self.root)
        self.assertEqual(out, "Report: 4 files, 15.6 KiB\n"
                              "  .bin          1     8.8 KiB\n"
                              "  .md           1     4.9 KiB\n"
                              "  (other)       2     2.0 KiB\n")

    def test_env_overrides_file_and_set_overrides_env(self):
        self.write_ini('[report]\nunits = "si"\ntitle = From file\n')
        code, out, _ = run("--config", self.ini, "--set", "report.title=From set", "report", self.root,
                           env={"TOOL_REPORT__UNITS": "b", "TOOL_REPORT__TITLE": "From env"})
        self.assertTrue(out.startswith("From set: 4 files, 16010 B\n"), out)

    def test_empty_env_removes(self):
        self.write_ini("[report]\nunits = b\n")
        out = run("--config", self.ini, "report", self.root, env={"TOOL_REPORT__UNITS": ""})[1]
        self.assertTrue(out.startswith("Report: 4 files, 15.6 KiB"), out)

    def test_backup_manifest(self):
        self.write_ini("[DEFAULT]\nchecksums = off\n[backup]\nname = nightly\norder = size\n")
        outdir = os.path.join(self.d, "out")
        code, out, _ = run("--config", self.ini, "backup", self.root, outdir)
        self.assertEqual(out, f"wrote {outdir}/nightly.manifest (4 files)\n")
        self.assertEqual(rd(os.path.join(outdir, "nightly.manifest")).splitlines()[:3],
                         ["# manifest nightly files=4 bytes=16010", "-  9000  big.bin", "-  5000  docs/readme.md"])

    def test_errors(self):
        self.write_ini("[report]\ntop = many\n")
        self.assertEqual(run("--config", self.ini, "report", self.root)[::2],
                         (2, "error: setting report.top: not an integer: 'many'\n"))
        self.assertEqual(run("--config", os.path.join(self.d, "nope.ini"), "show-config")[::2],
                         (2, f"error: config file not found: {self.d}/nope.ini\n"))
        self.assertEqual(run("--set", "oops", "show-config")[::2], (2, "error: --set expects KEY=VALUE\n"))

    def test_verbose_and_show_config(self):
        self.write_ini("[general]\nverbose = Yes\n[backup]\nexclude = *.bin\n")
        code, out, err = run("--config", self.ini, "--set", "x.y=1", "show-config", env={"TOOL_A_B__C_D": " v "})
        self.assertEqual(out, "a_b.c_d = v\nbackup.exclude = *.bin\ngeneral.verbose = Yes\nx.y = 1\n")
        code, out, err = run("--config", self.ini, "scan", self.root)
        self.assertIn("[tool] skip big.bin\n", err)
        self.assertTrue(err.endswith("[tool] done\n"))


if __name__ == "__main__":
    unittest.main()
