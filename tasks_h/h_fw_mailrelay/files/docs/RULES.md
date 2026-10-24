# ルールファイルの書式（config/firewall.rules）

iptables-save を簡単にした独自の書式です。1行に1つの定義を書きます。`#` から行末まではコメント、空行は無視します。

## アドレス集合（ipset）

    ipset <名前> <要素>[,<要素> ...]

要素は IPv4/IPv6 のアドレス、または CIDR（`10.40.0.0/16`、`2001:db8:40::/48`）。ルールの中では `@<名前>` で参照します。
集合はファイル全体で共通です（どのテーブルからでも参照できます）。

## テーブル（family ごと）

    *ip4
    *ip6

`*ip4` は IPv4、`*ip6` は IPv6 のテーブルの始まりです。次の `*...` 行が現れるまで、そのテーブルの定義が続きます。
各テーブルは1回だけ書けます。最後の `COMMIT` 行は書いても書かなくてもかまいません（無視されます）。

## チェイン（hook ごと）

    :INPUT <ACCEPT|DROP>
    :OUTPUT <ACCEPT|DROP>

テーブルの中で、受信（INPUT）・送信（OUTPUT）のチェインを宣言し、既定の判定（policy）を決めます。
チェインの宣言は、そのチェインのルールより前に書く必要があります。

**テーブルが無い、またはテーブルの中にそのチェインの宣言が無いとき、その family・方向のパケットは一切絞り込まれず、すべて ACCEPT されます**（本物の iptables でチェインが空のときと同じ）。

## ルール

    [<ID>] -A <INPUT|OUTPUT> [条件 ...] -j <ACCEPT|DROP|REJECT>

- ID はファイル全体で一意な名前（例 `in4-03`）。
- 判定: `ACCEPT`、`DROP`、`REJECT`（REJECT は DROP と同じく通さない。応答を返すかどうかの違いだけ）。
- ルールはチェインの中で上から順に評価し、**最初に条件がすべて当てはまったルールの判定で決まります**（先勝ち。本物の iptables と同じ）。どのルールにも当てはまらなければ、チェインの policy で決まります。
- 条件（すべて AND）:
  - `-i <名前>` / `-o <名前>`: 受信／送信インターフェース（`lo`、`eth0`）。
  - `-p <tcp|udp|icmp|ipv6-icmp>`: プロトコル。**IPv4 の ICMP は `icmp`、IPv6 の ICMPv6 は `ipv6-icmp`** です。`-p icmp` は IPv6 のパケットには当てはまりません。
  - `-s <アドレス|CIDR|@集合>` / `-d ...`: 送信元／宛先アドレス。family の違うアドレス（IPv6 パケットに対する IPv4 の CIDR など）には当てはまりません。
  - `--sport <ポート>` / `--dport <ポート>`: ポートは `22`、`8000:8100`（範囲）、`25,587,8000:8100`（並び）のどれか。`--sports` / `--dports` も同じ意味。ポートを持たないパケット（icmp など）には当てはまりません。
  - `--state <状態>[,<状態>...]`: 接続の状態 `NEW`、`ESTABLISHED`、`RELATED`、`INVALID` のどれか1つでも一致すれば当てはまります。`--ctstate` も同じ意味。
  - `--limit <N>/sec`: このルールのほかの条件がすべて当てはまったパケットを、時刻の秒（整数部分）ごとに N 個まで当てはめます。N 個を超えた分は「当てはまらない」として**次のルールへ進みます**（捨てられるわけではありません）。
  - `-m <モジュール名>`（`-m state`、`-m multiport` など）は書いてもよいが無視されます。

## 例

    ipset ops4 10.9.0.0/24
    *ip4
    :INPUT DROP
    :OUTPUT DROP
    [ex-01] -A INPUT -i lo -j ACCEPT
    [ex-02] -A INPUT -p tcp -s @ops4 --dport 22 --state NEW -j ACCEPT
    [ex-03] -A OUTPUT -p udp --dport 53,123 -j ACCEPT
    COMMIT

## 道具

`python3 tools/iptsim.py config/firewall.rules packets.txt` で、パケットの一覧に判定をつけて表示します（パケットの書式は iptsim.py の docstring）。
