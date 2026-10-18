"""Tier 3: repo-scale tasks (several files, reading existing code/docs, several bugs, tests to keep green)."""
import textwrap
d = textwrap.dedent

SHOP = {
    "shop/__init__.py": "",
    "shop/models.py": d("""
    from dataclasses import dataclass, field

    @dataclass
    class Item:
        sku: str
        price: int          # yen
        qty: int = 1

    @dataclass
    class Cart:
        items: list = field(default_factory=list)
        coupon: str | None = None

        def add(self, sku, price, qty=1):
            for it in self.items:
                if it.sku == sku:
                    it.qty += qty
                    return
            self.items.append(Item(sku, price, qty))

        def remove(self, sku, qty=1):
            for it in self.items:
                if it.sku == sku:
                    it.qty -= qty
                    if it.qty < 0:
                        self.items.remove(it)
                    return
            raise KeyError(sku)
    """),
    "shop/pricing.py": d("""
    from shop.coupons import discount_for

    TAX_RATE = 0.10

    def subtotal(cart):
        return sum(it.price * it.qty for it in cart.items)

    def total(cart):
        \"\"\"Subtotal, minus the coupon discount, plus 10% tax (rounded down to the yen).\"\"\"
        sub = subtotal(cart)
        disc = discount_for(cart.coupon, sub)
        taxed = (sub - disc) * (1 + TAX_RATE)
        return int(taxed)
    """),
    "shop/coupons.py": d("""
    COUPONS = {
        "WELCOME10": ("percent", 10),
        "YEN500": ("fixed", 500),
        "BIG20": ("percent_min", (20, 10000)),   # 20% off when subtotal >= 10000
    }

    def discount_for(code, sub):
        if code is None:
            return 0
        kind, val = COUPONS[code]
        if kind == "percent":
            return sub * val // 100
        if kind == "fixed":
            return val
        if kind == "percent_min":
            pct, minimum = val
            if sub > minimum:
                return sub * pct // 100
        return 0
    """),
    "docs/RULES.md": d("""
    # 料金ルール
    - 小計 = 各商品の 単価 × 数量 の合計
    - クーポンは小計に対して適用する。
      - WELCOME10: 小計の10%引き（1円未満切り捨て）
      - YEN500: 500円引き。ただし小計を超えて引かない（合計がマイナスにならない）
      - BIG20: 小計が10000円以上のとき20%引き
      - 存在しないクーポンコードは ValueError
    - 税は（小計−割引）に10%。1円未満切り捨て。浮動小数点の誤差を出さないこと。
    - remove で数量が0以下になった商品はカートから消える。存在しない商品の remove は KeyError。
    """),
    "tests/test_shop.py": d("""
    import unittest
    from shop.models import Cart
    from shop.pricing import total, subtotal

    class T(unittest.TestCase):
        def test_basic(self):
            c = Cart(); c.add("a", 1000, 2); c.add("b", 500)
            self.assertEqual(subtotal(c), 2500)
            self.assertEqual(total(c), 2750)

        def test_welcome(self):
            c = Cart(coupon="WELCOME10"); c.add("a", 1999)
            self.assertEqual(total(c), 1980)
    """),
}


