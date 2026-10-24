import os
import unittest

from docrender import render
from docrender.context import slugify

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


class BlocksTest(unittest.TestCase):
    def test_paragraph_and_inline(self):
        self.assertEqual(render("Hello **big**\n*world* & `<x>`\n"),
                         "<article>\n<p>Hello <strong>big</strong> <em>world</em> &amp; <code>&lt;x&gt;</code></p>\n</article>\n")

    def test_lists_and_code(self):
        self.assertEqual(render("- a\n- b [x](http://e/x)\n\n1. one\n\n```py\nif a < b:\n```\n---\n"),
                         "<article>\n<ul>\n<li>a</li>\n<li>b <a href=\"http://e/x\">x</a></li>\n</ul>\n"
                         "<ol>\n<li>one</li>\n</ol>\n<pre><code class=\"lang-py\">if a &lt; b:</code></pre>\n<hr>\n</article>\n")

    def test_slugify(self):
        self.assertEqual(slugify("Getting Started!"), "getting-started")
        self.assertEqual(slugify("手順 1"), "手順-1")


class DocumentTest(unittest.TestCase):
    def test_onboarding(self):
        with open(os.path.join(EX, "onboarding.txt"), encoding="utf-8") as f:
            html = render(f.read())
        with open(os.path.join(os.path.dirname(__file__), "onboarding.html"), encoding="utf-8") as f:
            self.assertEqual(html, f.read())
