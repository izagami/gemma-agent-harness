情報システム課の Excel マクロ（`vba/Module1.bas` の「顧客マスタ整形」）を Python に移植してください。Excel のない取込サーバーで動かしたいので、シート「顧客」を CSV で保存したファイルから、マクロと同じ `customers_load.txt` を作れるようにします。シートとファイルの説明は docs/README.md にあります。

- `/work/customer_clean.py` を作り、`python3 customer_clean.py <顧客シートの CSV> <出力ファイル>` で動くようにすること。CSV は Excel の「CSV (コンマ区切り)」形式（data/kokyaku.csv を参照）。
- 出力ファイルは、マクロが同じシートから作るファイルと 1 バイトも違わないこと（文字の変換、区切り、文字コード、改行を含む）。今回のシート（`python3 customer_clean.py data/kokyaku.csv customers_load.txt` が out/expected_customers_load.txt と一致すること）だけでなく、営業が今後入力するどんな値でもマクロと同じ結果になること。
- 標準ライブラリだけで書くこと。
- vba/ data/ out/ の既存ファイルは変更しないこと。
