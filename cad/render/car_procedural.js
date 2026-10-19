// Procedural car with smooth surfaces (metres; three.js axes: X forward, Y up, Z to the left).
// The body is one lofted surface: at every station along X a cross-section is built from the side silhouette,
// the plan-view width, the greenhouse (cabin) width and the wheel arches, then the stations are joined.
// Faces above the belt line become glass (except roof and pillars); wheel-arch walls are dark.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const L = 4.50, AXLE_F = 1.35, AXLE_R = -1.35, R_TYRE = 0.335, W_TYRE = 0.225;

// smooth 1-D profile through (x, value) points, Catmull-Rom
function profile(pts) {
  const xs = pts.map((p) => p[0]), vs = pts.map((p) => p[1]);
  return (x) => {
    if (x >= xs[0]) return vs[0];
    if (x <= xs[xs.length - 1]) return vs[vs.length - 1];
    let i = 0;
    while (!(x <= xs[i] && x >= xs[i + 1])) i++;
    const p0 = vs[Math.max(0, i - 1)], p1 = vs[i], p2 = vs[i + 1], p3 = vs[Math.min(vs.length - 1, i + 2)];
    const t = (xs[i] - x) / (xs[i] - xs[i + 1]);
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
  };
}
// stations run from the front (x = +2.25) to the rear (x = -2.25)
const top = profile([[2.25, 0.62], [2.17, 0.76], [1.85, 0.84], [1.25, 0.90], [0.95, 0.94], [0.55, 1.20], [0.22, 1.39],
                     [-0.30, 1.42], [-0.80, 1.38], [-1.30, 1.17], [-1.62, 1.02], [-2.05, 1.00], [-2.20, 0.92], [-2.25, 0.70]]);
const belt = profile([[2.25, 0.62], [1.0, 0.94], [0.0, 0.97], [-1.0, 0.99], [-1.6, 1.01], [-2.25, 0.70]]);
const halfW = profile([[2.25, 0.70], [2.10, 0.83], [1.80, 0.885], [1.0, 0.905], [-1.0, 0.91], [-1.85, 0.89], [-2.12, 0.85], [-2.25, 0.76]]);
const bottom = profile([[2.25, 0.34], [2.0, 0.24], [1.6, 0.19], [-1.6, 0.19], [-2.0, 0.25], [-2.25, 0.38]]);
const ghW = profile([[1.0, 0.66], [0.3, 0.67], [-0.8, 0.68], [-1.6, 0.66]]);   // half width at the roof

function archZ(x) {    // lowest body z near the outer side, raised over the wheels
  let z = 0;
  for (const xa of [AXLE_F, AXLE_R]) {
    const r = R_TYRE + 0.055, d = x - xa;
    if (Math.abs(d) < r) z = Math.max(z, R_TYRE + Math.sqrt(r * r - d * d));
  }
  return z;
}

// half cross-section (z >= 0 side) as a list of (z_lateral, y_up) points, from the centre bottom to the roof centre
function section(x) {
  // every station has the same 13 control points, so neighbouring stations line up and the surface stays smooth;
  // wheel arches and the cabin only move points (blended), they never add or remove them
  const w = halfW(x), zb = bottom(x), zt = top(x), zbelt = Math.min(belt(x), zt - 0.02);
  const za = Math.min(Math.max(zb, archZ(x)), zbelt - 0.28);
  const g = Math.min(1, Math.max(0, (zt - zbelt - 0.03) / 0.12));   // 0 over bonnet/boot, 1 at the cabin
  const wg = Math.min(ghW(x), w - 0.06);
  const mix = (a, b) => a + (b - a) * g;
  return [
    [0.0, zb], [w - 0.32, zb], [w - 0.30, za], [w - 0.07, za],          // floor, wheel-arch wall and lip
    [w - 0.01, za + 0.05], [w, za + 0.12],                               // lower side
    [w, zbelt - 0.10], [w - 0.015, zbelt - 0.035], [w - 0.03, zbelt - 0.005],   // shoulder and belt
    [mix(w - 0.07, w - 0.07), mix(zbelt + 0.006, zbelt + 0.015)],        // window sill / bonnet edge
    [mix(w * 0.86, wg + 0.02), mix(zt - 0.006, zt - 0.09)],              // tumblehome
    [mix(w * 0.62, wg - 0.06), mix(zt - 0.002, zt - 0.025)],
    [mix(w * 0.34, wg * 0.55), zt - 0.001],
    [0.0, zt],
  ];
}

// resample a polyline of 2-D points into n points spaced evenly along a smooth curve
function resample(pts, n) {
  const curve = new THREE.SplineCurve(pts.map((p) => new THREE.Vector2(p[0], p[1])));
  return curve.getSpacedPoints(n - 1);
}

