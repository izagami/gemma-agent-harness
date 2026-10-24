財務課の Excel マクロ（`vba/Module1.bas` の「支払予定表」）を Python に移植してください。資金繰りの集計を Excel なしで自動化したいので、シート「請求」を CSV で保存したファイルから、マクロと同じ `pay_schedule.txt` を作れるようにします。シートとファイルの説明は docs/README.md にあります。

- `/work/pay_schedule.py` を作り、`python3 pay_schedule.py <請求シートの CSV> <出力ファイル>` で動くようにすること。CSV は Excel の「CSV (コンマ区切り)」形式（data/seikyu.csv を参照）。
- 出力ファイルは、マクロが同じシートから作るファイルと 1 バイトも違わないこと（日付の計算、表記、文字コード、改行を含む）。今回のシート（`python3 pay_schedule.py data/seikyu.csv pay_schedule.txt` が out/expected_pay_schedule.txt と一致すること）だけでなく、ほかの請求日・支払条件・金額でもマクロと同じ結果になること。
- 標準ライブラリだけで書くこと。
- vba/ data/ out/ の既存ファイルは変更しないこと。
