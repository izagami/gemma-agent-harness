notes/ は sqlite3 を使った小さなメモ管理ツールです（`python3 -m notes --db PATH COMMAND ...`、README.md 参照）。今はスキーマを db.SCHEMA で直接作っていますが、migrations/ のSQLファイルでスキーマを管理するマイグレーション機能を追加してください。

コマンド: `python3 -m notes [--db PATH] migrate [status] [--dir DIR] [--dry-run] [--to N]`（DBの場所は既存と同じく --db → 環境変数 NOTES_DB → ./notes.db の順）

1. マイグレーションファイルは DIR 内の、名前が正規表現 `^([0-9]+)_([a-z0-9_]+)\.sql$` に完全一致するファイル。バージョンは先頭の数字を整数にしたもの（`2_x.sql` と `002_x.sql` はどちらもバージョン2）、名前は `_` の後ろの部分。一致しないファイルは無視する。バージョンは数値の昇順で扱う（2 は 10 より前）。
2. `--dir` の既定は、カレントディレクトリではなく、このプロジェクトの migrations/ ディレクトリ（notes パッケージと同じ階層にある migrations/）。別のディレクトリから `PYTHONPATH=<プロジェクト> python3 -m notes ...` で実行しても同じ場所を使うこと。
3. 適用済みの記録はDB内のテーブル `schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL)`。checksum はファイルの中身（バイト列）の sha256 の16進小文字。
4. 出力ではバージョンを常に3桁ゼロ埋め（`%03d`）で表す。`migrate` は未適用のものを昇順に1つずつ適用し、適用し終えるごとに標準出力に `apply 002 add_pinned` の形の行を出す。適用するものが無ければ `up to date` の1行だけ。終了コード0。
5. 各マイグレーションは、そのSQLと schema_migrations への記録をまとめて1つのトランザクションで行う。SQLの途中でエラーが起きたら、そのマイグレーションの変更（途中まで作られたテーブル等も含む）と記録をすべて取り消し、標準エラーに `error: migration 003 add_bad failed: <sqliteのエラーメッセージ>` を出して終了コード1。同じ実行で先に適用できたものは適用済みのまま残す。それ以降は適用しない。
6. `--to N`: バージョン N まで（N を含む）だけ適用する。N が DIR に存在する最大バージョンより大きければ `error: unknown target version 099`（N を3桁ゼロ埋め）で終了コード2。N が現在のバージョン以下なら `up to date`。
7. `--dry-run`: 何を行うかを `would apply 002 add_pinned`（後述のベースラインは `would baseline 001 initial`）の形で出すだけで、DBは一切変更しない。DBファイルが存在しなければ作成もしない（ファイルが無い＝何も適用されていない扱い）。何も無ければ `up to date`。
8. `migrate status`: DIR の全マイグレーションを昇順に、適用済みなら `[x] 001 initial`、未適用なら `[ ] 002 add_pinned` の形で1行ずつ出し、最後に `current: 002`（適用済みの最大バージョン。何も無ければ `current: none`）。DBは変更せず、DBファイルが無ければ作成もしない。
9. 検証（migrate・--dry-run・status のすべてで、何かを変更する前に次の順で確認する。エラー時はDBに一切変更を加えず、DBファイルが無ければ作成もしない。メッセージは標準エラーに1行）:
   - 同じバージョンのファイルが2つ以上 → `error: duplicate migration version 002`、終了コード2
   - DIR のバージョンが1から連続していない → 最小の欠番について `error: missing migration version 003`、終了コード2
   - DBに記録された適用済みバージョンのファイルが DIR に無い → 最小のものについて `error: applied migration 004 not found`、終了コード3
   - 適用済みのファイルの中身が変わっている（checksum 不一致） → 最小のものについて `error: checksum mismatch for 002 add_pinned`、終了コード3
   複数のエラーがあるときは上に書いた順で最初のものだけを出す。
10. ベースライン: 旧バージョンの `init` で作られたDB（notes テーブルはあるが schema_migrations テーブルが無い）は、バージョン1が適用済みとみなす。`migrate` では schema_migrations を作ってバージョン1（名前とchecksumは DIR のバージョン1のファイルのもの）を記録し、001 のSQLは実行せずに `baseline 001 initial` を出してから残りを通常どおり適用する。`--dry-run` は `would baseline 001 initial`、`status` は `[x] 001 initial` として表示する（どちらもDBは変更しない）。既存のメモは消えないこと。
11. `init` コマンドはマイグレーションで実装し直す: 既定の migrations/ ディレクトリで `migrate` と同じこと（ベースラインを含む）を最新まで行い、標準出力は今までどおり `initialized PATH` の1行だけ。エラー時のメッセージと終了コードは migrate と同じ。db.SCHEMA によるスキーマ作成は使わないこと。
12. 既存のコマンド（add / list / show / delete）の動作は変えないこと。tests/ の既存ファイルと migrations/ の既存ファイル（001_initial.sql, 002_add_pinned.sql）は変更しないこと。`python3 -m unittest discover -s tests` が通ること。
