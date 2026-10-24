import unittest

from feed.paginate import page


def mk(i, t, author="a", deleted=False):
    return {"id": i, "created_at": t, "author": author, "title": str(i), "deleted": deleted}


POSTS = [mk(1, "2026-01-01T00:00:00"), mk(2, "2026-01-02T00:00:00"), mk(3, "2026-01-03T00:00:00"),
         mk(4, "2026-01-04T00:00:00"), mk(5, "2026-01-05T00:00:00")]


class PageTest(unittest.TestCase):
    def test_first_page(self):
        r = page(POSTS, limit=2)
        self.assertEqual([p["id"] for p in r["items"]], [5, 4])
        self.assertIsNotNone(r["next"])

    def test_second_page(self):
        r = page(POSTS, limit=2, cursor=page(POSTS, limit=2)["next"])
        self.assertEqual([p["id"] for p in r["items"]], [3, 2])

    def test_last_short_page(self):
        r = page(POSTS, limit=3)
        r = page(POSTS, limit=3, cursor=r["next"])
        self.assertEqual([p["id"] for p in r["items"]], [2, 1])
        self.assertIsNone(r["next"])

    def test_limit(self):
        with self.assertRaises(ValueError):
            page(POSTS, limit=0)

    def test_bad_cursor(self):
        with self.assertRaises(ValueError):
            page(POSTS, cursor="!!!")


if __name__ == "__main__":
    unittest.main()
