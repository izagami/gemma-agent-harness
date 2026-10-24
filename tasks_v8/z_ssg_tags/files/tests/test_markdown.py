import unittest

from ssg.markdown import render


class MarkdownTest(unittest.TestCase):
    def test_blocks(self):
        self.assertEqual(render("# T\n\na *b*\nc\n\n- x\n- [y](http://e.x)\n"),
                         '<h1>T</h1>\n<p>a <em>b</em> c</p>\n<ul>\n<li>x</li>\n<li><a href="http://e.x">y</a></li>\n</ul>')

    def test_code(self):
        self.assertEqual(render("```\n<a>\n```"), "<pre><code>&lt;a&gt;</code></pre>")
        self.assertEqual(render("use `<b>` **now**"), "<p>use <code>&lt;b&gt;</code> <strong>now</strong></p>")


if __name__ == "__main__":
    unittest.main()
