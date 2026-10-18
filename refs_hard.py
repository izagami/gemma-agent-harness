"""Reference solutions for tasks_hard.py (merged into refs.R)."""
R = {}
R["h_lru"] = {"lru.py": "from collections import OrderedDict\nclass LRUCache:\n    def __init__(self, capacity):\n        if capacity <= 0: raise ValueError('capacity')\n        self.c=capacity; self.d=OrderedDict()\n    def get(self, k):\n        if k not in self.d: return -1\n        self.d.move_to_end(k); return self.d[k]\n    def put(self, k, v):\n        self.d[k]=v; self.d.move_to_end(k)\n        if len(self.d)>self.c: self.d.popitem(last=False)\n"}
R["h_bank"] = {"bank/ops.py": "from bank.account import Account\n\ndef transfer(src, dst, amount, fee=0):\n    s, d = src.balance, dst.balance\n    try:\n        src.withdraw(amount)\n        dst.deposit(amount)\n        if fee:\n            src.withdraw(fee)\n    except Exception:\n        src.balance, dst.balance = s, d\n        raise\n"}
R["h_ini"] = {"iniparse.py": r'''
def parse(text):
    out, sec, last = {}, "", None
    for n, raw in enumerate(text.split("\n"), 1):
        s = raw.strip()
        if not s or s[0] in "#;":
            continue
        if raw[0] in " \t" and last is not None:
            out[sec][last] += "\n" + s
            continue
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1].strip(); out.setdefault(sec, {}); last = None
            continue
        i = min([p for p in (s.find("="), s.find(":")) if p >= 0], default=-1)
        if i <= 0:
            raise ValueError(f"line {n}: {raw}")
        k, v = s[:i].strip().lower(), s[i + 1:].strip()
        out.setdefault(sec, {})[k] = v; last = k
    return out
'''}
R["h_todo"] = {"todo.py": r'''
import json, os, sys
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todo.json")
def load():
    return json.load(open(P)) if os.path.exists(P) else {"next": 1, "items": []}
def save(d): json.dump(d, open(P, "w"), ensure_ascii=False)
a = sys.argv[1:]
d = load()
def find(n):
    for it in d["items"]:
        if it["id"] == n: return it
    print(f"error: no task {n}", file=sys.stderr); sys.exit(1)
if a[:1] == ["add"] and len(a) > 1:
    d["items"].append({"id": d["next"], "text": " ".join(a[1:]), "done": False}); print("added", d["next"]); d["next"] += 1; save(d)
elif a == ["list"]:
    print("\n".join(f"{i['id']} [{'x' if i['done'] else ' '}] {i['text']}" for i in d["items"]) or "no tasks")
elif len(a) == 2 and a[0] in ("done", "delete") and a[1].isdigit():
    it = find(int(a[1]))
    if a[0] == "done": it["done"] = True; print("done", it["id"])
    else: d["items"].remove(it); print("deleted", it["id"])
    save(d)
else:
    print("usage: todo.py add TEXT | list | done N | delete N", file=sys.stderr); sys.exit(2)
'''}
R["h_bizdays"] = {"dates.py": "from datetime import date, timedelta\n\ndef business_days(start, end, holidays=()):\n    days, d = 0, start\n    while d <= end:\n        if d.weekday() < 5 and d not in holidays:\n            days += 1\n        d += timedelta(days=1)\n    return days\n"}
R["h_md"] = {"md2html.py": r'''
import html, re
def inline(t):
    parts = re.split(r"(`[^`]*`)", t)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append("<code>" + html.escape(p[1:-1], quote=False) + "</code>")
        else:
            p = html.escape(p, quote=False)
            p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
            p = re.sub(r"\*(.+?)\*", r"<em>\1</em>", p)
            out.append(p)
    return "".join(out)
def convert(md):
    blocks, para, items = [], [], []
    def flush():
        if para: blocks.append("<p>" + inline(" ".join(para)) + "</p>"); para.clear()
        if items: blocks.append("<ul>" + "".join("<li>" + inline(i) + "</li>" for i in items) + "</ul>"); items.clear()
    for line in md.split("\n"):
        m = re.match(r"(#{1,3}) (.*)", line)
        if not line.strip(): flush()
        elif m: flush(); n = len(m.group(1)); blocks.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif line.startswith("- "):
            if para: flush()
            items.append(line[2:])
        else:
            if items: flush()
            para.append(line.strip())
    flush()
    return "\n".join(blocks)
'''}
R["h_clean_csv"] = {"!": r'''python3 -c "
import csv,re
rows=list(csv.DictReader(open('raw.csv',encoding='utf-8-sig')))
def dt(s):
    s=s.strip()
    for p,o in [(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})$','ymd'),(r'(\d{1,2})-(\d{1,2})-(\d{4})$','mdy'),(r'(\d{4})年(\d{1,2})月(\d{1,2})日$','ymd')]:
        m=re.match(p,s)
        if m:
            a=m.groups(); y,mo,d=(a if o=='ymd' else (a[2],a[0],a[1])); return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
seen={}
for r in rows:
    if r['id'] not in seen: seen[r['id']]=[r['id'],r['name'].strip(),dt(r['date']),str(int(re.sub(r'[^0-9]','',r['amount'])))]
w=csv.writer(open('clean.csv','w',encoding='utf-8',newline=''),lineterminator='\n'); w.writerow(['id','name','date','amount'])
[w.writerow(v) for k,v in sorted(seen.items(),key=lambda x:int(x[0]))]
"'''}
R["h_inventory"] = {"!": r'''cat >> inventory.py <<'EOF'

    def low_stock(self, threshold):
        return sorted(((n, q) for n, q in self._items.items() if q < threshold), key=lambda x: (x[1], x[0]))
EOF
cat >> tests/test_inventory.py <<'EOF'

class L(unittest.TestCase):
    def test_low_stock_order(self):
        inv = Inventory(); inv.add("b", 1); inv.add("a", 1); inv.add("c", 5)
        self.assertEqual(inv.low_stock(2), [("a", 1), ("b", 1)])

    def test_low_stock_none(self):
        self.assertEqual(Inventory().low_stock(3), [])
EOF'''}
R["h_money"] = {"invoice.py": "import json, sys\nfrom decimal import Decimal, ROUND_DOWN\n\nTAX = Decimal('0.1')\n\ndef total(lines):\n    sub = sum(Decimal(str(l['price'])) * l['qty'] for l in lines)\n    tax = (sub * TAX).quantize(Decimal('1'), rounding=ROUND_DOWN)\n    return sub, tax, sub + tax\n\nif __name__ == '__main__':\n    lines = json.load(open(sys.argv[1]))\n    sub, tax, tot = total(lines)\n    print(f'subtotal={int(sub)} tax={int(tax)} total={int(tot)}')\n"}
R["h_calc"] = {"calc_expr.py": r'''
import re
def evaluate(expr):
    toks = re.findall(r"\d+\.?\d*|\.\d+|[-+*/()]|\S", expr)
    if not toks: raise ValueError("empty")
    pos = [0]
    def peek(): return toks[pos[0]] if pos[0] < len(toks) else None
    def take():
        t = peek(); pos[0] += 1; return t
    def expr_():
        v = term()
        while peek() in ("+", "-"):
            v = v + term() if take() == "+" else v - term()
        return v
    def term():
        v = unary()
        while peek() in ("*", "/"):
            if take() == "*": v *= unary()
            else:
                r = unary()
                if r == 0: raise ZeroDivisionError("division by zero")
                v /= r
        return v
    def unary():
        if peek() == "-": take(); return -unary()
        if peek() == "+": take(); return unary()
        t = take()
        if t == "(":
            v = expr_()
            if take() != ")": raise ValueError("missing )")
            return v
        try: return float(t)
        except (TypeError, ValueError): raise ValueError(f"bad token {t!r}")
    v = expr_()
    if peek() is not None: raise ValueError("trailing")
    return v
'''}
R["h_ratelimit"] = {"ratelimit.py": "import time\nclass TokenBucket:\n    def __init__(self, rate, capacity, clock=time.monotonic):\n        self.rate, self.cap, self.clock = rate, capacity, clock\n        self.tokens, self.t = capacity, clock()\n    def allow(self, n=1):\n        now = self.clock(); self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate); self.t = now\n        if self.tokens >= n:\n            self.tokens -= n; return True\n        return False\n"}
R["h_sync"] = {"sync.py": r'''
import filecmp, os, shutil, sys
a = [x for x in sys.argv[1:] if x != "--dry-run"]; dry = "--dry-run" in sys.argv
src, dst = a
ops = []
for root, dirs, files in os.walk(src):
    for f in files:
        s = os.path.join(root, f); rel = os.path.relpath(s, src); d = os.path.join(dst, rel)
        if not os.path.isfile(d) or not filecmp.cmp(s, d, shallow=False): ops.append(("copy", rel))
for root, dirs, files in os.walk(dst):
    for x in dirs + files:
        p = os.path.join(root, x); rel = os.path.relpath(p, dst)
        if not os.path.exists(os.path.join(src, rel)) and not any(rel.startswith(o[1] + "/") for o in ops if o[0] == "delete"):
            ops.append(("delete", rel))
for op, rel in sorted(ops, key=lambda o: o[1]):
    print(op, rel)
    if dry: continue
    d = os.path.join(dst, rel)
    if op == "copy": os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(os.path.join(src, rel), d)
    elif os.path.isdir(d): shutil.rmtree(d)
    elif os.path.exists(d): os.remove(d)
'''}
R["h_access"] = {"!": r'''python3 -c "
import re,json,collections
ips=collections.Counter(); st=collections.Counter(); b=0; bad=0
for l in open('access.log'):
    if not l.strip(): continue
    m=re.match(r'(\S+) \S+ \S+ \[[^\]]+\] \"[^\"]*\" (\d{3}) (\d+|-)$',l.strip())
    if not m: bad+=1; continue
    ips[m[1]]+=1; st[m[2]]+=1; b+=0 if m[3]=='-' else int(m[3])
json.dump({'top_ips':[list(x) for x in sorted(ips.items(),key=lambda x:(-x[1],x[0]))[:3]],'status':st,'bytes':b,'bad_lines':bad},open('result.json','w'))
"'''}
R["h_dupes"] = {"dupes.py": "def find_duplicates(items):\n    seen, out, added = set(), [], set()\n    for x in items:\n        if x in seen and x not in added:\n            out.append(x); added.add(x)\n        seen.add(x)\n    return out\n"}
R["h_sqlite"] = {"!": r'''python3 -c "
import sqlite3,csv,json
c=sqlite3.connect(':memory:')
c.execute('create table e(id,name,dept_id,salary)'); c.execute('create table d(id,name)')
c.executemany('insert into e values(?,?,?,?)',[(int(r['id']),r['name'],int(r['dept_id']),float(r['salary'])) for r in csv.DictReader(open('employees.csv'))])
c.executemany('insert into d values(?,?)',[(int(r['id']),r['name']) for r in csv.DictReader(open('departments.csv'))])
q1={n:round(a,1) for n,a in c.execute('select d.name,avg(salary) from e join d on e.dept_id=d.id group by d.id')}
q2=[n for (n,) in c.execute('select e.name from e where salary>(select avg(salary) from e e2 where e2.dept_id=e.dept_id) order by e.name')]
q3=[n for (n,) in c.execute('select name from d where id not in (select dept_id from e) order by name')]
json.dump({'q1':q1,'q2':q2,'q3':q3},open('answers.json','w'))
"'''}
