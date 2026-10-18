# ts 仕様

`python3 -m ts [--config PATH] <コマンド> ...` で実行する作業時間記録ツール。

## 1. 共通（v1・実装済み）

- 出力は標準出力。エラーは標準エラーに1行 `error: <メッセージ>` を出す。
  - 実行時エラー（TsError）は終了コード 1。
  - 不正な引数値（UsageError）は終了コード 2。
  - 設定ファイルのエラー（ConfigError）は `error: config: <メッセージ>` で終了コード 2。
  - argparse 自身の使い方エラー（不明なコマンドなど）は argparse の既定動作（終了コード 2）。
- 時間の表示は `H:MM`（例: 125分 → `2:05`、0分 → `0:00`、600分 → `10:00`）。
- 時間の入力は `1h30m` / `90m` / `2h` / `1:30` / `1.5h`（分単位にならない小数や0分は `invalid duration: <入力>`）。

### コマンド

- `add DATE PROJECT DURATION [NOTE...]` — 記録を1件追加。DATE は `YYYY-MM-DD`（不正なら `invalid date: <入力>`）、
  PROJECT は英小文字・数字で始まり英小文字・数字・`_`・`-` からなる名前（不正なら `invalid project: <入力>`）。
  NOTE は残りの引数を空白1つでつないだもの。出力: `added: 2026-09-01 alpha 1:30`
- `list [--project P]` — 記録を日付順（同じ日付はファイル内の順）に1行ずつ: `日付  プロジェクト  H:MM  メモ`
  （区切りは空白2つ。メモが空なら行末の空白は付けない）。0件なら `no entries`。
- `total [--project P]` — プロジェクト名順に `プロジェクト  H:MM`、最後に `TOTAL  H:MM`。0件なら `no entries`。

### データファイル

タブ区切りで1行1件: `日付<TAB>プロジェクト<TAB>分<TAB>メモ`。ファイルが無ければ0件として扱う。

## 2. 設定ファイル（v1・実装済み）

```
# コメント（; で始まる行もコメント）
data = work.tsv
[project.alpha]
rate = 6000
name = "Alpha Corp"
```

- 1行に `キー = 値`。キー・値の前後の空白は除く。値が `"` で囲まれていれば外す。
- `[名前]` でセクションを始める。最初のセクションより前のキーはトップレベル（セクション名 `""`）。
- 同じセクションの同じキーが複数回出たら後のものが有効。
- エラー: `line N: bad section header` / `line N: expected key = value` / `line N: empty key`（N は行番号、1始まり）。
- トップレベルの `data` はデータファイルのパス（既定 `entries.tsv`）。相対パスは**メインの**設定ファイルがある
  ディレクトリ基準。設定ファイルを使わないときはカレントディレクトリ基準。
- 設定ファイルの選び方（v1）: `--config PATH` があればそれ（無ければ `error: config: not found: PATH`、終了コード 2）。
  なければカレントディレクトリの `ts.conf` があればそれ、それも無ければ設定なし（すべて既定値）。

## 3. v2 で追加する仕様（未実装）

### 3.1 設定ファイルの指定: 環境変数 TS_CONFIG

優先順位は `--config PATH` ＞ 環境変数 `TS_CONFIG` ＞ `./ts.conf` ＞ 設定なし。
`TS_CONFIG` が空文字列のときは未設定と同じ。`--config` が指定されたときは `TS_CONFIG` は見ない。
`--config` なしで `TS_CONFIG` で指定したファイルが無いときは `error: config: not found: <TS_CONFIG の値>`（終了コード 2）。
相対パスはカレントディレクトリ基準。

### 3.2 設定ファイルの取り込み: `@include`

- 前後の空白を除いた行が `@include` と等しいか、`@include` の直後に空白が続く行は取り込み指示。
  `@include` より後ろ（前後の空白を除く）がパス。パスが空（行が `@include` だけ）なら `line N: bad include`。
