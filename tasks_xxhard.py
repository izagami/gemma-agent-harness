"""Tier 4: longer tasks on realistic multi-file codebases (300-700 lines, 6+ files).

Seeds, hidden check files and reference solutions live in xxhard/<id>/{seed,hidden,ref}/;
this module holds the instructions and check scripts.
"""
import os
import textwrap

d = textwrap.dedent
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xxhard")


def tree(tid, sub):
    """{relative path: text} for every file under xxhard/<tid>/<sub>/ (no __pycache__)."""
    base = os.path.join(HERE, tid, sub)
    out = {}
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for f in sorted(files):
            if f.endswith(".pyc"):
                continue
            p = os.path.join(root, f)
            with open(p, encoding="utf-8") as fh:
                out[os.path.relpath(p, base)] = fh.read()
    return out


def add(task):
    task("y_library", d("""
    app/ は図書館の貸出管理APIのコアです（HTTPサーバはありません。`create_app(storage, today).handle(method, path, body)` が `Response(status, body)` を返します。docs/API.md と既存コードを読んでください）。貸出（loans）機能を追加してください。

    共通:
    - 貸出はストレージ（app.storage）の "loans" テーブルに保存すること。Storage(path) で作り直したアプリからも見えること。id はストレージが振る1からの連番。
    - 今日の日付は app.today()（create_app の today 引数）で取得し、日付はすべて `YYYY-MM-DD` 形式の文字列で返す。
    - 貸出の表現: {"id", "book_id", "member_id", "loaned_on", "due_on", "returned_on"} の6キーだけ。returned_on は未返却なら null（None）。「貸出中」とは returned_on が null のもの。
    - エラーの本文は既存と同じ形（404 は {"error": "not_found", "detail": ...}、409 は {"error": "conflict", "detail": ...}）。ルーターの既存の動作（パスが合ってメソッドが違えば 405 など）は変えない。

    エンドポイント:
    1. `POST /loans` 本文 {"book_id": 整数・必須, "member_id": 整数・必須, "days": 整数・省略可（1以上30以下、省略時14）}
       - 本文の検証は app/validation.py の validate を使い、既存のエンドポイントと同じ 400 の形式・メッセージにする（例: 未知のフィールドは "unknown field"、真偽値は "must be an integer"、本文が辞書でなければ {"_body": "must be an object"}）。
       - 検証が通ったら次の順に確認する: 本が存在しない → 404 detail "book not found"／会員が存在しない → 404 "member not found"／その本が貸出中 → 409 "book already on loan"／その会員の貸出中の件数が既に3件 → 409 "loan limit reached"。
       - 成功したら 201。loaned_on は今日、due_on は今日の days 日後、returned_on は null。
    2. `POST /loans/{id}/return`（本文なし）: 返却。200 で returned_on に今日を入れた貸出を返す。貸出が存在しない → 404 "loan not found"／返却済み → 409 "already returned"。
    3. `GET /members/{id}/loans`: 200 {"loans": [...]}。その会員の貸出すべて（返却済みも含む）を id 昇順。クエリ `?active=1` のときは貸出中のものだけ。会員が存在しない → 404 "member not found"。
    4. `GET /loans/overdue`: 200 {"loans": [...]}。貸出中で due_on が今日より前のもの（due_on が今日のものは含まない）を id 昇順。
    5. 既存の `DELETE /books/{id}`: その本が貸出中なら 409 "book on loan" を返し、削除しない。返却済みの貸出しかない本は従来どおり削除できる。

    新機能のテストを tests/test_loans.py に unittest で書いてください（テストメソッド5個以上）。`python3 -m unittest discover -s tests` がすべて通ること。既存のテストファイルは変更しないでください。
    """).strip(),
         tree("y_library", "seed"),
         d("""
         set -e
         cd /work
         for f in test_router test_storage test_books test_members; do cmp -s tests/$f.py /check/$f.py || { echo "tests/$f.py was modified"; exit 1; }; done
         test -f tests/test_loans.py
         python3 -m unittest discover -s tests -q
         n=$(python3 -c "import unittest; print(unittest.defaultTestLoader.loadTestsFromName('tests.test_loans').countTestCases())")
         test "$n" -ge 5 || { echo "only $n tests in tests/test_loans.py"; exit 1; }
         python3 /check/check_loans.py
         """), tree("y_library", "hidden"))

    task("y_tzreport", d("""
    events/ は、イベントログ（data/*.log）を読み込んで日次・週次の集計レポートを作るパッケージです（例: `python3 -m events daily 2026-03-03 data/tokyo.log data/nyc.log --zone UTC`）。結合テスト tests/test_integration.py が失敗しています。原因を調べて直してください。

    要件:
    - `python3 -m unittest discover -s tests` がすべて通ること。tests/ と data/ のファイルは変更しないこと。
    - daily_report / weekly_report は、イベントのタイムスタンプがどのUTCオフセットで書かれていても、どのタイムゾーン（固定オフセット）でレポートしても正しく集計すること。日の区切りはレポートのタイムゾーンでの0時、週は月曜〜日曜。
    - 何度呼んでも、どんな順番で呼んでも（例: 日次の後に同じ週の週次）、途中で store にイベントを追加した後でも、結果は「その時点で store にある全イベントから計算した値」と一致すること。
    - aggregate.daily_counts のキャッシュはなくさないこと: 同じ store・日・タイムゾーンで、その間に store へのイベント追加がなければ、2回目の呼び出しはキャッシュから返し、cache.stats() の "hits" が1増えること。
    - daily_counts が返した辞書を呼び出し側が書き換えても、その後の daily_counts やレポートの結果に影響しないこと。
    - レポートの出力形式（events/report.py の docstring のとおり）と、各関数・コマンドの呼び出し方は変えないこと。
    """).strip(),
         tree("y_tzreport", "seed"),
         d("""
         set -e
         cd /work
         for f in tests/test_units.py tests/test_integration.py data/tokyo.log data/nyc.log data/late.log; do cmp -s $f /check/$(basename $f) || { echo "$f was modified"; exit 1; }; done
         python3 -m unittest discover -s tests -q
         python3 /check/check_tz.py
         test "$(python3 -m events daily 2026-03-03 data/tokyo.log data/nyc.log --zone UTC)" = "$(printf '# 2026-03-03 (+00:00)\\nsearch        5\\nlogin         2\\nupload        2\\nTOTAL         9\\nusers: aoi, kai, mia, ren')"
         """), tree("y_tzreport", "hidden"))

    task("y_ledger_split", d("""
    ledger.py（約350行）には、お金・勘定科目・取引・元帳・CSV入出力・レポートが1ファイルに詰め込まれています。これを同じ名前のパッケージ ledger/ に分割してください。

    - 分割後の構成（各名前はそのモジュールの中で定義すること）:
      - ledger/errors.py: LedgerError
      - ledger/money.py: Money, parse_money, format_money, set_rate, clear_rates, convert, set_default_currency, get_default_currency
      - ledger/models.py: ACCOUNT_KINDS, Account, Posting, Transaction, normalize_account_name
      - ledger/book.py: Ledger
      - ledger/csvio.py: load_csv, dump_csv
      - ledger/reports.py: balance_report, monthly_report, trial_balance
      - ledger/__init__.py: 上の公開名をすべて再エクスポートし、`__all__` は元の ledger.py の `__all__` と同じ名前の集合にする。__init__.py に書いてよいのは import 文・docstring・`__all__ = [...]` だけ（関数やクラスの定義、その他の処理は書かない）。
    - 上の公開名は、パッケージ全体でそれぞれちょうど1か所で定義すること（同じ定義を複数のファイルにコピーしない）。`_` で始まる非公開の補助関数・変数はどのサブモジュールに置いてもよい。
    - 元の ledger.py は削除すること。
    - 動作は一切変えないこと: 公開関数・クラスの戻り値、出力される文字列、例外の種類とメッセージがすべて元と同じであること。為替レート（set_rate / clear_rates）と既定通貨（set_default_currency）は、パッケージ全体で共有される1つの状態のままにすること（どのモジュール経由で設定・参照しても同じ値が見える）。
    - summary.py・budget.py・data/・tests/ は変更しないこと。summary.py と budget.py は今と同じ出力で動き、`python3 -m unittest discover -s tests` が通ること。
    """).strip(),
         tree("y_ledger_split", "seed"),
         d("""
         set -eo pipefail
         cd /work
         for f in tests/test_ledger.py tests/test_reports.py summary.py budget.py data/journal.csv; do cmp -s $f /check/$(basename $f) || { echo "$f was modified"; exit 1; }; done
         test ! -e ledger.py || { echo "ledger.py still exists"; exit 1; }
         test -f ledger/__init__.py
         python3 -m unittest discover -s tests -q
         python3 summary.py | cmp - /check/expected_summary.txt
         python3 budget.py | cmp - /check/expected_budget.txt
         python3 /check/check_split.py
         """), tree("y_ledger_split", "hidden"))

    task("y_timesheet", d("""
    ts/ はコマンドラインの作業時間記録ツールです（`python3 -m ts ...`）。docs/SPEC.md の「1」「2」が現在の仕様（実装済み）で、「3. v2 で追加する仕様（未実装）」の 3.1〜3.4（環境変数 TS_CONFIG、設定ファイルの @include、[alias] による別名、invoice サブコマンド）がまだ実装されていません。SPEC.md のとおりにすべて実装してください。

    - v1 の動作は変えないこと。
    - `python3 -m unittest discover -s tests` が通ること。tests/ の既存ファイルは変更しないこと（テストの追加は自由）。
    - 採点では、別のディレクトリをカレントディレクトリにして `PYTHONPATH=<このフォルダ> python3 -m ts ...` の形で実行し、標準出力・標準エラー・終了コードを SPEC.md と照合します。
    """).strip(),
         tree("y_timesheet", "seed"),
         d("""
         set -e
         cd /work
         for f in test_cli test_config test_durations helpers; do cmp -s tests/$f.py /check/$f.py || { echo "tests/$f.py was modified"; exit 1; }; done
         python3 -m unittest discover -s tests -q
         python3 /check/check_ts.py /work
         """), tree("y_timesheet", "hidden"))

    task("y_perf_report", d("""
    `python3 gen.py sales.csv` で30万行の売上データを生成し、`python3 report.py sales.csv` で集計レポートを標準出力に出すプログラムがあります（salesrep/ パッケージ）。小さいデータなら動きますが、30万行では遅すぎて終わりません。出力を1バイトも変えずに高速化してください。

    - gen.py が生成する任意のデータ（--rows や --seed を変えたものも含む）に対して、report.py の標準出力が現在の実装とまったく同じであること。現在の実装は小さいデータ（例: `python3 gen.py /tmp/s.csv --rows 3000 --seed 11`）なら数秒で終わるので、比較に使えます。
    - 既定の30万行（`python3 gen.py FILE` = --rows 300000 --seed 1）に対して `python3 report.py FILE` が、採点環境（python:3.12-slim コンテナ）で10秒以内に終わること（参考: 素直に計算量を直せば数秒です）。
    - gen.py と tests/ は変更しないこと。`python3 -m unittest discover -s tests` が通ること。標準ライブラリのみ使うこと。
    """).strip(),
         tree("y_perf_report", "seed"),
         d("""
         set -eo pipefail
         cd /work
         for f in gen.py tests/test_report.py tests/data/fixture.csv tests/data/fixture_expected.txt; do cmp -s $f /check/$(basename $f) || { echo "$f was modified"; exit 1; }; done
         python3 -m unittest discover -s tests -q
         python3 /check/gen.py /tmp/s1.csv --rows 3000 --seed 11
         timeout 20 python3 report.py /tmp/s1.csv > /tmp/o1.txt; cmp /tmp/o1.txt /check/exp_s1.txt
         python3 /check/gen.py /tmp/s2.csv --rows 12000 --seed 5
         timeout 20 python3 report.py /tmp/s2.csv > /tmp/o2.txt; cmp /tmp/o2.txt /check/exp_s2.txt
         python3 /check/gen.py /tmp/big.csv
         s=$(date +%s%N)
         timeout 20 python3 report.py /tmp/big.csv > /tmp/ob.txt
         e=$(date +%s%N)
         cmp /tmp/ob.txt /check/exp_big.txt
         ms=$(( (e - s) / 1000000 )); echo "300k rows: ${ms} ms"
         test $ms -le 10000
         """), tree("y_perf_report", "hidden"))
