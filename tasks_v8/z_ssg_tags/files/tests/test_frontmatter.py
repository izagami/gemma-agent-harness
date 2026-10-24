import unittest

from ssg.frontmatter import FrontMatterError, parse


class FrontMatterTest(unittest.TestCase):
    def test_basic(self):
        meta, body = parse("---\nTitle: Hi\ndate: 2026-01-02\ntags: a, b ,, c\n---\nbody\n")
        self.assertEqual(meta, {"title": "Hi", "date": "2026-01-02", "tags": ["a", "b", "c"], "draft": False})
        self.assertEqual(body, "body\n")

    def test_brackets_and_draft(self):
        meta, _ = parse("---\ntags: [x, y]\ndraft: yes\n---\n")
        self.assertEqual((meta["tags"], meta["draft"]), (["x", "y"], True))

    def test_no_front_matter(self):
        self.assertEqual(parse("just text"), ({}, "just text"))

    def test_errors(self):
        with self.assertRaises(FrontMatterError):
            parse("---\ntitle: x\n")
        with self.assertRaises(FrontMatterError):
            parse("---\ndraft: maybe\n---\n")


if __name__ == "__main__":
    unittest.main()
