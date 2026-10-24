#!/usr/bin/env python3
"""Hidden check: simulate packets against /work/config/rules.nft with an independent evaluator and compare with the
verdicts POLICY.md demands; then check audit/report.json names every injected violation."""
import ipaddress, json, sys

fails = []


def fail(msg):
    fails.append(msg)


# ---------------- independent evaluator of the dialect
class Rules:
    def __init__(self, text):
        self.sets, self.chains, chain = {}, {}, None
        for no, raw in enumerate(text.splitlines(), 1):
            s = raw.partition("#")[0].strip()
            if not s:
                continue
            head, _, rest = s.partition(" ")
            if head == "set":
                name, eq, vals = rest.partition("=")
                if not eq:
                    raise ValueError(f"line {no}: set without '='")
                self.sets[name.strip()] = [ipaddress.ip_network(v.strip(), strict=False) for v in vals.split(",") if v.strip()]
            elif head == "chain":
                w = rest.split()
                if len(w) != 7 or w[1] != "family" or w[3] != "hook" or w[5] != "policy":
                    raise ValueError(f"line {no}: bad chain line")
                key = (w[2], w[4])
                if key in self.chains:
                    raise ValueError(f"line {no}: second chain for {key}")
                chain = self.chains[key] = {"name": w[0], "policy": w[6], "rules": []}
            elif head == "rule":
                if chain is None:
                    raise ValueError(f"line {no}: rule outside a chain")
                rid, colon, body = rest.partition(":")
                if not colon:
                    raise ValueError(f"line {no}: rule without ':'")
                w = body.split()
                if not w or w[-1] not in ("accept", "drop", "reject"):
                    raise ValueError(f"line {no}: rule without verdict")
                conds, k = [], 0
                ws = w[:-1]
                while k < len(ws):
                    if ws[k] in ("counter", "log"):
                        k += 1
                        continue
                    if k + 1 >= len(ws) or ws[k] not in ("iif", "oif", "proto", "saddr", "daddr", "sport", "dport", "ct", "limit"):
                        raise ValueError(f"line {no}: bad condition {ws[k]}")
                    conds.append((ws[k], ws[k + 1]))
                    k += 2
                chain["rules"].append({"id": rid.strip(), "v": w[-1], "c": conds, "cnt": {}})
            else:
                raise ValueError(f"line {no}: unknown line")

    def nets(self, spec):
        if spec.startswith("@"):
            if spec[1:] not in self.sets:
                raise ValueError(f"unknown set {spec}")
            return self.sets[spec[1:]]
        return [ipaddress.ip_network(spec, strict=False)]

    @staticmethod
    def ports(spec):
        out = []
        for part in spec.replace("{", "").replace("}", "").split(","):
            a, _, b = part.partition("-")
            out.append((int(a), int(b or a)))
        return out

    def decide(self, p):
        ch = self.chains.get((p["family"], p["hook"]))
        if ch is None:
            return "accept"
        for r in ch["rules"]:
            ok, lim = True, None
            for k, v in r["c"]:
                if k == "limit":
                    lim = int(v.split("/")[0])
                elif k in ("iif", "oif", "proto"):
                    ok = p.get(k) == v
                elif k in ("saddr", "daddr"):
                    a = ipaddress.ip_address(p[k])
                    ok = any(n.version == a.version and a in n for n in self.nets(v))
                elif k in ("sport", "dport"):
                    ok = p.get(k) is not None and any(a <= p[k] <= b for a, b in self.ports(v))
                elif k == "ct":
                    ok = p["ct"] in v.split(",")
                if not ok:
                    break
            if ok and lim is not None:
                sec = int(p["t"])
                if r["cnt"].get(sec, 0) >= lim:
                    ok = False
                else:
                    r["cnt"][sec] = r["cnt"].get(sec, 0) + 1
            if ok:
                return "accept" if r["v"] == "accept" else "drop"
        return ch["policy"]


# ---------------- what the policy demands
NET = {
    "ip": dict(server="10.0.20.10", admin=ipaddress.ip_network("10.0.10.0/24"), app="10.0.30.5", dns="10.0.0.53",
               hosts=dict(admin="10.0.10.23", admin2="10.0.10.250", office="10.0.5.7", vendor="10.0.99.14",
                          app="10.0.30.5", appn="10.0.30.6", net="198.51.100.20"),
               otherdns="192.0.2.53", icmp="icmp"),
    "ip6": dict(server="2001:db8:20::10", admin=ipaddress.ip_network("2001:db8:10::/64"), app="2001:db8:30::5", dns="2001:db8::53",
                hosts=dict(admin="2001:db8:10::23", admin2="2001:db8:10:0:ffff::1", office="2001:db8:5::7", vendor="2001:db8:99::14",
                           app="2001:db8:30::5", appn="2001:db8:30::6", net="2001:db8:ffff::20"),
                otherdns="2001:db8:ffff::53", icmp="icmpv6"),
}
icmp_seen = {}


def policy(p):
    n = NET[p["family"]]
    if p["hook"] == "input":
        if p.get("iif") == "lo":
            return "accept"
        if p["ct"] == "invalid":
            return "drop"
        if p["ct"] in ("established", "related"):
            return "accept"
        if p["proto"] == n["icmp"]:
            key = (p["family"], int(p["t"]))
            icmp_seen[key] = icmp_seen.get(key, 0) + 1
            return "accept" if icmp_seen[key] <= 5 else "drop"
        if p["proto"] == "tcp" and p.get("dport") == 22:
            return "accept" if ipaddress.ip_address(p["saddr"]) in n["admin"] else "drop"
        if p["proto"] == "tcp" and p.get("dport") in (80, 443):
            return "accept"
        if p["proto"] == "tcp" and p.get("dport") == 5432:
            return "accept" if ipaddress.ip_address(p["saddr"]) == ipaddress.ip_address(n["app"]) else "drop"
        return "drop"
    if p.get("oif") == "lo":
        return "accept"
    if p["ct"] == "invalid":
        return "drop"
    if p["ct"] in ("established", "related"):
        return "accept"
    d = ipaddress.ip_address(p["daddr"])
    if p["proto"] in ("udp", "tcp") and p.get("dport") == 53:
        return "accept" if d == ipaddress.ip_address(n["dns"]) else "drop"
    if p["proto"] == "udp" and p.get("dport") == 123:
        return "accept"
    if p["proto"] == "tcp" and p.get("dport") == 443:
        return "accept"
    return "drop"


