buildorder/ は、依存関係ファイルからビルドの順番を出すツールです（仕様は docs/SPEC.md）。

利用者からの報告: 「`python3 -m buildorder data/project.deps` を実行すると `error: cycle: tests` と出て終了する。このファイルに循環はないはず。それと、別のプロジェクトでは、出てくる順番が docs/SPEC.md の規則（ビルドできるものが複数あるときはアルファベット順で小さいもの）と違うことがある。」

原因を調べて直してください。

- data/project.deps で正しいビルド順が出ること。
- どんな依存関係ファイルでも、出力・エラーメッセージ・終了コードが docs/SPEC.md のとおりになること（対象 TARGET を指定した場合、本当に循環がある場合のメッセージも含む）。
- コマンドの使い方は変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
