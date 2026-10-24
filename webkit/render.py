#!/usr/bin/env python3
"""render.py HTML [PNG]: open the page in headless Chromium (no network: three.js CDN URLs are served from a local
copy), wait, take a screenshot and print a report you can act on:

  errors      every console error / uncaught exception (scene.js line numbers for build.py pages)
  blank       the picture is (almost) one flat color - nothing visible / camera looks at nothing
  detail      share of the picture covered by visible structure (edges); a rich scene is roughly 0.15-0.45
  bbox        where the structure is on the screen; 'CUT OFF at top/left/...' when it runs past the frame
  colors      number of distinct colors in the structure (a rich voxel scene: 40+)
  animation   share of pixels that change within 1.5 s (0 = static)
  voxelkit    voxel counts per label (pages built with build.py)

Exit code 0 when there are no errors and the picture is not blank. Exit code 137 / "command killed" means the
machine was busy and the renderer ran out of time - NOT a problem in your scene: just run it again.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor")

ANALYZE_JS = """async (b64) => {
  const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
  const W = img.width, H = img.height, c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d'); g.drawImage(img, 0, 0); const d = g.getImageData(0, 0, W, H).data;
  let sum = 0, sum2 = 0, edges = 0, x0 = W, y0 = H, x1 = -1, y1 = -1; const cols = new Map();
  const bd = { top: 0, bottom: 0, left: 0, right: 0 }, by = H * 0.03, bx = W * 0.02;
  const lum = i => 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
  for (let y = 1; y < H - 1; y += 2) for (let x = 1; x < W - 1; x += 2) {
    const i = (y * W + x) * 4, l = lum(i); sum += l; sum2 += l * l;
    const gx = Math.abs(lum(i + 4) - lum(i - 4)), gy = Math.abs(lum(i + W * 4) - lum(i - W * 4));
    if (gx + gy > 24) {
      if (y < by && y > 40) bd.top++; if (y > H - by) bd.bottom++; if (x < bx) bd.left++; if (x > W - bx) bd.right++;
      edges++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      const k = (d[i] >> 4) + ',' + (d[i + 1] >> 4) + ',' + (d[i + 2] >> 4); cols.set(k, (cols.get(k) || 0) + 1);
    }
  }
  const n = ((W - 2) >> 1) * ((H - 2) >> 1), mean = sum / n, sd = Math.sqrt(Math.max(0, sum2 / n - mean * mean));
  const minc = edges * 0.002; let colors = 0; for (const v of cols.values()) if (v >= minc) colors++;
  for (const k in bd) bd[k] = edges ? bd[k] / edges : 0;
  return { W, H, mean, sd, detail: edges / n, bbox: edges ? [x0, y0, x1, y1] : null, colors, border: bd };
}"""

DIFF_JS = """async ([a, b]) => {
  const load = async s => { const im = new Image(); im.src = 'data:image/png;base64,' + s; await im.decode();
    const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const g = c.getContext('2d');
    g.drawImage(im, 0, 0); return g.getImageData(0, 0, im.width, im.height).data; };
  const A = await load(a), B = await load(b); let ch = 0, n = 0;
  for (let i = 0; i < A.length; i += 16) { n++; if (Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2]) > 30) ch++; }
  return ch / n;
}"""


def vendor_route(route):
    """three.js from any common CDN (jsdelivr / unpkg / skypack / esm.sh / cdnjs, any version) -> the local r160 copy"""
    url = route.request.url.split("?")[0]
    if re.search(r"(jsdelivr|unpkg|skypack|esm\.sh|cdnjs)", url) and "three" in url:
        m = re.search(r"examples/jsm/(.+?\.js)$", url) or re.search(r"/addons/(.+?\.js)$", url)
        rel = m.group(1) if m else "three.module.js"
        p = os.path.join(VENDOR, rel)
        if os.path.exists(p):
            return route.fulfill(path=p, content_type="application/javascript")
    if url.startswith(("http://", "https://")) and "127.0.0.1" not in url and "localhost" not in url:
        BLOCKED.append(url)
        return route.abort()
    return route.continue_()


BLOCKED = []


def on_alarm(signum, frame):
    # a page stuck in an endless loop blocks the browser thread; Playwright's own timeouts never fire then
    print("screenshot: none - the page did not finish building its scene in time")
    print("errors:\n  - TIMEOUT: scene.js never finished: an endless loop (check every while/for loop and recursion) or a "
          "far too heavy scene (millions of voxels: huge radius, nested loops over big boxes). Make it smaller/faster, then "
          "render again.", flush=True)
    os._exit(1)


def main():
    import base64
    import signal
    signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(int(os.environ.get("RENDER_LIMIT", "100")))
    from playwright.sync_api import sync_playwright
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    html = os.path.abspath(sys.argv[1])
    png = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(html)[0] + ".png"
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        w, h = (int(v) for v in os.environ.get("RENDER_SIZE", "800x500").split("x"))
        page = b.new_page(viewport={"width": w, "height": h})
        page.route("**/*", vendor_route)
        page.on("pageerror", lambda e: errors.append(str(e).splitlines()[0][:300]))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text[:300]))
        page.add_init_script("window.__vkLowCost = true")   # voxelkit: smaller shadow map, pixel ratio 1
        t0 = time.time()
        page.goto("file://" + html, wait_until="commit", timeout=60000)
        try:
            page.wait_for_function("() => (window.__vk && (window.__vk.started || window.__vkError)) || window.__vkError "
                                   "|| (!window.__vk && document.readyState === 'complete')", timeout=75000)
        except Exception as e:
            if "Timeout" not in str(e):
                raise
        page.wait_for_timeout(2500)
        shot1 = page.screenshot()
        page.wait_for_timeout(1000)
        shot2 = page.screenshot(path=png)
        vk = page.evaluate("window.__vk || null")
        syntax = None
        src = open(html, encoding="utf-8", errors="replace").read()
        if errors and "/*SCENE-BEGIN*/" in src:
            # a syntax error stops the whole module before any line mapping runs: compile the scene alone as a classic
            # script, where window.onerror gets the line number
            scene = src.split("/*SCENE-BEGIN*/\n", 1)[1].split("\n/*SCENE-END*/", 1)[0]
            syntax = page.evaluate("""(code) => new Promise(res => {
                const prev = window.onerror; let got = null;
                window.onerror = (msg, url, line, col) => { got = [String(msg), line, col]; return true; };
                const s = document.createElement('script'); s.textContent = '(function(){\\n' + code + '\\n})';
                document.head.appendChild(s); window.onerror = prev; res(got);
            })""", scene)
            if syntax and syntax[0].startswith(("SyntaxError", "Uncaught SyntaxError")):
                n = syntax[1] - 1
                lines = scene.split("\n")
                ctx = "\n".join(f"      {i + 1}| {lines[i]}" for i in range(max(0, n - 3), min(len(lines), n + 2)))
                msg = re.sub(r"^(Uncaught )?SyntaxError: (Failed to execute 'appendChild' on 'Node': )?", "", syntax[0])
                errors.insert(0, f"SYNTAX ERROR in scene.js line {n}, column {syntax[2]}: {msg}\n{ctx}")
        a = page.evaluate(ANALYZE_JS, base64.b64encode(shot2).decode())
        anim = page.evaluate(DIFF_JS, [base64.b64encode(shot1).decode(), base64.b64encode(shot2).decode()])
        b.close()
    errors = list(dict.fromkeys(e for e in errors if "net::ERR" not in e or "three" in e))
    blank = a["sd"] < 4 or a["detail"] < 0.004 or (a["mean"] < 25 and a["detail"] < 0.02)
    print(f"screenshot: {png} ({a['W']}x{a['H']}, rendered in {time.time() - t0:.0f} s)")
    print("errors:", "none" if not errors else "")
    for e in errors[:8]:
        print("  -", e)
    if any("CORS" in e and "vendor" in e for e in errors) or ".agent/webkit/vendor" in open(html, encoding="utf-8", errors="replace").read():
        print("  - the page loads .agent/webkit/vendor files directly: browsers block that for file:// pages. Do not write "
              "the html yourself - write scene.js and run build.py, which makes the right import map")
    for u in BLOCKED[:4]:
        print("  - external resource blocked (no network here; the page must work offline except three.js):", u)
    print(f"blank: {'YES - nothing visible (black/empty screen or camera pointing away)' if blank else 'no'}"
          f"  (mean brightness {a['mean']:.0f}, contrast {a['sd']:.0f})")
    print(f"detail: {a['detail']:.3f}" + ("  (low: the scene is small, plain or far away)" if not blank and a["detail"] < 0.03 else ""))
    if a["bbox"]:
        x0, y0, x1, y1 = a["bbox"]
        cut = [s for s, v in a["border"].items() if v > 0.04]
        fill = (x1 - x0) * (y1 - y0) / (a["W"] * a["H"])
        print(f"bbox: x {x0}-{x1}, y {y0}-{y1} (fills {fill:.0%} of the frame)"
              + (f"  CUT OFF at {'/'.join(cut)}: move the camera back or aim it at the center" if cut else "")
              + ("  (small: move the camera closer)" if fill < 0.15 else ""))
    print(f"colors: {a['colors']}" + ("  (few: add color variation / more materials)" if a["colors"] < 25 else ""))
    print(f"animation: {anim:.3f}" + ("  (static picture)" if anim < 0.002 else ""))
    if vk:
        labels = vk.get("labels") or {}
        print(f"voxelkit: {vk.get('voxels')} voxels, {vk.get('drawn')} drawn, labels {json.dumps(labels)}"
              + ("" if vk.get("started") else "  VK.start() was never reached"))
        kinds = [k for k in labels if k not in ("island", "pond")]
        if len(kinds) < 8:
            print(f"parts: {len(kinds)} labelled kinds besides island/pond (a rich scene has 8+; give every part a label)")
        fl = {k: n for k, n in (vk.get("floating") or {}).items() if n >= 4 and not any(w in k for w in ("petal", "cloud", "bird", "lantern light"))}
        if fl:
            print("floating: " + ", ".join(f"{k} {n} voxels" for k, n in fl.items())
                  + "  (not connected to anything below - a gap between parts; close it or rest it on the part below)")
        ow = {k: n for k, n in (vk.get("overWater") or {}).items() if "bridge" not in k and "lily" not in k and n >= 20}
        if ow:
            print("over the pond: " + ", ".join(f"{k} {n} voxels" for k, n in ow.items())
                  + "  (standing in the water? move it onto ground: check VK.inPond(x, z) before building)")
    sys.exit(0 if not errors and not blank else 1)


if __name__ == "__main__":
    main()
