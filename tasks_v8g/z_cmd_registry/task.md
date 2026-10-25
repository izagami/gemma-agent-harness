invtool/ はCSVファイルで在庫を管理するCLIです（`python3 -m invtool [--data PATH] COMMAND ...`、コマンド一覧は `python3 -m invtool help`）。invtool/commands.py が約400行の1ファイルに全コマンドと共通処理を if/elif の連鎖で詰め込んでいて、コマンドを追加するたびに USAGE・SUMMARY・分岐の3か所を直す必要があります。これを「1コマンド1モジュール＋レジストリ」の構成にリファクタリングしてください。

要件:
1. invtool/registry.py を作り、デコレータ `command(name, usage, summary)` と例外 `CommandError(msg, code=1)` を定義する。コマンドは
   ```python
   from invtool.registry import command, CommandError

   @command("ping", usage="ping [WORD...]", summary="reply with pong")
   def ping(args, data):
       ...
       return 0
   ```
   の形で登録する（usage と summary はキーワード引数で渡される）。関数は args（コマンド名より後ろの引数の文字列リスト）と data（データファイルのパス）を受け取り、終了コード（int）を返す。標準出力・標準エラーへは普通に print / sys.stdout に書く。`CommandError(msg, code)` を送出すると、ディスパッチャが標準エラーに `error: <msg>` を出して code で終了する。
2. invtool/commands.py は削除し、代わりにパッケージ invtool/commands/ を作る。既存の12コマンド（add, adjust, export, help, history, list, low, move, remove, search, show, value）は、それぞれ invtool/commands/<コマンド名>.py に1つずつ置く。共通の補助関数は別モジュール（例: invtool/common.py）に置いてよい。
3. invtool/commands/ パッケージ内のモジュールのうち、名前が `_` で始まらないものはすべて自動的に import されて登録されること。ディスパッチャ（cli.py など）や help にコマンド名ごとの分岐・一覧を書かないこと。採点では invtool/commands/ に新しいモジュールを1つ置くだけで、そのコマンドが実行でき、`help` の一覧と `help <name>` にも現れることを確認します。
4. `help` の一覧は登録されているコマンドを名前のアルファベット順に、今と同じ形式（`  {name:<10}{summary}`）で出す。`help NAME` は `usage: invtool <usage>`、空行、summary の3行。各コマンドの使い方エラー（`error: usage: invtool <usage>`）もレジストリの usage を使う。
5. 動作は1バイトも変えないこと: すべてのコマンドについて、標準出力・標準エラー・終了コード、書き換えられるデータファイル・履歴ファイル（`<data>.history`）の中身が今の実装と同じであること（エラー、未知のコマンド、引数なしで実行したときの help、`--data=PATH` 形式なども含む）。
6. tests/ と data/ は変更しないこと。`python3 -m unittest discover -s tests` が通ること。標準ライブラリのみ。
