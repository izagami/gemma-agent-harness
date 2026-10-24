import os, sqlite3, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data"))
import make_db
from shop import repo


class TestRepo(unittest.TestCase):
    def setUp(self):
        self.con = make_db.build(":memory:")

    def tearDown(self):
        self.con.close()

    def test_list_customers(self):
        self.assertEqual([c["name"] for c in repo.list_customers(self.con)], ["Aoki", "Baba", "Chiba"])

    def test_find(self):
        self.assertEqual(repo.find_customer(self.con, "Baba")["city"], "Osaka")
        self.assertIsNone(repo.find_customer(self.con, "Nobody"))

    def test_search(self):
        self.assertEqual(repo.search_products(self.con, "N"), ["ink", "notebook", "pen"])

    def test_orders(self):
        o = repo.orders_with_items(self.con, 1)
        self.assertEqual([x["total"] for x in o], [540, 2500])

    def test_page(self):
        names, cur = repo.products_page(self.con, 2)
        self.assertEqual(names, ["bag", "notebook"])


if __name__ == "__main__":
    unittest.main()
