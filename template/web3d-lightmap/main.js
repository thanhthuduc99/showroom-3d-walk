// HẺM, real-time: the shop is drawn fresh every frame at the screen's own resolution (like finely-crafted.com).
// Light comes from Cycles (blender/bake_hem.py): lightmaps on the architecture, light per vertex on the clothes.
import * as THREE from 'three';
import { GLTFLoader } from './vendor/three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from './vendor/three/addons/loaders/DRACOLoader.js';
import { HDRLoader } from './vendor/three/addons/loaders/HDRLoader.js';
import { mergeGeometries } from './vendor/three/addons/utils/BufferGeometryUtils.js';

const STORE = 2;                       // colour bakes and vertex light hold radiance / 2
const LSTORE = 6;                      // lightmaps hold light / 6
const EXPOSURE = 1;                    // the Cycles renders use exposure 0
const canvas = document.getElementById('view');
const QP = new URLSearchParams(location.search);
const GOODS_FLOOR = QP.has('gf') ? +QP.get('gf') : 0.4;   // lowest vertex light kept on the goods
const NEON = QP.has('neon') ? +QP.get('neon') : 0.8;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: !QP.has('noaa'), powerPreference: 'high-performance' });
renderer.setPixelRatio(QP.has('pr') ? +QP.get('pr') : Math.min(devicePixelRatio || 1, 1.5));   // MSAA on every frame: past 1.5x weak GPUs drop frames
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
const [walk, hem, goods, live, env, sky] = await Promise.all([
  fetch('assets/walk.json').then(r => r.json()),
  gltf.loadAsync('assets/hem.glb'),
  gltf.loadAsync('assets/goods.glb'),
  gltf.loadAsync('assets/live.glb'),
  new HDRLoader(manager).loadAsync('assets/env.hdr'),
  new HDRLoader(manager).loadAsync('assets/sky.hdr'),
]);

// ---- materials ----
const pmrem = new THREE.PMREMGenerator(renderer);
env.mapping = THREE.EquirectangularReflectionMapping;
scene.environment = pmrem.fromEquirectangular(env).texture;
sky.mapping = THREE.EquirectangularReflectionMapping;
scene.background = sky;                 // the strip of sky above the lane
scene.backgroundIntensity = 1.6;
const Q_ = new URLSearchParams(location.search);
const aniso = Q_.has('aniso') ? +Q_.get('aniso') : Math.min(4, renderer.capabilities.getMaxAnisotropy());
const tagOf = o => { for (let p = o; p; p = p.parent) { const m = /^(lf|lm|bp|vc)_/.exec(p.name); if (m) return m[1]; } return ''; };

// split a mesh into its connected parts (vertices that share a position belong together)
function pieces(geo) {
  const g = geo.index ? geo.toNonIndexed() : geo, pos = g.attributes.position, n = pos.count / 3;
  const parent = [...Array(n).keys()], find = i => parent[i] === i ? i : (parent[i] = find(parent[i]));
  const seen = new Map();
  for (let i = 0; i < pos.count; i++) {
    const k = [pos.getX(i), pos.getY(i), pos.getZ(i)].map(v => Math.round(v * 1000)).join();
    const t = Math.floor(i / 3);
    if (seen.has(k)) parent[find(t)] = find(seen.get(k)); else seen.set(k, t);
  }
  const groups = new Map();
  for (let t = 0; t < n; t++) { const r = find(t); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(t); }
  return [...groups.values()].map(tris => {
    const out = new THREE.BufferGeometry();
    for (const [name, a] of Object.entries(g.attributes)) {
      const arr = new a.array.constructor(tris.length * 3 * a.itemSize);
      tris.forEach((t, j) => arr.set(a.array.subarray(t * 3 * a.itemSize, (t + 1) * 3 * a.itemSize), j * 3 * a.itemSize));
      out.setAttribute(name, new THREE.BufferAttribute(arr, a.itemSize, a.normalized));
    }
    return out;
  });
}

// merge many small meshes into one per material: draw calls stay ~60 for the whole shop
function merged(meshes, matFor) {
  const groups = new Map(), out = new THREE.Group();
  for (const o of meshes) {
    const mat = matFor(o.material);
    if (!mat) continue;
    const g = o.geometry.clone().applyMatrix4(o.matrixWorld);
    if (!groups.has(mat)) groups.set(mat, []);
    groups.get(mat).push(g.index ? g.toNonIndexed() : g);
  }
  for (const [mat, list] of groups) {
    const keys = Object.keys(list[0].attributes).filter(k => list.every(g => g.attributes[k]));
    for (const g of list) for (const k of Object.keys(g.attributes)) if (!keys.includes(k)) g.deleteAttribute(k);
    out.add(new THREE.Mesh(mergeGeometries(list), mat));
  }
  return out;
}

