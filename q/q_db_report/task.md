このリポジトリは、ネットショップの売上レポートを SQLite のクエリで出すしくみです（スキーマは data/schema.sql、サンプル DB は data/shop.db、仕様は docs/REPORTS.md）。各レポートは queries/<名前>.sql の1つの SELECT 文で、`python3 report.py data/shop.db <名前>` で CSV として出力されます。

利用者からの報告: 「`customers_without_orders` が1人も出さない。まだ一度も買っていない人がいるはずなのに。`running_total` も、どの日も同じ数字が並んでいて、キャンセルした注文の分まで入っているように見える。」

次のことをしてください。

- 既存の `customers_without_orders` と `running_total` を docs/REPORTS.md のとおりに直すこと。
- まだない `monthly_category_revenue` と `top_customers_by_region` を docs/REPORTS.md のとおりに新しく作ること。
- 4つとも、サンプル DB だけでなく、同じスキーマのどんなデータ（ゲスト注文、キャンセルだけの顧客、販売終了の商品、地域未登録の顧客、売上のない月、同額の顧客など）でも、列名・列の順番・値・行の順番が docs/REPORTS.md のとおりになること。
- 各ファイルは1つの SELECT 文（WITH 句は可）だけにすること。report.py は変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
