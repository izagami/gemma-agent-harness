#!/usr/bin/env python3
"""Evaluate packets against a rules file (dialect in docs/RULES.md).

usage: fwsim.py RULES PACKETS

PACKETS has one packet per line, `key=value` pairs separated by spaces, e.g.
    t=0.0 family=ip hook=input iif=eth0 proto=tcp saddr=10.0.5.7 daddr=10.0.20.10 sport=40000 dport=22 ct=new
Keys: t (seconds, float), family (ip|ip6), hook (input|output), iif / oif, proto, saddr, daddr, sport, dport, ct.
Prints each packet with its verdict and the rule (or policy) that decided it. Lines starting with # are skipped.
"""
import ipaddress
import re
import sys


def parse(path):
    sets, chains, cur = {}, {}, None
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("set "):
            m = re.fullmatch(r"set (\S+) = (.+)", line)
            sets[m.group(1)] = [ipaddress.ip_network(x.strip(), strict=False) for x in m.group(2).split(",")]
        elif line.startswith("chain "):
            m = re.fullmatch(r"chain (\S+) family (ip|ip6) hook (input|output) policy (accept|drop)", line)
            if not m:
                raise SystemExit(f"line {n}: bad chain: {line}")
            cur = {"name": m.group(1), "policy": m.group(4), "rules": []}
            chains[(m.group(2), m.group(3))] = cur
        elif line.startswith("rule "):
            m = re.fullmatch(r"rule (\S+): (.*)", line)
            toks = m.group(2).split()
            cur["rules"].append({"id": m.group(1), "verdict": toks[-1], "conds": parse_conds(toks[:-1], n), "seen": {}})
        else:
            raise SystemExit(f"line {n}: cannot parse: {line}")
    return sets, chains


def parse_conds(toks, n):
    conds, i = [], 0
    while i < len(toks):
        k = toks[i]
        if k in ("counter", "log"):
            i += 1
            continue
        if k not in ("iif", "oif", "proto", "saddr", "daddr", "sport", "dport", "ct", "limit"):
            raise SystemExit(f"line {n}: unknown condition {k}")
        conds.append((k, toks[i + 1]))
        i += 2
    return conds


def port_ok(spec, port):
    if port is None:
        return False
    for part in spec.strip("{}").split(","):
        lo, _, hi = part.partition("-")
        if int(lo) <= port <= int(hi or lo):
            return True
    return False


def addr_ok(spec, sets, addr):
    nets = sets[spec[1:]] if spec.startswith("@") else [ipaddress.ip_network(spec, strict=False)]
    a = ipaddress.ip_address(addr)
    return any(a.version == net.version and a in net for net in nets)


def match(rule, sets, p):
    for k, v in rule["conds"]:
        if k == "limit":
            continue
        if k in ("iif", "oif", "proto") and p.get(k) != v:
            return False
        if k in ("saddr", "daddr") and not addr_ok(v, sets, p[k]):
            return False
        if k in ("sport", "dport") and not port_ok(v, p.get(k)):
            return False
        if k == "ct" and p.get("ct") not in v.split(","):
            return False
    for k, v in rule["conds"]:
        if k == "limit":
            sec = int(p["t"])
            if rule["seen"].get(sec, 0) >= int(v.split("/")[0]):
                return False
            rule["seen"][sec] = rule["seen"].get(sec, 0) + 1
    return True


def verdict(sets, chains, p):
    chain = chains.get((p["family"], p["hook"]))
    if chain is None:
        return "accept", "no chain"
    for r in chain["rules"]:
        if match(r, sets, p):
            return ("accept" if r["verdict"] == "accept" else "drop"), r["id"]
    return chain["policy"], "policy " + chain["name"]


def main():
    sets, chains = parse(sys.argv[1])
    for line in open(sys.argv[2], encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = dict(kv.split("=", 1) for kv in line.split())
        p["t"] = float(p.get("t", 0))
        for k in ("sport", "dport"):
            if k in p:
                p[k] = int(p[k])
        v, why = verdict(sets, chains, p)
        print(f"{v:6s} {why:16s} {line}")


if __name__ == "__main__":
    main()
