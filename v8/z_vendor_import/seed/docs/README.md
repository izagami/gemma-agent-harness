# custimport

複数の業者（vendor）から届く顧客リスト CSV を1つの顧客台帳（JSON）に統合するツール。

    python3 -m custimport import STORE.json data/vendor_a.csv data/vendor_b.csv ...
    python3 -m custimport list STORE.json [--source vendor_b]

- 業者名はファイル名（拡張子なし）。各行の出所は `業者名:業者側の顧客ID` として sources に記録する。
- 文字コードは UTF-8（BOM 付きのこともある）か Shift_JIS（cp932）。自動判定する。
- 列名は業者ごとに違う（reader.COLUMNS 参照）。列の順番も業者ごとに違う。
- 重複判定は custimport/dedupe.py の docstring のとおり（同じ出所 → skip、同じメール → merge、
  同じ氏名かつ同じ電話番号 → merge、それ以外 → new）。氏名・メール・電話の比較は normalize.*_key で行う。
- 同じファイルを何度取り込んでも台帳は変わらない（2回目以降はすべて skipped）。
- 台帳のフォーマットは custimport/store.py の docstring 参照。
