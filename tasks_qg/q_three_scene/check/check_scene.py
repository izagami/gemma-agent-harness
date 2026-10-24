"""Hidden check for q_three_scene: scene graph, camera, lights, pixels, resize and animation timing."""
import math, sys
sys.path.insert(0, "/check")
import pngread
from playwright.sync_api import sync_playwright

fails, n = [], [0]


def ok(cond, msg):
    n[0] += 1
    if not cond:
        fails.append(msg)


def close(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


INFO = """async () => {
  const T = await import('./lib/three.module.js');
  const s = window.scene, out = {};
  for (const name of ['floor','redBox','blueSphere','spinner','m0','m1','m2','markers','ambient','sun']) {
    const o = s.getObjectByName(name);
    if (!o) { out[name] = null; continue; }
    o.updateWorldMatrix(true, false);
    const p = new T.Vector3(); o.getWorldPosition(p);
    const r = {type: o.type, pos: [p.x, p.y, p.z], parent: o.parent ? o.parent.name : null};
    if (o.isMesh) {
      const b = new T.Box3().setFromObject(o), sz = new T.Vector3(); b.getSize(sz);
      const c = new T.Vector3(); b.getCenter(c);
      r.size = [sz.x, sz.y, sz.z]; r.center = [c.x, c.y, c.z];
      r.mat = o.material.type; r.color = o.material.color.getHexString();
      r.geo = o.geometry.type; r.params = o.geometry.parameters;
      const q = new T.Quaternion(); o.getWorldQuaternion(q);
      const nrm = new T.Vector3(0, 0, 1).applyQuaternion(q); r.normal = [nrm.x, nrm.y, nrm.z];
      const sc = new T.Vector3(); o.getWorldScale(sc); r.scale = [sc.x, sc.y, sc.z];
    }
    if (o.isLight) r.intensity = o.intensity;
    out[name] = r;
  }
  const c = window.camera, d = new T.Vector3(); c.getWorldDirection(d);
  out.camera = {type: c.type, fov: c.fov, near: c.near, far: c.far, aspect: c.aspect, pos: c.position.toArray(), dir: d.toArray()};
  out.bg = s.background && s.background.isColor ? s.background.getHexString() : null;
  out.canvas = [window.renderer.domElement.width, window.renderer.domElement.height];
  out.inner = [innerWidth, innerHeight];
  out.scroll = [document.documentElement.scrollWidth, document.documentElement.scrollHeight];
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


def near_rgb(a, b, tol=12):
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
        ctx = b.new_context(viewport={"width": 1024, "height": 768}, device_scale_factor=1)
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
        want = {"floor": ((0, 0, 0), (10, 0, 10), "404040", "PlaneGeometry"), "redBox": ((-2, 0.5, 0), (1, 1, 1), "ff0000", "BoxGeometry"),
                "blueSphere": ((2, 0.75, 0), (1.5, 1.5, 1.5), "0000ff", "SphereGeometry"),
                "m0": ((-1, 0.1, 2), (0.2, 0.2, 0.2), "ffff00", "BoxGeometry"), "m1": ((0, 0.1, 2), (0.2, 0.2, 0.2), "ffff00", "BoxGeometry"),
                "m2": ((1, 0.1, 2), (0.2, 0.2, 0.2), "ffff00", "BoxGeometry")}
        for name, (pos, size, col, geo) in want.items():
            o = I.get(name)
            ok(o is not None and o["type"] == "Mesh", f"{name}: missing or not a Mesh")
            if not o or o["type"] != "Mesh":
                continue
            ok(close(o["center"], pos, 0.02), f"{name}: world center {o['center']} != {pos}")
            ok(close(o["size"], size, 0.02), f"{name}: world size {o['size']} != {size}")
            ok(o["color"] == col, f"{name}: color #{o['color']} != #{col}")
            ok(o["mat"] == "MeshBasicMaterial", f"{name}: material {o['mat']}")
            ok(o["geo"] == geo, f"{name}: geometry {o['geo']}")
        fl = I.get("floor")
        ok(fl is not None and fl.get("normal") and fl["normal"][1] > 0.999, f"floor must face +Y, normal {fl and fl.get('normal')}")
        sp = I.get("spinner")
        ok(sp is not None and sp["type"] == "Mesh" and sp["geo"] == "BoxGeometry", "spinner missing")
        if sp and sp.get("params"):
            pr = sp["params"]
            ok(close([pr.get("width", 0) * sp["scale"][0], pr.get("height", 0) * sp["scale"][1], pr.get("depth", 0) * sp["scale"][2]], (0.5, 2, 0.5), 0.01),
               f"spinner size {pr} scale {sp['scale']}")
            ok(close(sp["pos"], (0, 1, -2), 0.01), f"spinner position {sp['pos']}")
            ok(sp["color"] == "00ff00" and sp["mat"] == "MeshBasicMaterial", "spinner color/material")
        mk = I.get("markers")
        ok(mk is not None and mk["type"] == "Group" and close(mk["pos"], (0, 0, 2)), f"markers group {mk}")
        ok(all(I.get(m) and I[m]["parent"] == "markers" for m in ("m0", "m1", "m2")), "m0..m2 must be children of markers")
        a, s = I.get("ambient"), I.get("sun")
        ok(a is not None and a["type"] == "AmbientLight" and abs(a["intensity"] - 0.5) < 1e-6, f"ambient {a}")
        ok(s is not None and s["type"] == "DirectionalLight" and abs(s["intensity"] - 1) < 1e-6 and close(s["pos"], (5, 10, 5)), f"sun {s}")
        c = I["camera"]
        ok(c["type"] == "PerspectiveCamera" and c["fov"] == 50 and abs(c["near"] - 0.1) < 1e-9 and c["far"] == 100, f"camera params {c}")
        ok(close(c["pos"], (0, 5, 8)), f"camera position {c['pos']}")
        tgt = (0, 0.5, 0); v = [t - p_ for t, p_ in zip(tgt, c["pos"])]; L = math.sqrt(sum(x * x for x in v))
        ok(sum(x / L * y for x, y in zip(v, c["dir"])) > 0.9999, f"camera must look at (0,0.5,0), dir {c['dir']}")
        ok(abs(c["aspect"] - 1024 / 768) < 1e-3 and I["canvas"] == [1024, 768], f"aspect {c['aspect']} canvas {I['canvas']}")
        ok(I["scroll"][0] <= 1024 and I["scroll"][1] <= 768, f"page scrolls: {I['scroll']}")
        # pixels where the objects must be visible
        pts = [(-2, 0.5, 0), (2, 0.75, 0), (0, 1, -2), (0, 0.1, 2), (3.5, 0, 3.5), (-3.5, 0, -3)]
        cols = pixels(pg, pts)
        exp = [(255, 0, 0), (0, 0, 255), (0, 255, 0), (255, 255, 0), (64, 64, 64), (64, 64, 64)]
        for pt, got, e in zip(pts, cols, exp):
            ok(near_rgb(got, e), f"pixel at {pt}: {got} != {e}")
        w, h, px = pngread.decode(pg.screenshot())
        ok(near_rgb(px(5, 5), (0, 0, 0), 4) and near_rgb(px(w - 5, 5), (0, 0, 0), 4), f"background must be black {px(5, 5)}")
        # animation: paused -> no real-time rotation; step(dt) -> exact angle
        r0 = pg.evaluate("window.scene.getObjectByName('spinner').rotation.y")
        pg.wait_for_timeout(400)
        r1 = pg.evaluate("window.scene.getObjectByName('spinner').rotation.y")
        ok(abs(r1 - r0) < 1e-9, f"spinner moved while paused ({r0} -> {r1})")
        r2 = pg.evaluate("(() => { window.step(2); return window.scene.getObjectByName('spinner').rotation.y; })()")
        ok(abs((r2 - r1) - math.pi / 2) < 1e-6, f"step(2) must add 90 deg, added {math.degrees(r2 - r1):.3f} deg")
        r3 = pg.evaluate("(() => { window.step(0.25); return window.scene.getObjectByName('spinner').rotation.y; })()")
        ok(abs((r3 - r2) - math.pi / 16) < 1e-6, f"step(0.25) must add 11.25 deg, added {math.degrees(r3 - r2):.3f} deg")
        # rendered after step: the spinner's side is now facing differently, the canvas must show it (frame rendered at once)
        ra = pg.evaluate("[window.scene.getObjectByName('spinner').rotation.y, performance.now()]")
        pg.evaluate("window.paused = false")
        pg.wait_for_timeout(1500)
        rb = pg.evaluate("[window.scene.getObjectByName('spinner').rotation.y, performance.now()]")
        rate = math.degrees(rb[0] - ra[0]) / ((rb[1] - ra[1]) / 1000)
        ok(38 <= rate <= 52, f"real-time rotation speed {rate:.1f} deg/s (want 45)")
        # resize
        pg.set_viewport_size({"width": 900, "height": 500})
        pg.wait_for_timeout(300)
        pg.evaluate("window.paused = true")
        pg.wait_for_timeout(100)
        I2 = pg.evaluate(INFO)
        ok(I2["canvas"] == [900, 500], f"canvas after resize {I2['canvas']}")
        ok(abs(I2["camera"]["aspect"] - 900 / 500) < 1e-3, f"aspect after resize {I2['camera']['aspect']}")
        cols = pixels(pg, pts[:4])
        for pt, got, e in zip(pts[:4], cols, exp[:4]):
            ok(near_rgb(got, e), f"after resize pixel at {pt}: {got} != {e}")
        slow = rate_at_low_fps(b, "spinner", "file:///work/index.html")
        ok(38 <= slow <= 52, f"speed at a low frame rate {slow:.1f} deg/s (want 45: must not depend on the frame rate)")
        ok(errs == [], f"console errors: {errs[:3]}")
        b.close()
    if fails:
        print(f"SCORE {n[0] - len(fails)}/{n[0]}")
        print(f"FAIL {len(fails)} of {n[0]} checks:")
        for f in fails[:15]:
            print(" -", f)
        sys.exit(1)
    print(f"ok {n[0]} checks")
    print(f"SCORE {n[0]}/{n[0]}")


main()
