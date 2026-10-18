#!/usr/bin/env python3
"""Writes the task suite to tasks/<id>/: task.md (instruction, Japanese), files/ (workspace seed), check/ (hidden; check.sh exits 0 on pass)."""
import os, shutil, textwrap

T = {}

def task(tid, instruction, files, check, hidden=None):
    T[tid] = (instruction, files, check, hidden or {})

d = textwrap.dedent

task("fizzbuzz", "1から100までのFizzBuzzを出力するPythonスクリプト fizzbuzz.py を作って、実行結果を out.txt に保存してください（1行に1つ。3の倍数はFizz、5の倍数はBuzz、両方はFizzBuzz）。",
     {}, d("""
     set -e
     python3 /work/fizzbuzz.py > /tmp/o.txt
     python3 -c "
     exp=['FizzBuzz' if i%15==0 else 'Fizz' if i%3==0 else 'Buzz' if i%5==0 else str(i) for i in range(1,101)]
     for f in ['/tmp/o.txt','/work/out.txt']:
         got=open(f).read().split()
         assert got==exp,(f,got[:20])
     "
     """))

task("avg_bug", "calc.py のテストが失敗しています。原因を調べて calc.py を直してください。テストファイルは変更しないでください。テストは `python3 -m unittest` で実行できます。",
     {"calc.py": d("""
     def average(xs):
         if not xs:
             return 0
         total = 0
         for i in range(1, len(xs)):
             total += xs[i]
         return total / len(xs)

     def median(xs):
         s = sorted(xs)
         n = len(s)
         return s[n // 2]
     """),
      "test_calc.py": d("""
     import unittest
     from calc import average, median
     class T(unittest.TestCase):
         def test_avg(self):
             self.assertEqual(average([2, 4, 6]), 4)
             self.assertEqual(average([]), 0)
         def test_median_odd(self):
             self.assertEqual(median([3, 1, 2]), 2)
         def test_median_even(self):
             self.assertEqual(median([4, 1, 3, 2]), 2.5)
     """)},
     d("""
     set -e
     cd /work
     cmp -s test_calc.py /check/test_calc.py
     python3 -m unittest -q test_calc 2>&1
     python3 -c "from calc import average,median; assert average([1,2])==1.5; assert median([1,2,3,10])==2.5; assert median([5])==5"
     """), {"test_calc.py": None})

task("csv_sum", "sales.csv のカテゴリごとの売上合計（quantity×price）を計算して、summary.json に {カテゴリ名: 合計} の形のJSONで保存してください。合計は小数第2位で四捨五入してください。",
     {"sales.csv": "date,category,item,quantity,price\n2026-10-01,食品,りんご,3,120.5\n2026-10-01,文具,ペン,10,80\n2026-10-02,食品,みかん,5,60\n2026-10-02,家電,電池,2,398.9\n2026-10-03,文具,ノート,4,150.25\n2026-10-03,食品,パン,1,210\n"},
     d("""
     python3 -c "
     import json
     d=json.load(open('/work/summary.json'))
     exp={'食品':round(3*120.5+5*60+210,2),'文具':round(800+4*150.25,2),'家電':round(2*398.9,2)}
     assert {k:round(float(v),2) for k,v in d.items()}==exp,(d,exp)
     "
     """))

task("rename", "photos/ フォルダの画像ファイル名を、すべて小文字にして、番号を3桁のゼロ埋めにそろえてください（例: IMG_7.JPG → img_007.jpg）。中身は変えないでください。",
     {"photos/IMG_7.JPG": "a", "photos/IMG_12.JPG": "b", "photos/img_3.jpeg": "c", "photos/IMG_105.PNG": "d"},
     d("""
     set -e
     cd /work/photos
     test "$(ls | sort | tr '\\n' ' ')" = "img_003.jpeg img_007.jpg img_012.jpg img_105.png "
     test "$(cat img_007.jpg)" = a; test "$(cat img_012.jpg)" = b; test "$(cat img_003.jpeg)" = c; test "$(cat img_105.png)" = d
     """))

logs = {}
import random
rnd = random.Random(7)
counts = {}
for name in ["api", "worker", "db", "cache", "auth"]:
    lines, c = [], 0
    for i in range(rnd.randint(40, 90)):
        lvl = rnd.choice(["INFO"] * 6 + ["WARN"] * 2 + ["ERROR"])
        c += lvl == "ERROR"
        lines.append(f"2026-10-17T10:{i % 60:02d}:00 {lvl} {name}: event {i}")
    counts[name] = c
    logs[f"logs/{name}.log"] = "\n".join(lines) + "\n"
