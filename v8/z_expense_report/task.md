exp/ は家計簿（経費記録）のコマンドラインツールです（`python3 -m exp [--db PATH] add/list/import ...`。使い方は exp/cli.py の docstring）。次の2つを実装してください。

A. 月次レポート `python3 -m exp [--db PATH] report --month YYYY-MM [--by category|day] [--format text|csv|json] [--rates PATH]`
1. 対象はその月（1日〜月末）の日付の経費すべて。ストアの場所の決め方（--db、環境変数 EXP_DB、既定 ./expenses.json）は他のサブコマンドと同じ。
2. 各経費を円に換算する: 金額 × レート（レートファイルの "rates"。1通貨単位が何円か、文字列の10進数）を、経費1件ごとに円未満四捨五入（0.5 は切り上げ。Decimal で計算し float は使わない）してから合計する。
3. レートファイルの既定は、このプロジェクトの data/rates.json（exp パッケージの親フォルダにある data/rates.json。カレントディレクトリがどこでもこのファイルを使う）。--rates を指定したときはそのパス（相対パスはカレントディレクトリからの相対）。
4. --by category（既定）は分類ごと、--by day は日付（YYYY-MM-DD）ごとにまとめ、各グループの件数と円の合計を出す。
5. 並び順: category のときは合計の大きい順、合計が同じならキーの昇順（Python の文字列比較）。day のときは日付の昇順。
6. text（既定）の形式: 1行目 `Report YYYY-MM (by category)`（day なら `(by day)`）、次にグループごとに1行、次に `-` を22個並べた行、最後に合計行。グループ行と合計行は Python の `f"{key:<12}{total:>10,}  ({count})"` と同じ形（キーを12文字で左詰め、金額は3桁ごとにカンマを入れて10文字で右詰め、空白2つ、括弧付きの件数）で、合計行のキーは `TOTAL`。例:
   ```
   Report 2026-09 (by category)
   books            5,327  (1)
   food             3,871  (4)
   transport        1,200  (1)
   ----------------------
   TOTAL           10,398  (6)
   ```
7. csv の形式: ヘッダ `key,count,total_jpy`、続いてグループごとに1行（並び順は 5 と同じ、金額はカンマなしの整数、合計行なし、改行は \n、Python の csv モジュールの既定のクォート）。
8. json の形式: `{"month": "YYYY-MM", "by": "category"|"day", "count": 全件数, "total_jpy": 全合計, "groups": [{"key": ..., "count": ..., "total_jpy": ...}, ...]}`（groups の並び順は 5 と同じ、数値は整数）。
9. その月の経費が0件のとき: text は `no expenses in YYYY-MM` の1行、csv はヘッダ行だけ、json は count 0・total_jpy 0・groups []。いずれも終了コード 0。
10. --month が `YYYY-MM`（月は01〜12）の形でなければ、標準出力には何も出さず、標準エラーに `error: invalid month: <指定された値>` の1行を出して終了コード 2。
11. 対象の月の経費にレートファイルにない通貨があれば、標準エラーに `error: no rate for <通貨コード>` を出して終了コード 1（標準出力には何も出さない）。レートファイルが読めないときも `error: ` で始まる1行を標準エラーに出して終了コード 1。

B. `import` を冪等にする
12. 同じ CSV を何度 import しても、2回目以降は経費が増えないこと。同一かどうかは（日付, 金額の数値, 通貨, 分類, メモ）を、既存の add/import と同じ正規化（分類は小文字化・前後の空白除去、通貨は大文字・空なら JPY、金額は `1,200` と `1200.00` と `1200` が同じ値）をした後で比べる。add で登録した経費も比較の対象。
13. 同じキーの行が CSV の中に n 行、ストアに既に m 件あるときは、n−m 件（0未満なら0件）だけ追加する（同じ日に同じ金額のランチを2回、のような正当な重複を消さないため）。
14. 出力は、スキップがなければ今までどおり `imported N`、1件以上スキップしたら `imported N, skipped M`。CSV に不正な行があるときは今までどおり何も追加しない。

その他: tests/ の既存ファイルと data/ のファイルは変更しないこと。新機能のテストを tests/test_report.py に書き（3個以上）、`python3 -m unittest discover -s tests` が通ること。採点では別のディレクトリをカレントディレクトリにして `PYTHONPATH=<このフォルダ> python3 -m exp ...` の形で実行し、標準出力・標準エラー・終了コードを確認します。
