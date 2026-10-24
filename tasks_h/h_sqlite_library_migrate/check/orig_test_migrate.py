import os, sqlite3, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "data"))
import make_v1


class TestMigrate(unittest.TestCase):
    def test_sample(self):
        db = os.path.join(tempfile.mkdtemp(), "lib.db")
        make_v1.build(db)
        r = subprocess.run([sys.executable, "-m", "biblio.migrate", db], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "migrated to v2: 3 books, 3 members, 4 loans")
        con = sqlite3.connect(db)
        self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertEqual(con.execute("SELECT code FROM members ORDER BY id").fetchall(),
                         [("M-0001",), ("M-0002",), ("M-0003",)])
        self.assertEqual(con.execute("SELECT loaned_at, fine_yen FROM loans WHERE id = 3").fetchone(),
                         ("2026-03-10T06:30:00Z", 300))
        con.close()


if __name__ == "__main__":
    unittest.main()
