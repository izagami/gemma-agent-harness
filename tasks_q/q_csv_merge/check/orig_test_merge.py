import os
import tempfile
import unittest

from csvmerge.merge import merge
from csvmerge.reader import read_table, write_table


def _write(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return p


class MergeTest(unittest.TestCase):
    def test_spec_example(self):
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.csv", "id,name\n1,Ann\n2,Bob\n")
            b = _write(d, "b.csv", "id,city\n2,Kyoto\n3,Nara\n")
            cols, rows = merge([read_table(a), read_table(b)])
            out = os.path.join(d, "out.csv")
            write_table(out, cols, rows)
            with open(out, encoding="utf-8") as f:
                self.assertEqual(f.read(), "id,name,city\n1,Ann,\n2,Bob,Kyoto\n3,,Nara\n")

    def test_later_file_wins(self):
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.csv", "id,name\n1,Ann\n")
            b = _write(d, "b.csv", "id,name\n1,Anne\n")
            cols, rows = merge([read_table(a), read_table(b)])
            self.assertEqual(rows, [{"id": "1", "name": "Anne"}])

    def test_rows_without_id_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.csv", "id,name\n,Nobody\n7,Gin\n")
            cols, rows = merge([read_table(a)])
            self.assertEqual([r["id"] for r in rows], ["7"])

    def test_case_insensitive_header(self):
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.csv", "ID,NAME\n1,Ann\n")
            self.assertEqual(read_table(a)[0], ["id", "name"])


if __name__ == "__main__":
    unittest.main()
