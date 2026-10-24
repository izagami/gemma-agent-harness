// title: Windmill Village
// EXAMPLE of a rich voxel scene with the kit (a different subject - copy the TECHNIQUES, not the content):
// 1 plan the layout first, 2 one big detailed hero, 3 many labelled supporting parts that never overlap,
// 4 life (petals/animals/lights), 5 VK.start at the end. 110 lines, ~45k voxels, renders in 2 s.
const P = VK.PAL;
VK.seed(3);

// --- 1. layout: island, a pond at the front-left, the hero at the back-right on solid ground
VK.island({ radius: 30, top: 4, hill: [8, -8, 12, 5] });
VK.pond(-12, 10, 9, 6);
const HX = 8, HZ = -8;                                   // hero position: check it is NOT in the pond
if (VK.inPond(HX, HZ)) throw new Error("hero placed in the pond");
const used = [];                                         // footprints of placed parts, to avoid overlaps
const free = (x, z, r) => !VK.inPond(x, z) && used.every(([ux, uz, ur]) => Math.hypot(x - ux, z - uz) > r + ur);
const claim = (x, z, r) => used.push([x, z, r]);
claim(HX, HZ, 9);

// --- 2. hero: a tall windmill - stone base, tapering tower with windows and trim, cap, turning sails (mover)
const g = VK.H(HX, HZ) + 1;
VK.box(HX - 6, g, HZ - 6, HX + 6, g, HZ + 6, P.stoneD, { label: "windmill" });          // plinth
for (let y = 0; y < 18; y++) {
  const r = 5 - Math.floor(y / 6);                        // tapering in three steps
  for (let x = -r; x <= r; x++) for (let z = -r; z <= r; z++) {
    if (Math.abs(x) !== r && Math.abs(z) !== r) continue;
    const win = y % 6 === 3 && (x === 0 || z === 0);      // a window on each side per stage
    VK.set(HX + x, g + 1 + y, HZ + z, win ? 0x3a2a1a : y % 6 === 5 ? P.woodL : P.white, { label: "windmill" });
  }
  if (y % 6 === 5) VK.shell(HX - r - 1, g + 1 + y, HZ - r - 1, HX + r + 1, g + 1 + y, HZ + r + 1, P.wood, { label: "windmill" }); // balcony trim
}
VK.box(HX - 1, g + 1, HZ + 5, HX + 1, g + 3, HZ + 5, P.wood, { label: "windmill" });  // door
const capY = VK.roof(HX, g + 19, HZ, 3, { overhang: 1, layers: 4, color: P.redD, edge: P.red, tip: P.gold, label: "windmill" });
VK.set(HX, capY, HZ, P.gold, { label: "windmill" });

// --- 3. supporting parts, each labelled, placed with free()/claim()
function cottage(x, z, roofColor) {                       // small house: walls, door, windows, roof, chimney
  const h = VK.H(x, z) + 1;
  VK.shell(x - 3, h, z - 3, x + 3, h + 3, z + 3, P.white, { label: "cottage" });
  VK.box(x - 3, h, z - 3, x + 3, h, z + 3, P.wood, { label: "cottage" });
  VK.box(x, h + 1, z + 3, x, h + 2, z + 3, P.wood, { label: "cottage" });
  for (const dx of [-2, 2]) VK.set(x + dx, h + 2, z + 3, 0x87ceeb, { label: "cottage" });
  VK.roof(x, h + 4, z, 3, { overhang: 1, layers: 3, color: roofColor, edge: roofColor, glowTips: false, label: "cottage" });
  VK.box(x + 2, h + 4, z - 2, x + 2, h + 7, z - 2, P.stoneD, { label: "cottage" });
}
for (const [x, z, c] of [[-14, -12, 0x8b3a2a], [18, 12, 0x3d5a80], [-20, -1, 0x6b4226], [2, 18, 0x8b3a2a]])
  if (free(x, z, 5)) { cottage(x, z, c); claim(x, z, 5); }

