// Product viewer: a model turning on a turntable (see docs/SPEC.md).
import * as THREE from 'three';

const renderer = new THREE.WebGLRenderer();
renderer.setPixelRatio(1);
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101010);

const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.1, 200);
camera.position.set(0, 3, 6);
camera.lookAt(0, 0.5, 0);

const model = new THREE.Group();
model.name = 'model';
scene.add(model);

const BODY_RGB = [0x33, 0x66, 0xcc];
const bodyMat = new THREE.MeshBasicMaterial();
bodyMat.color.setRGB(BODY_RGB[0] / 255, BODY_RGB[1] / 255, BODY_RGB[2] / 255, THREE.SRGBColorSpace);
const body = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 1), bodyMat);
body.name = 'body';
body.position.set(0, 0.5, 0);
model.add(body);

const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.3, 32), new THREE.MeshBasicMaterial({ color: 0xcc3333 }));
cap.name = 'cap';
cap.position.set(0, 1.15, 0);
model.add(cap);

const farMarker = new THREE.Mesh(new THREE.SphereGeometry(0.5, 24, 12), new THREE.MeshBasicMaterial({ color: 0xffcc00 }));
farMarker.name = 'farMarker';
farMarker.position.set(0, 0.5, -40);
scene.add(farMarker);

const START_ANGLE = 30;
model.rotation.y = THREE.MathUtils.degToRad(START_ANGLE);

window.elapsed = 0;
window.paused = false;

function update(dt) {
  window.elapsed += dt;
  model.rotation.y = THREE.MathUtils.degToRad(START_ANGLE + 60 * window.elapsed);
}

window.step = (dt) => {
  update(dt);
  renderer.render(scene, camera);
};

const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const dt = clock.getDelta();
  if (!window.paused) update(dt);
  renderer.render(scene, camera);
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

window.scene = scene;
window.camera = camera;
window.renderer = renderer;
renderer.render(scene, camera);
window.ready = true;
