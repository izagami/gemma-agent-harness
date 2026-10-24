// voxelkit: tested building blocks for voxel-art scenes in three.js (r160).
// build.py inlines this file and your scene.js into ONE html file; in scene.js the globals are THREE and VK.
//
// World (integer coordinates, y is up; 1 unit = 1 voxel)
//   VK.seed(n); VK.rand() -> [0,1); VK.noise(x, z) -> smooth [0,1)
//   VK.set(x, y, z, color, opts)    opts: {jitter: 0.06 (per-voxel brightness variation), glow: true (emissive,
//                                   lights up at night), water: true (transparent animated), label: "pagoda"}
//   VK.del / VK.has / VK.get(x, y, z)
//   VK.box(x0, y0, z0, x1, y1, z1, color, opts)          filled box (inclusive corners)
//   VK.shell(x0, y0, z0, x1, y1, z1, color, opts)        walls only (hollow box without top/bottom)
//   VK.sphere(cx, cy, cz, r, color, opts)                 color may be an array: a random one per voxel
//                                                         opts.fill 0..1 leaves gaps (foliage), opts.squash scales y
//   VK.cylinder(cx, y0, cz, r, h, color, opts)
//   VK.line(x0, y0, z0, x1, y1, z1, color, opts)          3D line of voxels
//   VK.roof(cx, y, cz, halfW, opts)                       East-Asian hip roof: wide eaves, steps inward, corners
//                                                         curl up; opts {halfD, overhang:3, layers:3, color, edge,
//                                                         tip (corner ornament color), glowTips} -> top y
//   VK.island({radius: 30, top: 4, hill: [x, z, r, h], depthScale}) -> floating island with grass/dirt/stone
//                                                         layers and a rocky underside; afterwards VK.H(x, z)
//                                                         gives the ground top (or -Infinity off the island)
//   VK.pond(cx, cz, rx, rz) carve an elliptic pond with water + sand bed + stone rim; VK.inPond(x, z)
//   VK.scatter(n, fn) call fn(x, z, groundY) at n random free ground points (not in ponds)
//   VK.blobTree(x, z, {trunk, trunkH, r, colors, fill, fallen}) round canopy tree (sakura, maple, oak...)
//   VK.padTree(x, z, {trunk, pads: [[dx, dy, dz, r], ...], colors}) cloud-pruned pine (niwaki)
//   VK.PAL                       palette of tested colors (grass, dirt, stone, water, red, gold, roof, sakura ...)
// Scene
//   VK.start({title, subtitle, sky: "sunset"|"day"|"dusk", petals: {colors, from: [[x,y,z],...], count},
//             fireflies: true, clouds: true, dayNight: true, autoRotate: true, onFrame(t, dt)})
//     builds meshes (hidden voxels culled, one instanced draw per material), sun + soft shadows + sky gradient + fog,
//     camera framed automatically on everything you built, orbit controls, title overlay, Day/Night + Rotate
//     buttons, animation loop. Returns {scene, camera, renderer, controls, add(object3d)}.
//   VK.mover(object3d, fn(t)) animate your own meshes (koi, birds, a turning wheel...): fn sets its position/rotation
// Checks: window.__vk = {voxels, drawn, labels: {name: count}, bounds, started, frames}
(() => {
  let s = 7;
  const VK = (window.VK = {});
  VK.seed = n => { s = Math.max(1, Math.floor(n)) % 2147483647; };
  VK.rand = () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
  VK.noise = (x, z) => {
    const h = (i, j) => { const v = Math.sin(i * 127.1 + j * 311.7) * 43758.5453; return v - Math.floor(v); };
    const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi;
    const u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
    return (h(xi, zi) * (1 - u) + h(xi + 1, zi) * u) * (1 - v) + (h(xi, zi + 1) * (1 - u) + h(xi + 1, zi + 1) * u) * v;
  };
  VK.PAL = {
    grass: 0x6fae4a, grass2: 0x86c25a, moss: 0x4f8a3c, leaf: 0x5c9a45, dirt: 0x8a5a3b, stone: 0x9c9a92, stoneD: 0x77756e,
    sand: 0xe8dcc0, sandD: 0xd6c7a4, water: 0x3d9bc4, red: 0xc0392b, redD: 0x962d22, wood: 0x6b4226, woodL: 0x9a6a3f,
    roof: 0x2f3b45, roofL: 0x3d4c58, gold: 0xe0b23c, white: 0xf3ede1, bark: 0x5b3a29, lantern: 0xffd27a,
    sakura: [0xf7b6c8, 0xf29bb5, 0xfcd4df], maple: [0xd9481f, 0xe8742a, 0xb5301c], pine: [0x2f6b3a, 0x3f7f47],
    flowers: [0xffffff, 0xffd84d, 0xb388ff, 0xff6f91], azalea: 0xd94f7a, lily: 0x5d9e3f, koi: 0xf2762e
  };
  const vox = new Map();
  const K = (x, y, z) => x + "," + y + "," + z;
  const stats = (window.__vk = { voxels: 0, drawn: 0, labels: {}, bounds: null, started: false, frames: 0 });
  const pick = c => (Array.isArray(c) ? c[Math.floor(VK.rand() * c.length)] : c);
  VK.set = (x, y, z, color, o = {}) => {
    x = Math.round(x); y = Math.round(y); z = Math.round(z);
    const c = new THREE.Color(pick(color));
    const j = o.jitter ?? 0.06;
    if (j) c.multiplyScalar(1 + (VK.rand() - 0.5) * 2 * j);
    vox.set(K(x, y, z), { c, glow: !!o.glow, water: !!o.water, label: o.label });
  };
  VK.del = (x, y, z) => vox.delete(K(Math.round(x), Math.round(y), Math.round(z)));
  VK.has = (x, y, z) => vox.has(K(Math.round(x), Math.round(y), Math.round(z)));
  VK.get = (x, y, z) => vox.get(K(Math.round(x), Math.round(y), Math.round(z)));
  VK.box = (x0, y0, z0, x1, y1, z1, color, o) => {
    for (let x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) for (let y = Math.min(y0, y1); y <= Math.max(y0, y1); y++)
      for (let z = Math.min(z0, z1); z <= Math.max(z0, z1); z++) VK.set(x, y, z, color, o);
  };
  VK.shell = (x0, y0, z0, x1, y1, z1, color, o) => {
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++)
      if (x === x0 || x === x1 || z === z0 || z === z1) VK.set(x, y, z, color, o);
  };
  VK.sphere = (cx, cy, cz, r, color, o = {}) => {
    const sq = o.squash ?? 1, fill = o.fill ?? 1;
    for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++)
      if (Math.hypot(x, y / sq, z) <= r && VK.rand() < fill) VK.set(cx + x, cy + y * sq, cz + z, color, o);
  };
  VK.cylinder = (cx, y0, cz, r, h, color, o) => {
    for (let y = y0; y < y0 + h; y++) for (let x = -r; x <= r; x++) for (let z = -r; z <= r; z++)
      if (Math.hypot(x, z) <= r + 0.3) VK.set(cx + x, y, cz + z, color, o);
  };
  VK.line = (x0, y0, z0, x1, y1, z1, color, o) => {
    const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0), 1);
    for (let i = 0; i <= n; i++) VK.set(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, z0 + (z1 - z0) * i / n, color, o);
  };
  VK.roof = (cx, y, cz, halfW, o = {}) => {
    const hd = o.halfD ?? halfW, ov = o.overhang ?? 3, layers = o.layers ?? 3;
    const color = o.color ?? VK.PAL.roof, edge = o.edge ?? VK.PAL.roofL, tip = o.tip ?? VK.PAL.gold;
    for (let l = 0; l < layers; l++) {
      const rx = halfW + ov - l * 2, rz = hd + ov - l * 2;
      if (rx < 0 || rz < 0) break;
      for (let x = -rx; x <= rx; x++) for (let z = -rz; z <= rz; z++) {
        // each layer reaches inward to just inside the wall line (halfW - 1 - l), so the roof rests on the walls /
        // brackets below and the layers overlap - no gap under the eaves
        const inner = Math.abs(x) < halfW - 1 - l && Math.abs(z) < hd - 1 - l;
        if (inner && l < layers - 1) continue;
        const corner = Math.abs(x) >= rx - 1 && Math.abs(z) >= rz - 1;
        const lift = l === 0 && corner ? 1 : 0;
        VK.set(cx + x, y + l + lift, cz + z, l === 0 && (Math.abs(x) === rx || Math.abs(z) === rz) ? edge : color, { label: o.label });
        if (l === 0 && Math.abs(x) === rx && Math.abs(z) === rz) {
          VK.set(cx + x, y + 1 + lift, cz + z, tip, { jitter: 0.02, label: o.label });
          if (o.glowTips !== false) VK.set(cx + x, y - 1 + lift, cz + z, VK.PAL.lantern, { jitter: 0, glow: true, label: o.label });
        }
      }
    }
    return y + layers;
  };
  const height = new Map();
  VK.H = (x, z) => height.get(Math.round(x) + "," + Math.round(z)) ?? -Infinity;
  VK.island = (o = {}) => {
    const R = o.radius ?? 30, top = o.top ?? 4, ds = o.depthScale ?? 0.55;
    for (let x = -R; x <= R; x++) for (let z = -R; z <= R; z++) {
      const d = Math.hypot(x, z) + VK.noise(x * 0.15, z * 0.15) * 5;
      if (d > R) continue;
      let h = top + Math.round(VK.noise(x * 0.08 + 3, z * 0.08) * 2);
      if (o.hill) { const [hx, hz, hr, hh] = o.hill, dd = Math.hypot(x - hx, z - hz); if (dd < hr) h += Math.round((1 - dd / hr) * hh); }
      const depth = Math.round(3 + (R - d) * ds + VK.noise(x * 0.3, z * 0.3) * 4);
      height.set(x + "," + z, h);
      for (let y = -depth; y <= h; y++)
        VK.set(x, y, z, y === h ? (VK.noise(x * 0.4, z * 0.4) > 0.55 ? VK.PAL.grass2 : VK.PAL.grass)
          : y > h - 3 ? VK.PAL.dirt : VK.rand() < 0.15 ? VK.PAL.stoneD : VK.PAL.stone, { jitter: 0.08, label: "island" });
    }
    return VK.H;
  };
  const ponds = [], waterY = new Map();
  VK.inPond = (x, z) => ponds.some(([cx, cz, rx, rz]) => ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 < 1);
  VK.pond = (cx, cz, rx, rz) => {
    ponds.push([cx, cz, rx, rz]);
    for (let x = Math.floor(cx - rx - 1); x <= cx + rx + 1; x++) for (let z = Math.floor(cz - rz - 1); z <= cz + rz + 1; z++) {
      const h = VK.H(x, z);
      if (h === -Infinity) continue;
      if (VK.inPond(x, z)) {
        VK.del(x, h, z); VK.del(x, h - 1, z);
        VK.set(x, h - 2, z, VK.PAL.sandD, { label: "pond" });
        VK.set(x, h - 1, z, VK.PAL.water, { jitter: 0.03, water: true, label: "pond" }); waterY.set(x + "," + z, h - 1);
      } else if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([a, b]) => VK.inPond(x + a, z + b)) && VK.rand() < 0.55)
        VK.set(x, h + 1, z, [VK.PAL.stone, VK.PAL.stoneD], { jitter: 0.1, label: "pond" });
    }
  };
  VK.scatter = (n, fn, tries = 20) => {
    let xs = [], zs = [];
    for (const k of height.keys()) { const [x, z] = k.split(",").map(Number); xs.push(x); zs.push(z); }
    for (let i = 0; i < n * tries && n > 0; i++) {
      const j = Math.floor(VK.rand() * xs.length), x = xs[j], z = zs[j], h = VK.H(x, z);
      if (VK.inPond(x, z) || VK.has(x, h + 1, z)) continue;
      if (fn(x, z, h) !== false) n--;
    }
  };
  VK.blobTree = (x, z, o = {}) => {
    const h0 = VK.H(x, z) + 1, th = o.trunkH ?? 6, r = o.r ?? 4, colors = o.colors ?? VK.PAL.sakura;
    for (let y = 0; y < th; y++) {
      const dx = y > th * 0.6 ? 1 : 0;
      VK.set(x + dx, h0 + y, z, o.trunk ?? VK.PAL.bark, { jitter: 0.1, label: o.label ?? "tree" });
      if (dx && !(y - 1 > th * 0.6)) VK.set(x, h0 + y, z, o.trunk ?? VK.PAL.bark, { jitter: 0.1, label: o.label ?? "tree" }); // keep the bend connected
    }
    VK.sphere(x + 1, h0 + th + 1, z, r, colors, { fill: o.fill ?? 0.88, squash: 0.75, jitter: 0.05, label: o.label ?? "tree" });
    for (let i = 0; i < (o.fallen ?? 12); i++) {
      const px = x + Math.round((VK.rand() - 0.5) * r * 3), pz = z + Math.round((VK.rand() - 0.5) * r * 3), ph = VK.H(px, pz);
      if (ph > -Infinity && !VK.inPond(px, pz) && !VK.has(px, ph + 1, pz)) VK.set(px, ph + 1, pz, pick(colors), { label: o.label ?? "tree" });
    }
    return [x + 1, h0 + th + 1, z];
  };
  VK.padTree = (x, z, o = {}) => {
    const h0 = VK.H(x, z) + 1, colors = o.colors ?? VK.PAL.pine;
    for (let y = 0; y < 7; y++) {
      const dx = (y > 3 ? 1 : 0) + (y > 5 ? 1 : 0);
      VK.set(x + dx, h0 + y, z, o.trunk ?? VK.PAL.bark, { jitter: 0.1, label: "tree" });
      if (y === 4 || y === 6) VK.set(x + dx - 1, h0 + y, z, o.trunk ?? VK.PAL.bark, { jitter: 0.1, label: "tree" });  // connected bends
    }
    for (const [ox, oy, oz, r] of o.pads ?? [[2, 7, 0, 3], [-1, 5, 1, 2.2], [3, 4, -1, 2], [0, 9, 0, 2]])
      for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) for (let dy = 0; dy <= 1; dy++)
        if (Math.hypot(dx, dz) < r - dy * 0.6) VK.set(x + ox + dx, h0 + oy + dy, z + oz + dz, colors, { jitter: 0.08, label: "tree" });
  };

  const movers = [];
  VK.mover = (obj, fn) => movers.push([obj, fn]);

  VK.start = (o = {}) => {
    const scene = new THREE.Scene();
    const geo = new THREE.BoxGeometry(1, 1, 1);
    const groups = { solid: [], water: [], glow: [] };
    const bb = new THREE.Box3();
    for (const [k, v] of vox) {
      const [x, y, z] = k.split(",").map(Number);
      stats.voxels++;
      if (v.label) stats.labels[v.label] = (stats.labels[v.label] || 0) + 1;
      bb.expandByPoint(new THREE.Vector3(x, y, z));
      if (VK.has(x + 1, y, z) && VK.has(x - 1, y, z) && VK.has(x, y + 1, z) && VK.has(x, y - 1, z) && VK.has(x, y, z + 1) && VK.has(x, y, z - 1)) continue;
      groups[v.water ? "water" : v.glow ? "glow" : "solid"].push([x, y, z, v.c]);
    }
    // parts built over a pond (a building standing in the water is a placement mistake; bridges are fine)
    stats.overWater = {};
    for (const [k, v] of vox) {
      if (v.water || v.label === "pond" || v.label === "island") continue;
      const [x, y, z] = k.split(",").map(Number), wy = waterY.get(x + "," + z);
      if (wy !== undefined && (y === wy + 1 || y === wy + 2)) { const l = v.label || "unlabelled"; stats.overWater[l] = (stats.overWater[l] || 0) + 1; }
    }
    // floating parts: voxels not touching (26-neighbour) anything connected to the island / ground
    stats.floating = {};
    {
      const seen = new Set(), queue = [];
      for (const [k, v] of vox) if (v.label === "island") { seen.add(k); queue.push(k); }
      if (!queue.length) { let lowest = null; for (const k of vox.keys()) { const y = +k.split(",")[1]; if (lowest === null || y < lowest[1]) lowest = [k, y]; } if (lowest) { seen.add(lowest[0]); queue.push(lowest[0]); } }
      while (queue.length) {
        const [x, y, z] = queue.pop().split(",").map(Number);
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {   // touching at an edge or corner counts
          const n = K(x + a, y + b, z + c);
          if (vox.has(n) && !seen.has(n)) { seen.add(n); queue.push(n); }
        }
      }
      stats.floatSample = {};
      for (const [k, v] of vox) if (!seen.has(k)) { const l = v.label || "unlabelled"; stats.floating[l] = (stats.floating[l] || 0) + 1; if (!stats.floatSample[l]) stats.floatSample[l] = k; }
    }
    if (!stats.voxels) throw new Error("VK.start(): no voxels were set - build the world before calling VK.start()");
    const mk = (list, mat, cast) => {
      if (!list.length) return null;
      const m = new THREE.InstancedMesh(geo, mat, list.length), M = new THREE.Matrix4();
      list.forEach(([x, y, z, c], i) => { M.setPosition(x, y, z); m.setMatrixAt(i, M); m.setColorAt(i, c); });
      m.castShadow = cast; m.receiveShadow = true; scene.add(m); stats.drawn += list.length; return m;
    };
    mk(groups.solid, new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0.02 }), true);
    const waterMat = new THREE.MeshStandardMaterial({ transparent: true, opacity: 0.78, roughness: 0.15, metalness: 0.1 });
    mk(groups.water, waterMat, false);
    const glowMat = new THREE.MeshStandardMaterial({ emissive: 0xffb347, emissiveIntensity: 0.3 });
    mk(groups.glow, glowMat, false);
    const size = bb.getSize(new THREE.Vector3()), center = bb.getCenter(new THREE.Vector3());
    stats.bounds = { min: bb.min.toArray(), max: bb.max.toArray() };

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(innerWidth, innerHeight);
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
    document.body.style.margin = "0"; document.body.style.overflow = "hidden";
    document.body.appendChild(renderer.domElement);

    // camera framed on the bounding sphere of everything built
    const radius = size.length() / 2;
    const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.5, radius * 20);
    // frame what is above ground mostly (the rocky underside of an island should not push the camera away)
    // ground level = most common top height of the island; frame from slightly below it to the top
    const tops = [...height.values()].sort((a, b) => a - b), ground = tops.length ? tops[tops.length >> 1] : bb.min.y;
    const low = Math.max(bb.min.y, ground - size.y * 0.15), focus = center.clone(); focus.y = (low + bb.max.y) / 2;
    const frameR = Math.hypot(size.x, bb.max.y - low, size.z) / 2;
    const fitDist = frameR / Math.sin(THREE.MathUtils.degToRad(42) / 2) * (innerWidth < innerHeight ? 1.3 : 0.85);
    const dir = new THREE.Vector3(0.62, 0.36, 0.66).normalize();
    camera.position.copy(focus).addScaledVector(dir, fitDist);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.copy(focus); controls.enableDamping = true;
    controls.autoRotate = o.autoRotate !== false; controls.autoRotateSpeed = 0.45;
    controls.maxPolarAngle = Math.PI * 0.6; controls.minDistance = radius * 0.4; controls.maxDistance = radius * 6;

    const hemi = new THREE.HemisphereLight(0xfff1e0, 0x6b8f5a, 0.9); scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xffe2c0, 2.4);
    sun.position.copy(center).add(new THREE.Vector3(radius * 0.9, radius * 1.4, radius * 0.5));
    sun.target.position.copy(center); scene.add(sun.target);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004;
    Object.assign(sun.shadow.camera, { left: -radius, right: radius, top: radius, bottom: -radius, near: 1, far: radius * 4 });
    scene.add(sun);
    const glowPts = groups.glow.slice(0, 6).map(([x, y, z]) => { const l = new THREE.PointLight(0xffa64d, 0, 18, 1.6); l.position.set(x, y, z); scene.add(l); return l; });

    const SKY = { sunset: [0x7fb8e6, 0xf9d7c3, 0xf6b38a], day: [0x5aa9e6, 0xcfe8f7, 0xa9d3ee], dusk: [0x2c3e7a, 0xe08a6b, 0x6a4a7a] }[o.sky ?? "sunset"] ?? [0x7fb8e6, 0xf9d7c3, 0xf6b38a];
    const skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false,
      uniforms: { top: { value: new THREE.Color(SKY[0]) }, mid: { value: new THREE.Color(SKY[1]) }, bot: { value: new THREE.Color(SKY[2]) } },
      vertexShader: "varying vec3 p; void main(){ p = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
      fragmentShader: "uniform vec3 top, mid, bot; varying vec3 p; void main(){ float h = p.y; vec3 c = h > 0.0 ? mix(mid, top, pow(h, 0.6)) : mix(mid, bot, pow(-h, 0.5)); gl_FragColor = vec4(c, 1.0); }"
    });
    const sky = new THREE.Mesh(new THREE.SphereGeometry(radius * 12, 32, 16), skyMat); sky.position.copy(center); scene.add(sky);
    scene.fog = new THREE.Fog(SKY[1], radius * 4, radius * 11);

    // petals
    let petals = null, petalData = [];
    if (o.petals) {
      const n = o.petals.count ?? 400, from = o.petals.from?.length ? o.petals.from : [[center.x, bb.max.y, center.z]];
      petals = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.35, 0.25), new THREE.MeshStandardMaterial({ side: THREE.DoubleSide }), n);
      for (let i = 0; i < n; i++) {
        const f = from[i % from.length];
        petalData.push({ f, x: f[0] + (VK.rand() - .5) * 10, y: f[1] - VK.rand() * 10, z: f[2] + (VK.rand() - .5) * 10, v: 0.6 + VK.rand() * 0.8, ph: VK.rand() * 6.28 });
        petals.setColorAt(i, new THREE.Color(pick(o.petals.colors ?? VK.PAL.sakura)));
      }
      scene.add(petals);
    }
    // fireflies
    let flies = null, flyBase = [];
    if (o.fireflies !== false) {
      const n = 120, pos = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) flyBase.push([bb.min.x + VK.rand() * size.x, center.y + VK.rand() * size.y * 0.4, bb.min.z + VK.rand() * size.z, VK.rand() * 6.28]);
      flies = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ color: 0xfff3a0, size: 0.5, transparent: true, opacity: 0 }));
      flies.geometry.setAttribute("position", new THREE.BufferAttribute(pos, 3)); scene.add(flies);
    }
    // clouds
    const clouds = new THREE.Group(), cloudMat = new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.92 });
    if (o.clouds !== false) {
      for (let i = 0; i < 9; i++) {
        const c = new THREE.Group();
        for (let j = 0; j < 6; j++) {
          const b = new THREE.Mesh(new THREE.BoxGeometry(4 + VK.rand() * 6, 2 + VK.rand() * 2, 3 + VK.rand() * 4), cloudMat);
          b.position.set((VK.rand() - .5) * 8, (VK.rand() - .5) * 1.5, (VK.rand() - .5) * 4); c.add(b);
        }
        const a = (i / 9) * Math.PI * 2, r = radius * (1.6 + VK.rand() * 0.6);
        c.position.set(center.x + Math.cos(a) * r, bb.min.y + VK.rand() * size.y, center.z + Math.sin(a) * r); clouds.add(c);
      }
      scene.add(clouds);
    }
    // overlay + buttons
    const css = document.createElement("style");
    css.textContent = `#vk-title{position:fixed;left:24px;top:20px;color:#fff;text-shadow:0 2px 12px rgba(80,30,20,.45);pointer-events:none;font-family:Georgia,serif}
#vk-title h1{margin:0;font-size:28px;letter-spacing:.18em;font-weight:600}#vk-title p{margin:4px 0 0;font-size:13px;letter-spacing:.12em}
#vk-ui{position:fixed;right:20px;bottom:20px;display:flex;gap:8px}#vk-ui button{background:rgba(255,255,255,.8);border:0;border-radius:18px;padding:8px 14px;font:13px sans-serif;color:#5a2a1e;cursor:pointer}
#vk-hint{position:fixed;left:24px;bottom:20px;color:rgba(255,255,255,.9);font:12px sans-serif;text-shadow:0 1px 4px rgba(0,0,0,.4)}`;
    document.head.appendChild(css);
    const ov = document.createElement("div"); ov.id = "vk-title";
    ov.innerHTML = `<h1></h1><p></p>`; ov.querySelector("h1").textContent = o.title ?? ""; ov.querySelector("p").textContent = o.subtitle ?? "";
    document.body.appendChild(ov);
    const hint = document.createElement("div"); hint.id = "vk-hint"; hint.textContent = "Drag to orbit · Scroll to zoom · Right-drag to pan"; document.body.appendChild(hint);
    const ui = document.createElement("div"); ui.id = "vk-ui"; document.body.appendChild(ui);
    let night = 0, nightTarget = 0;
    if (o.dayNight !== false) {
      const b = document.createElement("button"); b.textContent = "🌙 Night"; ui.appendChild(b);
      b.onclick = () => { nightTarget = 1 - nightTarget; b.textContent = nightTarget ? "☀️ Day" : "🌙 Night"; };
    }
    const rb = document.createElement("button"); rb.textContent = "⏸ Rotate"; ui.appendChild(rb);
    rb.onclick = () => { controls.autoRotate = !controls.autoRotate; rb.textContent = controls.autoRotate ? "⏸ Rotate" : "▶ Rotate"; };
    addEventListener("resize", () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

    const N = [0x0b1030, 0x2b2a5a, 0x3a2449], L = (a, b, t) => new THREE.Color(a).lerp(new THREE.Color(b), t);
    const clock = new THREE.Clock(), M = new THREE.Matrix4(), Q = new THREE.Quaternion(), E = new THREE.Euler(), S1 = new THREE.Vector3(1, 1, 1), P = new THREE.Vector3();
    const loop = () => {
      const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
      night += (nightTarget - night) * Math.min(1, dt * 2.5);
      skyMat.uniforms.top.value.copy(L(SKY[0], N[0], night)); skyMat.uniforms.mid.value.copy(L(SKY[1], N[1], night));
      skyMat.uniforms.bot.value.copy(L(SKY[2], N[2], night)); scene.fog.color.copy(L(SKY[1], 0x1d1c3d, night));
      sun.intensity = 2.4 - 2.15 * night; hemi.intensity = 0.9 - 0.68 * night; glowMat.emissiveIntensity = 0.3 + 2.7 * night;
      glowPts.forEach(l => (l.intensity = 22 * night)); cloudMat.color.copy(L(0xffffff, 0x4a4a7a, night));
      if (flies) {
        flies.material.opacity = night; const a = flies.geometry.attributes.position.array;
        flyBase.forEach(([x, y, z, ph], i) => { a[i * 3] = x + Math.sin(t * 0.7 + ph) * 2; a[i * 3 + 1] = y + Math.sin(t * 1.3 + ph * 2) * 1.2; a[i * 3 + 2] = z + Math.cos(t * 0.6 + ph) * 2; });
        flies.geometry.attributes.position.needsUpdate = true;
      }
      if (petals) {
        petalData.forEach((p, i) => {
          p.y -= p.v * dt; p.x += Math.sin(t * 1.3 + p.ph) * dt * 0.8 + dt * 0.6; p.z += Math.cos(t * 0.9 + p.ph) * dt * 0.5;
          if (p.y < bb.min.y + size.y * 0.25) { p.x = p.f[0] + (VK.rand() - .5) * 10; p.y = p.f[1] + VK.rand() * 3; p.z = p.f[2] + (VK.rand() - .5) * 10; }
          E.set(t * 1.7 + p.ph, t * 1.1 + p.ph, 0); Q.setFromEuler(E); P.set(p.x, p.y, p.z); M.compose(P, Q, S1); petals.setMatrixAt(i, M);
        });
        petals.instanceMatrix.needsUpdate = true;
      }
      waterMat.opacity = 0.74 + Math.sin(t * 1.5) * 0.04;
      clouds.rotation.y = t * 0.01;
      for (const [obj, fn] of movers) fn.call(obj, t, dt);
      if (o.onFrame) o.onFrame(t, dt);
      controls.update(); renderer.render(scene, camera); stats.frames++;
      requestAnimationFrame(loop);
    };
    stats.started = true;
    loop();
    return { scene, camera, renderer, controls, add: obj => (scene.add(obj), obj) };
  };
})();
