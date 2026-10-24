経理課の Excel マクロ（`vba/Module1.bas` の「月次売上集計」）を Python に移植してください。Excel を使わずにサーバーで毎月動かしたいので、シート「売上明細」を CSV で保存したファイルから、マクロと同じ `report_yyyymm.txt` を作れるようにします。使い方とデータの説明は docs/README.md にあります。

- `/work/sales_report.py` を作り、`python3 sales_report.py <売上明細の CSV> <対象月 yyyymm> <出力ファイル>` で動くようにすること。CSV は Excel の「CSV (コンマ区切り)」形式（docs/README.md と data/uriage_meisai.csv を参照）。
- 出力ファイルは、マクロが同じシートから作るファイルと 1 バイトも違わないこと（並び順、数値の表記、文字コード、改行を含む）。今回の 4 月分（`python3 sales_report.py data/uriage_meisai.csv 202604 report_202604.txt` が out/expected_report_202604.txt と一致すること）だけでなく、ほかの月・ほかの明細でもマクロと同じ結果になること。
- 標準ライブラリだけで書くこと。
- vba/ data/ out/ の既存ファイルは変更しないこと。