exp_report = "".join(f"{n}.log {c}\n" for n, c in sorted(counts.items(), key=lambda x: (-x[1], x[0])))
task("log_errors", "logs/ にある各ログファイルの ERROR 行の数を数えて、report.txt に「ファイル名 件数」の形で1行ずつ、件数の多い順（同数ならファイル名順）に書いてください。",
     logs, "diff <(cat /work/report.txt) /check/expected.txt\n", {"expected.txt": exp_report})

task("duration", "utils.py に関数 parse_duration(s) を実装してください。'1h30m' や '45s' や '2h5s' のような文字列を秒数（int）に変換します。単位は h, m, s で、どの単位も省略できます。不正な文字列（空文字、未知の単位、数字のない単位など）には ValueError を出してください。",
     {"utils.py": "# utilities\n"},
     d("""
     cd /work && python3 -c "
     from utils import parse_duration as p
     assert p('1h30m')==5400 and p('45s')==45 and p('2h5s')==7205 and p('10m')==600 and p('1h1m1s')==3661
     for bad in ['', 'abc', '5x', 'h', '1h-2m']:
         try: p(bad)
         except ValueError: pass
         else: raise SystemExit('no ValueError for '+repr(bad))
     "
     """))

task("refactor", "report_a.py と report_b.py に同じ処理（数値リストの書式化）が重複しています。共通部分を fmt.py の関数 format_numbers に切り出して、両方のファイルからそれを使うようにしてください。出力は変えないでください。",
     {"report_a.py": d("""
     data = [3.14159, 2.5, 100]
     out = []
     for x in data:
         out.append(f"{x:>10.2f}")
     print("A:" + "|".join(out))
     """),
      "report_b.py": d("""
     values = [1, 22.333, 0.5]
     out = []
     for x in values:
         out.append(f"{x:>10.2f}")
     print("B:" + "|".join(out))
     """)},
     d("""
     set -e
     cd /work
     test "$(python3 report_a.py)" = "A:      3.14|      2.50|    100.00"
     test "$(python3 report_b.py)" = "B:      1.00|     22.33|      0.50"
     grep -q "def format_numbers" fmt.py
     grep -q "format_numbers" report_a.py; grep -q "format_numbers" report_b.py
     ! grep -q ">10.2f" report_a.py; ! grep -q ">10.2f" report_b.py
     """))

task("config_edit", "config.json の server.port を 8443 に変更し、server に \"tls\": true を追加してください。ほかの設定は変えないでください。",
     {"config.json": '{\n  "name": "demo",\n  "server": {"host": "0.0.0.0", "port": 8080, "workers": 4},\n  "db": {"url": "sqlite:///app.db", "pool": 5},\n  "features": ["a", "b"]\n}\n'},
     d("""
     python3 -c "
     import json
     d=json.load(open('/work/config.json'))
     assert d=={'name':'demo','server':{'host':'0.0.0.0','port':8443,'workers':4,'tls':True},'db':{'url':'sqlite:///app.db','pool':5},'features':['a','b']},d
     "
     """))

task("wordcount", "コマンドラインツール wc.py を作ってください。`python3 wc.py ファイル名` で、そのファイルの行数・単語数（空白区切り）・文字数を `lines=3 words=7 chars=40` の形で1行出力します。`--top N` を付けたら、続けて出現回数の多い単語を上位N個、`単語 回数` の形で1行ずつ出力します（同数なら単語の辞書順）。ファイルがない場合は `error: file not found` を標準エラーに出して終了コード1で終わってください。",
     {"sample.txt": "the cat sat on the mat\nthe dog sat\n\n"},
     d("""
     set -e
     cd /work
     printf 'b a b\\nc a b\\n' > /tmp/t.txt
     test "$(python3 wc.py /tmp/t.txt)" = "lines=2 words=6 chars=12"
     test "$(python3 wc.py /tmp/t.txt --top 2)" = "$(printf 'lines=2 words=6 chars=12\\nb 3\\na 2')"
     set +e; python3 wc.py /nonexist 2>/tmp/e; c=$?; set -e
     test $c = 1; grep -q "error: file not found" /tmp/e
     """))

