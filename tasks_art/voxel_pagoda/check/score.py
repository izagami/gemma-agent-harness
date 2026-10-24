import os, re, subprocess, sys
if not os.path.exists("/work/index.html"):
    print("index.html missing"); print("SCORE 0/12"); sys.exit(1)
html = open("/work/index.html", encoding="utf-8", errors="replace").read()
r = subprocess.run(["env", "RENDER_SIZE=960x600", sys.executable, "/check/webkit/render.py", "/work/index.html", "/tmp/shot.png"], capture_output=True, text=True, timeout=56)
out = r.stdout + r.stderr
print(out[-1200:])
pts, why = 0, []
def add(ok, n, label):
    global pts
    pts += n if ok else 0
    if not ok: why.append(label)
m = lambda pat: re.search(pat, out, re.M)
add(m(r"^errors: none") is not None, 3, "errors")
add(m(r"^blank: no") is not None, 2, "blank")
d = m(r"^detail: ([\d.]+)"); add(bool(d) and float(d.group(1)) >= 0.03, 1, "detail")
c = m(r"^colors: (\d+)"); add(bool(c) and int(c.group(1)) >= 40, 1, "colors")
a = m(r"^animation: ([\d.]+)"); add(bool(a) and float(a.group(1)) >= 0.002, 1, "animation")
b = m(r"^bbox: .*fills (\d+)%"); add(bool(b) and int(b.group(1)) >= 30 and "CUT OFF" not in out, 1, "framing")
add(re.search(r"OrbitControls|addEventListener\(\s*['\"](pointer|mouse|key|wheel|click)", html) is not None, 1, "interaction")
local = [u for u in re.findall(r"""<(?:script|link|img)[^>]+(?:src|href)=["']([^"']+)["']""", html) if not u.startswith(("http", "data:"))]
add(not local, 1, "self-contained")
# richness: labelled part kinds (voxelkit pages) or, without the kit, many distinct colors
pk = m(r"^parts: (\d+) labelled"); vk = m(r"^voxelkit: ")
add((vk is not None and pk is None) or (vk is None and bool(c) and int(c.group(1)) >= 80), 1, "richness")
print("missing:", ", ".join(why) or "-")
print(f"SCORE {pts}/12")
sys.exit(0 if pts == 12 else 1)