let floorMesh = null;
hem.scene.updateMatrixWorld(true);
hem.scene.traverse(o => {
  if (!o.isMesh) return;
  const m = o.material, tag = tagOf(o);
  if (m.map) m.map.anisotropy = aniso;
  if (tag === 'lf') { floorMesh = o; return; }
  if (tag === 'lm') {                    // sharp tiling albedo x baked light (Basic material multiplies the light map by 1/PI)
    o.material = new THREE.MeshBasicMaterial({ map: m.map, color: m.color, lightMap: m.emissiveMap, lightMapIntensity: LSTORE * Math.PI });
  } else if (tag === 'bp') o.material = new THREE.MeshBasicMaterial({ map: m.map, color: new THREE.Color(STORE, STORE, STORE) });
});
scene.add(hem.scene);

// floor: tiled concrete x baked light, plus a soft reflection. The room never changes, so it is photographed once into a
// cube map after load and projected onto the room's box; a live mirror render each frame cost too much next to MSAA
const floorGeo = floorMesh.geometry.clone().applyMatrix4(floorMesh.matrixWorld);
floorGeo.setAttribute('uvL', floorGeo.attributes.uv1);
const floorAlb = floorMesh.material.map, floorLm = floorMesh.material.emissiveMap;
floorMesh.parent.remove(floorMesh);
const room = new THREE.Box3();
hem.scene.traverse(o => { if (o.isMesh && /^lm_walls/.test(o.name)) room.expandByObject(o); });
const probeRT = new THREE.WebGLCubeRenderTarget(512, { type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter });
const probe = new THREE.CubeCamera(0.05, 40, probeRT);
room.getCenter(probe.position).setY(1.3);
const floor = new THREE.Mesh(floorGeo, new THREE.ShaderMaterial({
  uniforms: {
    map: { value: floorAlb }, lm: { value: floorLm }, store: { value: LSTORE }, env: { value: probeRT.texture },
    boxMin: { value: room.min }, boxMax: { value: room.max }, probePos: { value: probe.position },
    blur: { value: Q_.has('blur') ? +Q_.get('blur') : 3.0 }, gain: { value: Q_.has('norefl') ? 0 : 0.9 },
  },
  vertexShader: `
    attribute vec2 uvL;
    varying vec2 vUv; varying vec2 vUvL; varying vec3 vWorld;
    void main() {
      vUv = uv; vUvL = uvL;
      vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz;
      gl_Position = projectionMatrix * viewMatrix * w;
    }`,
  fragmentShader: `
    uniform sampler2D map; uniform sampler2D lm; uniform float store; uniform samplerCube env;
    uniform vec3 boxMin; uniform vec3 boxMax; uniform vec3 probePos; uniform float blur; uniform float gain;
    varying vec2 vUv; varying vec2 vUvL; varying vec3 vWorld;
    #include <common>
    void main() {
      vec3 base = texture2D(map, vUv).rgb * texture2D(lm, vUvL).rgb * store;   // sRGB textures arrive linear
      vec3 V = normalize(cameraPosition - vWorld);
      vec3 R = vec3(-V.x, V.y, -V.z);                       // mirrored about the floor normal
      vec3 hit = mix((boxMin - vWorld) / R, (boxMax - vWorld) / R, step(0.0, R));
      vec3 dir = vWorld + R * min(min(hit.x, hit.y), hit.z) - probePos;
      float f = 0.04 + 0.96 * pow(1.0 - max(V.y, 0.0), 5.0);
      vec3 refl = textureLod(env, dir, blur).rgb;
      gl_FragColor = vec4(base + refl * f * gain, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
}));
floorAlb.anisotropy = 8;
scene.add(floor);
function shootProbe() {
  const gain = floor.material.uniforms.gain.value;
  floor.material.uniforms.gain.value = 0;      // the floor cannot read the cube it is being drawn into
  mirrorList.forEach(m => m.visible = false);
  const bg = scene.background; scene.background = new THREE.Color(0x0b0c0d);
  probe.update(renderer, scene);
  floor.material.uniforms.gain.value = gain;
  for (const m of mirrorList) if (m.userData.cube !== probe) m.userData.cube.update(renderer, scene);
  scene.background = bg;
  mirrorList.forEach(m => m.visible = true);
}

// clothes, shoes, mannequins, the scooter: their own texture x light baked per vertex
const goodsMats = new Map();
const goodsList = [];
goods.scene.updateMatrixWorld(true);
goods.scene.traverse(o => { if (o.isMesh) goodsList.push(o); });
const goodsGroup = merged(goodsList, m => {
  if (!goodsMats.has(m.name)) {
    if (m.map) m.map.anisotropy = aniso;
    const mat = new THREE.MeshBasicMaterial({ map: m.map, vertexColors: true, color: new THREE.Color(STORE, STORE, STORE) });
    // vertices tucked between packed garments bake near black and smear dark streaks over the faces we do see
    mat.onBeforeCompile = s => { s.fragmentShader = s.fragmentShader.replace('#include <color_fragment>', 'diffuseColor.rgb *= max(vColor.rgb, vec3(GOODS_FLOOR));'); };
    mat.defines = { GOODS_FLOOR: GOODS_FLOOR.toFixed(3) };
    goodsMats.set(m.name, mat);
  }
  return goodsMats.get(m.name);
});
scene.add(goodsGroup);

// neon, LED strips, lamp lenses, mirrors, plants: drawn live
const liveMats = new Map(), liveList = [], glowList = [], mirrorList = [];
function liveMat(m) {
  const n = m.name || m.uuid;
  if (liveMats.has(n)) return liveMats.get(n);
  let out = m;
  if (m.emissiveIntensity > 0 && m.emissive && (m.emissive.r + m.emissive.g + m.emissive.b) > 0)
    out = new THREE.MeshBasicMaterial({ color: m.emissive.clone().multiplyScalar(m.emissiveIntensity * NEON) });
  liveMats.set(n, out);
  return out;
}
live.scene.updateMatrixWorld(true);
live.scene.traverse(o => { if (o.isMesh) (o.material.emissiveIntensity > 0 && (o.material.emissive.r + o.material.emissive.g) > 0 ? glowList : liveList).push(o); });
if (!Q_.has('nolive')) {
  scene.add(merged(glowList, liveMat));
  // fitting-room mirrors
  const mirrors = liveList.filter(o => o.material.name === 'mirror');
  scene.add(merged(liveList.filter(o => !mirrors.includes(o)), liveMat));
  // each mirror sees its own booth: a snapshot from the middle of the booth, projected onto the booth's box
  const c = new THREE.Vector3(), rc = room.getCenter(new THREE.Vector3());
  const panes = mirrors.flatMap(o => pieces(o.geometry.clone().applyMatrix4(o.matrixWorld)));
  for (const g of panes) {
    g.computeBoundingBox();
    const box = g.boundingBox, size = box.getSize(new THREE.Vector3());
    box.getCenter(c);
    const ax = size.x < size.z ? 'x' : 'z', side = ax === 'x' ? 'z' : 'x', dir = Math.sign(rc[ax] - c[ax]);
    const lo = new THREE.Vector3(), hi = new THREE.Vector3();
    lo[ax] = Math.min(c[ax], c[ax] + dir * 1.6); hi[ax] = Math.max(c[ax], c[ax] + dir * 1.6);
    lo[side] = c[side] - 0.75; hi[side] = c[side] + 0.75;
    lo.y = room.min.y; hi.y = room.max.y;
    const booth = size[side] < 0.8;          // narrow panes hang in the fitting booths, the wide one on the shop wall sees the room
    let cam = probe;
    if (booth) {
      cam = new THREE.CubeCamera(0.05, 40, new THREE.WebGLCubeRenderTarget(512, { type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter }));
      cam.position.copy(c).setY(1.3);
      cam.position[ax] += dir * 0.8;
    }
    const m = new THREE.Mesh(g, new THREE.ShaderMaterial({
      uniforms: { env: { value: cam.renderTarget.texture }, boxMin: { value: booth ? lo : room.min }, boxMax: { value: booth ? hi : room.max }, probePos: { value: cam.position } },
      vertexShader: `
        varying vec3 vWorld; varying vec3 vN;
        void main() {
          vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
          gl_Position = projectionMatrix * viewMatrix * w;
        }`,
      fragmentShader: `
        uniform samplerCube env; uniform vec3 boxMin; uniform vec3 boxMax; uniform vec3 probePos;
        varying vec3 vWorld; varying vec3 vN;
        #include <common>
        void main() {
          vec3 R = reflect(normalize(vWorld - cameraPosition), normalize(vN));
          vec3 hit = mix((boxMin - vWorld) / R, (boxMax - vWorld) / R, step(0.0, R));
          vec3 dir = vWorld + R * min(min(hit.x, hit.y), hit.z) - probePos;
          gl_FragColor = vec4(textureLod(env, dir, 0.8).rgb * 0.85, 1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`,
    }));
    m.userData.cube = cam;
    mirrorList.push(m);
    scene.add(m);
  }
}

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
function fit() {
  const w = innerWidth, h = innerHeight, a = w / h;
  renderer.setSize(w, h, false);
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
  document.getElementById('card-n').textContent = String(k + 1).padStart(2, '0') + ' · Xem kỹ';
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
let cur = -1, raf = 0, last = 0, lastScroll = 0, dirty = true;
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
    renderer.render(scene, camera);       // MSAA on every frame, so frames in motion and at rest look the same
    ui(cur / (N - 1));
    dirty = false;
  }
  if (cur !== t || tilt.x !== goal.x || tilt.y !== goal.y) { last = now; kick(); }
  else last = 0;
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