task("pagination", "paginate.py の paginate(items, page, per_page) は1ページ目から数える仕様ですが、テストが失敗しています。直してください。テストは `python3 test_paginate.py` で実行できます。テストは変更しないでください。",
     {"paginate.py": d("""
     def paginate(items, page, per_page):
         \"\"\"Return the items of the given page (1-based). Out-of-range pages return [].\"\"\"
         start = page * per_page
         end = start + per_page
         return items[start:end]

     def page_count(n, per_page):
         return n // per_page
     """),
      "test_paginate.py": d("""
     from paginate import paginate, page_count
     items = list(range(1, 11))
     assert paginate(items, 1, 3) == [1, 2, 3]
     assert paginate(items, 4, 3) == [10]
     assert paginate(items, 5, 3) == []
     assert page_count(10, 3) == 4
     assert page_count(9, 3) == 3
     print("ok")
     """)},
     d("""
     set -e
     cd /work
     cmp -s test_paginate.py /check/test_paginate.py
     python3 test_paginate.py
     python3 -c "from paginate import paginate,page_count; assert paginate([1,2],0,2)==[] and page_count(0,5)==0 and paginate(list(range(7)),2,4)==[4,5,6]"
     """), {"test_paginate.py": None})

task("dedupe", "names.txt から重複した行を取り除いて、最初に出てきた順番のまま names_unique.txt に保存してください。前後の空白は無視して同じ名前とみなし、出力では空白を取り除いてください。空行は捨ててください。",
     {"names.txt": "田中\n佐藤\n 田中\n鈴木\n\n佐藤 \n高橋\n鈴木\n"},
     'test "$(cat /work/names_unique.txt)" = "$(printf \'田中\\n佐藤\\n鈴木\\n高橋\')"\n')

task("import_fix", "`python3 -m app` を実行するとエラーになります。原因を調べて、`OK 42` と出力されるように直してください。",
     {"app/__init__.py": "", "app/__main__.py": "from app.core import run\nrun()\n",
      "app/core.py": "from app.helpers import compute\n\ndef run():\n    print('OK', compute())\n",
      "app/helper.py": "def compute():\n    return 6 * 7\n"},
     'cd /work && test "$(python3 -m app)" = "OK 42"\n')

task("emails", "users.json のユーザーのうち、メールアドレスの形式が正しくないもの（@が1つでない、@の前後が空、ドメインに.がない、空白を含む）のユーザーIDを、小さい順に1行ずつ invalid.txt に書いてください。",
     {"users.json": '[{"id": 7, "email": "a@example.com"}, {"id": 3, "email": "bad.example.com"}, {"id": 12, "email": "x@y"}, {"id": 5, "email": "two@@example.com"}, {"id": 9, "email": "ok.name+tag@mail.co.jp"}, {"id": 1, "email": "sp ace@example.com"}, {"id": 4, "email": "@example.com"}]\n'},
     'test "$(cat /work/invalid.txt)" = "$(printf \'1\\n3\\n4\\n5\\n12\')"\n')

task("robust", "total.py を実行すると KeyError で止まります。amount が欠けている行は飛ばして、残りの合計を出力するように直してください。ほかの動作は変えないでください。",
     {"total.py": "import json\nrows = json.load(open('orders.json'))\ntotal = 0\nfor r in rows:\n    total += r['amount']\nprint(f'total={total}')\n",
      "orders.json": '[{"id":1,"amount":100},{"id":2},{"id":3,"amount":250},{"id":4,"amount":null},{"id":5,"amount":50}]\n'},
     d("""
     cd /work && out=$(python3 total.py) && test "$out" = "total=400"
     """))

task("md_table", "scores.csv を Markdown の表に変換して scores.md に保存してください。1行目は見出し、2行目は区切り線 `|---|---|---|` です。行は合計点（english+math）の高い順に並べ、最後に「合計」列を追加してください（列: name, english, math, 合計）。",
     {"scores.csv": "name,english,math\nAoi,70,95\nRen,88,72\nYui,91,90\n"},
     d("""
     python3 -c "
     rows=[l.strip() for l in open('/work/scores.md') if l.strip()]
     norm=lambda l:[c.strip() for c in l.strip('|').split('|')]
     assert norm(rows[0])==['name','english','math','合計'],rows[0]
     assert set(rows[1].replace('|','').replace(':',''))<= {'-',' '},rows[1]
     assert [norm(r) for r in rows[2:]]==[['Yui','91','90','181'],['Aoi','70','95','165'],['Ren','88','72','160']],rows
     "
     """))

