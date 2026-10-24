#!/usr/bin/env python3
"""Hidden check: simulate many packets against /work/config/firewall.rules with the checker's own copy of iptsim and
compare with the verdicts POLICY.md demands; then check audit/report.json names every planted violation."""
import ipaddress, json, sys

sys.path.insert(0, "/check")
import iptsim  # noqa: E402  (pristine copy, not the one in /work)

fails = []

NET = {
    "ip4": dict(server="203.0.113.25", lo="127.0.0.1", icmp="icmp",
                internal=ipaddress.ip_network("10.40.0.0/16"), jump="10.40.1.10", mon="10.40.2.20", mbox="10.40.3.30",
                dns=("10.40.0.53", "10.40.0.54"),
                hosts=dict(jump="10.40.1.10", mon="10.40.2.20", mbox="10.40.3.30", office="10.40.7.15",
                           office2="10.40.250.9", jumpn="10.40.1.11", dns1="10.40.0.53", vendor="198.51.100.77",
                           net="192.0.2.80", net2="198.51.100.200"),
                extdns="198.51.100.53"),
    "ip6": dict(server="2001:db8:100::25", lo="::1", icmp="ipv6-icmp",
                internal=ipaddress.ip_network("2001:db8:40::/48"), jump="2001:db8:40:1::10", mon="2001:db8:40:2::20",
                mbox="2001:db8:40:3::30", dns=("2001:db8:40::53", "2001:db8:40::54"),
                hosts=dict(jump="2001:db8:40:1::10", mon="2001:db8:40:2::20", mbox="2001:db8:40:3::30",
                           office="2001:db8:40:7::15", office2="2001:db8:40:ffff::9", jumpn="2001:db8:40:1::11",
                           dns1="2001:db8:40::53", vendor="2001:db8:51::77", net="2001:db8:f00::80",
                           net2="2001:db8:51::200"),
                extdns="2001:db8:51::53"),
}
seen = {}


def counted(kind, fam, t, cap):
    key = (kind, fam, int(t))
    seen[key] = seen.get(key, 0) + 1
    return seen[key] <= cap


def policy(p):
    n = NET[p["family"]]
    ip = lambda a: ipaddress.ip_address(a)  # noqa: E731
    if p["hook"] == "INPUT":
        if p.get("iif") == "lo":
            return "ACCEPT"
        if p["state"] == "INVALID":
            return "DROP"
        if p["state"] in ("ESTABLISHED", "RELATED"):
            return "ACCEPT"
        if p["proto"] == n["icmp"]:
            return "ACCEPT" if counted("icmp", p["family"], p["t"], 10) else "DROP"
        if p["proto"] != "tcp":
            return "DROP"
        s, dp = ip(p["saddr"]), p.get("dport")
        if dp == 25:
            return "ACCEPT" if counted("smtp", p["family"], p["t"], 20) else "DROP"
        if dp == 587:
            return "ACCEPT" if s in n["internal"] else "DROP"
        if dp in (22, 8443):
            return "ACCEPT" if s == ip(n["jump"]) else "DROP"
        if dp == 9100:
            return "ACCEPT" if s == ip(n["mon"]) else "DROP"
        return "DROP"
    if p.get("oif") == "lo":
        return "ACCEPT"
    if p["state"] == "INVALID":
        return "DROP"
    if p["state"] in ("ESTABLISHED", "RELATED"):
        return "ACCEPT"
    d, dp, pr = ip(p["daddr"]), p.get("dport"), p["proto"]
    if pr == "tcp" and dp == 25:
        return "ACCEPT"
    if pr in ("tcp", "udp") and dp == 53:
        return "ACCEPT" if d in {ip(x) for x in n["dns"]} else "DROP"
    if pr == "udp" and dp == 123:
        return "ACCEPT"
    if pr == "tcp" and dp == 24:
        return "ACCEPT" if d == ip(n["mbox"]) else "DROP"
    return "DROP"


