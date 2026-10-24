# 経費申請の一括登録

- app/: 経費申請システム(社内 Web 画面)をまねたもの。`python3 app/server.py --store /tmp/store.json` で
  http://127.0.0.1:8766 に起動(ユーザー demo / パスワード demo123)。登録された申請は --store の JSON に保存される。
  本番は応答が遅く、速さも毎回違う(`--delay 300,2000` などで再現できる)。
- automation/submit.py: CSV の申請を画面から1件ずつ登録するスクリプト(使い方はファイル先頭の説明)。
- data/applications.csv: 登録する申請の例。
