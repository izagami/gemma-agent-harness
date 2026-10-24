物流課の Excel マクロ（`vba/Module1.bas` の「在庫評価表」）を Python に移植してください。Excel を使わずに棚卸のたびにサーバーで動かしたいので、シート「入出庫」と「品目」を CSV で保存したファイルから、マクロと同じ `zaiko_yyyymmdd.txt` を作れるようにします。シートと使い方の説明は docs/README.md にあります。

- `/work/zaiko_hyoka.py` を作り、`python3 zaiko_hyoka.py <入出庫の CSV> <品目の CSV> <基準日 yyyy/mm/dd> <出力ファイル>` で動くようにすること。CSV は Excel の「CSV (コンマ区切り)」形式（data/nyushukko.csv と data/hinmoku.csv を参照）。
- 出力ファイルは、マクロが同じシートから作るファイルと 1 バイトも違わないこと（並び順、数値の表記、文字コード、改行を含む）。マクロがファイルを作らずに終わる場合は、出力ファイルも作らないこと。今回の 4 月末分（`python3 zaiko_hyoka.py data/nyushukko.csv data/hinmoku.csv 2026/04/30 zaiko_20260430.txt` が out/expected_zaiko_20260430.txt と一致すること）だけでなく、ほかの基準日・ほかの明細でもマクロと同じ結果になること。
- 標準ライブラリだけで書くこと。
- vba/ data/ out/ の既存ファイルは変更しないこと。
