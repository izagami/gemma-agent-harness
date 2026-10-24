// voxelkit: tested building blocks for voxel-art scenes in three.js (r160).
// build.py inlines this file and your scene.js into ONE html file; in scene.js the globals are THREE and VK.
//
// RECIPES - which functions make which thing (use these; they are tested and look right):
//   pagoda / temple      VK.building({storeys: 5, taper: 0.75}) + VK.torii + VK.lantern + VK.bridge + decorate({flora: "sakura"})
//   castle               VK.wall x4 (one with gate: true) + VK.tower({roof: "cone"}) at the corners
//                        + VK.building({roof: "battlement", wall: P.castle, pillar: P.castleD}) as the keep
//   town / village       VK.town(x, z, {houses: 8-12}) (houses + market stalls) or several VK.house
//   lighthouse + harbor  VK.sea() right after VK.island, VK.tower({roof: "lantern", stripes: [white, red]}),
//                        VK.harbor(x, z) at a shore point (quay + piers + boats), extra VK.boat on the sea
//   winter / snow        VK.island({snow: true}) + decorate({flora: "snow"}) + VK.start({snow: true, sky: "winter"})
//   forest               decorate({flora: "conifer"}) or many VK.conifer / VK.blobTree
//   house / cabin        VK.house (roof: P.snow for a snowy roof) - give it a yard: keep trees 4+ voxels away
//   windmill, farm ...   VK.building / VK.house + your own VK.box / VK.cylinder details (see the example scene)
//   CAMERA: the default view looks from the +x, +z side (front-right). Put what must be seen (harbor, gate, town,
//   the hero's front) on that side - e.g. VK.harbor(14, 14) rather than (-14, -14), which is hidden behind the island.
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
//   VK.building(cx, cz, {storeys: 3, halfW: 5, halfD, taper: 1, firstH: 5, storeyH: 4, wall, pillar, trim, window,
//               roof: "hip"|"gable"|"battlement"|"flat"|"none", roofColor, roofEdge, bracket, tip, overhang: 3, spire, spireH,
//               plinth: true, label}) -> {base, top}
//                                 TESTED storeyed building on the ground at (cx, cz): stone plinth + steps, every storey
//                                 with pillars, walls, windows, trim, bracket band and an upturned hip roof resting on it,
//                                 finial on top. Five storeys + taper 0.75 = a five-storey pagoda; roof "flat" + storeys 3
//                                 = a tower house; wall/pillar colors make temples, castles, lighthouses. Use it for the
//                                 hero, then add your own details around it.
//   Garden parts (TESTED; each claims its footprint, so call the big ones first):
//   VK.claim(x, z, r) / VK.free(x, z, r) -> bool    reserve ground / is the ground free (not pond, not claimed)
//   VK.bridge(x0, z0, x1, z1, {arch: 3, halfWidth: 1, deck, rail, post})  arched bridge across a pond
//   VK.torii(x, z, {half: 4, alongX: false, color})  shrine gate on the path
//   VK.lantern(x, z)                                 stone lantern, glows at night
//   VK.path([[x, z], [x, z], ...])                   stepping-stone path (skips water)
//   VK.fence(x0, z0, x1, z1)                         low wooden fence
//   VK.decorate({flora: "temperate"|"sakura"|"autumn"|"conifer"|"snow"|"coast", trees, conifers, pines, shrubs: 25,
//                rocks: 12, flowers: 150}) -> {trees: canopy centers for petals}  - pick the flora that fits the task
//                                                    fills the remaining free ground - call it LAST, before VK.start
//   More buildings / scenery (TESTED, generic - combine them for castles, villages, harbors, winter scenes ...):
//   VK.gable(cx, y, cz, halfW, halfD, {axis, color, overhang}) -> top y     pitched roof (houses, barns, halls)
//   VK.cone(cx, y, cz, r, {h, color, flag}) -> top y                        conical roof with a flag (round towers)
//   VK.battlements(x0, y, z0, x1, z1, {color})                              crenellated parapet around a rectangle
//   VK.tower(cx, cz, {r: 3, h: 14, wall, stripes: [c1, c2], roof: "cone"|"battlement"|"lantern", roofColor})
//                     -> {base, top, light: [x, y, z]}   castle tower / watchtower / lighthouse (roof "lantern" glows)
//   VK.wall(x0, z0, x1, z1, {h: 6, color, gate: true})                      curtain wall with walkway + crenels
//   VK.house(cx, cz, {halfW: 3, halfD: 2, h: 4, wall, frame, roof, litWindows}) timber-frame house, gable roof
//   VK.town(cx, cz, {houses: 8, radius: 12, stalls: 3}) -> [[x, z], ...]    houses + market stalls on free ground
//   VK.conifer(x, z, {h: 10, snow: false})                                   pine / fir; snow: true for winter
//   VK.sea({radius: 48, level: 2})     ocean around the island with sand beaches (call right after VK.island)
//   VK.harbor(x, z, {toward: [dx, dz], boats: 3, length: 12})   quay + piers + moored boats at a shore point (x, z)
//   VK.boat(x, z, {len: 7, dir: "x", sail: true, cabin: true, hull, sailColor}) / VK.pier(x0, z0, x1, z1)
//   VK.island({radius, top, hill, snow: true, ground: color})   snow: snow-covered ground
//   VK.start({... snow: true, sky: "winter"|"sea"|...})          falling snow
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
//   VK.add(object3d)   add your own three.js mesh/group to the scene - works before AND after VK.start
//   VK.mover(object3d, fn(t)) animate your own meshes (koi, birds, a turning wheel...): fn sets its position/rotation
//                      (use VK.add / VK.mover, not app.add before `const app = VK.start(...)` - that line throws)
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
    flowers: [0xffffff, 0xffd84d, 0xb388ff, 0xff6f91], azalea: 0xd94f7a, lily: 0x5d9e3f, koi: 0xf2762e,
    snow: 0xf4f7fb, snow2: 0xdfe7f0, conifer: [0x1f5130, 0x2a6138, 0x245a33], oak: [0x4f8a3c, 0x5c9a45, 0x6aa84f],
    castle: 0x9a978f, castleD: 0x7d7a73, slate: 0x4a5560, tile: 0xa8432f, thatch: 0xc9a25a, plaster: 0xeee3c8,
    timber: 0x5a3b24, sea: 0x2e86ab, sand2: 0xf0e2b6, glass: 0xfff2b0
  };
  const vox = new Map();
  const K = (x, y, z) => x + "," + y + "," + z;
  const stats = (window.__vk = { voxels: 0, drawn: 0, labels: {}, bounds: null, started: false, frames: 0 });
  const pick = c => (Array.isArray(c) ? c[Math.floor(VK.rand() * c.length)] : c);
  VK.set = (x, y, z, color, o = {}) => {
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return;
    x = Math.round(x); y = Math.round(y); z = Math.round(z);
    const c = new THREE.Color(pick(color));
    const j = o.jitter ?? 0.06;
    if (j) c.multiplyScalar(1 + (VK.rand() - 0.5) * 2 * j);
    vox.set(K(x, y, z), { c, glow: !!o.glow, water: !!o.water, label: o.label });
  };
  VK.del = (x, y, z) => vox.delete(K(Math.round(x), Math.round(y), Math.round(z)));
  VK.has = (x, y, z) => vox.has(K(Math.round(x), Math.round(y), Math.round(z)));
  VK.get = (x, y, z) => vox.get(K(Math.round(x), Math.round(y), Math.round(z)));
  // non-finite coordinates (a part placed off the island gets VK.H = -Infinity) would loop forever: skip + warn
  stats.warnings = [];
  const bad = (name, ...v) => {
    if (v.every(Number.isFinite)) return false;
    if (stats.warnings.length < 12) stats.warnings.push(`${name}(${v.map(n => Number.isFinite(n) ? Math.round(n) : String(n)).join(", ")}) skipped: `
      + (v.some(n => n === -Infinity) ? "placed off the island (VK.H is -Infinity there)" : "a coordinate is NaN/undefined"));
    return true;
  };
  VK.warn = msg => { if (stats.warnings.length < 12) stats.warnings.push(msg); };
  VK.box = (x0, y0, z0, x1, y1, z1, color, o) => {
    if (bad("box", x0, y0, z0, x1, y1, z1)) return;
    for (let x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) for (let y = Math.min(y0, y1); y <= Math.max(y0, y1); y++)
      for (let z = Math.min(z0, z1); z <= Math.max(z0, z1); z++) VK.set(x, y, z, color, o);
  };
  VK.shell = (x0, y0, z0, x1, y1, z1, color, o) => {
    if (bad("shell", x0, y0, z0, x1, y1, z1)) return;
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++)
      if (x === x0 || x === x1 || z === z0 || z === z1) VK.set(x, y, z, color, o);
  };
  VK.sphere = (cx, cy, cz, r, color, o = {}) => {
    if (bad("sphere", cx, cy, cz, r)) return;
    const sq = o.squash ?? 1, fill = o.fill ?? 1;
    for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++)
      if (Math.hypot(x, y / sq, z) <= r && VK.rand() < fill) VK.set(cx + x, cy + y * sq, cz + z, color, o);
  };
  VK.cylinder = (cx, y0, cz, r, h, color, o) => {
    if (bad("cylinder", cx, y0, cz, r, h)) return;
    for (let y = y0; y < y0 + h; y++) for (let x = -r; x <= r; x++) for (let z = -r; z <= r; z++)
      if (Math.hypot(x, z) <= r + 0.3) VK.set(cx + x, y, cz + z, color, o);
  };
  VK.line = (x0, y0, z0, x1, y1, z1, color, o) => {
    if (bad("line", x0, y0, z0, x1, y1, z1)) return;
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
  // storeyed building: pagoda, castle keep, temple hall, tower house, lighthouse ... -> {top, base}
  VK.building = (cx, cz, o = {}) => {
    if (o.y === undefined && VK.H(cx, cz) === -Infinity) { bad("building", cx, -Infinity, cz); return { base: 0, top: 0, light: [cx, 0, cz] }; }
    const L = o.label ?? "building", P = VK.PAL;
    const n = o.storeys ?? 3, w0 = o.halfW ?? 5, d0 = o.halfD ?? w0, taper = o.taper ?? 1;
    const wallC = o.wall ?? P.white, pillarC = o.pillar ?? P.red, trimC = o.trim ?? P.wood, winC = o.window ?? 0x3a2a1a;
    const g = o.y ?? VK.H(cx, cz) + 1;
    let y = g;
    if (o.plinth !== false) {                                           // stone base with steps at the front
      VK.box(cx - w0 - 2, y, cz - d0 - 2, cx + w0 + 2, y, cz + d0 + 2, P.stoneD, { label: L });
      VK.box(cx - w0 - 1, y + 1, cz - d0 - 1, cx + w0 + 1, y + 1, cz + d0 + 1, P.stone, { label: L });
      VK.box(cx - 1, y, cz + d0 + 3, cx + 1, y, cz + d0 + 3, P.stone, { label: L });
      y += 2;
    }
    for (let t = 0; t < n; t++) {
      const w = Math.max(1, w0 - Math.floor(t * taper)), d = Math.max(1, d0 - Math.floor(t * taper));
      const h = t === 0 ? (o.firstH ?? 5) : (o.storeyH ?? 4);
      VK.box(cx - w + 1, y, cz - d + 1, cx + w - 1, y, cz + d - 1, trimC, { label: L });           // floor
      for (let yy = 0; yy < h; yy++) for (let x = -w; x <= w; x++) for (let z = -d; z <= d; z++) {
        if (Math.abs(x) !== w && Math.abs(z) !== d) continue;
        const corner = Math.abs(x) === w && Math.abs(z) === d;
        const pillar = corner || (Math.abs(x) === w ? z % 2 === 0 : x % 2 === 0);
        if (t === 0 && Math.abs(x) <= 1 && z === d && yy < 3) continue;                             // doorway
        const win = !pillar && yy >= 1 && yy <= h - 2 && (yy % 2 === 1);
        VK.set(cx + x, y + yy, cz + z, pillar ? pillarC : yy === h - 1 ? trimC : win ? winC : wallC, { label: L });
      }
      y += h;
      const last = t === n - 1;
      if (o.roof === "gable") {                                   // pitched roof on the top storey, trim band between storeys
        if (last) y = VK.gable(cx, y, cz, w, d, { color: o.roofColor ?? VK.PAL.tile, gableWall: wallC, label: L, overhang: 1 });
        else { VK.shell(cx - w, y, cz - d, cx + w, y, cz + d, trimC, { label: L }); VK.box(cx - w, y, cz - d, cx + w, y, cz + d, trimC, { label: L }); y += 1; }
      } else if (o.roof === "battlement") {                       // castle keep: flat floors, crenellated top
        VK.box(cx - w - (last ? 1 : 0), y, cz - d - (last ? 1 : 0), cx + w + (last ? 1 : 0), y, cz + d + (last ? 1 : 0), o.trim ?? VK.PAL.castleD, { label: L });
        if (last) VK.battlements(cx - w - 1, y + 1, cz - d - 1, cx + w + 1, cz + d + 1, { color: wallC, label: L });
        y += last ? 3 : 1;
      } else if (o.roof !== "flat" && o.roof !== "none") {
        VK.shell(cx - w - 1, y, cz - d - 1, cx + w + 1, y, cz + d + 1, o.bracket ?? P.gold, { label: L });  // bracket band
        y = VK.roof(cx, y + 1, cz, w + 1, { halfD: d + 1, overhang: o.overhang ?? 3, layers: 3, color: o.roofColor ?? P.roof,
          edge: o.roofEdge ?? P.roofL, tip: o.tip ?? P.gold, label: L });
      } else {
        VK.shell(cx - w - 1, y, cz - d - 1, cx + w + 1, y, cz + d + 1, trimC, { label: L });          // parapet
        VK.box(cx - w, y, cz - d, cx + w, y, cz + d, trimC, { label: L });
        y += 1;
      }
    }
    if (o.spire !== false) {                                            // finial: shaft with rings and a glowing top
      const sh = o.spireH ?? 9;
      VK.box(cx, y, cz, cx, y + sh, cz, o.spireColor ?? P.gold, { label: L });
      for (let i = 1; i < sh - 1; i += 2) for (const [a, b] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) VK.set(cx + a, y + i, cz + b, o.spireColor ?? P.gold, { label: L });
      VK.set(cx, y + sh + 1, cz, P.lantern, { glow: true, label: L });
      y += sh + 2;
    }
    VK.claim(cx, cz, Math.max(w0, d0) + 4);
    return { base: g, top: y };
  };
  // pitched (gable) roof: ridge along x (axis "x") or z; steps up one voxel per voxel inward -> top y
  VK.gable = (cx, y, cz, halfW, halfD, o = {}) => {
    const ax = (o.axis ?? (halfW >= halfD ? "x" : "z")) === "x", ov = o.overhang ?? 1, L = o.label;
    const span = (ax ? halfD : halfW) + ov, len = (ax ? halfW : halfD) + ov, c = o.color ?? VK.PAL.tile;
    for (let k = 0; k <= span; k++) for (let a = -len; a <= len; a++) for (const sgn of k ? [-1, 1] : [1]) {
      const b = sgn * (span - k);
      VK.set(cx + (ax ? a : b), y + k, cz + (ax ? b : a), k === span ? (o.ridge ?? c) : c, { label: L });
      if (Math.abs(a) === len - ov && k < span) for (let f = 0; f < k; f++) VK.set(cx + (ax ? a : b), y + f, cz + (ax ? b : a), o.gableWall ?? VK.PAL.plaster, { label: L });
    }
    return y + span + 1;
  };
  // conical roof (round towers) -> top y
  VK.cone = (cx, y, cz, r, o = {}) => {
    const h = o.h ?? Math.round(r * 1.8), c = o.color ?? VK.PAL.slate;
    for (let k = 0; k < h; k++) { const rr = (r + 1) * (1 - k / h); for (let x = -r - 1; x <= r + 1; x++) for (let z = -r - 1; z <= r + 1; z++) if (Math.hypot(x, z) <= rr + 0.3) VK.set(cx + x, y + k, cz + z, c, { label: o.label }); }
    if (o.flag !== false) { VK.box(cx, y + h, cz, cx, y + h + 3, cz, 0x333333, { label: o.label }); VK.box(cx + 1, y + h + 2, cz, cx + 2, y + h + 3, cz, o.flagColor ?? VK.PAL.red, { label: o.label }); }
    return y + h + 4;
  };
  // crenellated parapet (merlons on every other voxel) around a rectangle at height y
  VK.battlements = (x0, y, z0, x1, z1, o = {}) => {
    const c = o.color ?? VK.PAL.castle;
    for (let x = x0; x <= x1; x++) for (let z = z0; z <= z1; z++) {
      if (x !== x0 && x !== x1 && z !== z0 && z !== z1) continue;
      VK.set(x, y, z, c, { label: o.label }); if ((x + z) % 2 === 0) VK.set(x, y + 1, z, c, { label: o.label });
    }
  };
  // round tower: castle tower, watchtower, lighthouse. roof "cone" | "battlement" | "lantern" (glass room + light)
  VK.tower = (cx, cz, o = {}) => {
    if (o.y === undefined && VK.H(cx, cz) === -Infinity) { bad("tower", cx, -Infinity, cz); return { base: 0, top: 0, light: [cx, 0, cz] }; }
    const L = o.label ?? "tower", r = o.r ?? 3, h = o.h ?? 14, g = o.y ?? VK.H(cx, cz) + 1;
    const stripes = o.stripes;                                   // e.g. [white, red] bands for a lighthouse
    for (let y = 0; y < h; y++) for (let x = -r; x <= r; x++) for (let z = -r; z <= r; z++) {
      const d = Math.hypot(x, z); if (d > r + 0.3 || d < r - 0.7) continue;
      const win = y % 5 === 3 && (x === 0 || z === 0);
      VK.set(cx + x, g + y, cz + z, win ? (o.window ?? 0x2a2a2a) : stripes ? stripes[Math.floor(y / (o.stripeH ?? 3)) % stripes.length] : (o.wall ?? VK.PAL.castle), { label: L });
    }
    VK.cylinder(cx, g, cz, r - 1, 1, o.wall ?? VK.PAL.castleD, { label: L });
    let top = g + h;
    const roof = o.roof ?? "cone";
    if (roof === "cone") top = VK.cone(cx, top, cz, r, { color: o.roofColor, label: L, flag: o.flag });
    else if (roof === "battlement") { VK.cylinder(cx, top, cz, r + 1, 1, o.wall ?? VK.PAL.castle, { label: L }); VK.battlements(cx - r - 1, top + 1, cz - r - 1, cx + r + 1, cz + r + 1, { color: o.wall, label: L }); top += 3; }
    else if (roof === "lantern") {                                // gallery, glass lantern room that glows, cap
      VK.cylinder(cx, top, cz, r + 1, 1, 0x333333, { label: L });
      for (let y = 1; y <= 3; y++) VK.cylinder(cx, top + y, cz, Math.max(1, r - 1), 1, VK.PAL.glass, { glow: true, jitter: 0, label: L });
      VK.cone(cx, top + 4, cz, Math.max(1, r - 1), { color: o.roofColor ?? VK.PAL.red, flag: false, h: 3, label: L });
      top += 8;
    }
    VK.claim(cx, cz, r + 2);
    return { base: g, top, light: [cx, g + h + 2, cz] };
  };
  // straight wall with walkway and battlements; gate: true leaves an opening in the middle
  VK.wall = (x0, z0, x1, z1, o = {}) => {
    const L = o.label ?? "wall", h = o.h ?? 6, n = Math.max(Math.abs(x1 - x0), Math.abs(z1 - z0), 1), c = o.color ?? VK.PAL.castle;
    for (let i = 0; i <= n; i++) {
      const x = Math.round(x0 + (x1 - x0) * i / n), z = Math.round(z0 + (z1 - z0) * i / n), g = VK.H(x, z) + 1;
      if (g === -Infinity || VK.inWater(x, z)) continue;
      const gap = o.gate && Math.abs(i - n / 2) <= 1.5;
      for (let y = 0; y < h; y++) if (!gap || y >= 4) VK.set(x, g + y, z, (y + i) % 4 === 0 ? (o.dark ?? VK.PAL.castleD) : c, { label: L });
      VK.set(x, g + h, z, c, { label: L }); if (i % 2 === 0) VK.set(x, g + h + 1, z, c, { label: L });
      VK.claim(x, z, 1);
    }
  };
  // small house: plaster or wood walls, timber frame, door, windows, gable roof, chimney. For towns and villages.
  VK.house = (cx, cz, o = {}) => {
    if (o.y === undefined && VK.H(cx, cz) === -Infinity) { bad("house", cx, -Infinity, cz); return { base: 0, top: 0, light: [cx, 0, cz] }; }
    const L = o.label ?? "house", w = o.halfW ?? 3, d = o.halfD ?? 2, h = o.h ?? 4, g = VK.H(cx, cz) + 1;
    const wall = o.wall ?? VK.PAL.plaster, frame = o.frame ?? VK.PAL.timber;
    for (let y = 0; y < h; y++) for (let x = -w; x <= w; x++) for (let z = -d; z <= d; z++) {
      if (Math.abs(x) !== w && Math.abs(z) !== d) continue;
      const post = (Math.abs(x) === w && Math.abs(z) === d) || y === h - 1 || y === 0;
      const door = z === d && x === 0 && y < 2, win = y === 2 && !post && (Math.abs(x) === w ? z === 0 : x % 2 === 0 && x !== 0);
      if (door) { VK.set(cx + x, g + y, cz + z, 0x4a2f1c, { label: L }); continue; }
      VK.set(cx + x, g + y, cz + z, win ? (o.window ?? 0x9fd3e8) : post ? frame : wall, { label: L, glow: win && o.litWindows });
    }
    VK.box(cx - w + 1, g, cz - d + 1, cx + w - 1, g, cz + d - 1, frame, { label: L });
    const top = VK.gable(cx, g + h, cz, w, d, { color: o.roof ?? VK.PAL.tile, gableWall: wall, label: L, axis: w >= d ? "x" : "z" });
    if (o.chimney !== false) VK.box(cx + w - 1, g + h, cz - 1, cx + w - 1, top + 1, cz - 1, VK.PAL.stoneD, { label: L });
    VK.claim(cx, cz, Math.max(w, d) + (o.yard ?? 3));          // keep a small yard free so the house stays visible
    return { base: g, top };
  };
  // town: n houses with varied roofs/walls on free ground around (cx, cz), plus market stalls; -> list of [x, z]
  VK.town = (cx, cz, o = {}) => {
    const n = o.houses ?? 8, R = o.radius ?? 12, out = [];
    const roofs = o.roofs ?? [VK.PAL.tile, VK.PAL.slate, VK.PAL.thatch, 0x8b3a2a], walls = o.walls ?? [VK.PAL.plaster, 0xe8d8b0, 0xd9c7a3, 0xf3ede1];
    for (let t = 0; t < n * 30 && out.length < n; t++) {
      const a = VK.rand() * Math.PI * 2, rr = 3 + VK.rand() * R, x = Math.round(cx + Math.cos(a) * rr), z = Math.round(cz + Math.sin(a) * rr);
      const w = 2 + Math.round(VK.rand()), d = 2;
      if (!VK.free(x, z, Math.max(w, d) + 1)) continue;
      VK.house(x, z, { yard: 1, halfW: w, halfD: d, h: 3 + Math.round(VK.rand() * 2), roof: roofs[out.length % roofs.length], wall: walls[out.length % walls.length], litWindows: true, label: o.label ?? "house" });
      out.push([x, z]);
    }
    for (let i = 0; i < (o.stalls ?? 3); i++) {                  // market stalls: counter + striped awning
      for (let t = 0; t < 30; t++) {
        const x = Math.round(cx + (VK.rand() - 0.5) * 8), z = Math.round(cz + (VK.rand() - 0.5) * 8);
        if (!VK.free(x, z, 2)) continue;
        const g = VK.H(x, z) + 1, col = [VK.PAL.red, 0x2f6fb5, 0xe0b23c][i % 3];
        VK.box(x - 1, g, z, x + 1, g, z, VK.PAL.woodL, { label: "market stall" });
        for (const dx of [-1, 1]) VK.box(x + dx, g + 1, z - 1, x + dx, g + 2, z - 1, VK.PAL.wood, { label: "market stall" });
        for (let dx = -2; dx <= 2; dx++) VK.set(x + dx, g + 3, z - 1 + (dx % 2 === 0 ? 0 : 0), dx % 2 ? col : 0xffffff, { label: "market stall" });
        VK.claim(x, z, 2); break;
      }
    }
    return out;
  };
  // conifer (pine / fir / spruce): stacked shrinking discs, optional snow on top of each layer
  VK.conifer = (x, z, o = {}) => {
    if (o.y === undefined && VK.H(x, z) === -Infinity) { bad("conifer", x, -Infinity, z); return { base: 0, top: 0, light: [x, 0, z] }; }
    const g = VK.H(x, z) + 1, h = o.h ?? 10, L = o.label ?? "conifer", colors = o.colors ?? VK.PAL.conifer;
    VK.box(x, g, z, x, g + 2, z, VK.PAL.bark, { label: L });
    for (let k = 0; k < h; k++) {
      const r = Math.max(0, Math.round((h - k) * (o.width ?? 0.38))), y = g + 2 + k;
      for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) if (Math.hypot(dx, dz) <= r + 0.3)
        VK.set(x + dx, y, z + dz, o.snow && k % 3 === 2 && Math.hypot(dx, dz) > r - 1.2 && VK.rand() < 0.75 ? VK.PAL.snow : colors, { label: L });
    }
    VK.set(x, g + 2 + h, z, o.snow ? VK.PAL.snow : colors, { label: L });
    VK.claim(x, z, Math.round(h * (o.width ?? 0.38)) + 1);
    return [x, g + h, z];
  };
  // boat on water at (x, z): wide hull with a stripe, deck, small wheelhouse, optional mast + sail; dir "x" or "z"
  VK.boat = (x, z, o = {}) => {
    const L = o.label ?? "boat", n = o.len ?? 7, ax = (o.dir ?? "x") === "x", y = (waterY.get(Math.round(x) + "," + Math.round(z)) ?? VK.H(x, z)) + 1;
    const P = (i, k, yy, c) => VK.set(ax ? x + i : x + k, yy, ax ? z + k : z + i, c, { label: L });
    const hull = o.hull ?? 0x7a4a2a, stripe = o.stripe ?? 0xf3ede1;
    for (let i = -n; i <= n; i++) {
      const w = Math.abs(i) >= n ? 0 : Math.abs(i) >= n - 2 ? 1 : 2;          // pointed bow and stern
      for (let k = -w; k <= w; k++) {
        P(i, k, y, hull);                                                     // bottom
        if (Math.abs(k) === w) { P(i, k, y + 1, stripe); P(i, k, y + 2, hull); }   // sides with a stripe
        else P(i, k, y + 1, VK.PAL.woodL);                                    // deck
      }
    }
    if (o.cabin !== false) { for (let i = -1; i <= 1; i++) for (let k = -1; k <= 1; k++) for (let yy = 2; yy <= 3; yy++) P(i - 2, k, y + yy, yy === 3 ? (o.roof ?? 0xc0392b) : 0xf3ede1); P(-2, 0, y + 2, 0x9fd3e8); }
    if (o.sail !== false) {
      for (let yy = 2; yy <= 10; yy++) P(2, 0, y + yy, VK.PAL.wood);
      for (let yy = 4; yy <= 9; yy++) for (let i = 1; i <= Math.round((10 - yy) * 0.7) + 1; i++) P(2 + i, 0, y + yy, o.sailColor ?? 0xf3ede1);
    }
  };
  // harbor at a shore point: stone quay along the shore, two piers out to sea with boats moored beside them, crates,
  // lamp posts. toward = [dx, dz] direction of the open sea (default: away from the island center). Call after VK.sea.
  VK.harbor = (x, z, o = {}) => {
    let [dx, dz] = o.toward ?? [x, z]; const len = Math.hypot(dx, dz) || 1; dx /= len; dz /= len;
    const ax = Math.abs(dx) >= Math.abs(dz), sx = Math.sign(dx) || 1, sz = Math.sign(dz) || 1;
    const out = o.length ?? 12, boats = o.boats ?? 3;
    // quay: a stone strip along the shore, perpendicular to the sea direction
    for (let t = -8; t <= 8; t++) {
      const qx = ax ? x : x + t, qz = ax ? z + t : z, h = VK.H(qx, qz);
      if (h === -Infinity) continue;
      const top = Math.max(h, (waterY.get(qx + "," + qz) ?? h) + 1);
      VK.box(qx, top - 2, qz, qx, top, qz, [VK.PAL.stone, VK.PAL.stoneD], { label: "quay" });
      if (t % 4 === 0) { VK.box(qx, top + 1, qz, qx, top + 3, qz, 0x333333, { label: "quay" }); VK.set(qx, top + 4, qz, VK.PAL.lantern, { glow: true, label: "quay" }); }
      if (t % 5 === 2) VK.box(qx - (ax ? sx : 0), top + 1, qz - (ax ? 0 : sz), qx - (ax ? sx : 0), top + 1, qz - (ax ? 0 : sz), 0x8a5a3b, { label: "crates" });
    }
    // piers + boats
    for (const off of [-5, 5]) {
      const px = ax ? x : x + off, pz = ax ? z + off : z;
      VK.pier(px, pz, px + (ax ? sx * out : 0), pz + (ax ? 0 : sz * out), { label: "pier" });
    }
    const colors = [[0xc0392b, 0xf3ede1], [0x2f6fb5, 0xf3ede1], [0x2a6138, 0xe8c860], [0xe0b23c, 0xf3ede1]];
    for (let b = 0; b < boats; b++) {
      const along = 5 + (b % 2) * 5, side = b < 2 ? -1 : 1, lane = side * (b % 2 ? 9 : 1);
      const bx = ax ? x + sx * along : x + lane, bz = ax ? z + lane : z + sz * along;
      VK.boat(bx, bz, { dir: ax ? "x" : "z", hull: colors[b % 4][0], sailColor: colors[b % 4][1], sail: b % 2 === 0, len: 6 });
    }
    VK.claim(x, z, 9);
  };
  // pier / dock: planks from the shore out over the water
  VK.pier = (x0, z0, x1, z1, o = {}) => {
    const n = Math.max(Math.abs(x1 - x0), Math.abs(z1 - z0), 1), ax = Math.abs(x1 - x0) >= Math.abs(z1 - z0);
    for (let i = 0; i <= n; i++) {
      const x = Math.round(x0 + (x1 - x0) * i / n), z = Math.round(z0 + (z1 - z0) * i / n), wy = waterY.get(x + "," + z), y = (wy ?? VK.H(x, z)) + 1;
      for (let k = -1; k <= 1; k++) VK.set(ax ? x : x + k, y, ax ? z + k : z, VK.PAL.woodL, { label: o.label ?? "pier" });
      if (wy !== undefined && i % 3 === 0) for (const k of [-1, 1]) VK.box(ax ? x : x + k, wy - 1, ax ? z + k : z, ax ? x : x + k, y + 1, ax ? z + k : z, VK.PAL.wood, { label: o.label ?? "pier" });
    }
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
        VK.set(x, y, z, y === h ? (o.snow ? VK.PAL.snow : o.ground ?? (VK.noise(x * 0.4, z * 0.4) > 0.55 ? VK.PAL.grass2 : VK.PAL.grass))
          : y > h - 3 ? (o.snow && y === h - 1 ? VK.PAL.snow2 : VK.PAL.dirt) : VK.rand() < 0.15 ? VK.PAL.stoneD : VK.PAL.stone, { jitter: o.snow ? 0.03 : 0.08, label: "island" });
    }
    return VK.H;
  };
  const ponds = [], waterY = new Map();
  const seaCells = new Set();
  VK.inPond = (x, z) => seaCells.has(Math.round(x) + "," + Math.round(z)) || ponds.some(([cx, cz, rx, rz]) => ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 < 1);
  VK.inWater = VK.inPond;
  // sea around the island: a water ring at `level` out to `radius`; shore cells of the island turn into sand beach.
  // Call after VK.island. Boats go on it (VK.boat); VK.H(x, z) on the sea = water level.
  VK.sea = (o = {}) => {
    const R = o.radius ?? 48, lvl = o.level ?? 2;
    for (let x = -R; x <= R; x++) for (let z = -R; z <= R; z++) {
      if (Math.hypot(x, z) > R) continue;
      const h = VK.H(x, z);
      if (h === -Infinity || h < lvl) {
        if (h !== -Infinity) for (let y = h + 1; y < lvl; y++) VK.set(x, y, z, VK.PAL.sandD, { label: "sea" });
        VK.set(x, lvl, z, o.color ?? VK.PAL.sea, { jitter: 0.04, water: true, label: "sea" });
        seaCells.add(x + "," + z); waterY.set(x + "," + z, lvl);
        if (h === -Infinity) height.set(x + "," + z, lvl);
      } else if (h <= lvl + 2 && [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([a, b]) => VK.H(x + a, z + b) === -Infinity || VK.H(x + a, z + b) < lvl)) {
        VK.set(x, h, z, VK.PAL.sand2, { jitter: 0.05, label: "beach" });
      }
    }
  };
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
    if (o.y === undefined && VK.H(x, z) === -Infinity) { bad("blobTree", x, -Infinity, z); return { base: 0, top: 0, light: [x, 0, z] }; }
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
    if (o.y === undefined && VK.H(x, z) === -Infinity) { bad("padTree", x, -Infinity, z); return { base: 0, top: 0, light: [x, 0, z] }; }
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

  // ---- placement bookkeeping: claim footprints so parts never overlap
  const claims = [];
  VK.claim = (x, z, r) => { claims.push([x, z, r]); };
  VK.free = (x, z, r = 0) => VK.H(x, z) > -Infinity && !VK.inPond(x, z) && claims.every(([a, b, c]) => Math.hypot(x - a, z - b) > r + c);
  // ---- garden parts (each claims its footprint)
  VK.bridge = (x0, z0, x1, z1, o = {}) => {             // arched bridge with railings between two points (across a pond)
    const L = o.label ?? "bridge", n = Math.max(Math.abs(x1 - x0), Math.abs(z1 - z0), 1), w = o.halfWidth ?? 1;
    const along = Math.abs(x1 - x0) >= Math.abs(z1 - z0), y0 = Math.max(VK.H(x0, z0), VK.H(x1, z1));
    for (let i = 0; i <= n; i++) {
      const x = Math.round(x0 + (x1 - x0) * i / n), z = Math.round(z0 + (z1 - z0) * i / n);
      const y = y0 + Math.round(Math.sin(i / n * Math.PI) * (o.arch ?? 3));
      for (let k = -w; k <= w; k++) VK.set(along ? x : x + k, y, along ? z + k : z, o.deck ?? VK.PAL.woodL, { label: L });
      for (const k of [-w - 1, w + 1]) {
        VK.set(along ? x : x + k, y + 1, along ? z + k : z, o.rail ?? VK.PAL.red, { label: L });
        if (i % 3 === 0) VK.set(along ? x : x + k, y + 2, along ? z + k : z, o.post ?? VK.PAL.redD, { label: L });
      }
      VK.claim(x, z, w + 1);
    }
  };
  VK.torii = (x, z, o = {}) => {
    if (o.y === undefined && VK.H(x, z) === -Infinity) { bad("torii", x, -Infinity, z); return { base: 0, top: 0, light: [x, 0, z] }; }                         // shrine gate; o.alongX: true when the path runs along x
    const L = o.label ?? "torii", h = VK.H(x, z) + 1, s = o.half ?? 4, ax = o.alongX ?? false;
    const P = (a, y, c) => VK.set(ax ? x : x + a, y, ax ? z + a : z, c, { label: L });
    for (const a of [-s, s]) for (let y = 0; y <= 8; y++) P(a, h + y, o.color ?? VK.PAL.red);
    for (let a = -s - 2; a <= s + 2; a++) P(a, h + 9, 0x222222);
    for (let a = -s - 1; a <= s + 1; a++) P(a, h + 8, o.color ?? VK.PAL.red);
    for (let a = -s; a <= s; a++) P(a, h + 6, o.color ?? VK.PAL.red);
    P(0, h + 7, VK.PAL.gold); P(-s - 2, h + 10, 0x222222); P(s + 2, h + 10, 0x222222);
    VK.claim(x, z, s + 1);
  };
  VK.lantern = (x, z, o = {}) => {
    if (o.y === undefined && VK.H(x, z) === -Infinity) { bad("lantern", x, -Infinity, z); return { base: 0, top: 0, light: [x, 0, z] }; }                       // stone lantern (toro) that glows at night
    const L = o.label ?? "lantern", h = VK.H(x, z) + 1, S = VK.PAL.stone, D = VK.PAL.stoneD;
    VK.box(x - 1, h, z - 1, x + 1, h, z + 1, D, { label: L }); VK.box(x, h + 1, z, x, h + 2, z, S, { label: L });
    VK.box(x - 1, h + 3, z - 1, x + 1, h + 3, z + 1, S, { label: L }); VK.set(x, h + 4, z, VK.PAL.lantern, { glow: true, jitter: 0, label: L });
    VK.box(x - 2, h + 5, z - 2, x + 2, h + 5, z + 2, D, { label: L }); VK.box(x - 1, h + 6, z - 1, x + 1, h + 6, z + 1, S, { label: L });
    VK.set(x, h + 7, z, S, { label: L }); VK.claim(x, z, 2);
  };
  VK.path = (points, o = {}) => {                        // stepping-stone path through [[x, z], ...]
    const L = o.label ?? "path";
    for (let p = 0; p + 1 < points.length; p++) {
      const [ax, az] = points[p], [bx, bz] = points[p + 1], n = Math.max(Math.abs(bx - ax), Math.abs(bz - az), 1);
      for (let i = 0; i <= n; i += 2) {
        const x = Math.round(ax + (bx - ax) * i / n), z = Math.round(az + (bz - az) * i / n);
        if (VK.H(x, z) === -Infinity || VK.inPond(x, z)) continue;
        for (const [a, b] of [[0, 0], [1, 0], [0, 1], [1, 1]]) VK.set(x + a, VK.H(x + a, z + b) + 1, z + b, [VK.PAL.stone, VK.PAL.stoneD], { label: L });
        VK.claim(x, z, 1);
      }
    }
  };
  VK.fence = (x0, z0, x1, z1, o = {}) => {               // low wooden fence along a line
    const L = o.label ?? "fence", n = Math.max(Math.abs(x1 - x0), Math.abs(z1 - z0), 1);
    for (let i = 0; i <= n; i++) {
      const x = Math.round(x0 + (x1 - x0) * i / n), z = Math.round(z0 + (z1 - z0) * i / n);
      if (VK.H(x, z) === -Infinity || VK.inPond(x, z)) continue;
      const h = VK.H(x, z) + 1;
      VK.set(x, h + 1, z, o.color ?? VK.PAL.woodL, { label: L }); if (i % 2 === 0) VK.set(x, h, z, o.color ?? VK.PAL.wood, { label: L });
    }
  };
  VK.decorate = (o = {}) => {                            // fill the free ground: shrubs, flowers, rocks, extra trees
    // flora: "temperate" (default: green broadleaf + conifers), "sakura" (cherry + maple + pruned pines, Japanese),
    //        "autumn", "conifer" (forest), "snow" (snowy conifers, no flowers), "coast" (few trees, grass, rocks)
    const out = { trees: [] }, fl = o.flora ?? "temperate";
    const leaf = { temperate: [VK.PAL.oak], sakura: [VK.PAL.sakura, VK.PAL.maple], autumn: [VK.PAL.maple, [0xe0a030, 0xd08a20, 0xb86f18]], coast: [VK.PAL.oak] }[fl];
    const nTrees = o.trees ?? (fl === "coast" ? 2 : fl === "conifer" || fl === "snow" ? 0 : 4);
    VK.scatter(nTrees, (x, z) => { if (!VK.free(x, z, 4) || !leaf) return false;
      out.trees.push(VK.blobTree(x, z, { colors: leaf[Math.floor(VK.rand() * leaf.length)], r: 3 + Math.round(VK.rand()), fallen: fl === "sakura" || fl === "autumn" ? 12 : 0, label: "tree" })); VK.claim(x, z, 4); });
    const nCon = o.conifers ?? (fl === "conifer" || fl === "snow" ? 14 : fl === "sakura" ? 0 : 2);
    VK.scatter(nCon, (x, z) => { if (!VK.free(x, z, 3)) return false; out.trees.push(VK.conifer(x, z, { h: 8 + Math.round(VK.rand() * 6), snow: fl === "snow" })); });
    VK.scatter(o.pines ?? (fl === "sakura" ? 2 : 0), (x, z) => { if (!VK.free(x, z, 4)) return false; VK.padTree(x, z); VK.claim(x, z, 4); });
    if (fl === "snow") { o = Object.assign({ flowers: 0, shrubs: 0 }, o); }
    if (fl === "coast") { o = Object.assign({ flowers: 40, shrubs: 10, rocks: 20 }, o); }
    VK.scatter(o.shrubs ?? 25, (x, z, h) => { if (!VK.free(x, z, 1)) return false;
      VK.sphere(x, h + 1, z, VK.rand() < 0.5 ? 1 : 2, VK.rand() < 0.35 ? VK.PAL.azalea : [VK.PAL.moss, VK.PAL.leaf], { jitter: 0.12, label: "shrub" }); VK.claim(x, z, 1); });
    VK.scatter(o.rocks ?? 12, (x, z, h) => { if (!VK.free(x, z, 1)) return false;
      VK.box(x, h + 1, z, x + 1, h + 1 + Math.round(VK.rand()), z + Math.round(VK.rand()), [VK.PAL.stone, VK.PAL.stoneD], { label: "rocks" }); VK.claim(x, z, 1); });
    VK.scatter(o.flowers ?? 150, (x, z, h) => { if (!VK.free(x, z, 0)) return false; VK.set(x, h + 1, z, VK.PAL.flowers, { label: "flowers" }); });
    return out;                                          // out.trees: canopy centers for VK.start({petals: {from: out.trees}})
  };
  const movers = [], pending = [];
  let liveScene = null;
  VK.mover = (obj, fn) => movers.push([obj, fn]);
  VK.add = obj => { if (liveScene) liveScene.add(obj); else pending.push(obj); return obj; };   // works before or after VK.start

  VK.start = (o = {}) => {
    const scene = new THREE.Scene();
    const geo = new THREE.BoxGeometry(1, 1, 1);
    const groups = { solid: [], water: [], glow: [] };
    const bb = new THREE.Box3();
    for (const [k, v] of vox) {
      const [x, y, z] = k.split(",").map(Number);
      stats.voxels++;
      if (v.label) stats.labels[v.label] = (stats.labels[v.label] || 0) + 1;
      if (v.label !== "sea") bb.expandByPoint(new THREE.Vector3(x, y, z));   // frame the land, not the whole ocean
      if (VK.has(x + 1, y, z) && VK.has(x - 1, y, z) && VK.has(x, y + 1, z) && VK.has(x, y - 1, z) && VK.has(x, y, z + 1) && VK.has(x, y, z - 1)) continue;
      groups[v.water ? "water" : v.glow ? "glow" : "solid"].push([x, y, z, v.c]);
    }
    // parts built over a pond (a building standing in the water is a placement mistake; bridges are fine)
    stats.overWater = {};
    for (const [k, v] of vox) {
      if (v.water || ["pond", "island", "sea", "beach", "boat", "pier", "bridge"].includes(v.label)) continue;
      const [x, y, z] = k.split(",").map(Number), wy = waterY.get(x + "," + z);
      if (wy !== undefined && (y === wy + 1 || y === wy + 2)) { const l = v.label || "unlabelled"; stats.overWater[l] = (stats.overWater[l] || 0) + 1; }
    }
    // floating parts: non-island voxels not touching (26-neighbour) anything connected to the island / ground.
    // Only the (few thousand) non-island voxels are walked; island voxels count as ground.
    stats.floating = {}; stats.floatSample = {};
    {
      const N26 = []; for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) if (a || b || c) N26.push([a, b, c]);
      const ground = v => v && (v.label === "island" || v.label === "sea" || v.label === "beach");
      const rest = []; for (const [k, v] of vox) if (!ground(v)) rest.push(k);
      const seen = new Set(), queue = [];
      const hasGround = ground([...vox.values()].find(ground));
      for (const k of rest) {
        const [x, y, z] = k.split(",").map(Number);
        if (!hasGround || N26.some(([a, b, c]) => ground(vox.get(K(x + a, y + b, z + c))))) { seen.add(k); queue.push(k); }
      }
      if (!hasGround && rest.length) { seen.clear(); queue.length = 0; let low = null; for (const k of rest) { const y = +k.split(",")[1]; if (low === null || y < low[1]) low = [k, y]; } seen.add(low[0]); queue.push(low[0]); }
      while (queue.length) {
        const [x, y, z] = queue.pop().split(",").map(Number);
        for (const [a, b, c] of N26) { const n = K(x + a, y + b, z + c); if (!seen.has(n) && vox.has(n) && !ground(vox.get(n))) { seen.add(n); queue.push(n); } }
      }
      for (const k of rest) if (!seen.has(k)) { const v = vox.get(k), l = v.label || "unlabelled"; stats.floating[l] = (stats.floating[l] || 0) + 1; if (!stats.floatSample[l]) stats.floatSample[l] = k; }
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
    const low = !!window.__vkLowCost;                   // headless check renders: cheaper settings, same picture
    renderer.setPixelRatio(low ? 1 : Math.min(devicePixelRatio, 2));
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
    const lowY = Math.max(bb.min.y, ground - size.y * 0.15), focus = center.clone(); focus.y = (lowY + bb.max.y) / 2;
    const frameR = Math.hypot(size.x, bb.max.y - lowY, size.z) / 2;
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
    sun.castShadow = true; sun.shadow.mapSize.set(low ? 1024 : 2048, low ? 1024 : 2048); sun.shadow.bias = -0.0004;
    Object.assign(sun.shadow.camera, { left: -radius, right: radius, top: radius, bottom: -radius, near: 1, far: radius * 4 });
    scene.add(sun);
    const glowPts = groups.glow.slice(0, 6).map(([x, y, z]) => { const l = new THREE.PointLight(0xffa64d, 0, 18, 1.6); l.position.set(x, y, z); scene.add(l); return l; });

    const SKY = { sunset: [0x7fb8e6, 0xf9d7c3, 0xf6b38a], day: [0x5aa9e6, 0xcfe8f7, 0xa9d3ee], dusk: [0x2c3e7a, 0xe08a6b, 0x6a4a7a],
      winter: [0x8fa9c9, 0xdfe7f0, 0xc5d3e3], sea: [0x4a90c8, 0xd8ecf5, 0x9cc9e0] }[o.sky ?? "sunset"] ?? [0x7fb8e6, 0xf9d7c3, 0xf6b38a];
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
    if (o.snow) o.petals = { colors: [0xffffff, 0xf0f4fa], count: 900, from: Array.from({ length: 30 }, () => [bb.min.x + VK.rand() * size.x, bb.max.y + 4, bb.min.z + VK.rand() * size.z]) };
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
      // low-cost mode (headless check renders on the CPU): ~6 frames per second is enough for two screenshots
      if (low) setTimeout(() => requestAnimationFrame(loop), 160); else requestAnimationFrame(loop);
    };
    liveScene = scene; pending.forEach(o => scene.add(o));
    stats.started = true;
    // first frame on the next tick: the rest of scene.js (movers, meshes declared below VK.start) runs first
    // (cycle 57: a mover touched `koiMeshes`, declared after VK.start, during a synchronous first frame)
    requestAnimationFrame(loop);
    return { scene, camera, renderer, controls, add: obj => (scene.add(obj), obj) };
  };
})();
