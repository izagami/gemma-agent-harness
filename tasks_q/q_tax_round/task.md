invo/ は請求書 CSV から明細ごとの税抜額・税額と請求合計を出すツールです（計算規則は docs/SPEC.md）。経理から次の報告がありました。

「`python3 -m invo data/invoice_0412.csv` の結果が手計算と合わない。米（rice）やスタンプ（stamp）の税額がおかしく、値引きのある行は 1 円ずれることがある。値引きのない普通の商品は合っている。」

原因を調べて直してください。

- 明細行の金額（`invo.invoice.price_line` が返す net, tax, total）と請求合計が、どの請求書でも docs/SPEC.md の規則どおりになること。今回の CSV の行だけでなく、ほかの値段・数量・値引き率・カテゴリの書き方でも正しいこと。
- 出力の形式、コマンドの使い方、`price_line` / `load_csv` / `summarize` の呼び出し方と戻り値の形は変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
