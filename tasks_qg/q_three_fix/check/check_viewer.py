"""Hidden check for q_three_fix: angle units, colours, far plane, resize, frame-rate independent rotation."""
import math, sys
sys.path.insert(0, "/check")
import pngread
from playwright.sync_api import sync_playwright

fails, n = [], [0]
TAU = 2 * math.pi


def ok(cond, msg):
    n[0] += 1
    if not cond:
        fails.append(msg)


def close(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def ang_diff(a, b):
    d = (a - b) % TAU
    return min(d, TAU - d)


INFO = """async () => {
  const T = await import('./lib/three.module.js');
  const s = window.scene, out = {};
  for (const name of ['model', 'body', 'cap', 'farMarker']) {
    const o = s.getObjectByName(name);
    if (!o) { out[name] = null; continue; }
    o.updateWorldMatrix(true, false);
    const p = new T.Vector3(); o.getWorldPosition(p);
    const r = {type: o.type, pos: p.toArray(), parent: o.parent ? o.parent.name : null};
    if (o.isMesh) { r.color = o.material.color.getHexString(); r.mat = o.material.type; r.geo = o.geometry.type; r.params = o.geometry.parameters; }
    out[name] = r;
  }
  const c = window.camera, d = new T.Vector3(); c.getWorldDirection(d);
  out.camera = {fov: c.fov, near: c.near, far: c.far, aspect: c.aspect, pos: c.position.toArray(), dir: d.toArray()};
  const P = new T.Matrix4().multiplyMatrices(c.projectionMatrix, c.matrixWorldInverse);
  out.projAspect = c.projectionMatrix.elements[5] / c.projectionMatrix.elements[0];
  out.bg = s.background && s.background.isColor ? s.background.getHexString() : null;
  out.canvas = [window.renderer.domElement.width, window.renderer.domElement.height];
  out.rot = s.getObjectByName('model') ? s.getObjectByName('model').rotation.y : null;
  out.elapsed = window.elapsed;
  return out;
}"""

PROJECT = """async (pts) => {
  const T = await import('./lib/three.module.js');
  window.camera.updateMatrixWorld();
  return pts.map(([x, y, z]) => { const v = new T.Vector3(x, y, z).project(window.camera);
    return [Math.round((v.x + 1) / 2 * innerWidth), Math.round((1 - v.y) / 2 * innerHeight)]; });
}"""


def pixels(pg, pts):
    xy = pg.evaluate(PROJECT, pts)
    w, h, px = pngread.decode(pg.screenshot())
    return [px(min(max(x, 0), w - 1), min(max(y, 0), h - 1)) for x, y in xy]


def near_rgb(a, b, tol=10):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


SLOW_RAF = """(() => { const raf = window.requestAnimationFrame.bind(window); let k = 0;
  window.requestAnimationFrame = (cb) => { const f = (t) => { if (++k % 3) return raf(f); cb(t); }; return raf(f); }; })()"""


def rate_at_low_fps(b, obj, url):
    """Rotation speed in deg/s while only every 3rd animation frame runs (a frame-counting animation slows down)."""
    ctx = b.new_context(viewport={"width": 800, "height": 600}, device_scale_factor=1)
    ctx.add_init_script(SLOW_RAF)
    pg = ctx.new_page()
    pg.goto(url)
    pg.wait_for_function("window.ready === true", timeout=10000)
    pg.wait_for_timeout(300)
    q = f"[window.scene.getObjectByName('{obj}').rotation.y, performance.now()]"
    ra = pg.evaluate(q); pg.wait_for_timeout(1500); rb = pg.evaluate(q)
    ctx.close()
    return math.degrees(rb[0] - ra[0]) / ((rb[1] - ra[1]) / 1000)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files"])
        ctx = b.new_context(viewport={"width": 1000, "height": 700}, device_scale_factor=1)
        pg = ctx.new_page()
        errs = []
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file:///work/index.html")
        try:
            pg.wait_for_function("window.ready === true && !!window.scene && !!window.camera && !!window.renderer", timeout=10000)
        except Exception:
            print("FAIL: window.ready / scene / camera / renderer not set within 10 s", errs[:3]); sys.exit(1)
        pg.evaluate("window.paused = true")
        pg.wait_for_timeout(100)
        I = pg.evaluate(INFO)
        for name in ("model", "body", "cap", "farMarker"):
            ok(I.get(name) is not None, f"{name} missing")
        if fails:
            return report()
        ok(I["body"]["parent"] == "model" and I["cap"]["parent"] == "model", "body/cap must be children of model")
        ok(I["body"]["color"] == "3366cc", f"body color #{I['body']['color']} != #3366cc")
        ok(I["cap"]["color"] == "cc3333", f"cap color #{I['cap']['color']}")
        ok(I["farMarker"]["color"] == "ffcc00", f"farMarker color #{I['farMarker']['color']}")
        ok(I["bg"] == "101010", f"background #{I['bg']}")
        ok(close(I["farMarker"]["pos"], (0, 0.5, -40)), f"farMarker position {I['farMarker']['pos']}")
        c = I["camera"]
        ok(c["fov"] == 45 and close(c["pos"], (0, 3, 6)), f"camera {c}")
        ok(c["near"] <= 0.1 + 1e-9 and c["far"] >= 200 - 1e-6, f"camera must show 0.1..200 (near {c['near']}, far {c['far']})")
        # angle = 30 deg + 60 deg/s * elapsed
        want = math.radians(30) + math.radians(60) * I["elapsed"]
        ok(ang_diff(I["rot"], want) < 1e-4, f"model.rotation.y {math.degrees(I['rot']):.2f} deg != 30 + 60*elapsed = {math.degrees(want):.2f} deg")
        r0 = pg.evaluate("window.scene.getObjectByName('model').rotation.y")
        pg.wait_for_timeout(300)
        r1 = pg.evaluate("window.scene.getObjectByName('model').rotation.y")
        ok(abs(r1 - r0) < 1e-9, "model turned while paused")
        e0 = pg.evaluate("window.elapsed")
        r2, e2 = pg.evaluate("(() => { window.step(1.5); return [window.scene.getObjectByName('model').rotation.y, window.elapsed]; })()")
        ok(abs(e2 - e0 - 1.5) < 1e-9, f"step(1.5) must add 1.5 s to elapsed (added {e2 - e0})")
        ok(abs((r2 - r1) - math.pi / 2) < 1e-6, f"step(1.5) must turn 90 deg, turned {math.degrees(r2 - r1):.3f} deg")
        r3 = pg.evaluate("(() => { window.step(0.1); window.step(0.2); return window.scene.getObjectByName('model').rotation.y; })()")
        ok(abs((r3 - r2) - math.radians(18)) < 1e-6, f"step(0.1)+step(0.2) must turn 18 deg, turned {math.degrees(r3 - r2):.3f} deg")
        # pixels: body colour exact, far marker visible, cap visible
        pg.evaluate("(() => { const m = window.scene.getObjectByName('model'); window.step(0); })()")
        cols = pixels(pg, [(0, 0.5, 0.5), (0, 1.15, 0), (0, 0.5, -40)])
        ok(near_rgb(cols[0], (0x33, 0x66, 0xcc)), f"body pixel {cols[0]} != (51,102,204)")
        ok(near_rgb(cols[1], (0xcc, 0x33, 0x33)), f"cap pixel {cols[1]} != (204,51,51)")
        ok(near_rgb(cols[2], (0xff, 0xcc, 0x00)), f"farMarker pixel {cols[2]} (must be visible)")
        w, h, px = pngread.decode(pg.screenshot())
        ok(near_rgb(px(4, 4), (16, 16, 16), 3), f"background pixel {px(4, 4)}")
        # real time: about 60 deg/s regardless of frame rate
        ra = pg.evaluate("[window.scene.getObjectByName('model').rotation.y, performance.now()]")
        pg.evaluate("window.paused = false")
        pg.wait_for_timeout(1500)
        rb = pg.evaluate("[window.scene.getObjectByName('model').rotation.y, performance.now()]")
        rate = math.degrees(rb[0] - ra[0]) / ((rb[1] - ra[1]) / 1000)
        ok(45 <= rate <= 70, f"real-time speed {rate:.1f} deg/s (want 60)")
        # resize: canvas and aspect follow, no distortion
        for vw, vh in [(600, 800), (1200, 500)]:
            pg.set_viewport_size({"width": vw, "height": vh})
            pg.wait_for_timeout(300)
            J = pg.evaluate(INFO)
            ok(J["canvas"] == [vw, vh], f"canvas after resize to {vw}x{vh}: {J['canvas']}")
            ok(abs(J["camera"]["aspect"] - vw / vh) < 1e-3, f"aspect after resize to {vw}x{vh}: {J['camera']['aspect']}")
            ok(abs(J["projAspect"] - vw / vh) < 1e-3, f"projection matrix not updated after resize to {vw}x{vh}")
        pg.evaluate("window.paused = true")
        cols = pixels(pg, [(0, 0.5, -40)])
        ok(near_rgb(cols[0], (0xff, 0xcc, 0x00)), f"after resize farMarker pixel {cols[0]}")
        slow = rate_at_low_fps(b, "model", "file:///work/index.html")
        ok(51 <= slow <= 69, f"speed at a low frame rate {slow:.1f} deg/s (want 60: must not depend on the frame rate)")
        ok(errs == [], f"console errors: {errs[:3]}")
        b.close()
    report()


def report():
    if fails:
        print(f"SCORE {n[0] - len(fails)}/{n[0]}")
        print(f"FAIL {len(fails)} of {n[0]} checks:")
        for f in fails[:15]:
            print(" -", f)
        sys.exit(1)
    print(f"ok {n[0]} checks")
    print(f"SCORE {n[0]}/{n[0]}")
    sys.exit(0)


main()
