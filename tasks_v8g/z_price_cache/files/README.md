# shop

卸売窓口の受注・価格計算サービス（メモリ内）。

- shop/catalog.py   商品と定価（価格表は日中に差し替えられることがある: Catalog.reload）
- shop/customers.py 顧客と会員ランク（standard / silver / gold / platinum）
- shop/rules.py     ランク・商品カテゴリ別の割引率
- shop/pricing.py   顧客別の単価（メモ化あり）
- shop/orders.py    受注。単価は受注した時点の価格・ランクで確定する
- shop/report.py    日次レポート
- shop/service.py   組み立てとシナリオ（JSON lines）の再生

    python3 -m shop replay data data/may01.jsonl
