import os, subprocess, sys, tempfile, unittest

TSEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tsel.py")


def W(p, s):
    with open(p, "w") as f:
        f.write(s)


def run(*args, stdin=b""):
    r = subprocess.run([sys.executable, TSEL, *args], input=stdin, capture_output=True)
    return r.returncode, r.stdout.decode(), r.stderr.decode()


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, "a.tsv")
        W(self.f, "id\tname\tcity\n1\tA\tX\n2\tB\tY\n3\tC\tX\n")

    def test_fields_order_dupes(self):
        self.assertEqual(run("-f", "city,id,id", self.f), (0, "city\tid\tid\nX\t1\t1\nY\t2\t2\nX\t3\t3\n", ""))

    def test_range(self):
        self.assertEqual(run("-f2-3", self.f)[1].splitlines()[0], "name\tcity")

    def test_where_and(self):
        self.assertEqual(run("-w", "city=X", "-w", "id!=1", "-f", "id", self.f), (0, "id\n3\n", ""))

    def test_regex(self):
        self.assertEqual(run("--where=name~^[AB]$", "-n", self.f), (0, "2\n", ""))

    def test_no_match(self):
        self.assertEqual(run("-w", "city=Z", self.f), (1, "id\tname\tcity\n", ""))

    def test_stdin(self):
        self.assertEqual(run("-H", "-f", "2", stdin=b"\xef\xbb\xbfa\tb\r\nc\td\r\n"), (0, "b\nd\n", ""))

    def test_csv_quoting(self):
        code, out, _ = run("-d,", "-f", "b", stdin='a,b\n1,"x, ""y"""\n'.encode())
        self.assertEqual(out, 'b\n"x, ""y"""\n')

    def test_multi_files_and_mismatch(self):
        g = os.path.join(self.d, "b.tsv")
        W(g, "id\tname\tcity\n4\tD\tZ\n")
        self.assertEqual(run("-n", self.f, g)[1], "4\n")
        W(g, "id\tname\n4\tD\n")
        self.assertEqual(run(self.f, g), (2, "", f"tsel: error: header mismatch: {g}\n"))

    def test_errors(self):
        self.assertEqual(run("-x", self.f), (2, "", "tsel: error: unknown option: -x\n"))
        self.assertEqual(run(self.f, "-d"), (2, "", "tsel: error: option requires an argument: -d\n"))
        self.assertEqual(run("-f", "zz", self.f), (2, "", "tsel: error: unknown field: zz\n"))
        self.assertEqual(run("-f", "4", self.f), (2, "", "tsel: error: field index out of range: 4\n"))
        self.assertEqual(run("nope.tsv"), (2, "", "tsel: error: cannot open: nope.tsv\n"))


if __name__ == "__main__":
    unittest.main()