function bodyGeometry() {
  const NX = 420, NS = 72;                    // stations along X, points per half section
  const pos = [], idx = [], groups = [];
  const xs = [];
  for (let i = 0; i < NX; i++) xs.push(2.25 - (L * i) / (NX - 1));
  const rings = xs.map((x) => {
    const half = resample(section(x), NS);
    // full ring: right side (z negative) from roof centre down to the floor, then left side back up
    const ring = [];
    for (let k = NS - 1; k >= 0; k--) ring.push([x, half[k].y, -half[k].x]);
    for (let k = 1; k < NS - 1; k++) ring.push([x, half[k].y, half[k].x]);
    return ring;
  });
  const N = rings[0].length;
  rings.forEach((r) => r.forEach((p) => pos.push(p[0], p[1], p[2])));
  const tri = { paint: [], glass: [], dark: [] };
  const kind = (a, b, c) => {
    const P = [a, b, c].map((i) => [pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]]);
    const x = (P[0][0] + P[1][0] + P[2][0]) / 3, y = (P[0][1] + P[1][1] + P[2][1]) / 3, z = Math.abs((P[0][2] + P[1][2] + P[2][2]) / 3);
    const w = halfW(x), zt = top(x), zb = Math.min(belt(x), zt - 0.02);
    if (y < archZ(x) + 0.004 && z < w - 0.075 && z > w - 0.33) return 'dark';     // wheel-arch wall
    if (y < bottom(x) + 0.03 && z < w - 0.3) return 'dark';                        // underbody
    const inCabin = x < 0.98 && x > -1.62 && zt - zb > 0.08;
    if (inCabin && y > zb + 0.03) {
      const roof = y > zt - 0.06 && x < 0.18 && x > -0.86;
      const bPillar = z > 0.45 && x < -0.18 && x > -0.30;
      const cPillar = z > 0.45 && x < -1.04 && x > -1.38 && y > zb + 0.06;
      const aPillar = z > ghW(x) - 0.05 && x > 0.22;
      if (!roof && !bPillar && !cPillar && !aPillar) return 'glass';
    }
    return 'paint';
  };
  for (let i = 0; i < rings.length - 1; i++) {
    for (let k = 0; k < N; k++) {
      const a = i * N + k, b = i * N + ((k + 1) % N), c = (i + 1) * N + k, d = (i + 1) * N + ((k + 1) % N);
      tri[kind(a, b, c)].push(a, b, c);        // counter-clockwise seen from outside
      tri[kind(b, d, c)].push(b, d, c);
    }
  }
  // close the front and rear ends
  for (const i of [0, rings.length - 1]) {
    const ci = pos.length / 3;
    const r = rings[i];
    const cy = r.reduce((s, p) => s + p[1], 0) / N;
    pos.push(r[0][0], cy, 0);
    for (let k = 0; k < N; k++) {
      const a = i * N + k, b = i * N + ((k + 1) % N);
      if (i === 0) tri.paint.push(ci, a, b); else tri.paint.push(ci, b, a);
    }
  }
  let start = 0;
  for (const [name, list] of Object.entries(tri)) {
    for (const v of list) idx.push(v);   // (spread would overflow the call stack on big meshes)
    groups.push([start, list.length, name]);
    start += list.length;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  groups.forEach(([s, c], i) => g.addGroup(s, c, i));
  g.computeVertexNormals();
  return { geometry: g, order: groups.map((x) => x[2]) };
}

function tyreGeometry() {
  // tyre cross-section (radius, lateral) with rounded shoulders and a few tread grooves, lathed about the axle
  const pts = [], r0 = 0.235, r1 = R_TYRE, hw = W_TYRE / 2;
  pts.push(new THREE.Vector2(r0, -hw * 0.82));
  for (let i = 0; i <= 8; i++) { const a = Math.PI / 2 * (1 - i / 8); pts.push(new THREE.Vector2(r1 - 0.035 + 0.035 * Math.sin(Math.PI / 2 - a) , -hw + 0.035 * (1 - Math.cos(Math.PI / 2 - a)) )); }
  for (let i = 1; i < 12; i++) {
    const z = -hw + 0.035 + (2 * hw - 0.07) * i / 12;
    const groove = [3, 6, 9].includes(i) ? 0.006 : 0;
    pts.push(new THREE.Vector2(r1 - groove, z));
  }
  for (let i = 0; i <= 8; i++) { const a = Math.PI / 2 * i / 8; pts.push(new THREE.Vector2(r1 - 0.035 + 0.035 * Math.cos(a), hw - 0.035 + 0.035 * Math.sin(a))); }
  pts.push(new THREE.Vector2(r0, hw * 0.82));
  const g = new THREE.LatheGeometry(pts.map((p) => new THREE.Vector2(p.x, p.y)), 96);
  g.rotateX(Math.PI / 2);   // lathe axis Y -> axle along Z
  return g;
}

