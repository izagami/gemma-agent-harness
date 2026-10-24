custimport/ は、複数の業者から届く顧客リスト CSV を1つの顧客台帳（JSON）に統合するツールです（使い方と仕様は docs/README.md と各モジュールの docstring）。

利用者からの報告: 「`python3 -m custimport import store.json data/vendor_a.csv data/vendor_b.csv data/vendor_c.csv` を実行すると、vendor_c.csv から入った一部の顧客名が文字化けし、vendor_a / vendor_b に既にいる同じ顧客が重複して登録される。vendor_a.csv と vendor_b.csv だけなら問題ない。」

原因を調べて直してください。

- 直した後、上のコマンドで3ファイルを取り込むと、文字化けも重複もなく docs/README.md の重複判定ルールどおりの台帳になること。
- 今回の vendor_c.csv だけでなく、今後届く他の業者のファイル（UTF-8 の BOM あり／なし、cp932、列の順番や列名の違い、ファイルの大きさの違い）でも同じ問題が起きないようにすること。
- 同じファイルを何度取り込んでも台帳が変わらないこと（2回目以降はすべて skipped）、cp932 のファイルがこれまでどおり読めることは維持すること。
- コマンドの使い方、出力の形式（`<業者名>: encoding=... added=N merged=N skipped=N`）、台帳のフォーマットは変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
