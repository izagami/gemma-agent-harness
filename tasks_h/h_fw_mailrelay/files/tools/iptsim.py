#!/usr/bin/env python3
"""Evaluate packets against a rules file (dialect in docs/RULES.md). First match wins.

usage: iptsim.py RULES PACKETS

PACKETS has one packet per line, `key=value` pairs separated by spaces, e.g.
    t=0.0 family=ip4 hook=INPUT iif=eth0 proto=tcp saddr=10.40.1.10 daddr=203.0.113.25 sport=40000 dport=22 state=NEW
Keys: t (seconds, float), family (ip4|ip6), hook (INPUT|OUTPUT), iif / oif, proto (tcp|udp|icmp|ipv6-icmp),
saddr, daddr, sport, dport, state (NEW|ESTABLISHED|RELATED|INVALID).
Prints each packet with its verdict and the rule (or policy) that decided it. Lines starting with # are skipped.
Rate-limit counters (--limit) persist across the packets of one run, so put packets in time order.
"""
import ipaddress
import re
import sys

OPTS = {"-i": "iif", "-o": "oif", "-p": "proto", "-s": "saddr", "-d": "daddr", "--sport": "sport", "--sports": "sport",
        "--dport": "dport", "--dports": "dport", "--state": "state", "--ctstate": "state", "--limit": "limit"}
STATES = {"NEW", "ESTABLISHED", "RELATED", "INVALID"}
PROTOS = {"tcp", "udp", "icmp", "ipv6-icmp"}


class RuleError(ValueError):
    pass


def parse_ports(spec, n):
    out = []
    for part in spec.split(","):
        a, _, b = part.partition(":")
        if not a.isdigit() or (b and not b.isdigit()):
            raise RuleError(f"line {n}: bad port spec {spec}")
        out.append((int(a), int(b or a)))
    return out


class Rules:
    def __init__(self, text):
        self.sets, self.tables, self.ids = {}, {}, set()
        table = None
        for n, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line or line == "COMMIT":
                continue
            if line.startswith("ipset "):
                w = line.split(None, 2)
                if len(w) != 3:
                    raise RuleError(f"line {n}: bad ipset: {line}")
                try:
                    self.sets[w[1]] = [ipaddress.ip_network(x.strip(), strict=False) for x in w[2].split(",") if x.strip()]
                except ValueError as e:
                    raise RuleError(f"line {n}: {e}")
            elif line.startswith("*"):
                fam = line[1:]
                if fam not in ("ip4", "ip6"):
                    raise RuleError(f"line {n}: unknown table {line}")
                if fam in self.tables:
                    raise RuleError(f"line {n}: table {line} defined twice")
                table = self.tables[fam] = {}
            elif line.startswith(":"):
                m = re.fullmatch(r":(INPUT|OUTPUT)\s+(ACCEPT|DROP)", line)
                if not m:
                    raise RuleError(f"line {n}: bad chain line: {line}")
                if table is None:
                    raise RuleError(f"line {n}: chain outside a table")
                if m.group(1) in table:
                    raise RuleError(f"line {n}: chain {m.group(1)} declared twice")
                table[m.group(1)] = {"policy": m.group(2), "rules": []}
            elif line.startswith("["):
                m = re.fullmatch(r"\[([^\]\s]+)\]\s+-A\s+(INPUT|OUTPUT)\s+(.*)", line)
                if not m:
                    raise RuleError(f"line {n}: bad rule: {line}")
                rid, chain, rest = m.groups()
                if table is None or chain not in table:
                    raise RuleError(f"line {n}: rule {rid} before ':{chain}' was declared in this table")
                if rid in self.ids:
                    raise RuleError(f"line {n}: duplicate rule ID {rid}")
                self.ids.add(rid)
                toks = rest.split()
                if len(toks) < 2 or toks[-2] != "-j" or toks[-1] not in ("ACCEPT", "DROP", "REJECT"):
                    raise RuleError(f"line {n}: rule must end with -j ACCEPT|DROP|REJECT")
                table[chain]["rules"].append({"id": rid, "verdict": toks[-1], "conds": self.parse_conds(toks[:-2], n), "seen": {}})
            else:
                raise RuleError(f"line {n}: cannot parse: {line}")

    def parse_conds(self, toks, n):
        conds, i = [], 0
        while i < len(toks):
            k = toks[i]
            if i + 1 >= len(toks):
                raise RuleError(f"line {n}: option {k} without a value")
            v = toks[i + 1]
            i += 2
            if k == "-m":
                continue
            if k not in OPTS:
                raise RuleError(f"line {n}: unknown option {k}")
            key = OPTS[k]
            if key == "proto" and v not in PROTOS:
                raise RuleError(f"line {n}: unknown protocol {v}")
            if key in ("sport", "dport"):
                v = parse_ports(v, n)
            elif key == "state":
                v = set(v.split(","))
                if not v <= STATES:
                    raise RuleError(f"line {n}: unknown state in {toks[i - 1]}")
            elif key == "limit":
                mm = re.fullmatch(r"(\d+)/sec", v)
                if not mm:
                    raise RuleError(f"line {n}: limit must be N/sec")
                v = int(mm.group(1))
            elif key in ("saddr", "daddr"):
                if v.startswith("@"):
                    if v[1:] not in self.sets:
                        raise RuleError(f"line {n}: unknown ipset {v}")
                else:
                    try:
                        ipaddress.ip_network(v, strict=False)
                    except ValueError as e:
                        raise RuleError(f"line {n}: {e}")
            conds.append((key, v))
        return conds

    def nets(self, spec):
        if spec.startswith("@"):
            return self.sets[spec[1:]]
        return [ipaddress.ip_network(spec, strict=False)]

    def decide(self, p):
        """-> (verdict ACCEPT|DROP, decided-by)"""
        ch = self.tables.get(p["family"], {}).get(p["hook"])
        if ch is None:
            return "ACCEPT", "no chain (unfiltered)"
        for r in ch["rules"]:
            ok, lim = True, None
            for k, v in r["conds"]:
                if k == "limit":
                    lim = v
                elif k in ("iif", "oif", "proto"):
                    ok = p.get(k) == v
                elif k in ("saddr", "daddr"):
                    a = ipaddress.ip_address(p[k])
                    ok = any(net.version == a.version and a in net for net in self.nets(v))
                elif k in ("sport", "dport"):
                    ok = p.get(k) is not None and any(lo <= int(p[k]) <= hi for lo, hi in v)
                elif k == "state":
                    ok = p["state"] in v
                if not ok:
                    break
            if ok and lim is not None:
                sec = int(float(p["t"]))
                if r["seen"].get(sec, 0) >= lim:
                    ok = False
                else:
                    r["seen"][sec] = r["seen"].get(sec, 0) + 1
            if ok:
                return ("ACCEPT" if r["verdict"] == "ACCEPT" else "DROP"), r["id"]
        return ch["policy"], "policy"


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    try:
        rules = Rules(open(sys.argv[1], encoding="utf-8").read())
    except RuleError as e:
        raise SystemExit(f"{sys.argv[1]}: {e}")
    for raw in open(sys.argv[2], encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = dict(kv.split("=", 1) for kv in line.split())
        p.setdefault("t", "0")
        verdict, by = rules.decide(p)
        print(f"{verdict:6} {by:24} {line}")


if __name__ == "__main__":
    main()
