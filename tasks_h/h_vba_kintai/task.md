総務課の Excel マクロ（`vba/Module1.bas` の「勤怠集計」）を Python に移植してください。Excel のない給与サーバーで毎月動かしたいので、シート「勤怠」を CSV で保存したファイルから、マクロと同じ `kyuyo_yyyymm.txt` を作れるようにします。シートと使い方の説明は docs/README.md にあります。

- `/work/kintai.py` を作り、`python3 kintai.py <勤怠シートの CSV> <支給月 yyyymm> <出力ファイル>` で動くようにすること。CSV は Excel の「CSV (コンマ区切り)」形式（data/kintai.csv を参照）。
- 出力ファイルは、マクロが同じシートから作るファイルと 1 バイトも違わないこと（並び順、日付・時刻・金額の表記、文字コード、改行を含む）。マクロがファイルを作らずに終わる場合は、出力ファイルも作らないこと。今回の 4 月支給分（`python3 kintai.py data/kintai.csv 202604 kyuyo_202604.txt` が out/expected_kyuyo_202604.txt と一致すること）だけでなく、ほかの月・ほかの勤怠でもマクロと同じ結果になること。
- 標準ライブラリだけで書くこと。
- vba/ data/ out/ の既存ファイルは変更しないこと。