def packets():
    out = []
    for fam, n in NET.items():
        base = 0.0 if fam == "ip4" else 100.0
        srv, h, lo = n["server"], n["hosts"], n["lo"]
        I = dict(family=fam, hook="INPUT", iif="eth0", daddr=srv, sport=41000)
        O = dict(family=fam, hook="OUTPUT", oif="eth0", saddr=srv, sport=40100)
        # new inbound connections from every host to many ports (spread over seconds so SMTP stays under the cap)
        for k, (name, a) in enumerate(h.items()):
            t = base + 1 + k
            for dp in (22, 24, 25, 80, 443, 587, 993, 8443, 9010, 9100):
                out.append(dict(I, t=t, proto="tcp", saddr=a, dport=dp, state="NEW"))
            out.append(dict(I, t=t, proto="udp", saddr=a, sport=5353, dport=53, state="NEW"))
            out.append(dict(I, t=t, proto="udp", saddr=a, sport=40000, dport=9100, state="NEW"))
            # replies and related traffic coming back
            out.append(dict(I, t=t, proto="tcp", saddr=a, sport=25, dport=50123, state="ESTABLISHED"))
            out.append(dict(I, t=t, proto="tcp", saddr=a, sport=41000, dport=22, state="ESTABLISHED"))
            out.append(dict(I, t=t, proto=n["icmp"], saddr=a, state="RELATED"))
            out.append(dict(I, t=t, proto="tcp", saddr=a, dport=25, state="INVALID"))
            out.append(dict(I, t=t, proto="tcp", saddr=a, dport=8443, state="INVALID"))
        t = base + 20
        out += [
            dict(I, t=t, proto="udp", saddr=n["dns"][1], sport=53, dport=40001, state="ESTABLISHED"),
            dict(I, t=t, iif="lo", proto="tcp", saddr=lo, daddr=lo, dport=10025, state="NEW"),
            dict(I, t=t, iif="lo", proto="tcp", saddr=lo, daddr=lo, dport=10025, state="INVALID"),
            dict(I, t=t, iif="lo", proto="udp", saddr=lo, daddr=lo, dport=53, state="NEW"),
        ]
        # outbound
        t = base + 21
        for pr, da, dp, st in [
            ("tcp", h["net"], 25, "NEW"), ("tcp", h["net2"], 25, "NEW"), ("tcp", h["mbox"], 25, "NEW"),
            ("udp", n["dns"][0], 53, "NEW"), ("udp", n["dns"][1], 53, "NEW"), ("udp", n["extdns"], 53, "NEW"),
            ("tcp", n["dns"][0], 53, "NEW"), ("tcp", n["dns"][1], 53, "NEW"), ("tcp", n["extdns"], 53, "NEW"),
            ("udp", h["net"], 123, "NEW"), ("udp", n["dns"][0], 123, "NEW"),
            ("tcp", h["mbox"], 24, "NEW"), ("tcp", h["net"], 24, "NEW"), ("tcp", h["office"], 24, "NEW"),
            ("tcp", h["net"], 443, "NEW"), ("tcp", h["net"], 80, "NEW"), ("tcp", h["vendor"], 22, "NEW"),
            ("udp", h["office"], 514, "NEW"), ("tcp", h["mbox"], 993, "NEW"), ("tcp", h["net"], 587, "NEW"),
            ("tcp", h["net"], 25, "INVALID"), ("udp", n["dns"][0], 53, "INVALID"),
        ]:
            out.append(dict(O, t=t, proto=pr, daddr=da, dport=dp, state=st))
        out.append(dict(O, t=t, proto=n["icmp"], daddr=h["net"], state="NEW"))
        # replies to accepted inbound connections, and related ICMP errors
        for name in ("net", "net2", "office", "jump", "mon", "vendor"):
            out.append(dict(O, t=t, proto="tcp", daddr=h[name], sport=25, dport=41000, state="ESTABLISHED"))
            out.append(dict(O, t=t, proto="tcp", daddr=h[name], sport=22, dport=41000, state="ESTABLISHED"))
            out.append(dict(O, t=t, proto=n["icmp"], daddr=h[name], state="RELATED"))
        out.append(dict(O, t=t, proto="tcp", daddr=h["office"], sport=587, dport=41000, state="ESTABLISHED"))
        out.append(dict(O, t=t, proto="tcp", daddr=h["mon"], sport=9100, dport=41000, state="ESTABLISHED"))
        out.append(dict(O, t=t, oif="lo", proto="tcp", saddr=lo, daddr=lo, dport=10025, state="NEW"))
        out.append(dict(O, t=t, oif="lo", proto="tcp", saddr=lo, daddr=lo, dport=10025, state="INVALID"))
        # SMTP burst at the edge: 26 new connections in one second, then 7 in the next
        srcs = [h["net"], h["net2"], h["vendor"], h["office"]]
        for i in range(26):
            out.append(dict(I, t=base + 30 + i / 30, proto="tcp", saddr=srcs[i % 4], sport=42000 + i, dport=25, state="NEW"))
        for i in range(7):
            out.append(dict(I, t=base + 31 + i / 10, proto="tcp", saddr=srcs[i % 4], sport=43000 + i, dport=25, state="NEW"))
        # ICMP burst: 15 in one second, then 4 in the next
        for i in range(15):
            out.append(dict(I, t=base + 40 + i / 20, proto=n["icmp"], saddr=srcs[i % 4], state="NEW"))
        for i in range(4):
            out.append(dict(I, t=base + 41 + i / 5, proto=n["icmp"], saddr=srcs[i % 4], state="NEW"))
    return out


