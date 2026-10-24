import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data"))
import make_db
from tt import repo


class TestRepo(unittest.TestCase):
    def setUp(self):
        self.con = make_db.build(":memory:")

    def tearDown(self):
        self.con.close()

    def test_summary(self):
        self.assertEqual(repo.project_summary(self.con), [
            {"id": 1, "name": "Alpha", "entries": 3, "minutes": 90, "amount_yen": 9000},
            {"id": 2, "name": "Beta", "entries": 1, "minutes": 45, "amount_yen": None}])

    def test_search(self):
        self.assertEqual(repo.search_entries(self.con, "meeting"), [1])

    def test_page(self):
        ids, cur = repo.entries_page(self.con, "ann", 2)
        self.assertEqual(ids, [4, 3])
        self.assertIsNotNone(cur)

    def test_report(self):
        r = repo.user_report(self.con, "bob")
        self.assertEqual([(x["project"], x["minutes"]) for x in r], [("Alpha", 30), ("Old site", 15)])


if __name__ == "__main__":
    unittest.main()
