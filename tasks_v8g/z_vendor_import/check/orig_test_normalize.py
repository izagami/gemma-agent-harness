import unittest

from custimport import normalize as n


class NormalizeTest(unittest.TestCase):
    def test_clean_name(self):
        self.assertEqual(n.clean_name("  山田　 太郎 "), "山田 太郎")

    def test_name_key(self):
        self.assertEqual(n.name_key("山田　太郎"), n.name_key("山田太郎"))
        self.assertEqual(n.name_key("Ｊｏｈｎ Smith"), n.name_key("john smith"))

    def test_phone(self):
        self.assertEqual(n.clean_phone("０９０－１２３４－５６７８"), "090-1234-5678")
        self.assertEqual(n.phone_key("+81 90-1234-5678"), "09012345678")
        self.assertEqual(n.phone_key("090-1234-5678"), "09012345678")

    def test_email_key(self):
        self.assertEqual(n.email_key(" Taro@Example.JP "), "taro@example.jp")


if __name__ == "__main__":
    unittest.main()
