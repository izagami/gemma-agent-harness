import os, sqlite3, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "data"))
import make_v1


class TestMigrate(unittest.TestCase):
    def test_sample(self):
        db = os.path.join(tempfile.mkdtemp(), "c.db")
        make_v1.build(db)
        r = subprocess.run([sys.executable, "-m", "crm.migrate", db], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        con = sqlite3.connect(db)
        self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0], 3)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM notes").fetchone()[0], 3)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM tags").fetchone()[0], 2)
        con.close()


if __name__ == "__main__":
    unittest.main()
