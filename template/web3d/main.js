// Hollow Oak lounge, real-time: the room is drawn fresh every frame at the screen's own resolution (like finely-crafted.com).
// Lighting comes from Cycles, baked into the textures (blender/bake.py); the browser adds the floor reflection and glass.
import * as THREE from 'three';
import { GLTFLoader } from './vendor/three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from './vendor/three/addons/loaders/DRACOLoader.js';
import { HDRLoader } from './vendor/three/addons/loaders/HDRLoader.js';
import { mergeGeometries } from './vendor/three/addons/utils/BufferGeometryUtils.js';
import { EffectComposer } from './vendor/three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/three/addons/postprocessing/RenderPass.js';
import { OutputPass } from './vendor/three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from './vendor/three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from './vendor/three/addons/shaders/FXAAShader.js';

const STORE = 2;                       // baked textures hold radiance / 2
const EXPOSURE = 2 ** 1.6;             // same exposure as the Cycles renders
const canvas = document.getElementById('view');
const QP = new URLSearchParams(location.search);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: QP.has('aa'), powerPreference: 'high-performance' });
renderer.setPixelRatio(QP.has('pr') ? +QP.get('pr') : Math.min(devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = EXPOSURE;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d0b09);
const camera = new THREE.PerspectiveCamera(45, 16 / 9, 0.05, 40);
const reduce = matchMedia('(prefers-reduced-motion: reduce)');
const touch = matchMedia('(hover: none)');

const manager = new THREE.LoadingManager();
const pct = document.getElementById('pct');
manager.onProgress = (_u, done, total) => { pct.textContent = Math.round(100 * done / total) + '%'; };
const draco = new DRACOLoader(manager).setDecoderPath('./vendor/draco/');
const gltf = new GLTFLoader(manager).setDRACOLoader(draco);
const [walk, lounge, live, env, sky] = await Promise.all([
  fetch('assets/walk.json').then(r => r.json()),
  gltf.loadAsync('assets/lounge.glb'),
  gltf.loadAsync('assets/live.glb'),
  new HDRLoader(manager).loadAsync('assets/env.hdr'),
  new HDRLoader(manager).loadAsync('assets/sky.hdr'),
]);

// ---- materials ----
const pmrem = new THREE.PMREMGenerator(renderer);
env.mapping = THREE.EquirectangularReflectionMapping;
scene.environment = pmrem.fromEquirectangular(env).texture;
sky.mapping = THREE.EquirectangularReflectionMapping;
scene.background = sky;                 // seen only through the window: the afternoon sky, blown out like the Cycles camera saw it
scene.backgroundIntensity = 3;
const Q_ = new URLSearchParams(location.search);
const aniso = Q_.has('aniso') ? +Q_.get('aniso') : Math.min(4, renderer.capabilities.getMaxAnisotropy());

let floorMesh = null;
lounge.scene.traverse(o => {
  if (!o.isMesh) return;
  const map = o.material.map;
  if (map) map.anisotropy = aniso;
  if (o.name.startsWith('bk_floor')) { floorMesh = o; return; }
  if (o.name.startsWith('bk_room')) o.material = new THREE.MeshBasicMaterial({ map, color: new THREE.Color(STORE, STORE, STORE) });
  else for (const m of [o.material].flat()) {          // baked look in emission; the live shader keeps only the reflections
    m.emissiveMap.anisotropy = aniso; m.emissiveIntensity = STORE; m.envMapIntensity = 2;
    m.onBeforeCompile = sh => {
      sh.fragmentShader = sh.fragmentShader.replace('#include <lights_fragment_end>',
        '#include <lights_fragment_end>\n reflectedLight.directDiffuse = vec3(0.0); reflectedLight.indirectDiffuse = vec3(0.0);');
    };
  }
});
scene.add(lounge.scene);

// floor: baked look plus a soft reflection. The room never changes, so it is photographed once into a cube map after
// load and projected onto the room's box: one texture read per pixel instead of drawing the room twice every frame
const floorMap = floorMesh.material.map;
const floorGeo = floorMesh.geometry.clone().applyMatrix4(floorMesh.matrixWorld);
floorMesh.parent.remove(floorMesh);
const room = new THREE.Box3();
lounge.scene.traverse(o => { if (o.isMesh && o.name.startsWith('bk_room')) room.expandByObject(o); });
const probeRT = new THREE.WebGLCubeRenderTarget(512, { type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter });
const probe = new THREE.CubeCamera(0.05, 40, probeRT);
probe.layers.enableAll();
room.getCenter(probe.position).setY(1.3);
const floor = new THREE.Mesh(floorGeo, new THREE.ShaderMaterial({
  uniforms: {
    map: { value: floorMap }, store: { value: STORE }, env: { value: probeRT.texture },
    boxMin: { value: room.min }, boxMax: { value: room.max }, probePos: { value: probe.position },
    blur: { value: Q_.has('blur') ? +Q_.get('blur') : 3.0 }, gain: { value: Q_.has('norefl') ? 0 : 0.9 },
  },
  vertexShader: `
    varying vec2 vUv; varying vec3 vWorld;
    void main() {
      vUv = uv;
      vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz;
      gl_Position = projectionMatrix * viewMatrix * w;
    }`,
  fragmentShader: `
    uniform sampler2D map; uniform float store; uniform samplerCube env;
    uniform vec3 boxMin; uniform vec3 boxMax; uniform vec3 probePos; uniform float blur; uniform float gain;
    varying vec2 vUv; varying vec3 vWorld;
    #include <common>
    void main() {
      vec3 base = texture2D(map, vUv).rgb * store;
      vec3 V = normalize(cameraPosition - vWorld);
      vec3 R = vec3(-V.x, V.y, -V.z);                       // mirrored about the floor normal
      vec3 hit = mix((boxMin - vWorld) / R, (boxMax - vWorld) / R, step(0.0, R));
      vec3 dir = vWorld + R * min(min(hit.x, hit.y), hit.z) - probePos;
      float f = 0.04 + 0.96 * pow(1.0 - max(V.y, 0.0), 5.0);
      gl_FragColor = vec4(base + textureLod(env, dir, blur).rgb * f * gain, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
}));
scene.add(floor);
function shootProbe() {
  const gain = floor.material.uniforms.gain.value;
  floor.material.uniforms.gain.value = 0;      // the floor cannot read the cube it is being drawn into
  const bg = scene.background; scene.background = new THREE.Color(0x0d0b09);
  probe.update(renderer, scene);
  floor.material.uniforms.gain.value = gain;
  scene.background = bg;
}

// small things (bottles, glasses, lamps, plant): merged into one mesh per material, so ~200 draw calls become ~25
const glass = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.04, metalness: 0, transparent: true, opacity: 0.22, envMapIntensity: 1.6, depthWrite: false });
const whiskey = new THREE.MeshStandardMaterial({ color: 0xc86418, roughness: 0.1, transparent: true, opacity: 0.88, envMapIntensity: 1.2 });
const liveMats = new Map(), groups = new Map();
function liveMat(m) {
  const n = m.name || m.uuid;
  if (liveMats.has(n)) return liveMats.get(n);
  let out = m;
  if (n === 'glass' || /glass_(clear|green|orange|yellow)/.test(n)) {
    out = glass.clone();
    if (/green|orange|yellow/.test(n)) out.color.copy(m.color);
  } else if (n === 'whiskey') out = whiskey;
  else if (/wine_/.test(n)) out = new THREE.MeshStandardMaterial({ color: m.color, roughness: 0.15, transparent: true, opacity: 0.9 });
  else if (n === 'bulb') out = new THREE.MeshBasicMaterial({ color: new THREE.Color(6, 4.2, 2.4) });
  else if (n === 'shade_inner') out = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.9, 1.15, 0.5), side: THREE.DoubleSide });
  else if (n === 'shade_black') m.side = THREE.DoubleSide;
  liveMats.set(n, out);
  return out;
}
live.scene.updateMatrixWorld(true);
live.scene.traverse(o => {
  if (!o.isMesh) return;
  const mat = liveMat(o.material);
  const g = o.geometry.clone().applyMatrix4(o.matrixWorld);
  for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
  if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
  if (!g.attributes.normal) g.computeVertexNormals();
  const gi = g.index ? g.toNonIndexed() : g;
  if (!groups.has(mat)) groups.set(mat, []);
  groups.get(mat).push(gi);
});
const liveGroup = new THREE.Group();
for (const [mat, list] of groups) {
  if (Q_.has('noglass') && mat.transparent) continue;
  if (Q_.has('onlyglass') && !mat.transparent) continue;
  const mesh = new THREE.Mesh(mergeGeometries(list), mat);
  if (mat.transparent) mesh.renderOrder = 2;
  liveGroup.add(mesh);
}

if (!Q_.has('nolive')) scene.add(liveGroup);

// ---- camera walk: per-frame camera from Blender, interpolated between frames ----
const N = walk.frames.length;
const P = walk.frames.map(f => new THREE.Vector3(...f.p)), Q = walk.frames.map(f => new THREE.Quaternion(...f.q));
// even pace on screen: a turn of 1 radian sweeps the picture about as much as walking 2.5 m, so scroll by that cost
const COST = [0];
for (let i = 1; i < N; i++) COST.push(COST[i - 1] + P[i].distanceTo(P[i - 1]) + 2.5 * Q[i].angleTo(Q[i - 1]));
function frameAt(p) {
  const c = p * COST[N - 1];
  let i = 0;
  while (i < N - 2 && COST[i + 1] < c) i++;
  return i + Math.min(1, (c - COST[i]) / Math.max(1e-6, COST[i + 1] - COST[i]));
}
const tanH = Math.tan(THREE.MathUtils.degToRad(walk.hfov / 2));
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new OutputPass());                       // tone mapping + sRGB, then edge smoothing on the final picture
const fxaa = new ShaderPass(FXAAShader);
composer.addPass(fxaa);
function fit() {
  const w = innerWidth, h = innerHeight, a = w / h, pr = renderer.getPixelRatio();
  renderer.setSize(w, h, false);
  composer.setPixelRatio(pr); composer.setSize(w, h);
  fxaa.material.uniforms.resolution.value.set(1 / (w * pr), 1 / (h * pr));
  camera.aspect = a;
  // keep the frame Cycles saw on 16:9 and wider screens; on narrow screens show more height, but not fisheye
  camera.fov = a >= 16 / 9 ? THREE.MathUtils.radToDeg(2 * Math.atan(tanH * 9 / 16)) : Math.min(68, THREE.MathUtils.radToDeg(2 * Math.atan(tanH / a)));
  camera.updateProjectionMatrix();
  dirty = true;
  kick();
}

// ---- captions, hotspots, card (same page as the frame-sequence version) ----
const caps = [...document.querySelectorAll('.cap')].map(el => {
  const d = el.dataset;
  if (d.key) {
    const k = COST[walk.keys[+d.key]] / COST[N - 1];
    return { el, from: k - +d.before, to: k + +d.after, on: false };
  }
  return { el, from: +d.from, to: +d.to, on: false };
});
const card = document.getElementById('card');
let openK = -1;
const spots = walk.hotspots.map((h, k) => {
  const el = document.createElement('button');
  el.type = 'button'; el.className = 'spot'; el.setAttribute('aria-label', h.title);
  el.addEventListener('click', () => open(k));
  document.getElementById('spots').appendChild(el);
  return { ...h, at: new THREE.Vector3(...h.at), el, on: false };
});
function open(k) {
  openK = k;
  const h = spots[k];
  document.getElementById('card-n').textContent = String(k + 1).padStart(2, '0') + ' · Look closer';
  document.getElementById('card-t').textContent = h.title;
  document.getElementById('card-p').textContent = h.text;
  card.classList.add('on');
  caps.forEach(c => c.el.style.visibility = 'hidden');
}
function close() {
  openK = -1;
  card.classList.remove('on');
  caps.forEach(c => c.el.style.visibility = '');
}
card.querySelector('button').addEventListener('click', close);
addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
const tmp = new THREE.Vector3();

const bar = document.getElementById('bar'), halo = document.getElementById('halo');
function ui(p) {
  bar.style.transform = `scaleX(${p.toFixed(4)})`;
  for (const c of caps) {
    const on = p >= c.from && p < c.to;
    if (on !== c.on) c.el.classList.toggle('on', c.on = on);
  }
  halo.classList.toggle('on', caps[0].on);
  for (const s of spots) {
    tmp.copy(s.at).project(camera);
    const f = Math.round(frameAt(p));       // occlusion per frame was worked out in Blender (build_all.py)
    const on = p >= s.from && p <= s.to && tmp.z < 1 && Math.abs(tmp.x) < 0.94 && Math.abs(tmp.y) < 0.92 && !!s.vis[f];
    if (on !== s.on) {
      s.el.classList.toggle('on', s.on = on);
      if (!on && openK === spots.indexOf(s)) close();
    }
    if (on) s.el.style.transform = `translate(${((tmp.x + 1) / 2 * innerWidth).toFixed(1)}px, ${((1 - tmp.y) / 2 * innerHeight).toFixed(1)}px)`;
  }
}

// ---- scroll -> walk, same glide as before; mouse turns the head a little (a real camera turn, no zoom) ----
const IDLE = 220, GLIDE = 0.9, TILT = THREE.MathUtils.degToRad(2.2);
let cur = -1, raf = 0, last = 0, lastScroll = 0, dirty = true, polished = false, polishTimer = 0;
let tilt = { x: 0, y: 0 }, aim = { x: 0, y: 0 };
const qTilt = new THREE.Quaternion(), eTilt = new THREE.Euler(0, 0, 0, 'YXZ');
const target = () => {
  const max = document.documentElement.scrollHeight - innerHeight;
  return (max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 0) * (N - 1);
};
const kick = () => { if (!raf) raf = requestAnimationFrame(tick); };
const ease = (v, goal, k) => { const nv = v + (goal - v) * k; return Math.abs(goal - nv) < 0.0005 ? goal : nv; };
function place() {
  const f = frameAt(cur / (N - 1)), i = Math.min(N - 2, Math.floor(f)), u = f - i;
  camera.position.lerpVectors(P[i], P[i + 1], u);
  camera.quaternion.slerpQuaternions(Q[i], Q[i + 1], u);
  eTilt.set(-tilt.y * TILT * 0.6, -tilt.x * TILT, 0);
  camera.quaternion.multiply(qTilt.setFromEuler(eTilt));
  camera.updateMatrixWorld();
}
function tick(now) {
  raf = 0;
  const t = target();
  const dt = last ? Math.min(now - last, 100) : 16.7;
  const prev = cur;
  if (cur < 0 || reduce.matches) cur = t;
  else {
    cur += (t - cur) * (1 - Math.pow(GLIDE, dt / 16.7));
    if (Math.abs(t - cur) < 0.002) cur = t;
  }
  const goal = !touch.matches && !reduce.matches ? aim : { x: 0, y: 0 }, kt = 1 - Math.pow(0.9, dt / 16.7);
  const tx = tilt.x, ty = tilt.y;
  tilt = { x: ease(tilt.x, goal.x, kt), y: ease(tilt.y, goal.y, kt) };
  if (dirty || cur !== prev || tilt.x !== tx || tilt.y !== ty) {
    place();
    renderer.render(scene, camera);       // while moving: one plain pass (post passes cost ~3x on integrated GPUs)
    polished = false;
    ui(cur / (N - 1));
    dirty = false;
  }
  if (cur !== t || tilt.x !== goal.x || tilt.y !== goal.y) { last = now; kick(); }
  else {
    last = 0;
    clearTimeout(polishTimer);             // at rest: one frame with edge smoothing
    polishTimer = setTimeout(() => { if (!raf && !polished) { composer.render(); polished = true; } }, 120);
  }
}
addEventListener('scroll', () => { lastScroll = performance.now(); kick(); }, { passive: true });
addEventListener('pointermove', e => {
  if (e.pointerType !== 'mouse') return;
  aim = { x: e.clientX / innerWidth * 2 - 1, y: e.clientY / innerHeight * 2 - 1 };
  kick();
}, { passive: true });
document.addEventListener('pointerleave', () => { aim = { x: 0, y: 0 }; kick(); });
addEventListener('resize', fit);
fit();
cur = target(); place(); shootProbe();
renderer.compile(scene, camera);
document.getElementById('load').classList.add('done');
window.__walk = { renderer, scene, camera };
