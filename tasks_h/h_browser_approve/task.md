automation/approve.py は、CSV に並んだ購買申請を、社内の承認システム(app/ はそれをまねたもの。docs/README.md)の画面から1件ずつ承認するスクリプトです。

経理部からの報告: 「承認システムの画面が新しくなってから、`python3 automation/approve.py data/approve_list.csv` が動かなくなった。しばらく止まったあと `playwright._impl._errors.TimeoutError: Page.fill: Timeout 5000ms exceeded.` で落ちる。そういえば前から、システムが混んでいる日には、リストにない申請が承認されていたり、監査から『同じ申請に承認操作が2回記録されている』『コメントに変な引用符が付いている』と言われたりしていた。」

原因を調べて直してください。

- CSV の申請のうち申請中のものだけが、CSV のコメントどおりに、ちょうど1回の承認操作で承認されること。それ以外の申請には承認操作をしないこと。
- 本番のように申請が多く、応答が遅くて速さが毎回違うときでも正しく動くこと。
- 使い方(引数、環境変数 APP_URL / APP_USER / APP_PASS)と表示の形式(`APPROVED <申請番号>` / `SKIP <申請番号> <状態>`、最後に `approved N skipped M`)は変えないこと。
- app/ と data/ の既存ファイルは変更しないこと。
