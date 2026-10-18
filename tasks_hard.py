"""Harder tasks (multi-file, specs, hidden edge-case tests). Imported by make_tasks.py."""
import textwrap
d = textwrap.dedent


def add(task):
    task("h_lru", "lru.py に LRUCache クラスを実装してください。LRUCache(capacity) で作り、get(key) は値を返し（なければ -1）、put(key, value) で追加・更新します。容量を超えたら最も長く使われていないものを捨てます。get も「使った」に数えます。capacity が 0 以下なら ValueError。get/put は O(1) にしてください。",
         {"lru.py": "# implement LRUCache here\n"},
         d("""
         cd /work && timeout 20 python3 -c "
         from lru import LRUCache
         c=LRUCache(2); c.put(1,1); c.put(2,2); assert c.get(1)==1; c.put(3,3); assert c.get(2)==-1; c.put(4,4)
         assert c.get(1)==-1 and c.get(3)==3 and c.get(4)==4
         c=LRUCache(1); c.put('a',1); c.put('a',2); assert c.get('a')==2; c.put('b',3); assert c.get('a')==-1
         c=LRUCache(2); c.put(1,1); c.put(2,2); c.put(1,10); c.put(3,3); assert c.get(2)==-1 and c.get(1)==10
         for bad in (0,-1):
             try: LRUCache(bad)
             except ValueError: pass
             else: raise SystemExit('no ValueError')
         import time; c=LRUCache(50000); t=time.time()
         for i in range(200000): c.put(i,i); c.get(i//2)
         assert time.time()-t<3, 'too slow'
         "
         """))

    task("h_bank", "bank/ パッケージの transfer() に不具合があり、残高不足などで送金が失敗したときにお金が消えることがあります。失敗したときは両方の口座が元の残高に戻るように直してください。既存のテスト（python3 -m unittest discover -s tests）が通る状態を保ち、テストファイルは変更しないでください。",
         {"bank/__init__.py": "",
          "bank/account.py": d("""
          class InsufficientFunds(Exception):
              pass

          class Account:
              def __init__(self, owner, balance=0):
                  self.owner = owner
                  self.balance = balance

              def withdraw(self, amount):
                  if amount <= 0:
                      raise ValueError("amount must be positive")
                  if amount > self.balance:
                      raise InsufficientFunds(self.owner)
                  self.balance -= amount

              def deposit(self, amount):
                  if amount <= 0:
                      raise ValueError("amount must be positive")
                  self.balance += amount
          """),
          "bank/ops.py": d("""
          from bank.account import Account

          def transfer(src: Account, dst: Account, amount, fee=0):
              \"\"\"Move amount from src to dst; src also pays fee. All or nothing.\"\"\"
              src.withdraw(amount)
              dst.deposit(amount)
              if fee:
                  src.withdraw(fee)
          """),
          "tests/test_ops.py": d("""
          import unittest
          from bank.account import Account, InsufficientFunds
          from bank.ops import transfer

          class T(unittest.TestCase):
              def test_ok(self):
                  a, b = Account("a", 100), Account("b", 0)
                  transfer(a, b, 30, fee=1)
                  self.assertEqual((a.balance, b.balance), (69, 30))

              def test_insufficient(self):
                  a, b = Account("a", 10), Account("b", 0)
                  with self.assertRaises(InsufficientFunds):
                      transfer(a, b, 20)
                  self.assertEqual((a.balance, b.balance), (10, 0))
          """)},
         d("""
         set -e
         cd /work
         cmp -s tests/test_ops.py /check/test_ops.py
         python3 -m unittest discover -s tests -q
         python3 -c "
         from bank.account import Account, InsufficientFunds
         from bank.ops import transfer
         a,b=Account('a',30),Account('b',5)
         try: transfer(a,b,30,fee=1)
         except InsufficientFunds: pass
         else: raise SystemExit('should fail')
         assert (a.balance,b.balance)==(30,5),(a.balance,b.balance)
         a,b=Account('a',30),Account('b',5)
         try: transfer(a,b,-5)
         except ValueError: pass
         assert (a.balance,b.balance)==(30,5)
         a,b=Account('a',31),Account('b',5); transfer(a,b,30,fee=1); assert (a.balance,b.balance)==(0,35)
         "
         """), {"test_ops.py": "tests/test_ops.py"})

    task("h_ini", "docs/SPEC.md の仕様どおりに、iniparse.py に関数 parse(text) を実装してください。",
         {"docs/SPEC.md": d("""
          # 設定ファイル形式

          parse(text) は dict を返す。キーはセクション名、値は {キー: 値} の dict。

          - `[name]` でセクションを始める。名前の前後の空白は取り除く。
          - セクションより前のキーは "" （空文字）セクションに入る。そのキーがなければ "" セクションは作らない。
          - `key = value` または `key: value`。キーと値の前後の空白は取り除く。キーは小文字にそろえる。
          - `#` または `;` で始まる行（前に空白があってもよい）はコメント。値の途中の # はコメントではない。
          - 空行は無視する。
          - 行頭が空白で始まり、直前にキーがある行は、直前の値の続き。改行1つでつなぐ（続きの行の前後の空白は取り除く）。
          - 同じセクションが2回出たら中身をまとめる。同じキーは後のものが勝つ。
          - 上のどれにも当てはまらない行があれば ValueError を出す（メッセージに行番号を含める。1行目が1）。
          """)},
         d("""
         cd /work && python3 -c "
         from iniparse import parse
         t='''top = 1
         [ Main ]
         Name = demo app
         ; comment
           # indented comment
         url: http://x/#frag
         desc = first
            second line
         [main]
         name = override

         [other]
         K=v
         '''
         r=parse(t)
         assert r=={'':{'top':'1'},'Main':{'name':'demo app','url':'http://x/#frag','desc':'first\\\\nsecond line'},'main':{'name':'override'},'other':{'k':'v'}},r
         assert parse('[a]\\\\nx=1\\\\n[a]\\\\ny=2\\\\nx=3')=={'a':{'x':'3','y':'2'}}
         assert parse('')=={}
         try: parse('[a]\\\\nx=1\\\\nbadline\\\\n')
         except ValueError as e: assert '3' in str(e), e
         else: raise SystemExit('no error')
         "
         """))

    task("h_todo", "todo.py というコマンドラインのTODO管理ツールを作ってください。データは同じフォルダの todo.json に保存します。\n"
         "- `python3 todo.py add 牛乳を買う` → `added 1`（番号は1から連番。消しても番号は再利用しない）\n"
         "- `python3 todo.py list` → 未完了を `1 [ ] 牛乳を買う`、完了を `2 [x] ...` の形で番号順に1行ずつ。1件もなければ `no tasks`\n"
         "- `python3 todo.py done 1` → `done 1`\n- `python3 todo.py delete 1` → `deleted 1`\n"
         "- 存在しない番号には `error: no task 5` を標準エラーに出して終了コード1。コマンドが不正なら使い方を標準エラーに出して終了コード2。",
         {},
         d("""
         set -e
         D=$(mktemp -d); cp /work/todo.py $D/; cd $D
         test "$(python3 todo.py list)" = "no tasks"
         test "$(python3 todo.py add 牛乳を買う)" = "added 1"
         test "$(python3 todo.py add 本を返す)" = "added 2"
         test "$(python3 todo.py done 2)" = "done 2"
         test "$(python3 todo.py list)" = "$(printf '1 [ ] 牛乳を買う\\n2 [x] 本を返す')"
         test "$(python3 todo.py delete 1)" = "deleted 1"
         test "$(python3 todo.py add 掃除)" = "added 3"
         set +e; python3 todo.py done 9 2>e; c=$?; set -e; test $c = 1; grep -q "error: no task 9" e
         set +e; python3 todo.py frobnicate 2>/dev/null; c=$?; set -e; test $c = 2
         test -f todo.json
         """))

    task("h_bizdays", "dates.py の business_days(start, end, holidays) は、start から end まで（両端を含む）の平日（月〜金）のうち holidays に含まれない日数を返す関数ですが、結果がおかしいことがあります。原因を見つけて直してください。start が end より後なら 0 を返します。",
         {"dates.py": d("""
          from datetime import date, timedelta

          def business_days(start: date, end: date, holidays=()):
              days = 0
              d = start
              while d < end:
                  if d.weekday() < 5 or d not in holidays:
                      days += 1
                  d += timedelta(days=1)
              return days
          """)},
         d("""
         cd /work && python3 -c "
         from datetime import date as D
         from dates import business_days as b
         assert b(D(2026,10,12),D(2026,10,16))==5
         assert b(D(2026,10,12),D(2026,10,18))==5
         assert b(D(2026,10,17),D(2026,10,18))==0
         assert b(D(2026,10,16),D(2026,10,16))==1
         assert b(D(2026,10,12),D(2026,10,16),[D(2026,10,13),D(2026,10,17)])==4
         assert b(D(2026,10,20),D(2026,10,1))==0
         "
         """))

    task("h_md", "md2html.py に関数 convert(md) を作って、Markdown の一部を HTML に変換してください。対応するのは: 見出し（# 〜 ###、`<h1>`〜`<h3>`）、段落（空行で区切られた連続行を `<p>` にまとめ、行は空白1つでつなぐ）、`- ` で始まる箇条書き（連続する項目を1つの `<ul><li>..</li></ul>` に）、**太字**（`<strong>`）、*斜体*（`<em>`）、`コード`（`<code>`、中は太字などを変換しない）。HTMLの特殊文字 & < > はエスケープしてください。ブロックは改行1つで区切って出力します。",
         {},
         d("""
         cd /work && python3 -c "
         from md2html import convert as c
         assert c('# Title')=='<h1>Title</h1>', c('# Title')
         assert c('## a *b*')=='<h2>a <em>b</em></h2>'
         assert c('one\\\\ntwo\\\\n\\\\nthree')=='<p>one two</p>\\\\n<p>three</p>', c('one\\\\ntwo\\\\n\\\\nthree')
         assert c('- a\\\\n- **b**\\\\n\\\\ntext')=='<ul><li>a</li><li><strong>b</strong></li></ul>\\\\n<p>text</p>'
         assert c('use \\x60x **y**\\x60 & <z>')=='<p>use <code>x **y**</code> &amp; &lt;z&gt;</p>', c('use \\x60x **y**\\x60 & <z>')
         assert c('### h3\\\\npara')=='<h3>h3</h3>\\\\n<p>para</p>', c('### h3\\\\npara')
         "
         """))

    task("h_clean_csv", "raw.csv は手作業で集めた汚いデータです。clean.csv に整えて保存してください。ルール: 文字コードはUTF-8（BOMなし）、列は id,name,date,amount、date は YYYY-MM-DD にそろえる（元は 2026/10/3、10-03-2026、2026年10月3日 など）、amount は数値（カンマや円記号を取る、整数）、name の前後の空白は取る、id が重複していたら最初の行だけ残す、id の昇順に並べる。",
         {"raw.csv": "﻿id,name,date,amount\n3, 佐藤 ,2026/10/3,\"1,200円\"\n1,田中,10-05-2026,500\n2,\"鈴木, 花子\",2026年10月4日,¥3000\n3,重複,2026/10/9,1\n10,伊藤,2026-10-01,\"12,345\"\n"},
         d("""
         python3 -c "
         import csv
         b=open('/work/clean.csv','rb').read(); assert not b.startswith(b'\\xef\\xbb\\xbf'),'BOM'
         rows=list(csv.reader(open('/work/clean.csv',encoding='utf-8')))
         assert rows==[['id','name','date','amount'],['1','田中','2026-10-05','500'],['2','鈴木, 花子','2026-10-04','3000'],['3','佐藤','2026-10-03','1200'],['10','伊藤','2026-10-01','12345']],rows
         "
         """))

    task("h_inventory", "inventory.py に機能を追加してください: low_stock(threshold) は、在庫数が threshold 未満の商品を (在庫数の少ない順、同数なら名前順) で [(name, qty), ...] のリストで返します。あわせて tests/test_inventory.py に low_stock のテストを2つ以上追加してください。既存のテストは全部通るようにしてください（python3 -m unittest discover -s tests）。",
         {"inventory.py": d("""
          class Inventory:
              def __init__(self):
                  self._items = {}

              def add(self, name, qty):
                  if qty < 0:
                      raise ValueError("qty must be >= 0")
                  self._items[name] = self._items.get(name, 0) + qty

              def remove(self, name, qty):
                  have = self._items.get(name, 0)
                  if qty > have:
                      raise ValueError(f"only {have} {name}")
                  self._items[name] = have - qty

              def qty(self, name):
                  return self._items.get(name, 0)
          """),
          "tests/test_inventory.py": d("""
          import unittest
          from inventory import Inventory

          class T(unittest.TestCase):
              def test_add_remove(self):
                  inv = Inventory()
                  inv.add("pen", 5)
                  inv.remove("pen", 2)
                  self.assertEqual(inv.qty("pen"), 3)

              def test_remove_too_many(self):
                  inv = Inventory()
                  with self.assertRaises(ValueError):
                      inv.remove("pen", 1)
          """)},
         d("""
         set -e
         cd /work
         python3 -m unittest discover -s tests -q
         grep -q "test_add_remove" tests/test_inventory.py
         test $(grep -c "low_stock" tests/test_inventory.py) -ge 2
         python3 -c "
         from inventory import Inventory
         i=Inventory(); [i.add(n,q) for n,q in [('b',2),('a',2),('c',9),('d',0)]]
         assert i.low_stock(3)==[('d',0),('a',2),('b',2)], i.low_stock(3)
         assert i.low_stock(0)==[]
         "
         """))

    task("h_money", "invoice.py が作る請求書の合計金額が、1円ずれることがあります（浮動小数点の誤差）。金額は decimal.Decimal で計算するように直して、税額は1円未満を切り捨て（明細ごとではなく合計に対して）にしてください。出力の形式は変えないでください。",
         {"invoice.py": d("""
          import json, sys

          TAX = 0.1

          def total(lines):
              sub = 0.0
              for l in lines:
                  sub += l["price"] * l["qty"]
              tax = round(sub * TAX)
              return sub, tax, sub + tax

          if __name__ == "__main__":
              lines = json.load(open(sys.argv[1]))
              sub, tax, tot = total(lines)
              print(f"subtotal={int(sub)} tax={int(tax)} total={int(tot)}")
          """),
          "items.json": '[{"price": 19.99, "qty": 3}, {"price": 0.1, "qty": 7}, {"price": 1005, "qty": 1}]\n'},
         d("""
         set -e
         cd /work
         test "$(python3 invoice.py items.json)" = "subtotal=1065 tax=106 total=1171"
         printf '[{"price": "33.35", "qty": 3}]' > /tmp/a.json
         test "$(python3 invoice.py /tmp/a.json)" = "subtotal=100 tax=10 total=110"
         grep -q "Decimal" invoice.py
         """))

    task("h_calc", "calc_expr.py に関数 evaluate(expr) を実装してください。四則演算（+ - * /）、かっこ、単項マイナス（-3、-(2+1)）、小数に対応し、演算子の優先順位どおりに計算して float を返します。eval や exec は使わないでください。ゼロ除算は ZeroDivisionError、構文がおかしい式（'2+'、'(1'、'1 2'、'a+1'）は ValueError にしてください。",
         {},
         d("""
         cd /work && ! grep -qE "\\\\beval\\\\(|\\\\bexec\\\\(" calc_expr.py && python3 -c "
         from calc_expr import evaluate as e
         assert e('1+2*3')==7 and e('(1+2)*3')==9 and e('-3+5')==2 and e('-(2+1)*2')==-6
         assert abs(e('10/4')-2.5)<1e-9 and e('2*-3')==-6 and e(' 1.5 + 2.25 ')==3.75 and e('8-3-2')==3 and e('64/4/2')==8
         try: e('1/0')
         except ZeroDivisionError: pass
         else: raise SystemExit('zero')
         for bad in ['2+','(1','1 2','a+1','',')(']:
             try: e(bad)
             except ValueError: pass
             else: raise SystemExit('no ValueError '+bad)
         "
         """))

    task("h_ratelimit", "ratelimit.py に TokenBucket クラスを実装してください。TokenBucket(rate, capacity, clock=time.monotonic) で、rate は1秒あたりに補充されるトークン数、capacity は上限です。作った直後は満タン。allow(n=1) はトークンが n 以上あれば n 減らして True、足りなければ減らさずに False を返します。時間は clock() で取ります（テストでは偽の時計を渡します）。",
         {},
         d("""
         cd /work && python3 -c "
         from ratelimit import TokenBucket
         t=[0.0]; clk=lambda:t[0]
         b=TokenBucket(2,5,clock=clk)
         assert all(b.allow() for _ in range(5)) and not b.allow()
         t[0]=1.0; assert b.allow() and b.allow() and not b.allow()
         t[0]=100; assert b.allow(5) and not b.allow()
         t[0]=100.25; assert not b.allow(); t[0]=100.5; assert b.allow()
         assert not b.allow(6)
         "
         """))

    task("h_sync", "sync.py を作ってください。`python3 sync.py SRC DST` で、SRC フォルダの中身を DST に同期します（サブフォルダも含む）。DST にないファイルや中身が違うファイルはコピーし、SRC にないファイルやフォルダは DST から消します。`--dry-run` を付けたら何も変更せず、行うはずの操作を `copy パス`・`delete パス`（DSTからの相対パス、辞書順）で1行ずつ出力します。付けないときも同じ形式で、実際に行った操作を出力します。",
         {},
         d("""
         set -e
         D=$(mktemp -d); cd $D
         mkdir -p s/sub d/old; echo 1 > s/a.txt; echo 2 > s/sub/b.txt; echo x > d/a.txt; echo 2 > d/same.txt; cp d/same.txt s/same.txt; echo z > d/old/z.txt
         out=$(python3 /work/sync.py s d --dry-run)
         test "$out" = "$(printf 'copy a.txt\\ndelete old\\ncopy sub/b.txt')" || test "$out" = "$(printf 'copy a.txt\\ndelete old/z.txt\\ndelete old\\ncopy sub/b.txt')" || test "$out" = "$(printf 'copy a.txt\\ndelete old/z.txt\\ncopy sub/b.txt')"
         test "$(cat d/a.txt)" = x
         python3 /work/sync.py s d > /dev/null
         diff -r s d
         test -z "$(python3 /work/sync.py s d)"
         """))

    task("h_access", "access.log（Apache形式）を解析して、result.json に次の内容を保存してください: \"top_ips\": アクセス数の多いIP上位3件 [[ip, 回数], ...]（同数ならIPの文字列順）、\"status\": ステータスコードごとの件数 {\"200\": n, ...}、\"bytes\": 送信バイト数の合計（\"-\" は0）、\"bad_lines\": 形式に合わない行の数。",
         {"access.log": "\n".join([
             '10.0.0.1 - - [17/Oct/2026:10:00:00 +0900] "GET / HTTP/1.1" 200 512',
             '10.0.0.2 - - [17/Oct/2026:10:00:01 +0900] "GET /a HTTP/1.1" 404 -',
             '10.0.0.1 - - [17/Oct/2026:10:00:02 +0900] "POST /api HTTP/1.1" 201 64',
             'garbage line here',
             '10.0.0.3 - - [17/Oct/2026:10:00:03 +0900] "GET / HTTP/1.1" 200 1024',
             '10.0.0.2 - - [17/Oct/2026:10:00:04 +0900] "GET /b HTTP/1.1" 200 100',
             '10.0.0.10 - - [17/Oct/2026:10:00:05 +0900] "GET /c HTTP/1.1" 500 0',
             '10.0.0.3 - - [17/Oct/2026:10:00:06 +0900] "GET / HTTP/1.1" 304 -',
             '',
             '10.0.0.1 - - [17/Oct/2026:10:00:07 +0900] "GET /x HTTP/1.1" 200 8']) + "\n"},
         d("""
         python3 -c "
         import json
         r=json.load(open('/work/result.json'))
         assert r['top_ips']==[['10.0.0.1',3],['10.0.0.2',2],['10.0.0.3',2]],r['top_ips']
         assert {str(k):v for k,v in r['status'].items()}=={'200':4,'404':1,'201':1,'500':1,'304':1},r['status']
         assert r['bytes']==512+64+1024+100+0+8,r['bytes']
         assert r['bad_lines']==1,r['bad_lines']
         "
         """))

    task("h_dupes", "dupes.py の find_duplicates(items) は、2回以上出てくる要素を、2回目が出てきた順で（重複なしで）返します。正しく動きますが、20万件で何分もかかります。結果を変えずに速くして、`python3 bench.py` が2秒以内に終わるようにしてください。bench.py は変更しないでください。",
         {"dupes.py": "def find_duplicates(items):\n    out = []\n    for i, x in enumerate(items):\n        if x in items[:i] and x not in out:\n            out.append(x)\n    return out\n",
          "bench.py": "import random, time\nfrom dupes import find_duplicates\nrandom.seed(1)\nitems = [random.randint(0, 150000) for _ in range(200000)]\nt = time.time()\nr = find_duplicates(items)\nprint(len(r), round(time.time() - t, 2))\n"},
         d("""
         set -e
         cd /work
         cmp -s bench.py /check/bench.py
         timeout 5 python3 bench.py
         python3 -c "
         from dupes import find_duplicates as f
         assert f([3,1,3,2,1,3])==[3,1] and f([])==[] and f(['a','b','a'])==['a'] and f([1,2,2,1])==[2,1]
         "
         """), {"bench.py": "bench.py"})

    task("h_sqlite", "employees.csv と departments.csv を読み込んで（Python の sqlite3 を使ってください）、answers.json に次の答えを保存してください: \"q1\": 部署ごとの平均給与を {部署名: 平均（小数第1位で四捨五入）}、\"q2\": 給与が所属部署の平均より高い社員の名前の一覧（名前順）、\"q3\": 社員が1人もいない部署名の一覧（名前順）。",
         {"employees.csv": "id,name,dept_id,salary\n1,Aoki,1,500\n2,Baba,1,700\n3,Chiba,2,400\n4,Doi,2,450\n5,Endo,2,350\n6,Fujii,3,900\n",
          "departments.csv": "id,name\n1,Sales\n2,Dev\n3,Legal\n4,HR\n5,Ops\n"},
         d("""
         python3 -c "
         import json
         r=json.load(open('/work/answers.json'))
         assert {k:round(float(v),1) for k,v in r['q1'].items()}=={'Sales':600.0,'Dev':400.0,'Legal':900.0},r['q1']
         assert r['q2']==['Baba','Doi'],r['q2']
         assert r['q3']==['HR','Ops'],r['q3']
         "
         """))
