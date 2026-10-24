feed/ は、投稿をページ単位で一覧表示するツールです（仕様は docs/SPEC.md）。

利用者からの報告: 「`python3 -m feed data/posts.jsonl --limit 5` で最初のページを見ると、5件より少ないのに `next: -` になっていて、続きが見られない。別のデータでは、`next` をたどって全ページを見ても、一部の投稿が一度も出てこないことがある。」

原因を調べて直してください。

- どのデータ・どの `--limit`・`--author` の組み合わせでも、`next` をたどると条件に合う投稿がすべて、ちょうど1回ずつ、docs/SPEC.md の順番で出てくること。
- ページの件数と `next` の有無が docs/SPEC.md のとおりになること（最後のページでは `next: -`）。
- コマンドと `feed.paginate.page()` の使い方、出力の形式は変えないこと。
- data/ と tests/ の既存ファイルは変更しないこと（テストの追加は自由）。`python3 -m unittest discover -s tests` が通ること。
