vsort/ はリリースタグを Semantic Versioning の規則で並べ替え・比較するツールです（規則とコマンドは docs/SPEC.md）。リリース担当から次の報告がありました。

「`python3 -m vsort sort data/releases.txt` で 1.4.0-rc.10 が 1.4.0-rc.2 より前に出る。CI が付けた 1.4.0+build-7 は不正なバージョンと言われて捨てられる。`max` も、同じ優先順位のタグが複数あるときに選ばれるものが仕様と違う気がする。」

原因を調べて直してください。

- 解析（`vsort.parse.parse`）、比較（`vsort.compare.compare`）、`sort` / `max` / `cmp` の各コマンドが、docs/SPEC.md の規則どおりに動くこと。今回のファイルだけでなく、どんなバージョン文字列でも正しいこと（不正な文字列はすべて不正と判定すること）。
- 出力の形式、終了コード、コマンドの使い方、関数の呼び出し方は変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
