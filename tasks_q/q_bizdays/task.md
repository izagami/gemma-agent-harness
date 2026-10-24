bizcal/ は、納期や支払期日を営業日で計算するツールです（仕様は docs/SPEC.md、休日は data/holidays.txt）。

利用者からの報告: 「`python3 -m bizcal add 2026-12-25 10` が 2027-01-13 を返すが、年始休業を考えると明らかに早すぎる。また、`python3 -m bizcal add 2027-01-15 -5` のようにマイナスの日数を指定すると、日付がまったく動かない。」

原因を調べて直してください。

- 直した後、`add` と `count`（ライブラリの add_business_days / count_business_days も同じ）が、どの日付・どの日数（正・負・0、年をまたぐ場合を含む）でも docs/SPEC.md のとおりの結果になること。
- 休日は data/holidays.txt に書かれたものだけを使うこと。土日に重なる休日で何かがずれることはないこと。
- コマンドの使い方、出力の形式、エラーメッセージと終了コードは変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
