import * as THREE from 'three';

const renderer = new THREE.WebGLRenderer({ antialias: false });
renderer.setPixelRatio(1);
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000);
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 100);
camera.position.set(0, 5, 8);
camera.lookAt(0, 0.5, 0);

function mesh(name, geo, color, x, y, z) {
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color }));
  m.name = name;
  m.position.set(x, y, z);
  return m;
}
const floor = mesh('floor', new THREE.PlaneGeometry(10, 10), 0x404040, 0, 0, 0);
floor.rotation.x = -Math.PI / 2;
scene.add(floor);
scene.add(mesh('redBox', new THREE.BoxGeometry(1, 1, 1), 0xff0000, -2, 0.5, 0));
scene.add(mesh('blueSphere', new THREE.SphereGeometry(0.75, 32, 16), 0x0000ff, 2, 0.75, 0));
const spinner = mesh('spinner', new THREE.BoxGeometry(0.5, 2, 0.5), 0x00ff00, 0, 1, -2);
scene.add(spinner);
const markers = new THREE.Group();
markers.name = 'markers';
markers.position.set(0, 0, 2);
[-1, 0, 1].forEach((x, i) => markers.add(mesh('m' + i, new THREE.BoxGeometry(0.2, 0.2, 0.2), 0xffff00, x, 0.1, 0)));
scene.add(markers);

const ambient = new THREE.AmbientLight(0xffffff, 0.5);
ambient.name = 'ambient';
scene.add(ambient);
const sun = new THREE.DirectionalLight(0xffffff, 1.0);
sun.name = 'sun';
sun.position.set(5, 10, 5);
scene.add(sun);

const SPEED = THREE.MathUtils.degToRad(45);
let elapsed = 0;
function draw() {
  spinner.rotation.y = elapsed * SPEED;
  renderer.render(scene, camera);
}

window.paused = false;
window.step = (dt) => { elapsed += dt; draw(); };

let last = performance.now();
renderer.setAnimationLoop((now) => {
  const dt = (now - last) / 1000;
  last = now;
  if (!window.paused) elapsed += dt;
  draw();
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  draw();
});

window.scene = scene;
window.camera = camera;
window.renderer = renderer;
draw();
window.ready = true;