- 相対パスは、**その `@include` 行を含むファイル**があるディレクトリ基準。
- 取り込んだファイルの内容は、その位置に書かれていたのと同じように処理する（後に書かれた値が有効、というルールもそのまま）。
  ただし取り込まれたファイルは**トップレベルのセクションから始まり**、取り込みが終わったら、取り込み元のセクションに戻る。
- 取り込まれたファイルがさらに `@include` してよい。同じファイルを（循環にならない形で）複数回取り込むのは可。
- 取り込み先のファイルが無い: `line N: include not found: <書かれたパス>`。
- 循環（取り込み中のファイルを再び取り込む。自分自身を含む）: `line N: include cycle: <書かれたパス>`。
  ファイルの同一性は絶対パス（シンボリックリンク解決後）で判定する。
- エラーの位置表記: メインの設定ファイル内のエラーは従来どおり `line N: ...`。取り込まれたファイル内のエラーは
  `<そのファイルを取り込んだ @include 行に書かれたパス>: line N: ...`（N はそのファイル内の行番号。
  入れ子の場合も、エラーが起きたファイルを直接取り込んだ行のパスだけを付ける）。
  例: メインが `@include sub/a.conf`、a.conf の3行目が `@include b.conf`、b.conf の2行目が不正なら
  `error: config: b.conf: line 2: expected key = value`。a.conf の3行目の b.conf が存在しなければ
  `error: config: sub/a.conf: line 3: include not found: b.conf`。

### 3.3 コマンドの別名: `[alias]` セクション

```
[alias]
wk = list --project work
tw = total --project work
```

- コマンドの位置（全体オプション `--config PATH` / `--config=PATH` の後の最初の引数）が `[alias]` のキーと一致し、
  かつ組み込みコマンド名（`add` `list` `total` `invoice`）でなければ、その引数を値に置き換える。
  値は `shlex.split` で分割し、元のコマンド位置より後ろの引数はそのまま後ろにつなぐ。
  例: `ts wk` → `ts list --project work`、`ts tw --project x`（後ろの引数が付く）→ `ts total --project work --project x`。
- 展開は1回だけ（展開結果の先頭がさらに別名でも展開しない）。組み込みコマンドと同名の別名は無視する。
- 別名は、そのとき使われる設定ファイル（3.1 の優先順位）から読む。

### 3.4 請求書: `invoice PROJECT --month YYYY-MM`

- `--month` は必須。`YYYY-MM` 形式（月は01〜12）でなければ `invalid month: <入力>`（UsageError、終了コード 2）。
  PROJECT の形式チェックは add と同じ（`invalid project: <入力>`）。
- 設定:
  - `[project.<PROJECT>]` の `rate`: 1時間あたりの単価（円、0以上の整数）。キーが無ければ
    `error: no rate for project: <PROJECT>`（終了コード 1）。整数でない・負なら `bad rate for project: <PROJECT>`（ConfigError）。
  - `[project.<PROJECT>]` の `name`: 表示名。無ければ PROJECT。
  - `[invoice]` の `round_to`: 切り上げ単位（分、1以上の整数、既定 1）。不正なら `bad invoice.round_to`（ConfigError）。
- 上のエラー（`invalid month` などの引数エラー、`no rate`、`bad rate`、`bad invoice.round_to`）になるときは、標準出力には何も出さない。
- 対象は、そのプロジェクトの、日付がその月の記録。日付順（同じ日付はファイル内の順）。
- 各記録の請求分数 = 分数を `round_to` の倍数に切り上げた値。金額 = 請求分数 × rate ÷ 60 を1円未満四捨五入（0.5 は切り上げ）。
- 出力（区切りは空白2つ、金額は3桁カンマ区切り、メモが空なら行末の空白は付けない）:

```
Invoice: Alpha Corp (alpha) 2026-09
2026-09-01  1:30  9,000  design review
2026-09-03  0:15  1,500
Total: 1:45  10,500
```

  1行目は `Invoice: <表示名> (<PROJECT>) <YYYY-MM>`。最終行の時間は請求分数の合計、金額は各行の金額の合計。
  対象が0件なら1行目の後に `Total: 0:00  0` だけを出す。
