import os
import shutil
import tempfile
import unittest

from ssg import site

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "example")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out)

    def read(self, rel):
        with open(os.path.join(self.out, rel), encoding="utf-8") as f:
            return f.read()

    def test_index_order_and_drafts(self):
        site.build(EXAMPLE, self.out)
        idx = self.read("index.html")
        order = [s for s in ["py-typing", "py-dataclasses", "kyoto", "hello"]]
        pos = [idx.index(f'href="posts/{s}.html"') for s in order]
        self.assertEqual(pos, sorted(pos))
        self.assertNotIn("wip", idx)
        self.assertFalse(os.path.exists(os.path.join(self.out, "posts", "wip.html")))
        self.assertTrue(os.path.exists(os.path.join(self.out, "style.css")))

    def test_post_page(self):
        site.build(EXAMPLE, self.out)
        p = self.read("posts/kyoto.html")
        self.assertIn("<title>冬の京都 - 小さなノート</title>", p)
        self.assertIn('<link rel="stylesheet" href="../style.css">', p)
        self.assertIn("<p>雪の金閣寺を見に行った。</p>", p)

    def test_rebuild_writes_nothing(self):
        self.assertGreater(site.build(EXAMPLE, self.out), 0)
        self.assertEqual(site.build(EXAMPLE, self.out), 0)


if __name__ == "__main__":
    unittest.main()