def packets():
    out, t = [], 0.0
    for fam, n in NET.items():
        srv = n["server"]
        lo = "127.0.0.1" if fam == "ip" else "::1"
        for name, h in n["hosts"].items():
            for dp in (22, 80, 443, 5432, 3306, 8080):
                out.append(dict(t=t, family=fam, hook="input", iif="eth0", proto="tcp", saddr=h, daddr=srv, sport=41000, dport=dp, ct="new"))
            out.append(dict(t=t, family=fam, hook="input", iif="eth0", proto="udp", saddr=h, daddr=srv, sport=5353, dport=53, ct="new"))
        h = n["hosts"]
        out += [
            dict(t=t, family=fam, hook="input", iif="eth0", proto="tcp", saddr=h["net"], daddr=srv, sport=443, dport=51234, ct="established"),
            dict(t=t, family=fam, hook="input", iif="eth0", proto="udp", saddr=n["dns"], daddr=srv, sport=53, dport=40001, ct="established"),
            dict(t=t, family=fam, hook="input", iif="eth0", proto="tcp", saddr=h["admin"], daddr=srv, sport=41000, dport=80, ct="invalid"),
            dict(t=t, family=fam, hook="input", iif="eth0", proto="tcp", saddr=h["vendor"], daddr=srv, sport=41000, dport=22, ct="related"),
            dict(t=t, family=fam, hook="input", iif="lo", proto="tcp", saddr=lo, daddr=lo, sport=41000, dport=5432, ct="new"),
            dict(t=t, family=fam, hook="input", iif="lo", proto="tcp", saddr=lo, daddr=lo, sport=41000, dport=6379, ct="invalid"),
        ]
        o = dict(family=fam, hook="output", oif="eth0", saddr=srv, sport=40100)
        out += [dict(o, t=t, proto=pr, daddr=da, dport=dp, ct=ct) for pr, da, dp, ct in [
            ("tcp", h["net"], 443, "new"), ("tcp", h["net"], 80, "new"), ("udp", n["dns"], 53, "new"),
            ("udp", n["otherdns"], 53, "new"), ("tcp", n["dns"], 53, "new"), ("tcp", n["otherdns"], 53, "new"),
            ("udp", h["net"], 123, "new"), ("tcp", h["net"], 25, "new"), ("tcp", h["vendor"], 22, "new"),
            ("tcp", h["admin"], 41000, "established"), ("tcp", h["net"], 41000, "established"),
            ("tcp", h["app"], 41000, "established"), ("tcp", h["net"], 443, "invalid"), ("udp", h["office"], 514, "new")]]
        out.append(dict(o, t=t, oif="lo", proto="tcp", saddr=lo, daddr=lo, dport=5432, ct="new"))
        # ICMP bursts: 8 in one second, 3 in the next
        for i, ts in enumerate([10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 11.1, 11.5, 11.9]):
            out.append(dict(t=ts, family=fam, hook="input", iif="eth0", proto=n["icmp"], saddr=h["office" if i % 2 else "net"], daddr=srv, ct="new"))
        t = 20.0
    return out


def main():
    try:
        text = open("/work/config/rules.nft", encoding="utf-8").read()
        rules = Rules(text)
    except (OSError, ValueError) as e:
        print("cannot use config/rules.nft:", e)
        sys.exit(1)
    pk = packets()
    bad = 0
    for p in pk:
        want = policy(p)
        try:
            got = rules.decide(p)
        except ValueError as e:
            print("evaluation error:", e)
            sys.exit(1)
        if got != want:
            bad += 1
            if bad <= 12:
                fail(f"{p['family']} {p['hook']} {p['proto']} {p.get('saddr')}->{p.get('daddr')} dport={p.get('dport')} ct={p['ct']} t={p['t']}: got {got}, policy says {want}")
    print(f"packets: {len(pk) - bad}/{len(pk)} as the policy says")
    # report
    need = {("admin4", "wide_cidr"), ("in4-04", "shadowing"), ("in4-09", "debug_rule"), ("output4", "missing_state"),
            ("in6-05", "shadowing"), ("output6", "missing_chain")}
    kinds = {"shadowing", "wide_cidr", "debug_rule", "missing_state", "missing_chain"}
    try:
        rep = json.load(open("/work/audit/report.json", encoding="utf-8"))
        vs = rep["violations"]
        have = {(str(v["id"]).strip(), str(v["kind"]).strip()) for v in vs}
        if any(v["kind"] not in kinds for v in vs):
            fail("report.json: unknown kind in " + ", ".join(sorted({str(v['kind']) for v in vs} - kinds)))
        if len(vs) > 10:
            fail(f"report.json: {len(vs)} entries (list only real violations)")
        for item in sorted(need - have):
            fail(f"report.json: violation not reported: id={item[0]} kind={item[1]}")
        print(f"report: {len(need & have)}/{len(need)} violations reported")
    except Exception as e:
        fail(f"audit/report.json unreadable or wrong format: {e!r}")
    for f in fails:
        print("FAIL", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