function wheel(M, side) {
  const grp = new THREE.Group();
  const tyre = new THREE.Mesh(tyreGeometry(), M.rubber);
  grp.add(tyre);
  // rim barrel and dish
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.236, 0.236, W_TYRE * 0.86, 64, 1, true), M.darkMetal);
  barrel.rotation.x = Math.PI / 2; grp.add(barrel);
  const lip = new THREE.Mesh(new THREE.TorusGeometry(0.232, 0.012, 12, 96), M.alloy);
  lip.position.z = side * W_TYRE * 0.40; grp.add(lip);
  // five twin spokes
  const shape = new THREE.Shape();
  shape.moveTo(0.05, -0.022); shape.lineTo(0.225, -0.034); shape.lineTo(0.225, 0.034); shape.lineTo(0.05, 0.022); shape.lineTo(0.05, -0.022);
  const spokeG = new THREE.ExtrudeGeometry(shape, { depth: 0.035, bevelEnabled: true, bevelThickness: 0.008, bevelSize: 0.006, bevelSegments: 3 });
  for (let i = 0; i < 10; i++) {
    const s = new THREE.Mesh(spokeG, M.alloy);
    s.rotation.z = (i * Math.PI) / 5 + (i % 2 ? 0.16 : -0.16) + (Math.PI * 2 / 5) * 0;
    s.position.z = side * (W_TYRE * 0.36) - 0.0175;
    grp.add(s);
  }
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 0.05, 32), M.alloy);
  hub.rotation.x = Math.PI / 2; hub.position.z = side * W_TYRE * 0.38; grp.add(hub);
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.012, 32), M.badge);
  cap.rotation.x = Math.PI / 2; cap.position.z = side * (W_TYRE * 0.38 + 0.028); grp.add(cap);
  // brake disc and calliper behind the spokes
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.025, 64), M.disc);
  disc.rotation.x = Math.PI / 2; disc.position.z = -side * 0.02; grp.add(disc);
  const cal = new THREE.Mesh(new RoundedBoxGeometry(0.09, 0.14, 0.06, 3, 0.015), M.calliper);
  cal.position.set(-0.13, 0.08, side * 0.005); cal.rotation.z = 0.6; grp.add(cal);
  grp.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return grp;
}

export function buildCar(M) {
  const car = new THREE.Group();
  const { geometry, order } = bodyGeometry();
  const body = new THREE.Mesh(geometry, order.map((k) => ({ paint: M.paint, glass: M.glass, dark: M.plastic })[k]));
  body.castShadow = true; body.receiveShadow = true;
  car.add(body);

  const add = (mesh, x, y, z) => { mesh.position.set(x, y, z); mesh.castShadow = true; car.add(mesh); return mesh; };
  // headlights: slim units following the front corners
  for (const s of [1, -1]) {
    const hl = add(new THREE.Mesh(new RoundedBoxGeometry(0.16, 0.075, 0.40, 4, 0.03), M.head), 2.13, 0.72, s * 0.56);
    hl.rotation.y = s * 0.28; hl.rotation.z = -0.32;
    const drl = add(new THREE.Mesh(new RoundedBoxGeometry(0.03, 0.018, 0.34, 2, 0.008), M.drl), 2.17, 0.70, s * 0.55);
    drl.rotation.y = s * 0.28;
    const tl = add(new THREE.Mesh(new RoundedBoxGeometry(0.06, 0.07, 0.42, 4, 0.025), M.tail), -2.16, 0.86, s * 0.56);
    tl.rotation.y = -s * 0.22;
    // mirrors
    const mir = add(new THREE.Mesh(new RoundedBoxGeometry(0.16, 0.11, 0.17, 4, 0.04), M.paint), 0.80, 1.00, s * 0.93);
    mir.rotation.y = -s * 0.15;
    add(new THREE.Mesh(new RoundedBoxGeometry(0.09, 0.03, 0.08, 2, 0.01), M.plastic), 0.86, 0.97, s * 0.85);
    // door handles
    for (const x of [0.25, -0.65]) add(new THREE.Mesh(new RoundedBoxGeometry(0.16, 0.025, 0.02, 2, 0.008), M.alloy), x, 0.88, s * 0.913);
    // side skirt
    const sk = add(new THREE.Mesh(new RoundedBoxGeometry(1.95, 0.07, 0.05, 3, 0.02), M.plastic), 0.0, 0.215, s * 0.885);
  }
  // grille and lower intake
  add(new THREE.Mesh(new RoundedBoxGeometry(0.06, 0.12, 0.70, 4, 0.03), M.grille), 2.21, 0.55, 0);
  add(new THREE.Mesh(new RoundedBoxGeometry(0.05, 0.08, 0.95, 4, 0.03), M.grille), 2.17, 0.38, 0);
  // rear diffuser and exhaust tips
  add(new THREE.Mesh(new RoundedBoxGeometry(0.08, 0.08, 1.20, 4, 0.03), M.plastic), -2.22, 0.33, 0);
  for (const s of [1, -1]) {
    const ex = add(new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.10, 32, 1, true), M.alloy), -2.24, 0.30, s * 0.45);
    ex.rotation.z = Math.PI / 2;
  }
  // wheels
  for (const x of [AXLE_F, AXLE_R]) for (const s of [1, -1]) {
    const w = wheel(M, s);
    w.position.set(x, R_TYRE, s * (0.905 - W_TYRE / 2 - 0.012));
    car.add(w);
  }
  return car;
}
