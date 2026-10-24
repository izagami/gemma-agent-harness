durfmt/ は、ジョブスケジューラーの設定ファイルで使う「1h30m」のような時間の長さを読み書きするライブラリとコマンドです（仕様は docs/SPEC.md）。

利用者からの報告: 「設定に `1 h 30 m` と書くと `invalid duration` エラーになる。また `python3 -m durfmt format 3600` が `1h` ではなく `1h0m0s` を出す。」

原因を調べて直してください。

- 直した後、parse_duration / format_duration とコマンド（parse・format）が、docs/SPEC.md に書かれたすべての規則（空白の位置、小数、単位の順番と重複、秒にならない値、エラーメッセージ、0 の扱い、往復しても値が変わらないこと）のとおりに動くこと。
- 関数の呼び出し方、コマンドの使い方、出力の形式、エラーメッセージと終了コードは変えないこと。
- tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
