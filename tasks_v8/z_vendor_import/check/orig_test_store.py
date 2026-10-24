import json
import os
import tempfile
import unittest

from custimport import reader
from custimport.store import Store


def write(d, name, text, enc="utf-8"):
    p = os.path.join(d, name)
    with open(p, "wb") as f:
        f.write(text.encode(enc))
    return p


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "store.json")

    def load(self, *files):
        s = Store(self.path)
        out = []
        for f in files:
            recs, _ = reader.read_file(f)
            out.append([s.apply(r) for r in recs])
        s.save()
        return out

    def test_merge_by_email_and_name_phone(self):
        a = write(self.d, "va.csv", "id,name,email,phone\n1,山田 太郎,taro@example.jp,090-1111-2222\n2,佐藤 花子,,03-1234-5678\n")
        b = write(self.d, "vb.csv", "顧客番号,氏名,電話番号,メールアドレス\n9,山田太郎,,TARO@example.jp\n8,佐藤　花子,０３－１２３４－５６７８,hana@example.jp\n", "cp932")
        self.assertEqual(self.load(a, b), [["new", "new"], ["merge", "merge"]])
        d = json.load(open(self.path, encoding="utf-8"))
        self.assertEqual(d["next_id"], 3)
        self.assertEqual(d["customers"][1], {"id": 2, "name": "佐藤 花子", "email": "hana@example.jp",
                                             "phone": "03-1234-5678", "sources": ["va:2", "vb:8"]})

    def test_reimport_is_skipped(self):
        a = write(self.d, "va.csv", "id,name,email\n1,Tom,tom@example.com\n")
        self.load(a)
        self.assertEqual(self.load(a), [["skip"]])
        self.assertEqual(len(Store(self.path).customers), 1)

    def test_missing_id_column(self):
        a = write(self.d, "va.csv", "name,email\nTom,tom@example.com\n")
        with self.assertRaises(reader.ReadError):
            reader.read_file(a)


if __name__ == "__main__":
    unittest.main()
