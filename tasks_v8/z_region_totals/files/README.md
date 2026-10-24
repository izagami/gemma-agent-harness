# salesrep — 月次売上レポート

    python3 report.py --month 2026-09                 # 地域別の売上・返金・純額
    python3 report.py --month 2026-09 --detail kanto  # 地域内の店舗別内訳も出す
    python3 report.py --month 2026-09 --out out/2026-09.txt

- 地域と所属店舗: config/base.ini + config/regions.d/*.ini（salesrep/config.py）
- 店舗マスタ・旧店舗ID: data/stores.csv, data/store_aliases.csv（salesrep/stores.py）
- POS から届く売上・返金: data/sales/, data/refunds/（salesrep/loaders.py, docs/data.md）

純額(net) = 売上(qty × unit_price の合計) − 返金額の合計。返金はその返金の日付の月に計上する。

テスト: `python3 -m unittest discover -s tests`
