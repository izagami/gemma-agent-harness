import unittest

from custimport import sniff


class SniffTest(unittest.TestCase):
    def test_ascii_is_utf8(self):
        self.assertEqual(sniff.detect_encoding(b"id,name\n1,Tom\n"), "utf-8")

    def test_utf8_japanese(self):
        data = "id,name\n1,山田 太郎\n".encode("utf-8")
        self.assertEqual(sniff.decode(data), ("id,name\n1,山田 太郎\n", "utf-8"))

    def test_cp932(self):
        data = "顧客番号,氏名\n1,佐藤 花子\n".encode("cp932")
        text, enc = sniff.decode(data)
        self.assertEqual(enc, "cp932")
        self.assertEqual(text, "顧客番号,氏名\n1,佐藤 花子\n")


if __name__ == "__main__":
    unittest.main()
