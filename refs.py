#!/usr/bin/env python3
"""Reference solutions: prove every check can pass. usage: refs.py (runs all, prints failures)."""
import json, os, shutil, subprocess, tempfile
import eval as ev

R = {}
R["fizzbuzz"] = {"fizzbuzz.py": "for i in range(1,101):\n    print('FizzBuzz' if i%15==0 else 'Fizz' if i%3==0 else 'Buzz' if i%5==0 else i)\n", "!": "python3 fizzbuzz.py > out.txt"}
R["avg_bug"] = {"calc.py": "def average(xs):\n    return sum(xs)/len(xs) if xs else 0\n\ndef median(xs):\n    s=sorted(xs); n=len(s)\n    return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2\n"}
R["csv_sum"] = {"!": "python3 -c \"import csv,json\nd={}\nfor r in csv.DictReader(open('sales.csv')): d[r['category']]=d.get(r['category'],0)+int(r['quantity'])*float(r['price'])\njson.dump({k:round(v,2) for k,v in d.items()},open('summary.json','w'),ensure_ascii=False)\""}
R["rename"] = {"!": "cd photos && for f in *; do b=${f%.*}; e=${f##*.}; n=${b#*_}; mv \"$f\" \"img_$(printf %03d $n).${e,,}\"; done"}
R["log_errors"] = {"!": "for f in logs/*.log; do echo \"$(basename $f) $(grep -c ' ERROR ' $f)\"; done | sort -k2,2nr -k1,1 > report.txt"}
R["duration"] = {"utils.py": "import re\ndef parse_duration(s):\n    m=re.fullmatch(r'(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?',s)\n    if not s or not m: raise ValueError(s)\n    h,mi,se=(int(x or 0) for x in m.groups())\n    return h*3600+mi*60+se\n"}
R["refactor"] = {"fmt.py": "def format_numbers(xs):\n    return '|'.join(f'{x:>10.2f}' for x in xs)\n",
                 "report_a.py": "from fmt import format_numbers\nprint('A:' + format_numbers([3.14159, 2.5, 100]))\n",
                 "report_b.py": "from fmt import format_numbers\nprint('B:' + format_numbers([1, 22.333, 0.5]))\n"}
R["config_edit"] = {"!": "python3 -c \"import json\nd=json.load(open('config.json')); d['server']['port']=8443; d['server']['tls']=True\njson.dump(d,open('config.json','w'),indent=2)\""}
R["wordcount"] = {"wc.py": "import sys,collections\nargs=sys.argv[1:]\ntry:\n    t=open(args[0]).read()\nexcept OSError:\n    print('error: file not found',file=sys.stderr); sys.exit(1)\nw=t.split()\nprint(f'lines={len(t.splitlines())} words={len(w)} chars={len(t)}')\nif '--top' in args:\n    n=int(args[args.index('--top')+1])\n    for k,v in sorted(collections.Counter(w).items(),key=lambda x:(-x[1],x[0]))[:n]: print(k,v)\n"}
R["pagination"] = {"paginate.py": "def paginate(items, page, per_page):\n    if page < 1: return []\n    s=(page-1)*per_page\n    return items[s:s+per_page]\n\ndef page_count(n, per_page):\n    return -(-n//per_page)\n"}
R["dedupe"] = {"!": "python3 -c \"seen=[]\nfor l in open('names.txt'):\n    l=l.strip()\n    if l and l not in seen: seen.append(l)\nopen('names_unique.txt','w').write('\\n'.join(seen)+'\\n')\""}
R["import_fix"] = {"!": "sed -i 's/app.helpers/app.helper/' app/core.py"}
R["emails"] = {"!": "python3 -c \"import json\ndef ok(e):\n    if ' ' in e or e.count('@')!=1: return False\n    a,b=e.split('@'); return bool(a) and '.' in b and not b.startswith('.')\nopen('invalid.txt','w').write('\\n'.join(str(u['id']) for u in sorted(json.load(open('users.json')),key=lambda u:u['id']) if not ok(u['email']))+'\\n')\""}
R["robust"] = {"!": "sed -i \"s/    total += r\\['amount'\\]/    if r.get('amount') is not None:\\n        total += r['amount']/\" total.py"}
R["md_table"] = {"!": "python3 -c \"import csv\nr=list(csv.DictReader(open('scores.csv'))); r.sort(key=lambda x:-(int(x['english'])+int(x['math'])))\nL=['| name | english | math | 合計 |','|---|---|---|---|']+[f\\\"| {x['name']} | {x['english']} | {x['math']} | {int(x['english'])+int(x['math'])} |\\\" for x in r]\nopen('scores.md','w').write('\\n'.join(L)+'\\n')\""}
R["scaffold"] = {"project/src/main.py": "print('hello')\n", "project/src/__init__.py": "", "project/tests/test_main.py": "", "project/README.md": "# project\n", "project/.gitignore": "__pycache__/\n"}
R["speed"] = {"fib.py": "import sys\n\ndef fib(n):\n    a,b=0,1\n    for _ in range(n): a,b=b,a+b\n    return a\n\nif __name__ == '__main__':\n    print(fib(int(sys.argv[1])))\n"}
R["merge_csv"] = {"!": "python3 -c \"import csv\nc={r['customer_id']:r['name'] for r in csv.DictReader(open('customers.csv'))}\no=sorted(csv.DictReader(open('orders.csv')),key=lambda r:int(r['order_id']))\nw=csv.writer(open('merged.csv','w',newline=''),lineterminator='\\n'); w.writerow(['order_id','customer_id','name','amount'])\n[w.writerow([r['order_id'],r['customer_id'],c.get(r['customer_id'],''),r['amount']]) for r in o]\""}
R["unused"] = {"unused.txt": "backup\nlegacy_clean\nnormalize\n"}
R["stats_cli"] = {"!": "python3 -c \"import json,statistics as s\nxs=[float(l) for l in open('data.txt') if l.strip() and not l.startswith('#')]\njson.dump({'mean':round(s.mean(xs),3),'min':round(min(xs),3),'max':round(max(xs),3),'std':round(s.pstdev(xs),3)},open('stats.json','w'))\""}

if __name__ == "__main__":
    fails = []
    for t, sol in R.items():
        w = tempfile.mkdtemp(dir="/tmp/claude-1000/-home-izagami/b7c81ef9-c842-4623-b699-d4513c80a0c7/scratchpad"); os.rmdir(w)
        src = f"tasks/{t}/files"
        shutil.copytree(src, w) if os.path.isdir(src) else os.makedirs(w)
        for k, v in sol.items():
            if k != "!":
                os.makedirs(os.path.dirname(os.path.join(w, k)) or w, exist_ok=True); open(os.path.join(w, k), "w").write(v)
        if "!" in sol:
            subprocess.run(["podman", "run", "--rm", "--network", "none", "--userns=keep-id", "-v", f"{w}:/work:Z", "-w", "/work", ev.agent.IMAGE, "bash", "-c", sol["!"]], check=True)
        ok, out = ev.check(w, os.path.abspath(f"tasks/{t}/check"))
        if not ok: fails.append((t, out[-400:]))
        shutil.rmtree(w)
    print("reference failures:", fails or "none", f"({len(R)} refs)")
