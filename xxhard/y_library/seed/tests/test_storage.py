import os
import tempfile
import unittest

from app.storage import Storage


class StorageTest(unittest.TestCase):
    def test_crud(self):
        s = Storage()
        a = s.insert("t", {"x": 1})
        b = s.insert("t", {"x": 2})
        self.assertEqual((a["id"], b["id"]), (1, 2))
        self.assertEqual(s.update("t", 1, {"x": 5}), {"id": 1, "x": 5})
        self.assertEqual(s.find("t", x=5), [{"id": 1, "x": 5}])
        self.assertTrue(s.delete("t", 1))
        self.assertFalse(s.delete("t", 1))
        self.assertIsNone(s.get("t", 1))
        self.assertEqual(s.insert("t", {"x": 3})["id"], 3)

    def test_returned_rows_are_copies(self):
        s = Storage()
        row = s.insert("t", {"tags": ["a"]})
        row["tags"].append("b")
        self.assertEqual(s.get("t", 1)["tags"], ["a"])

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "db.json")
            s = Storage(p)
            s.insert("t", {"x": 1})
            s.insert("t", {"x": 2})
            s.delete("t", 2)
            s2 = Storage(p)
            self.assertEqual(s2.find("t"), [{"id": 1, "x": 1}])
            self.assertEqual(s2.insert("t", {"x": 9})["id"], 3)
