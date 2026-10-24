import unittest

from jwrap.width import text_width
from jwrap.wrap import wrap


class TestWidth(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(text_width("abc"), 3)

    def test_kana(self):
        self.assertEqual(text_width("あいう"), 6)


class TestWrap(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(wrap("abcdefghij", 4), ["abcd", "efgh", "ij"])

    def test_kana(self):
        self.assertEqual(wrap("あいうえおかき", 6), ["あいう", "えおか", "き"])

    def test_paragraphs(self):
        self.assertEqual(wrap("ab\n\ncd", 5), ["ab", "", "cd"])

    def test_kuten_hangs(self):
        self.assertEqual(wrap("あいう。えお", 6), ["あいう。", "えお"])

    def test_width_error(self):
        with self.assertRaises(ValueError):
            wrap("abc", 1)


if __name__ == "__main__":
    unittest.main()
