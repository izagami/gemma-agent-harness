# ルールファイルの書式（config/rules.nft）

nftables を簡単にした独自の書式です。1行に1つの定義を書きます。`#` から行末まではコメント、空行は無視します。

## 集合（set）

    set <名前> = <要素>[, <要素> ...]

要素は IPv4/IPv6 のアドレス、または CIDR（`10.0.10.0/24`、`2001:db8:10::/64`）。ルールの中では `@<名前>` で参照します。

## チェイン（chain）

    chain <名前> family <ip|ip6> hook <input|output> policy <accept|drop>

続く `rule` 行は、次の `chain` 行が現れるまでこのチェインに属します。
同じ family と hook の組み合わせに、チェインは1つまでです。**family と hook の組み合わせにチェインが1つもないとき、そのパケットは一切絞り込まれず、すべて accept されます**（nftables と同じ）。

## ルール（rule）

    rule <ID>: [条件 ...] <判定>

- 判定: `accept`、`drop`、`reject`（reject は drop と同じく通さない。応答を返すかどうかの違いだけ）。
- ルールは上から順に評価し、**最初に条件がすべて当てはまったルールの判定で決まります**（先勝ち）。どのルールにも当てはまらなければ、チェインの policy で決まります。
- 条件（すべて AND）:
  - `iif <名前>` / `oif <名前>`: 受信／送信インターフェース（`lo`、`eth0`）。
  - `proto <tcp|udp|icmp|icmpv6>`
  - `saddr <アドレス|CIDR|@集合>` / `daddr ...`: 送信元／宛先アドレス。
  - `sport <ポート>` / `dport <ポート>`: ポートは `22`、`{80,443}`、`8000-8100` のどれか。ポートを持たないパケット（icmp など）には当てはまりません。
  - `ct <状態>[,<状態>...]`: 接続の状態 `new`、`established`、`related`、`invalid` のどれか1つでも一致すれば当てはまります。
  - `limit <N>/second`: このルールのほかの条件がすべて当てはまったパケットを、時刻の秒（整数部分）ごとに N 個まで当てはめます。N 個を超えた分は「当てはまらない」として次のルールへ進みます。
- `counter`、`log` は書いてもよいが、判定には影響しません。

## 道具

`python3 tools/fwsim.py config/rules.nft packets.txt` で、パケットの一覧に判定をつけて表示します（書式は fwsim.py の docstring）。