def main():
    try:
        rules = iptsim.Rules(open("/work/config/firewall.rules", encoding="utf-8").read())
    except (OSError, ValueError) as e:
        print("cannot use config/firewall.rules:", e)
        print("SCORE 0/1000")
        sys.exit(1)
    pk = packets()
    bad = 0
    for p in pk:
        want = policy(p)
        try:
            got, by = rules.decide(p)
        except (ValueError, KeyError) as e:
            print("evaluation error:", e)
            print("SCORE 0/1000")
            sys.exit(1)
        if got != want:
            bad += 1
            if bad <= 15:
                fails.append(f"{p['family']} {p['hook']} {p['proto']} {p.get('saddr')}->{p.get('daddr')} "
                             f"dport={p.get('dport')} state={p['state']} t={p['t']:.2f}: got {got} ({by}), policy says {want}")
    print(f"packets: {len(pk) - bad}/{len(pk)} as the policy says")
    need = {("in4-05", "shadowing"), ("mon4", "wide_cidr"), ("in4-10", "debug_rule"), ("in4-11", "ineffective_limit"),
            ("ip4:output", "missing_state"), ("out4-04", "rule_order"), ("ip6:input", "default_accept"),
            ("in6-07", "wrong_port"), ("in6-08", "wrong_proto"), ("ip6:output", "missing_chain")}
    kinds = {"shadowing", "rule_order", "wide_cidr", "debug_rule", "ineffective_limit", "wrong_port", "wrong_proto",
             "missing_state", "default_accept", "missing_chain"}
    have = set()
    try:
        rep = json.load(open("/work/audit/report.json", encoding="utf-8"))
        vs = rep["violations"]
        have = {(str(v["id"]).strip().lower(), str(v["kind"]).strip()) for v in vs}
        unknown = {str(v["kind"]) for v in vs} - kinds
        if unknown:
            fails.append("report.json: unknown kind " + ", ".join(sorted(unknown)))
        if len(vs) > 15:
            fails.append(f"report.json: {len(vs)} entries (list only real violations)")
        for item in sorted(need - have):
            fails.append(f"report.json: violation not reported: id={item[0]} kind={item[1]}")
        print(f"report: {len(need & have)}/{len(need)} violations reported")
    except Exception as e:  # noqa: BLE001
        fails.append(f"audit/report.json unreadable or wrong format: {e!r}")
    for f in fails:
        print("FAIL", f)
    # packets and the report weigh half each
    print(f"SCORE {round(500 * (len(pk) - bad) / len(pk) + 500 * len(need & have) / len(need))}/1000")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
