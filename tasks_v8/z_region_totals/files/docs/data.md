# POS データの形式

POS ベンダーごとに data/sales/<pos>/ と data/refunds/<pos>/ にファイルが届く（regista: 関東・中部と関西の一部、posmate: 関西の K05 以降）。

sales/<pos>/YYYY-MM.csv

    date,store,sku,qty,unit_price
    2026-09-01,T01,SKU-1234,3,480

refunds/<pos>/YYYY-MM.csv（そのファイルが出力された月。前月分の返金が遅れて入ることがある）

    date,store,amount,reason
    2026-09-02,K03,960,返品

- date は YYYY-MM-DD。
- store は店舗ID。番号変更された店舗は、旧ID が data/store_aliases.csv にある。
- 金額はすべて税込の円（整数）。
