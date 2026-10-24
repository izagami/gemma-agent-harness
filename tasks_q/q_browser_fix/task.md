automation/submit.py は、CSV に並んだ経費申請を、社内の経費申請システム(app/ はそれをまねたもの。docs/README.md)の画面から1件ずつ登録するスクリプトです。

総務からの報告: 「先週システムの画面が更新されてから、`python3 automation/submit.py data/applications.csv` が動かなくなった。見た目は前とほとんど同じなのに、しばらく止まったあと `playwright._impl._errors.TimeoutError: Page.fill: Timeout 5000ms exceeded.` で落ちる。前は動いていたが、本番が混んでいる日はときどき失敗していた。」

原因を調べて直してください。

- CSV の全行が、CSV の内容どおりに、ちょうど1回ずつ登録されること(二重登録や登録漏れがないこと)。
- 本番のように応答が遅く、速さが毎回違うときでも正しく動くこと。
- 使い方(引数、環境変数 APP_URL / APP_USER / APP_PASS)と表示の形式(1件ごとに `OK <氏名> <申請番号>`、最後に `registered N`)は変えないこと。
- app/ と data/ の既存ファイルは変更しないこと。