task("scaffold", "次の構成のディレクトリとファイルを作ってください。project/src/main.py（中身は print('hello')）、project/src/__init__.py（空）、project/tests/test_main.py（空）、project/README.md（1行目が「# project」）、project/.gitignore（__pycache__/ を含む）。",
     {}, d("""
     set -e
     cd /work/project
     test "$(python3 src/main.py)" = hello
     test -f src/__init__.py; test -f tests/test_main.py
     head -1 README.md | grep -qx "# project"
     grep -qx "__pycache__/" .gitignore
     """))

task("speed", "fib.py の fib(n) が遅すぎて fib(80) が終わりません。結果を変えずに高速化してください。`python3 fib.py 80` が1秒以内に終わるようにしてください。",
     {"fib.py": "import sys\n\ndef fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\n\nif __name__ == '__main__':\n    print(fib(int(sys.argv[1])))\n"},
     d("""
     cd /work && test "$(timeout 2 python3 fib.py 80)" = 23416728348467685 && test "$(python3 fib.py 10)" = 55 && python3 -c "from fib import fib; assert fib(0)==0 and fib(1)==1 and fib(90)==2880067194370816120"
     """))

task("merge_csv", "customers.csv と orders.csv を customer_id で結合して、merged.csv（列: order_id,customer_id,name,amount、order_id の昇順）を作ってください。対応する顧客がいない注文は name を空にしてください。",
     {"customers.csv": "customer_id,name\n1,Sato\n2,Ito\n4,Kato\n", "orders.csv": "order_id,customer_id,amount\n103,2,500\n101,1,1200\n104,3,800\n102,4,300\n"},
     d("""
     python3 -c "
     import csv
     rows=list(csv.reader(open('/work/merged.csv')))
     assert rows==[['order_id','customer_id','name','amount'],['101','1','Sato','1200'],['102','4','Kato','300'],['103','2','Ito','500'],['104','3','','800']],rows
     "
     """))

task("unused", "lib/ フォルダの Python ファイルで定義されている関数のうち、lib/ と main.py のどこからも呼ばれていないものの名前を、アルファベット順に1行ずつ unused.txt に書いてください。",
     {"main.py": "from lib.a import load, save\nfrom lib.b import clean\n\ndata = clean(load('x'))\nsave(data)\n",
      "lib/__init__.py": "",
      "lib/a.py": "def load(p):\n    return _read(p)\n\ndef _read(p):\n    return [p]\n\ndef save(d):\n    pass\n\ndef backup(d):\n    save(d)\n",
      "lib/b.py": "def clean(d):\n    return [strip(x) for x in d]\n\ndef strip(x):\n    return x.strip()\n\ndef normalize(x):\n    return x.lower()\n\ndef legacy_clean(d):\n    return d\n"},
     'test "$(cat /work/unused.txt)" = "$(printf \'backup\\nlegacy_clean\\nnormalize\')"\n')

task("stats_cli", "data.txt に1行1つ数値が入っています（空行やコメント行 # は無視）。平均・最小・最大・標準偏差（母標準偏差）を計算して、stats.json に {\"mean\":..., \"min\":..., \"max\":..., \"std\":...} の形で、どれも小数第3位で四捨五入して保存してください。",
     {"data.txt": "# measurements\n12.5\n7\n\n9.25\n# outlier removed\n15\n10.1\n"},
     d("""
     python3 -c "
     import json,statistics as s
     xs=[12.5,7,9.25,15,10.1]
     d=json.load(open('/work/stats.json'))
     exp={'mean':round(s.mean(xs),3),'min':7,'max':15,'std':round(s.pstdev(xs),3)}
     assert all(abs(float(d[k])-v)<1e-9 for k,v in exp.items()),(d,exp)
     "
     """))

import tasks_hard
tasks_hard.add(task)

if __name__ == "__main__":
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
    shutil.rmtree(root, ignore_errors=True)
    for tid, (ins, files, check, hidden) in T.items():
        base = os.path.join(root, tid)
        for rel, content in files.items():
            p = os.path.join(base, "files", rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(content.lstrip("\n"))
        os.makedirs(os.path.join(base, "check"), exist_ok=True)
        open(os.path.join(base, "task.md"), "w").write(ins + "\n")
        open(os.path.join(base, "check", "check.sh"), "w").write("#!/bin/bash\n" + check.lstrip("\n"))
        for rel, content in hidden.items():
            content = files[rel] if content is None else files.get(content, content)
            open(os.path.join(base, "check", rel), "w").write(content.lstrip("\n"))
    print(len(T), "tasks")
