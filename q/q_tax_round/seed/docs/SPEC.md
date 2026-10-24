# 請求金額の計算規則

請求書 CSV の列: `item, category, unit_price, qty, discount_pct`（unit_price は円の整数、qty は整数、
discount_pct は値引き率 % で小数あり、空欄は 0）。

## 明細行ごとの計算（この順番で行う）

1. 金額 `gross = unit_price × qty`
2. 値引き額 `discount = gross × discount_pct ÷ 100` を 1 円未満四捨五入（0.5 円は切り上げ）
3. 税抜額 `net = gross − discount`
4. 税率: category が `food` なら 8%、`exempt` なら 0%、それ以外は 10%。
   category の大文字・小文字と前後の空白は区別しない（`Food`, ` FOOD ` も food）。
5. 税額 `tax = net × 税率` を 1 円未満四捨五入（0.5 円は切り上げ）
6. 行合計 `total = net + tax`

値引きは税抜の金額に対して行う（税込金額から値引きしない）。端数処理は必ず行ごとに行う。

## 請求書の合計

- `SUBTOTAL` = 各行の net の合計
- `TAX` = 各行の tax の合計（行ごとに丸めた税額を足す。合計してから丸め直さない）
- `TOTAL` = SUBTOTAL + TAX

## 出力（`python3 -m invo FILE`）

    <item> <net> <tax> <total>
    ...
    SUBTOTAL <n>
    TAX <n>
    TOTAL <n>

金額は 3 桁ごとに `,` を入れる。

## 例

- `pen,stationery,150,3,0` → gross 450, net 450, tax 45, total 495
- `rice,food,1980,1,5` → discount 99, net 1881, tax 150.48→150, total 2031
- `tea,food,325,2,0` → net 650, tax 52, total 702
- `cup,kitchen,1250,1,10` → discount 125, net 1125, tax 112.5→113, total 1238