def add(task):
    task("x_shop", "shop/ パッケージは docs/RULES.md の料金ルールどおりに動くはずですが、いくつかルールと違う動作があります。ルールどおりに直してください。既存のテスト（python3 -m unittest discover -s tests）は通るようにし、テストファイルは変更しないでください。",
         SHOP,
         d("""
         set -e
         cd /work
         cmp -s tests/test_shop.py /check/test_shop.py
         python3 -m unittest discover -s tests -q
         python3 -c "
         from shop.models import Cart
         from shop.pricing import total
         def mk(items, coupon=None):
             c=Cart(coupon=coupon)
             for s,p,q in items: c.add(s,p,q)
             return c
         assert total(mk([('a',300,1)],'YEN500'))==0, total(mk([('a',300,1)],'YEN500'))
         assert total(mk([('a',10000,1)],'BIG20'))==8800
         assert total(mk([('a',9999,1)],'BIG20'))==10998
         assert total(mk([('a',1100,3)]))==3630, total(mk([('a',1100,3)]))
         try: total(mk([('a',1,1)],'NOPE'))
         except ValueError: pass
         else: raise SystemExit('no ValueError')
         c=mk([('a',100,2)]); c.remove('a',2); assert c.items==[], c.items
         c=mk([('a',100,2)]); c.remove('a',1); assert c.items[0].qty==1
         try: mk([]).remove('z')
         except KeyError: pass
         else: raise SystemExit('no KeyError')
         "
         """), {"test_shop.py": "tests/test_shop.py"})

    task("x_cli_sub", "notes.py は簡単なメモ管理CLIです（使い方は notes.py --help）。新しいサブコマンド `search` を追加してください: `python3 notes.py search キーワード` で、タイトルか本文にキーワードを含むメモを、既存の list と同じ形式で出力します（大文字小文字は区別しない）。1件もなければ `no match` と出力。--tag タグ名 を付けたら、そのタグを持つメモだけに絞ります。既存のサブコマンドの動作は変えないでください。",
         {"notes.py": d("""
          import argparse, json, os, sys

          DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.json")

          def load():
              return json.load(open(DB, encoding="utf-8")) if os.path.exists(DB) else []

          def save(notes):
              json.dump(notes, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

          def fmt(n):
              tags = ",".join(n["tags"])
              return f"#{n['id']} {n['title']}" + (f" [{tags}]" if tags else "")

          def cmd_add(a):
              notes = load()
              nid = max([n["id"] for n in notes], default=0) + 1
              notes.append({"id": nid, "title": a.title, "body": a.body or "", "tags": a.tag or []})
              save(notes)
              print(f"added #{nid}")

          def cmd_list(a):
              notes = load()
              if a.tag:
                  notes = [n for n in notes if a.tag in n["tags"]]
              for n in notes:
                  print(fmt(n))
              if not notes:
                  print("no notes")

          def main(argv=None):
              p = argparse.ArgumentParser(prog="notes.py")
              sub = p.add_subparsers(dest="cmd", required=True)
              s = sub.add_parser("add"); s.add_argument("title"); s.add_argument("--body"); s.add_argument("--tag", action="append")
              s.set_defaults(fn=cmd_add)
              s = sub.add_parser("list"); s.add_argument("--tag"); s.set_defaults(fn=cmd_list)
              a = p.parse_args(argv)
              a.fn(a)

          if __name__ == "__main__":
              main()
          """)},
         d("""
         set -e
         D=$(mktemp -d); cp /work/notes.py $D/; cd $D
         python3 notes.py add "買い物" --body "牛乳 と Bread" --tag home >/dev/null
         python3 notes.py add "Meeting" --body "議事録 bread" --tag work >/dev/null
         python3 notes.py add "読書" --tag home >/dev/null
         test "$(python3 notes.py list)" = "$(printf '#1 買い物 [home]\\n#2 Meeting [work]\\n#3 読書 [home]')"
         test "$(python3 notes.py search BREAD)" = "$(printf '#1 買い物 [home]\\n#2 Meeting [work]')"
         test "$(python3 notes.py search bread --tag work)" = "#2 Meeting [work]"
         test "$(python3 notes.py search 読書)" = "#3 読書 [home]"
         test "$(python3 notes.py search zzz)" = "no match"
         test "$(python3 notes.py list --tag home)" = "$(printf '#1 買い物 [home]\\n#3 読書 [home]')"
         """))

    task("x_logs_pipeline", "pipeline/ のデータ処理は3段階（parse.py → enrich.py → report.py、run.py でまとめて実行）です。`python3 run.py data/events.log` の出力 report.txt が、期待される形式（docs/FORMAT.md）と合っていません。原因を調べて直してください。どの段階に問題があるかは分かっていません。",
         {"run.py": "import sys\nfrom pipeline.parse import parse\nfrom pipeline.enrich import enrich\nfrom pipeline.report import report\n\nrows = parse(open(sys.argv[1], encoding='utf-8').read())\nrows = enrich(rows)\nopen('report.txt', 'w', encoding='utf-8').write(report(rows))\n",
          "pipeline/__init__.py": "",
          "pipeline/parse.py": "def parse(text):\n    rows = []\n    for line in text.splitlines():\n        if not line.strip() or line.startswith('#'):\n            continue\n        ts, user, action, ms = line.split(',')\n        rows.append({'ts': ts, 'user': user.strip(), 'action': action.strip(), 'ms': ms})\n    return rows\n",
          "pipeline/enrich.py": "TEAM = {'aoi': 'red', 'ren': 'blue', 'yui': 'red'}\n\ndef enrich(rows):\n    for r in rows:\n        r['team'] = TEAM.get(r['user'], 'none')\n    return rows\n",
          "pipeline/report.py": "from collections import defaultdict\n\ndef report(rows):\n    by = defaultdict(list)\n    for r in rows:\n        by[r['team']].append(r['ms'])\n    out = []\n    for team in sorted(by):\n        ms = by[team]\n        out.append(f\"{team}: n={len(ms)} avg={sum(ms) / len(ms):.1f}ms max={max(ms)}ms\")\n    return '\\n'.join(out) + '\\n'\n",
          "data/events.log": "# ts,user,action,ms\n2026-10-18T10:00,aoi,login,120\n2026-10-18T10:01, Ren ,search,95\n2026-10-18T10:02,yui,login,1300\n\n2026-10-18T10:03,kai,login,40\n2026-10-18T10:04,aoi,search,80\n",
          "docs/FORMAT.md": "# report.txt\nチームごとに1行、チーム名の辞書順。\n`チーム: n=件数 avg=平均ms max=最大ms`（avg は小数第1位、ms は整数）。\nユーザー名は大文字小文字・前後の空白を区別しない。チームが分からないユーザーは none。\n"},
         'cd /work && python3 run.py data/events.log && test "$(cat report.txt)" = "$(printf \'blue: n=1 avg=95.0ms max=95ms\\nnone: n=1 avg=40.0ms max=40ms\\nred: n=3 avg=500.0ms max=1300ms\')"\n')

    task("x_write_tests", "slugify.py の slugify(text) にはテストがありません。tests/test_slugify.py に unittest でテストを書いてください（最低6ケース。空文字、記号、連続する空白・ハイフン、前後の空白、大文字、数字を含めること）。各ケースは assertEqual などで1行ずつ書いてください（assert の行が6つ以上）。テストが通ることを確認してください。slugify.py は変更しないでください。",
         {"slugify.py": "import re\n\ndef slugify(text):\n    text = text.strip().lower()\n    text = re.sub(r'[^a-z0-9\\s-]', '', text)\n    text = re.sub(r'[\\s-]+', '-', text)\n    return text.strip('-')\n",
          "tests/__init__.py": ""},
         d("""
         set -e
         cd /work
         cmp -s slugify.py /check/slugify.py
         python3 -m unittest discover -s tests -q
         n=$(python3 -c "
         import unittest,sys
         s=unittest.defaultTestLoader.discover('tests');
         def c(x): return sum(c(t) for t in x) if isinstance(x,unittest.TestSuite) else 1
         print(c(s))")
         a=$(grep -cE "assert(Equal|True|False|In)" tests/test_slugify.py)
         test $a -ge 6
         # the tests must catch a broken implementation
         cp slugify.py /tmp/good.py
         printf 'def slugify(text):\\n    return text.lower().replace(\\" \\", \\"-\\")\\n' > slugify.py
         if python3 -m unittest discover -s tests -q >/dev/null 2>&1; then cp /tmp/good.py slugify.py; echo "tests do not catch a bad slugify"; exit 1; fi
         cp /tmp/good.py slugify.py
         """), {"slugify.py": "slugify.py"})

    task("x_cache_bug", "fetcher.py の CachedFetcher は、同じURLの結果をttl秒だけキャッシュするはずですが、テスト（python3 -m unittest test_fetcher）がときどき失敗します。原因を特定して直してください。呼び出し側が渡した params の辞書を書き換えないようにもしてください。テストファイルは変更しないでください。",
         {"fetcher.py": d("""
          import time

          class CachedFetcher:
              def __init__(self, fetch, ttl=60, clock=time.time, max_entries=100):
                  self.fetch, self.ttl, self.clock, self.max = fetch, ttl, clock, max_entries
                  self.cache = {}   # url -> (value, stored_at)

              def get(self, url, params={}):
                  key = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
                  hit = self.cache.get(key)
                  if hit and self.clock() - hit[1] < self.ttl:
                      return hit[0]
                  value = self.fetch(url, params)
                  params["_fetched"] = True
                  self.cache[key] = (value, self.clock())
                  if len(self.cache) > self.max:
                      oldest = min(self.cache, key=lambda k: self.cache[k][1])
                      del self.cache[oldest]
                  return value
          """),
          "test_fetcher.py": d("""
          import unittest
          from fetcher import CachedFetcher

          class T(unittest.TestCase):
              def setUp(self):
                  self.calls = []
                  self.t = [0.0]
                  self.f = CachedFetcher(lambda u, p: self.calls.append((u, dict(p))) or len(self.calls), ttl=10, clock=lambda: self.t[0], max_entries=2)

              def test_hit(self):
                  self.assertEqual(self.f.get("a"), 1)
                  self.assertEqual(self.f.get("a"), 1)
                  self.assertEqual(len(self.calls), 1)

              def test_expire(self):
                  self.f.get("a"); self.t[0] = 10.5
                  self.assertEqual(self.f.get("a"), 2)

              def test_params_order(self):
                  self.f.get("a", {"x": 1, "y": 2})
                  self.f.get("a", {"y": 2, "x": 1})
                  self.assertEqual(len(self.calls), 1)

              def test_default_params_not_shared(self):
                  self.f.get("a")
                  self.f.get("b")
                  self.assertEqual(self.calls[1], ("b", {}))
          """)},
         d("""
         set -e
         cd /work
         cmp -s test_fetcher.py /check/test_fetcher.py
         python3 -m unittest -q test_fetcher
         python3 -c "
         from fetcher import CachedFetcher
         t=[0.0]; calls=[]
         f=CachedFetcher(lambda u,p: calls.append(u) or len(calls), ttl=5, clock=lambda:t[0], max_entries=2)
         f.get('a'); t[0]=1; f.get('b'); t[0]=2; f.get('a')
         assert len(calls)==2, calls
         p={'k':1}; f.get('z',p); assert p=={'k':1}, p
         "
         """), {"test_fetcher.py": "test_fetcher.py"})
