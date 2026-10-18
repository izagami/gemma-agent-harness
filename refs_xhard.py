"""Reference solutions for tasks_xhard.py."""
R = {}
R["x_shop"] = {
    "shop/coupons.py": "COUPONS = {\n    'WELCOME10': ('percent', 10),\n    'YEN500': ('fixed', 500),\n    'BIG20': ('percent_min', (20, 10000)),\n}\n\ndef discount_for(code, sub):\n    if code is None:\n        return 0\n    if code not in COUPONS:\n        raise ValueError(code)\n    kind, val = COUPONS[code]\n    if kind == 'percent':\n        return sub * val // 100\n    if kind == 'fixed':\n        return min(val, sub)\n    pct, minimum = val\n    return sub * pct // 100 if sub >= minimum else 0\n",
    "shop/pricing.py": "from shop.coupons import discount_for\n\ndef subtotal(cart):\n    return sum(it.price * it.qty for it in cart.items)\n\ndef total(cart):\n    sub = subtotal(cart)\n    base = sub - discount_for(cart.coupon, sub)\n    return base * 110 // 100\n",
    "!": "sed -i 's/if it.qty < 0:/if it.qty <= 0:/' shop/models.py"}
R["x_cli_sub"] = {"!": r'''python3 - <<'EOF'
s=open('notes.py').read()
s=s.replace("def main(argv=None):", """def cmd_search(a):
    q = a.keyword.lower()
    notes = [n for n in load() if q in n["title"].lower() or q in n["body"].lower()]
    if a.tag:
        notes = [n for n in notes if a.tag in n["tags"]]
    for n in notes:
        print(fmt(n))
    if not notes:
        print("no match")

def main(argv=None):""")
s=s.replace("    a = p.parse_args(argv)", """    s = sub.add_parser("search"); s.add_argument("keyword"); s.add_argument("--tag"); s.set_defaults(fn=cmd_search)
    a = p.parse_args(argv)""")
open('notes.py','w').write(s)
EOF'''}
R["x_logs_pipeline"] = {"!": r'''sed -i "s/'user': user.strip(), 'action': action.strip(), 'ms': ms}/'user': user.strip().lower(), 'action': action.strip(), 'ms': int(ms)}/" pipeline/parse.py'''}
R["x_write_tests"] = {"tests/test_slugify.py": "import unittest\nfrom slugify import slugify\n\nclass T(unittest.TestCase):\n    def test_empty(self): self.assertEqual(slugify(''), '')\n    def test_symbols(self): self.assertEqual(slugify('Hello, World!'), 'hello-world')\n    def test_runs(self): self.assertEqual(slugify('a  -- b'), 'a-b')\n    def test_strip(self): self.assertEqual(slugify('  x y  '), 'x-y')\n    def test_upper(self): self.assertEqual(slugify('ABC'), 'abc')\n    def test_digits(self): self.assertEqual(slugify('Python 3.12'), 'python-312')\n"}
R["x_cache_bug"] = {"fetcher.py": "import time\n\nclass CachedFetcher:\n    def __init__(self, fetch, ttl=60, clock=time.time, max_entries=100):\n        self.fetch, self.ttl, self.clock, self.max = fetch, ttl, clock, max_entries\n        self.cache = {}\n\n    def get(self, url, params=None):\n        params = dict(params or {})\n        key = url + '?' + '&'.join(f'{k}={v}' for k, v in sorted(params.items()))\n        hit = self.cache.get(key)\n        if hit and self.clock() - hit[1] < self.ttl:\n            return hit[0]\n        value = self.fetch(url, params)\n        self.cache[key] = (value, self.clock())\n        if len(self.cache) > self.max:\n            oldest = min(self.cache, key=lambda k: self.cache[k][1])\n            del self.cache[oldest]\n        return value\n"}