// wooden bridge over the pond, fence along the path, a well, hay bales
for (let x = -22; x <= -3; x++) {
  const y = VK.H(-22, 10) + Math.round(Math.sin((x + 22) / 19 * Math.PI) * 3);
  VK.box(x, y, 9, x, y, 11, P.woodL, { label: "bridge" });
  if (x % 2 === 0) for (const z of [8, 12]) VK.box(x, y + 1, z, x, y + 2, z, P.wood, { label: "bridge" });
}
for (let z = -2; z <= 20; z++) if (!VK.inPond(-1, z) && z % 2 === 0) VK.box(-1, VK.H(-1, z) + 1, z, -1, VK.H(-1, z) + 2, z, P.woodL, { label: "fence" });
for (let z = -2; z <= 20; z += 2) VK.set(1, VK.H(1, z) + 1, z, P.stone, { label: "path" });
if (free(10, 8, 3)) { const h = VK.H(10, 8) + 1; VK.shell(9, h, 7, 11, h + 1, 9, P.stone, { label: "well" });
  VK.box(9, h + 4, 7, 11, h + 4, 9, P.redD, { label: "well" }); VK.box(9, h + 2, 8, 9, h + 3, 8, P.wood, { label: "well" }); claim(10, 8, 3); }
VK.scatter(6, (x, z, h) => { if (!free(x, z, 2)) return false; VK.cylinder(x, h + 1, z, 1, 2, 0xd9b44a, { label: "hay" }); claim(x, z, 2); });

// trees of three kinds, shrubs, flowers, rocks, lily pads
const blossoms = [];
VK.scatter(5, (x, z) => { if (!free(x, z, 5)) return false; blossoms.push(VK.blobTree(x, z, { colors: P.sakura, label: "blossom tree" })); claim(x, z, 5); });
VK.scatter(4, (x, z) => { if (!free(x, z, 4)) return false; VK.blobTree(x, z, { colors: P.maple, r: 3, label: "maple" }); claim(x, z, 4); });
VK.scatter(3, (x, z) => { if (!free(x, z, 4)) return false; VK.padTree(x, z); claim(x, z, 4); });
VK.scatter(25, (x, z, h) => { if (!free(x, z, 1)) return false; VK.sphere(x, h + 1, z, 1, [P.moss, P.leaf, P.azalea], { label: "shrub" }); });
VK.scatter(150, (x, z, h) => { if (!free(x, z, 0)) return false; VK.set(x, h + 1, z, P.flowers, { label: "flowers" }); });
VK.scatter(12, (x, z, h) => { if (!free(x, z, 1)) return false; VK.box(x, h + 1, z, x + 1, h + 1 + Math.round(VK.rand()), z, [P.stone, P.stoneD], { label: "rocks" }); });
for (let i = 0; i < 8; i++) { const x = -12 + Math.round((VK.rand() - .5) * 14), z = 10 + Math.round((VK.rand() - .5) * 8);
  if (VK.inPond(x, z)) VK.set(x, VK.H(x, z), z, P.lily, { label: "lily" }); }
// lamp posts that glow at night
for (const [x, z] of [[3, 0], [3, 10], [3, 20], [-5, -6]]) if (free(x, z, 1)) {
  const h = VK.H(x, z) + 1; VK.box(x, h, z, x, h + 3, z, 0x333333, { label: "lamp" }); VK.set(x, h + 4, z, P.lantern, { glow: true, label: "lamp" });
}

// --- 4/5. start, then life: sails turning, ducks on the pond, petals from the blossom trees
const app = VK.start({ title: "Windmill Village", subtitle: "a voxel afternoon", sky: "day", petals: { from: blossoms, colors: P.sakura } });
const sails = new THREE.Group();
sails.position.set(HX, g + 14, HZ + 7);
const sailMat = new THREE.MeshStandardMaterial({ color: 0xf3ede1 }), armMat = new THREE.MeshStandardMaterial({ color: 0x6b4226 });
for (let i = 0; i < 4; i++) {
  const arm = new THREE.Group(); arm.rotation.z = i * Math.PI / 2;
  const beam = new THREE.Mesh(new THREE.BoxGeometry(0.6, 13, 0.6), armMat); beam.position.y = 6.5; arm.add(beam);
  const sail = new THREE.Mesh(new THREE.BoxGeometry(3, 10, 0.2), sailMat); sail.position.set(1.8, 7.5, 0); arm.add(sail);
  sails.add(arm);
}
app.add(sails);
VK.mover(sails, function (t) { this.rotation.z = t * 0.6; });
for (let i = 0; i < 3; i++) {
  const duck = app.add(new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.6, 0.6), new THREE.MeshStandardMaterial({ color: 0xffffff })));
  VK.mover(duck, function (t) { const a = t * 0.25 + i * 2.1; this.position.set(-12 + Math.cos(a) * 5, VK.H(-12, 10) - 0.5, 10 + Math.sin(a) * 3); this.rotation.y = -a; });
}
