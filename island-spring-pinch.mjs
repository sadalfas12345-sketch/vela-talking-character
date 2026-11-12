import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = id => document.getElementById(id);
const canvas = $('viewport');
const ui = {
  character: $('character'), state: $('loadState'), loadProgressBar: $('loadProgressBar'), loadProgressText: $('loadProgressText'), stageText: $('stageText'), island: $('islandSelect'), metrics: $('metrics'),
  showOriginal: $('showOriginal'), showIslands: $('showIslands'), showSprings: $('showSprings'), showInner: $('showInner'),
  showStrain: $('showStrain'), showMass: $('showMass'), gravityDirection: $('gravityDirection'), depth: $('depth'), depthOut: $('depthOut'), neighbors: $('neighbors'), neighborsOut: $('neighborsOut'),
  wireDensity: $('wireDensity'), physicsPreset: $('physicsPreset'), physicsBackend: $('physicsBackend'), integrator: $('integrator'), pinchKp: $('pinchKp'), pinchKd: $('pinchKd'), kpOut: $('kpOut'), kdOut: $('kdOut'), hardDrag: $('hardDrag'), pause: $('pause'), exploreMode: $('exploreMode'), pinchMode: $('pinchMode'), interactionHint: $('interactionHint'),
};
const PHYSICS_PRESETS = {
  biological: {
    name: 'biological', sourceMetersPerUnit: 0.30, rhoEffective: 1100, thicknessMeters: 0.0015, massScale: 1,
    surfaceModulusPa: 30000, innerModulusPa: 10000, compliantThicknessMeters: 0.005, dampingRatio: 0.08,
  },
  realtime: {
    // Automated-calibration candidate. These values are intentionally not
    // biological; the calibration report records whether this candidate is
    // numerically and geometrically acceptable on the original islands.
    name: 'realtime-rk4', sourceMetersPerUnit: 0.30, rhoEffective: 1100, thicknessMeters: 0.0015, massScale: 1e6,
    surfaceModulusPa: 7500, innerModulusPa: 8000000, compliantThicknessMeters: 0.005, dampingRatio: 0.18,
  },
  diagnostic: {
    name: 'diagnostic', sourceMetersPerUnit: 0.30, rhoEffective: 11111111.111111, thicknessMeters: 1.0, massScale: 1,
    surfaceModulusPa: 1.0, innerModulusPa: 0.35, compliantThicknessMeters: 1.0, dampingRatio: 0.08,
  },
};
const MODEL_URLS = {
  female: './assets/tripo/vela-photoreal/generated-original.glb',
  male: './assets/tripo/generalization-male-20261105/generated-original.glb',
};
const ATTACHMENT_URLS = {
  female: './verification/plan-a5-subcutaneous-run/female-corrected-attachments.json',
  male: './verification/plan-a2-hookean-run/male-original-attachments.json',
};
const STAGE_TEXT = {
  1: 'Original mesh islands. Colors come from real indexed triangle connectivity; no material, proximity, semantic segmentation, welding, or cross-island links are used.',
  2: 'Surface springs. Every unique undirected edge from the selected island’s original triangles becomes one Hookean spring. Rendered wire density is only a display filter.',
  3: 'Fixed inner layer. One local inward-offset anchor is generated per selected-island vertex. Own and same-island neighbor tethers are shown without changing the render mesh.',
  4: 'Dynamics validation. Explicit RK4 is measured directly; biological settings use a visible implicit physical fallback when explicit substepping is impractical.',
  5: 'Actual pinch. Pointer raycasts the visible original triangle, preserves its barycentric hit point, applies one compliant Kp/Kd force distributed by its three original vertex weights during RK4, then releases it to recover.',
};
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070d17);
scene.add(new THREE.HemisphereLight(0xffffff, 0x243047, 2.2));
const keyLight = new THREE.DirectionalLight(0xffffff, 3.0);
keyLight.position.set(2, 3, 4);
scene.add(keyLight);
const camera = new THREE.PerspectiveCamera(34, innerWidth / innerHeight, 0.001, 100);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
function resizeRenderer() {
  const maxPixelRatio = innerWidth < 800 ? 1.25 : 2;
  renderer.setPixelRatio(Math.min(devicePixelRatio, maxPixelRatio));
  renderer.setSize(innerWidth, innerHeight, false);
}
resizeRenderer();
renderer.outputColorSpace = THREE.SRGBColorSpace;
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
const loader = new GLTFLoader();
THREE.Cache.enabled = true;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const state = {
  model: 'female', gltf: null, root: null, entries: [], meshes: [], faceScale: 1, faceCenter: new THREE.Vector3(),
  front: new THREE.Vector3(0, 0, 1), right: new THREE.Vector3(1, 0, 0), up: new THREE.Vector3(0, 1, 0), stage: 1, selected: null, spring: null,
  overlay: null, springLines: null, strainLines: null, massHeatmap: null, innerLines: null, innerPoints: null, pinMarker: null, targetMarker: null, forceLine: null, running: false, pin: null, lastPinch: null,
  tests: {}, frameCount: 0, lastFrame: performance.now(), attachments: null, attachmentRecords: null, pointerDebug: null, interactionMode: 'explore',
  gpu: { socket: null, connected: false, connecting: false, busy: false, pendingSeconds: 0, stateHeader: null, globalToLocal: null, lastRuntimeMs: 0, lastSteps: 0, error: null },
  gravity: new THREE.Vector3(), gravityMagnitude: 9.81,
  performance: { frames: 0, physicsSteps: 0, physicsMs: 0, wallMs: 0, lastPhysicsMs: 0, lastFrameMs: 0, simTime: 0 },
};

function dsu(n) {
  const parent = new Int32Array(n);
  for (let i = 0; i < n; i++) parent[i] = i;
  const find = x => { let root = x; while (parent[root] !== root) root = parent[root]; while (parent[x] !== x) { const q = parent[x]; parent[x] = root; x = q; } return root; };
  const union = (a, b) => { a = find(a); b = find(b); if (a !== b) parent[b] = a; };
  return { find, union };
}

function disposeObject(object) {
  if (!object) return;
  object.traverse(item => {
    if (item.geometry) item.geometry.dispose();
    if (item.material) (Array.isArray(item.material) ? item.material : [item.material]).forEach(m => m.dispose());
  });
  scene.remove(object);
}

function setLoadProgress(percent, message) {
  ui.loadProgressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  ui.loadProgressText.textContent = message;
}

function nextPaint() { return new Promise(resolve => requestAnimationFrame(() => resolve())); }

function loadGltfWithProgress(url, label) {
  return new Promise((resolve, reject) => loader.load(url, resolve, event => {
    const fraction = event.total > 0 ? event.loaded / event.total : 0;
    setLoadProgress(5 + fraction * 55, `${label}: ${event.total > 0 ? `${Math.round(fraction * 100)}%` : 'downloading...'}`);
  }, reject));
}

async function preloadModelAsset(name) {
  const url = MODEL_URLS[name];
  if (THREE.Cache.get(url)) return;
  try {
    ui.loadProgressText.textContent = `Ready. Preloading ${name} for faster switching...`;
    const response = await fetch(url, { cache: 'force-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    THREE.Cache.add(url, await response.arrayBuffer());
    await fetch(ATTACHMENT_URLS[name], { cache: 'force-cache' });
    ui.loadProgressText.textContent = `Ready. ${name} is preloaded.`;
  } catch (error) {
    ui.loadProgressText.textContent = `Ready. ${name} will download when selected.`;
    console.warn(`Background preload skipped for ${name}:`, error);
  }
}

function uniqueEdges(entry, island) {
  const index = entry.geometry.index.array;
  const map = new Map();
  const a = [], b = [];
  const key = (u, v) => u < v ? `${u}:${v}` : `${v}:${u}`;
  for (const face of island.faces) {
    const offset = face * 3;
    const vertices = [index[offset], index[offset + 1], index[offset + 2]];
    for (let k = 0; k < 3; k++) {
      const u = vertices[k], v = vertices[(k + 1) % 3], edgeKey = key(u, v);
      if (!map.has(edgeKey)) { map.set(edgeKey, a.length); a.push(u); b.push(v); }
    }
  }
  const aa = new Uint32Array(a), bb = new Uint32Array(b), rest = new Float32Array(a.length);
  const position = entry.geometry.attributes.position;
  const va = new THREE.Vector3(), vb = new THREE.Vector3();
  for (let i = 0; i < a.length; i++) {
    va.fromBufferAttribute(position, aa[i]); vb.fromBufferAttribute(position, bb[i]); rest[i] = va.distanceTo(vb);
  }
  let zeroLengthEdges = 0;
  for (const value of rest) if (value <= 1e-12) zeroLengthEdges++;
  let boundaryEdgeCount = 0;
  const edgeUseCount = new Map();
  for (const face of island.faces) {
    const offset = face * 3;
    const vertices = [index[offset], index[offset + 1], index[offset + 2]];
    for (let k = 0; k < 3; k++) {
      const edgeKey = key(vertices[k], vertices[(k + 1) % 3]);
      edgeUseCount.set(edgeKey, (edgeUseCount.get(edgeKey) || 0) + 1);
    }
  }
  for (const count of edgeUseCount.values()) if (count === 1) boundaryEdgeCount++;
  const boundaryA = [], boundaryB = [];
  for (const [edgeKey, count] of edgeUseCount) {
    if (count !== 1) continue;
    const [u, v] = edgeKey.split(':').map(Number);
    boundaryA.push(u); boundaryB.push(v);
  }
  return { a: aa, b: bb, rest, duplicateRawEdges: island.faces.length * 3 - a.length, zeroLengthEdges, boundaryEdgeCount, boundaryA: new Uint32Array(boundaryA), boundaryB: new Uint32Array(boundaryB) };
}

function buildEntry(mesh) {
  const source = mesh.geometry;
  if (!source.index) throw new Error(`${mesh.name}: original geometry is not indexed`);
  const geometry = source.clone();
  mesh.geometry = geometry;
  // The source GLBs contain mixed winding across reconstruction islands. The
  // browser preview must show the original textured surface from either side;
  // this changes only runtime material culling, never source topology.
  const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  for (const material of materials) {
    if (material) {
      material.side = THREE.DoubleSide;
      // Preserve the source maps and colors, but keep the diagnostic preview
      // opaque. Some Tripo reconstruction islands carry alpha-mode metadata
      // that makes a WebGL preview disappear even though the GLB is valid.
      material.transparent = false;
      material.opacity = 1;
      material.alphaTest = 0;
      material.depthWrite = true;
      material.needsUpdate = true;
    }
  }
  // Keep the source color maps, but use an unlit preview shader for the
  // diagnostic page. This avoids driver-specific PBR/alpha behavior on the
  // female reconstruction while leaving all source GLB materials untouched.
  mesh.material = materials.map(material => new THREE.MeshBasicMaterial({
    map: material?.map || null,
    color: material?.color ? material.color.clone() : 0xffffff,
    side: THREE.DoubleSide,
    transparent: false,
    opacity: 1,
    depthWrite: true,
  }));
  if (mesh.material.length === 1) mesh.material = mesh.material[0];
  mesh.frustumCulled = false;
  mesh.visible = true;
  geometry.computeVertexNormals();
  const vertexCount = geometry.attributes.position.count;
  const index = geometry.index.array;
  const faceCount = index.length / 3;
  const sets = dsu(vertexCount);
  for (let i = 0; i < index.length; i += 3) { sets.union(index[i], index[i + 1]); sets.union(index[i + 1], index[i + 2]); }
  const rootToId = new Map();
  const vertexIsland = new Int32Array(vertexCount);
  const islands = [];
  for (let i = 0; i < vertexCount; i++) {
    const root = sets.find(i);
    let id = rootToId.get(root);
    if (id === undefined) { id = islands.length; rootToId.set(root, id); islands.push({ id, vertices: [], faces: [], bounds: new THREE.Box3() }); }
    vertexIsland[i] = id;
    islands[id].vertices.push(i);
  }
  const faceIsland = new Int32Array(faceCount);
  for (let face = 0; face < faceCount; face++) { const id = vertexIsland[index[face * 3]]; faceIsland[face] = id; islands[id].faces.push(face); }
  let crossIslandTriangleEdges = 0;
  for (let face = 0; face < faceCount; face++) {
    const id = faceIsland[face], offset = face * 3;
    for (let corner = 0; corner < 3; corner++) {
      if (vertexIsland[index[offset + corner]] !== id) crossIslandTriangleEdges++;
    }
  }
  const topology = { vertexCount, faceCount, faceAssignmentCount: faceIsland.length, crossIslandTriangleEdges, everyFaceAssignedOnce: faceIsland.length === faceCount && crossIslandTriangleEdges === 0 };
  const position = geometry.attributes.position;
  for (const island of islands) for (const vertex of island.vertices) island.bounds.expandByPoint(new THREE.Vector3().fromBufferAttribute(position, vertex));
  return { mesh, geometry, islands, vertexIsland, faceIsland, index, topology };
}

function loadFaceFrame(attachmentData) {
  const records = [...attachmentData.records].sort((a, b) => a.index - b.index);
  // Goal-1 attachments were serialized from Blender world coordinates. GLTF
  // stores the same geometry in its Y-up frame, which is [x,z,-y] relative to
  // those records. Apply this only to the camera/anatomical frame; source
  // vertex IDs and triangle coordinates stay in the loaded GLB's frame.
  const toThree = values => new THREE.Vector3(values[0], values[2], -values[1]);
  const points = records.map(record => toThree(record.meshXYZ));
  const right = points[263].clone().sub(points[33]).normalize();
  const brow = [70, 63, 105, 336, 293, 334].reduce((s, id) => s.add(points[id]), new THREE.Vector3()).multiplyScalar(1 / 6);
  const chin = [152, 175, 199, 396, 421, 428].reduce((s, id) => s.add(points[id]), new THREE.Vector3()).multiplyScalar(1 / 6);
  const rawUp = chin.clone().sub(brow).multiplyScalar(-1);
  const up = rawUp.addScaledVector(right, -rawUp.dot(right)).normalize();
  const front = new THREE.Vector3().crossVectors(right, up).normalize();
  const meanNormal = records.reduce((s, r) => s.add(toThree(r.surfaceNormal || [0, 0, 1]).normalize()), new THREE.Vector3());
  if (front.dot(meanNormal) < 0) front.negate();
  state.attachments = points;
  state.attachmentRecords = records;
  state.faceScale = points[263].distanceTo(points[33]);
  state.faceCenter = points.reduce((s, point) => s.add(point), new THREE.Vector3()).multiplyScalar(1 / points.length);
  state.front.copy(front); state.right.copy(right);
  state.up.copy(new THREE.Vector3().crossVectors(front, right).normalize());
  controls.target.copy(state.faceCenter);
  camera.position.copy(state.faceCenter).addScaledVector(state.front, state.faceScale * 4.1);
  camera.lookAt(state.faceCenter); controls.update();
}

function setGravityDirection(direction) {
  const axes = {
    none: new THREE.Vector3(), down: state.up.clone().negate(), up: state.up.clone(), left: state.right.clone().negate(), right: state.right.clone(), forward: state.front.clone(), backward: state.front.clone().negate(),
  };
  state.gravity.copy(axes[direction] || axes.none).multiplyScalar(state.gravityMagnitude);
  if (state.spring) state.spring.markActive();
  gpuSend({ type: 'gravity', value: state.gravity.toArray() });
  updateMetrics(`Gravity: ${direction || 'none'} at ${state.gravityMagnitude.toFixed(2)} m/s²`);
}

function buildIslandOverlay() {
  if (state.overlay) disposeObject(state.overlay);
  state.overlay = new THREE.Group();
  for (const entry of state.entries) {
    const geometry = entry.geometry.clone();
    const colors = new Float32Array(geometry.attributes.position.count * 3);
    const color = new THREE.Color();
    for (let i = 0; i < geometry.attributes.position.count; i++) {
      color.setHSL((entry.vertexIsland[i] * 0.61803398875) % 1, 0.72, 0.52);
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
    }
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.52, depthWrite: false }));
    mesh.visible = false; mesh.renderOrder = 3; state.overlay.add(mesh);
  }
  scene.add(state.overlay);
}

function removeDiagnostics() {
  for (const key of ['springLines', 'strainLines', 'massHeatmap', 'innerLines', 'innerPoints', 'pinMarker', 'targetMarker', 'forceLine']) {
    if (state[key]) { disposeObject(state[key]); state[key] = null; }
  }
}

function activeData() { return state.selected ? state.selected : null; }

function closeGpuBackend(reason = '') {
  const gpu = state.gpu;
  gpu.connected = false; gpu.connecting = false; gpu.busy = false; gpu.pendingSeconds = 0; gpu.stateHeader = null; gpu.globalToLocal = null;
  if (gpu.socket) { try { gpu.socket.close(); } catch {} }
  gpu.socket = null;
  gpu.error = reason || null;
}

function gpuSend(message) {
  const socket = state.gpu.socket;
  if (!state.gpu.connected || !socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(message));
  return true;
}

function gpuSendPin(pin) {
  if (!pin || pin.hard) return false;
  return gpuSend({ type: 'pinch', ids: pin.globalIds, weights: pin.weights, target: pin.target.toArray(), velocity: pin.velocity.toArray() });
}

function applyGpuPositions(values) {
  const gpu = state.gpu, selection = activeData(), spring = state.spring;
  if (!gpu.globalToLocal || !selection || !spring || values.length !== gpu.globalToLocal.size * 3) return false;
  for (let i = 0; i < gpu.globalToLocal.size; i++) {
    const global = gpu.globalIds[i], local = gpu.globalToLocal.get(global);
    if (local === undefined) return false;
    spring.positions[local * 3] = values[i * 3]; spring.positions[local * 3 + 1] = values[i * 3 + 1]; spring.positions[local * 3 + 2] = values[i * 3 + 2];
  }
  spring.update();
  return true;
}

function syncGpuBackend() {
  const mode = ui.physicsBackend?.value || 'auto';
  const shouldUseGpu = mode !== 'cpu' && Boolean(state.selected?.entry && state.spring) && ui.integrator?.value === 'rk4' && !ui.hardDrag?.checked;
  closeGpuBackend();
  if (!shouldUseGpu) return;
  const gpu = state.gpu; gpu.connecting = true;
  const url = new URLSearchParams(location.search).get('gpuServer') || 'ws://127.0.0.1:8765';
  let socket;
  try { socket = new WebSocket(url); } catch (error) { gpu.connecting = false; gpu.error = error.message; return; }
  gpu.socket = socket; socket.binaryType = 'arraybuffer';
  socket.onopen = () => socket.send(JSON.stringify({ type: 'init', model: state.model, domain: `island-${state.selected.island.id}`, kp: Number(ui.pinchKp.value), kd: Number(ui.pinchKd.value) }));
  socket.onmessage = async event => {
    if (typeof event.data === 'string') {
      const message = JSON.parse(event.data);
      if (message.type === 'ready') {
        gpu.globalIds = message.globalVertexIds.map(value => Number(value));
        gpu.globalToLocal = new Map(gpu.globalIds.map((global, index) => [global, index]));
        const expected = state.selected.island.vertices;
        if (expected.length !== gpu.globalIds.length || expected.some(global => !gpu.globalToLocal.has(global))) { closeGpuBackend('GPU fixture does not match the selected original island'); return; }
        gpu.connected = true; gpu.connecting = false; gpu.error = null; updateMetrics('GPU Warp backend connected');
      } else if (message.type === 'state') {
        gpu.stateHeader = message;
      } else if (message.type === 'error') {
        closeGpuBackend(message.message);
      }
      return;
    }
    const buffer = event.data instanceof Blob ? await event.data.arrayBuffer() : event.data;
    const values = new Float32Array(buffer);
    if (!applyGpuPositions(values)) { closeGpuBackend('GPU state size or island correspondence mismatch'); return; }
    gpu.lastRuntimeMs = gpu.stateHeader?.runtimeMs || 0; gpu.lastSteps = gpu.stateHeader?.steps || 0; gpu.busy = false;
    const simulated = gpu.stateHeader?.seconds || 0;
    state.performance.frames++; state.performance.physicsSteps += gpu.lastSteps; state.performance.physicsMs += gpu.lastRuntimeMs; state.performance.wallMs += simulated * 1000; state.performance.lastPhysicsMs = gpu.lastRuntimeMs; state.performance.lastFrameMs = simulated * 1000; state.performance.simTime += simulated;
    gpu.stateHeader = null;
    if (gpu.pendingSeconds > 1.0e-8) { const next = gpu.pendingSeconds; gpu.pendingSeconds = 0; gpuSendTick(next); }
  };
  socket.onclose = () => { if (state.gpu.socket === socket) { gpu.socket = null; gpu.connected = false; gpu.connecting = false; gpu.busy = false; } };
  socket.onerror = () => { if (mode === 'gpu') gpu.error = `GPU server unavailable at ${url}`; };
}

function gpuSendTick(seconds) {
  const gpu = state.gpu;
  if (!gpu.connected || gpu.busy) { gpu.pendingSeconds += seconds; return false; }
  gpu.busy = true;
  return gpuSend({ type: 'tick', seconds, gravity: state.gravity.toArray() });
}

function buildSystem() {
  const selection = activeData();
  if (!selection) return;
  removeDiagnostics();
  const { entry, island } = selection;
  const geometry = entry.geometry;
  const index = geometry.index.array;
  const position = geometry.attributes.position;
  const localMap = new Map(island.vertices.map((vertex, i) => [vertex, i]));
  const vertexCount = island.vertices.length;
  const edgeInfo = uniqueEdges(entry, island);
  const edgeA = new Uint32Array(edgeInfo.a.length), edgeB = new Uint32Array(edgeInfo.b.length);
  for (let i = 0; i < edgeA.length; i++) { edgeA[i] = localMap.get(edgeInfo.a[i]); edgeB[i] = localMap.get(edgeInfo.b[i]); }

  const neutral = new Float32Array(vertexCount * 3);
  for (let i = 0; i < vertexCount; i++) {
    const point = new THREE.Vector3().fromBufferAttribute(position, island.vertices[i]);
    neutral[i * 3] = point.x; neutral[i * 3 + 1] = point.y; neutral[i * 3 + 2] = point.z;
  }
  const neutralFaceAreas = new Float32Array(island.faces.length);
  const neutralFaceNormals = new Float32Array(island.faces.length * 3);
  const localFaceVertices = new Uint32Array(island.faces.length * 3);
  const faceNeighbors = Array.from({ length: island.faces.length }, () => []);
  const faceEdgeOwners = new Map();
  for (let fi = 0; fi < island.faces.length; fi++) {
    const face = island.faces[fi], offset = face * 3;
    const ga = index[offset], gb = index[offset + 1], gc = index[offset + 2];
    const ia = localMap.get(ga), ib = localMap.get(gb), ic = localMap.get(gc);
    localFaceVertices[fi * 3] = ia; localFaceVertices[fi * 3 + 1] = ib; localFaceVertices[fi * 3 + 2] = ic;
    const ax = neutral[ia * 3], ay = neutral[ia * 3 + 1], az = neutral[ia * 3 + 2];
    const abx = neutral[ib * 3] - ax, aby = neutral[ib * 3 + 1] - ay, abz = neutral[ib * 3 + 2] - az;
    const acx = neutral[ic * 3] - ax, acy = neutral[ic * 3 + 1] - ay, acz = neutral[ic * 3 + 2] - az;
    const nx = aby * acz - abz * acy, ny = abz * acx - abx * acz, nz = abx * acy - aby * acx;
    const length = Math.hypot(nx, ny, nz);
    neutralFaceAreas[fi] = length * 0.5;
    if (length > 1e-15) { neutralFaceNormals[fi * 3] = nx / length; neutralFaceNormals[fi * 3 + 1] = ny / length; neutralFaceNormals[fi * 3 + 2] = nz / length; }
    for (const [u, v] of [[ia, ib], [ib, ic], [ic, ia]]) {
      const key = u < v ? `${u}:${v}` : `${v}:${u}`, previous = faceEdgeOwners.get(key);
      if (previous !== undefined) { faceNeighbors[fi].push(previous); faceNeighbors[previous].push(fi); } else faceEdgeOwners.set(key, fi);
    }
  }
  const preset = PHYSICS_PRESETS[ui.physicsPreset.value] || PHYSICS_PRESETS.biological;
  const sourceMetersPerUnit = preset.sourceMetersPerUnit;
  const attributedArea = new Float64Array(vertexCount);
  const masses = new Float32Array(vertexCount);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), ab = new THREE.Vector3(), ac = new THREE.Vector3();
  let totalAreaM2 = 0, degenerateFaceCount = 0;
  for (const face of island.faces) {
    const offset = face * 3;
    a.fromBufferAttribute(position, index[offset]); b.fromBufferAttribute(position, index[offset + 1]); c.fromBufferAttribute(position, index[offset + 2]);
    const sourceArea = ab.subVectors(b, a).cross(ac.subVectors(c, a)).length() * 0.5;
    const areaM2 = sourceArea * sourceMetersPerUnit * sourceMetersPerUnit;
    if (areaM2 <= 1e-18) degenerateFaceCount++;
    totalAreaM2 += areaM2;
    attributedArea[localMap.get(index[offset])] += areaM2 / 3; attributedArea[localMap.get(index[offset + 1])] += areaM2 / 3; attributedArea[localMap.get(index[offset + 2])] += areaM2 / 3;
  }
  let zeroMassVertexCount = 0;
  for (let i = 0; i < vertexCount; i++) {
    masses[i] = preset.rhoEffective * preset.thicknessMeters * attributedArea[i] * preset.massScale;
    if (!(masses[i] > 0) || !Number.isFinite(masses[i])) zeroMassVertexCount++;
  }
  const sortedMasses = Array.from(masses).sort((x, y) => x - y);
  const positiveMasses = sortedMasses.filter(value => value > 0 && Number.isFinite(value));
  const medianMass = positiveMasses[Math.floor(positiveMasses.length / 2)] || 1e-12;
  const numericalMassFloor = Math.max(1e-12, medianMass * 1e-6);
  for (let i = 0; i < vertexCount; i++) if (!(masses[i] > 0) || !Number.isFinite(masses[i])) masses[i] = numericalMassFloor;
  const invMass = new Float32Array(vertexCount);
  for (let i = 0; i < vertexCount; i++) invMass[i] = 1 / masses[i];

  const normals = geometry.attributes.normal;
  const centroid = new THREE.Vector3();
  for (let i = 0; i < vertexCount; i++) centroid.add(new THREE.Vector3(neutral[i * 3], neutral[i * 3 + 1], neutral[i * 3 + 2]));
  centroid.multiplyScalar(1 / vertexCount);
  let orientation = 0;
  for (let i = 0; i < vertexCount; i++) {
    const global = island.vertices[i], normal = new THREE.Vector3().fromBufferAttribute(normals, global);
    orientation += normal.dot(new THREE.Vector3(neutral[i * 3], neutral[i * 3 + 1], neutral[i * 3 + 2]).sub(centroid));
  }
  const orientationSign = orientation >= 0 ? 1 : -1;
  const depthFactor = Number(ui.depth.value);
  const sortedLengths = [...edgeInfo.rest].sort((x, y) => x - y);
  const medianEdge = sortedLengths[Math.floor(sortedLengths.length / 2)] || state.faceScale * 0.005;
  const anchors = new Float32Array(vertexCount * 3);
  for (let i = 0; i < vertexCount; i++) {
    const global = island.vertices[i], normal = new THREE.Vector3().fromBufferAttribute(normals, global);
    const depth = depthFactor * medianEdge;
    anchors[i * 3] = neutral[i * 3] - orientationSign * normal.x * depth;
    anchors[i * 3 + 1] = neutral[i * 3 + 1] - orientationSign * normal.y * depth;
    anchors[i * 3 + 2] = neutral[i * 3 + 2] - orientationSign * normal.z * depth;
  }

  const adjacency = Array.from({ length: vertexCount }, () => []);
  for (let i = 0; i < edgeA.length; i++) { adjacency[edgeA[i]].push(edgeB[i]); adjacency[edgeB[i]].push(edgeA[i]); }
  const neighborCount = Number(ui.neighbors.value), supportA = [], supportB = [], supportRest = [], supportK = [];
  for (let i = 0; i < vertexCount; i++) {
    const neighbors = [...new Set(adjacency[i])].sort((u, v) => {
      const du = Math.hypot(neutral[u * 3] - neutral[i * 3], neutral[u * 3 + 1] - neutral[i * 3 + 1], neutral[u * 3 + 2] - neutral[i * 3 + 2]);
      const dv = Math.hypot(neutral[v * 3] - neutral[i * 3], neutral[v * 3 + 1] - neutral[i * 3 + 1], neutral[v * 3 + 2] - neutral[i * 3 + 2]);
      return du - dv;
    }).slice(0, neighborCount);
    const tetherCount = 1 + neighbors.length;
    const foundationK = preset.innerModulusPa * attributedArea[i] / preset.compliantThicknessMeters;
    const perTetherK = foundationK / tetherCount;
    supportA.push(i); supportB.push(i); supportRest.push(Math.hypot(neutral[i * 3] - anchors[i * 3], neutral[i * 3 + 1] - anchors[i * 3 + 1], neutral[i * 3 + 2] - anchors[i * 3 + 2])); supportK.push(perTetherK);
    for (const neighbor of neighbors) { supportA.push(i); supportB.push(neighbor); supportRest.push(Math.hypot(neutral[i * 3] - anchors[neighbor * 3], neutral[i * 3 + 1] - anchors[neighbor * 3 + 1], neutral[i * 3 + 2] - anchors[neighbor * 3 + 2])); supportK.push(perTetherK); }
  }
  const supportAArray = new Uint32Array(supportA), supportBArray = new Uint32Array(supportB), supportRestArray = new Float32Array(supportRest), supportKArray = new Float32Array(supportK);
  let maxDegree = 1;
  for (const neighbors of adjacency) maxDegree = Math.max(maxDegree, neighbors.length);
  let minMass = Infinity;
  for (const mass of masses) minMass = Math.min(minMass, mass);
  const requestedDt = 1 / 600, stabilityFactor = 0.12;
  const biologicalSurfaceK = preset.surfaceModulusPa * preset.thicknessMeters;
  const stableStiffness = minMass * Math.pow(stabilityFactor / requestedDt, 2) / (maxDegree + neighborCount + 1);
  const surfaceK = ui.physicsPreset.value === 'diagnostic' ? Math.min(1, Math.max(stableStiffness, 1e-12)) : biologicalSurfaceK;
  const innerK = ui.physicsPreset.value === 'diagnostic' ? 0.35 * surfaceK : 1;
  const damping = preset.dampingRatio * 2 * Math.sqrt(Math.max(surfaceK * medianMass, 1e-18));
  const localStiffness = new Float64Array(vertexCount);
  for (let i = 0; i < edgeA.length; i++) { localStiffness[edgeA[i]] += surfaceK; localStiffness[edgeB[i]] += surfaceK; }
  for (let i = 0; i < supportAArray.length; i++) localStiffness[supportAArray[i]] += supportKArray[i];
  let maxLocalStiffness = 1e-18;
  for (const value of localStiffness) maxLocalStiffness = Math.max(maxLocalStiffness, value);
  const stableDt = Math.min(requestedDt, stabilityFactor * Math.sqrt(minMass / maxLocalStiffness));
  const explicitSubstepsPerFrame = Math.max(1, Math.ceil((1 / 60) / Math.max(stableDt, 1e-18)));
  const requestedIntegrator = ui.integrator.value;
  const integrator = requestedIntegrator === 'auto'
    ? (explicitSubstepsPerFrame > 200 ? 'implicit' : 'rk4')
    : requestedIntegrator;
  let positions = neutral.slice(), velocities = new Float32Array(vertexCount * 3), pin = null, innerEnabled = true, neutralSettled = true;
  state.performance = { frames: 0, physicsSteps: 0, physicsMs: 0, wallMs: 0, lastPhysicsMs: 0, lastFrameMs: 0, simTime: 0 };

  const scratchLength = vertexCount * 3;
  const rkScratch = {
    a1: new Float32Array(scratchLength), a2: new Float32Array(scratchLength), a3: new Float32Array(scratchLength), a4: new Float32Array(scratchLength),
    x2: new Float32Array(scratchLength), x3: new Float32Array(scratchLength), x4: new Float32Array(scratchLength),
    v2: new Float32Array(scratchLength), v3: new Float32Array(scratchLength), v4: new Float32Array(scratchLength),
  };
  const implicitCandidate = new Float64Array(scratchLength);
  const implicitVelocity = new Float64Array(scratchLength);
  const implicitAcceleration = new Float64Array(scratchLength);
  const implicitResidual = new Float64Array(scratchLength);
  const implicitTrialResidual = new Float64Array(scratchLength);
  const implicitNewtonDelta = new Float64Array(scratchLength);
  const implicitCgResidual = new Float64Array(scratchLength);
  const implicitCgPreconditioned = new Float64Array(scratchLength);
  const implicitCgDirection = new Float64Array(scratchLength);
  const implicitCgProduct = new Float64Array(scratchLength);
  const implicitCgWeightedResidual = new Float64Array(scratchLength);
  const implicitCgWeightedRhs = new Float64Array(scratchLength);
  const implicitPreconditioner = new Float64Array(scratchLength);
  const massRoot = new Float64Array(vertexCount);
  const inverseMassRoot = new Float64Array(vertexCount);
  for (let i = 0; i < vertexCount; i++) { massRoot[i] = Math.sqrt(masses[i]); inverseMassRoot[i] = 1 / massRoot[i]; }
  const diagonalK = new Float64Array(vertexCount);
  for (let i = 0; i < edgeA.length; i++) { diagonalK[edgeA[i]] += surfaceK; diagonalK[edgeB[i]] += surfaceK; }
  for (let i = 0; i < supportAArray.length; i++) diagonalK[supportAArray[i]] += supportKArray[i];
  const edgeInvSqrtMassProduct = new Float64Array(edgeA.length);
  for (let i = 0; i < edgeA.length; i++) edgeInvSqrtMassProduct[i] = inverseMassRoot[edgeA[i]] * inverseMassRoot[edgeB[i]];
  // The release step can start far from the next implicit equilibrium even
  // though the held step is close.  Keep the physical equations unchanged,
  // but give the nonlinear solve enough iterations and a finer numerical
  // trust-region backtrack to resolve that release transient.
  const implicitNewtonIterations = 32, implicitCgIterations = 16, implicitLineSearchMin = 1 / 4096;
  let implicitDiagnostics = { iterations: 0, linearIterations: 0, finalCorrection: 0, equationResidual: 0, positionVelocityResidual: 0, converged: false, status: 'idle', correctionTolerance: 0, residualTolerance: 0, residualHistory: [], linearStatus: 'idle', negativeCurvatureEvents: 0, regularizationHistory: [], weightedCgResidual: 0 };
  function acceleration(x, v, withInner, pinState, targetOffset = 0, result = rkScratch.a1) {
    result.fill(0);
    for (let i = 0; i < edgeA.length; i++) {
      const ia = edgeA[i], ib = edgeB[i], dx = x[ib * 3] - x[ia * 3], dy = x[ib * 3 + 1] - x[ia * 3 + 1], dz = x[ib * 3 + 2] - x[ia * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const q = surfaceK * ((length - edgeInfo.rest[i]) * sourceMetersPerUnit) / length, fx = q * dx, fy = q * dy, fz = q * dz;
      // Convert physical acceleration back to source-coordinate acceleration.
      result[ia * 3] += fx * invMass[ia] / sourceMetersPerUnit; result[ia * 3 + 1] += fy * invMass[ia] / sourceMetersPerUnit; result[ia * 3 + 2] += fz * invMass[ia] / sourceMetersPerUnit;
      result[ib * 3] -= fx * invMass[ib] / sourceMetersPerUnit; result[ib * 3 + 1] -= fy * invMass[ib] / sourceMetersPerUnit; result[ib * 3 + 2] -= fz * invMass[ib] / sourceMetersPerUnit;
    }
    if (withInner) for (let i = 0; i < supportAArray.length; i++) {
      const ia = supportAArray[i], ib = supportBArray[i], dx = anchors[ib * 3] - x[ia * 3], dy = anchors[ib * 3 + 1] - x[ia * 3 + 1], dz = anchors[ib * 3 + 2] - x[ia * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const q = supportKArray[i] * ((length - supportRestArray[i]) * sourceMetersPerUnit) / length;
      result[ia * 3] += q * dx * invMass[ia] / sourceMetersPerUnit; result[ia * 3 + 1] += q * dy * invMass[ia] / sourceMetersPerUnit; result[ia * 3 + 2] += q * dz * invMass[ia] / sourceMetersPerUnit;
    }
    if (pinState && !pinState.hard) {
      const ids = pinState.ids, weights = pinState.weights;
      let qx = 0, qy = 0, qz = 0, qvx = 0, qvy = 0, qvz = 0;
      for (let j = 0; j < 3; j++) { const id = ids[j], w = weights[j]; qx += w * x[id * 3]; qy += w * x[id * 3 + 1]; qz += w * x[id * 3 + 2]; qvx += w * v[id * 3]; qvy += w * v[id * 3 + 1]; qvz += w * v[id * 3 + 2]; }
      const targetX = pinState.target.x + pinState.velocity.x * targetOffset;
      const targetY = pinState.target.y + pinState.velocity.y * targetOffset;
      const targetZ = pinState.target.z + pinState.velocity.z * targetOffset;
      const forceX = pinState.kp * ((targetX - qx) * sourceMetersPerUnit) + pinState.kd * ((pinState.velocity.x - qvx) * sourceMetersPerUnit);
      const forceY = pinState.kp * ((targetY - qy) * sourceMetersPerUnit) + pinState.kd * ((pinState.velocity.y - qvy) * sourceMetersPerUnit);
      const forceZ = pinState.kp * ((targetZ - qz) * sourceMetersPerUnit) + pinState.kd * ((pinState.velocity.z - qvz) * sourceMetersPerUnit);
      pinState.currentForce.set(forceX, forceY, forceZ);
      pinState.peakForce = Math.max(pinState.peakForce, Math.hypot(forceX, forceY, forceZ));
      pinState.peakTrackingError = Math.max(pinState.peakTrackingError, Math.hypot((targetX - qx) * sourceMetersPerUnit, (targetY - qy) * sourceMetersPerUnit, (targetZ - qz) * sourceMetersPerUnit));
      for (let j = 0; j < 3; j++) { const id = ids[j], w = weights[j] / (masses[id] * sourceMetersPerUnit); result[id * 3] += w * forceX; result[id * 3 + 1] += w * forceY; result[id * 3 + 2] += w * forceZ; }
    }
    const gx = state.gravity.x / sourceMetersPerUnit, gy = state.gravity.y / sourceMetersPerUnit, gz = state.gravity.z / sourceMetersPerUnit;
    for (let i = 0; i < vertexCount; i++) {
      result[i * 3] += gx; result[i * 3 + 1] += gy; result[i * 3 + 2] += gz;
      result[i * 3] -= damping * v[i * 3] * invMass[i]; result[i * 3 + 1] -= damping * v[i * 3 + 1] * invMass[i]; result[i * 3 + 2] -= damping * v[i * 3 + 2] * invMass[i];
    }
    return result;
  }

  function projectConstraint(x, v, pinState) {
    if (!pinState || !pinState.hard) return;
    const ids = pinState.ids, weights = pinState.weights;
    let cx = 0, cy = 0, cz = 0, denominator = 0;
    for (let j = 0; j < 3; j++) { cx += weights[j] * x[ids[j] * 3]; cy += weights[j] * x[ids[j] * 3 + 1]; cz += weights[j] * x[ids[j] * 3 + 2]; denominator += weights[j] * weights[j] * invMass[ids[j]]; }
    if (denominator <= 1e-12) return;
    const dx = pinState.target.x - cx, dy = pinState.target.y - cy, dz = pinState.target.z - cz;
    for (let j = 0; j < 3; j++) { const q = weights[j] * invMass[ids[j]] / denominator; x[ids[j] * 3] += q * dx; x[ids[j] * 3 + 1] += q * dy; x[ids[j] * 3 + 2] += q * dz; }
    let vx = 0, vy = 0, vz = 0;
    for (let j = 0; j < 3; j++) { vx += weights[j] * v[ids[j] * 3]; vy += weights[j] * v[ids[j] * 3 + 1]; vz += weights[j] * v[ids[j] * 3 + 2]; }
    for (let j = 0; j < 3; j++) { const q = weights[j] * invMass[ids[j]] / denominator; v[ids[j] * 3] += q * (pinState.velocity.x - vx); v[ids[j] * 3 + 1] += q * (pinState.velocity.y - vy); v[ids[j] * 3 + 2] += q * (pinState.velocity.z - vz); }
  }

  function integrateOne(dt) {
    acceleration(positions, velocities, innerEnabled, pin, 0, rkScratch.a1);
    for (let i = 0; i < scratchLength; i++) { rkScratch.x2[i] = positions[i] + velocities[i] * dt * 0.5; rkScratch.v2[i] = velocities[i] + rkScratch.a1[i] * dt * 0.5; }
    projectConstraint(rkScratch.x2, rkScratch.v2, pin); acceleration(rkScratch.x2, rkScratch.v2, innerEnabled, pin, dt * 0.5, rkScratch.a2);
    for (let i = 0; i < scratchLength; i++) { rkScratch.x3[i] = positions[i] + rkScratch.v2[i] * dt * 0.5; rkScratch.v3[i] = velocities[i] + rkScratch.a2[i] * dt * 0.5; }
    projectConstraint(rkScratch.x3, rkScratch.v3, pin); acceleration(rkScratch.x3, rkScratch.v3, innerEnabled, pin, dt * 0.5, rkScratch.a3);
    for (let i = 0; i < scratchLength; i++) { rkScratch.x4[i] = positions[i] + rkScratch.v3[i] * dt; rkScratch.v4[i] = velocities[i] + rkScratch.a3[i] * dt; }
    projectConstraint(rkScratch.x4, rkScratch.v4, pin); acceleration(rkScratch.x4, rkScratch.v4, innerEnabled, pin, dt, rkScratch.a4);
    for (let i = 0; i < positions.length; i++) { positions[i] += dt * (velocities[i] + 2 * rkScratch.v2[i] + 2 * rkScratch.v3[i] + rkScratch.v4[i]) / 6; velocities[i] += dt * (rkScratch.a1[i] + 2 * rkScratch.a2[i] + 2 * rkScratch.a3[i] + rkScratch.a4[i]) / 6; }
    projectConstraint(positions, velocities, pin);
    for (const value of positions) if (!Number.isFinite(value)) throw new Error('RK4 produced nonfinite positions');
    for (const value of velocities) if (!Number.isFinite(value)) throw new Error('RK4 produced nonfinite velocities');
  }

  function implicitResidualAt(x, dt, out) {
    for (let i = 0; i < scratchLength; i++) implicitVelocity[i] = (x[i] - positions[i]) / dt;
    acceleration(x, implicitVelocity, innerEnabled, pin, dt, implicitAcceleration);
    let maxResidual = 0;
    for (let i = 0; i < scratchLength; i++) {
      out[i] = x[i] - positions[i] - dt * velocities[i] - dt * dt * implicitAcceleration[i];
      maxResidual = Math.max(maxResidual, Math.abs(out[i]));
    }
    return maxResidual;
  }

  function applyImplicitJacobian(x, direction, dt, out, weighted = false, regularizationShift = 0) {
    out.set(direction);
    const addEdge = (ia, ib, rest, stiffness, dx, dy, dz, length, edgeIndex = -1) => {
      if (length <= 1e-12) return;
      const ux = dx / length, uy = dy / length, uz = dz / length, ratio = rest / length;
      const scale = stiffness * (1 - ratio), axial = stiffness * ratio;
      const hxx = scale + axial * ux * ux, hxy = axial * ux * uy, hxz = axial * ux * uz;
      const hyy = scale + axial * uy * uy, hyz = axial * uy * uz, hzz = scale + axial * uz * uz;
      const factor = dt * dt;
      // R(x) = x - x_n - dt*v_n - dt^2*a(x).  For a surface spring,
      // da_a = +M_a^-1 H (d_b - d_a), so its contribution to dR is
      // -dt^2 M_a^-1 H (d_b - d_a).  The previous implementation used
      // the opposite sign, making the Newton operator indefinite and
      // invalidating the CG solve on the real meshes.
      if (!weighted) {
        const dx0 = direction[ib * 3] - direction[ia * 3], dy0 = direction[ib * 3 + 1] - direction[ia * 3 + 1], dz0 = direction[ib * 3 + 2] - direction[ia * 3 + 2];
        const kx = hxx * dx0 + hxy * dy0 + hxz * dz0, ky = hxy * dx0 + hyy * dy0 + hyz * dz0, kz = hxz * dx0 + hyz * dy0 + hzz * dz0;
        out[ia * 3] -= factor * (kx * invMass[ia]); out[ia * 3 + 1] -= factor * (ky * invMass[ia]); out[ia * 3 + 2] -= factor * (kz * invMass[ia]);
        out[ib * 3] += factor * (kx * invMass[ib]); out[ib * 3 + 1] += factor * (ky * invMass[ib]); out[ib * 3 + 2] += factor * (kz * invMass[ib]);
      } else {
        // A = M^(1/2) J M^(-1/2). This is symmetric when the spring
        // Hessian is symmetric, even when vertex masses differ.
        const cross = edgeInvSqrtMassProduct[edgeIndex], ma = invMass[ia], mb = invMass[ib];
        out[ia * 3] += factor * (hxx * ma * direction[ia * 3] - hxx * cross * direction[ib * 3] + hxy * ma * direction[ia * 3 + 1] - hxy * cross * direction[ib * 3 + 1] + hxz * ma * direction[ia * 3 + 2] - hxz * cross * direction[ib * 3 + 2]);
        out[ia * 3 + 1] += factor * (hxy * ma * direction[ia * 3] - hxy * cross * direction[ib * 3] + hyy * ma * direction[ia * 3 + 1] - hyy * cross * direction[ib * 3 + 1] + hyz * ma * direction[ia * 3 + 2] - hyz * cross * direction[ib * 3 + 2]);
        out[ia * 3 + 2] += factor * (hxz * ma * direction[ia * 3] - hxz * cross * direction[ib * 3] + hyz * ma * direction[ia * 3 + 1] - hyz * cross * direction[ib * 3 + 1] + hzz * ma * direction[ia * 3 + 2] - hzz * cross * direction[ib * 3 + 2]);
        out[ib * 3] += factor * (hxx * mb * direction[ib * 3] - hxx * cross * direction[ia * 3] + hxy * mb * direction[ib * 3 + 1] - hxy * cross * direction[ia * 3 + 1] + hxz * mb * direction[ib * 3 + 2] - hxz * cross * direction[ia * 3 + 2]);
        out[ib * 3 + 1] += factor * (hxy * mb * direction[ib * 3] - hxy * cross * direction[ia * 3] + hyy * mb * direction[ib * 3 + 1] - hyy * cross * direction[ia * 3 + 1] + hyz * mb * direction[ib * 3 + 2] - hyz * cross * direction[ia * 3 + 2]);
        out[ib * 3 + 2] += factor * (hxz * mb * direction[ib * 3] - hxz * cross * direction[ia * 3] + hyz * mb * direction[ib * 3 + 1] - hyz * cross * direction[ia * 3 + 1] + hzz * mb * direction[ib * 3 + 2] - hzz * cross * direction[ia * 3 + 2]);
      }
    };
    for (let i = 0; i < edgeA.length; i++) {
      const ia = edgeA[i], ib = edgeB[i], dx = x[ib * 3] - x[ia * 3], dy = x[ib * 3 + 1] - x[ia * 3 + 1], dz = x[ib * 3 + 2] - x[ia * 3 + 2];
      addEdge(ia, ib, edgeInfo.rest[i], surfaceK, dx, dy, dz, Math.hypot(dx, dy, dz), i);
    }
    for (let i = 0; i < supportAArray.length; i++) {
      const ia = supportAArray[i], dx = anchors[supportBArray[i] * 3] - x[ia * 3], dy = anchors[supportBArray[i] * 3 + 1] - x[ia * 3 + 1], dz = anchors[supportBArray[i] * 3 + 2] - x[ia * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const ux = dx / length, uy = dy / length, uz = dz / length, ratio = supportRestArray[i] / length, scale = supportKArray[i] * (1 - ratio), axial = supportKArray[i] * ratio;
      const hxx = scale + axial * ux * ux, hxy = axial * ux * uy, hxz = axial * ux * uz, hyy = scale + axial * uy * uy, hyz = axial * uy * uz, hzz = scale + axial * uz * uz;
      const qx = direction[ia * 3], qy = direction[ia * 3 + 1], qz = direction[ia * 3 + 2], factor = dt * dt * invMass[ia];
      out[ia * 3] += factor * (hxx * qx + hxy * qy + hxz * qz); out[ia * 3 + 1] += factor * (hxy * qx + hyy * qy + hyz * qz); out[ia * 3 + 2] += factor * (hxz * qx + hyz * qy + hzz * qz);
    }
    for (let i = 0; i < vertexCount; i++) { const factor = dt * damping * invMass[i]; out[i * 3] += factor * direction[i * 3]; out[i * 3 + 1] += factor * direction[i * 3 + 1]; out[i * 3 + 2] += factor * direction[i * 3 + 2]; }
    if (pin && !pin.hard) {
      const pinFactor = dt * dt * pin.kp + dt * pin.kd, weightedValues = [0, 0, 0];
      for (let j = 0; j < 3; j++) { const id = pin.ids[j], w = pin.weights[j], scale = weighted ? inverseMassRoot[id] : 1; weightedValues[0] += w * direction[id * 3] * scale; weightedValues[1] += w * direction[id * 3 + 1] * scale; weightedValues[2] += w * direction[id * 3 + 2] * scale; }
      for (let j = 0; j < 3; j++) { const id = pin.ids[j], factor = pin.weights[j] * (weighted ? inverseMassRoot[id] : invMass[id]) * pinFactor; out[id * 3] += factor * weightedValues[0]; out[id * 3 + 1] += factor * weightedValues[1]; out[id * 3 + 2] += factor * weightedValues[2]; }
    }
    if (weighted && regularizationShift) for (let i = 0; i < scratchLength; i++) out[i] += regularizationShift * direction[i];
    return out;
  }

  function buildImplicitPreconditioner(dt, regularizationShift = 0, weighted = false) {
    for (let i = 0; i < vertexCount; i++) {
      let pinK = 0, pinD = 0;
      if (pin && !pin.hard) for (let j = 0; j < 3; j++) if (pin.ids[j] === i) { pinK += pin.kp * pin.weights[j] * pin.weights[j]; pinD += pin.kd * pin.weights[j] * pin.weights[j]; }
      const value = 1 + dt * invMass[i] * (damping + pinD) + dt * dt * invMass[i] * (diagonalK[i] + pinK) + (weighted ? regularizationShift : 0);
      implicitPreconditioner[i * 3] = value; implicitPreconditioner[i * 3 + 1] = value; implicitPreconditioner[i * 3 + 2] = value;
    }
  }

  function solveImplicitLinearSystem(x, dt, rhs, out) {
    out.fill(0); let rhsNorm = 0;
    for (let i = 0; i < scratchLength; i++) { implicitCgWeightedRhs[i] = rhs[i] * massRoot[Math.floor(i / 3)]; rhsNorm = Math.max(rhsNorm, Math.abs(implicitCgWeightedRhs[i])); }
    const shifts = [0]; for (let shift = 1e-8; shift <= 1e6; shift *= 100) shifts.push(shift);
    let totalIterations = 0, last = { converged: false, negativeCurvature: false, residualNorm: Infinity, shift: 0, status: 'not-run' };
    for (const shift of shifts) {
      buildImplicitPreconditioner(dt, shift, true); implicitCgResidual.set(implicitCgWeightedRhs); let residualNorm = 0;
      for (let i = 0; i < scratchLength; i++) residualNorm = Math.max(residualNorm, Math.abs(implicitCgResidual[i]));
      const tolerance = Math.max(rhsNorm * 1e-7, state.faceScale * Math.sqrt(Math.max(medianMass, 1e-30)) * 1e-12), z = implicitCgPreconditioned, p = implicitCgDirection, ap = implicitCgProduct;
      for (let i = 0; i < scratchLength; i++) z[i] = implicitCgResidual[i] / Math.max(implicitPreconditioner[i], 1e-30);
      p.set(z); let rz = 0; for (let i = 0; i < scratchLength; i++) rz += implicitCgResidual[i] * z[i];
      let iterations = 0, negativeCurvature = false, converged = residualNorm <= tolerance;
      for (; iterations < implicitCgIterations && !converged; iterations++) {
        applyImplicitJacobian(x, p, dt, ap, true, shift); let denominator = 0; for (let i = 0; i < scratchLength; i++) denominator += p[i] * ap[i];
        if (!(denominator > Math.max(1e-30, Math.abs(rz) * 1e-14)) || !Number.isFinite(denominator)) { negativeCurvature = true; break; }
        const alpha = rz / denominator; for (let i = 0; i < scratchLength; i++) { out[i] += alpha * p[i]; implicitCgResidual[i] -= alpha * ap[i]; }
        residualNorm = 0; for (let i = 0; i < scratchLength; i++) residualNorm = Math.max(residualNorm, Math.abs(implicitCgResidual[i]));
        converged = residualNorm <= tolerance;
        if (converged) { iterations++; break; }
        for (let i = 0; i < scratchLength; i++) z[i] = implicitCgResidual[i] / Math.max(implicitPreconditioner[i], 1e-30);
        let nextRz = 0; for (let i = 0; i < scratchLength; i++) nextRz += implicitCgResidual[i] * z[i];
        const beta = nextRz / Math.max(rz, 1e-30); for (let i = 0; i < scratchLength; i++) p[i] = z[i] + beta * p[i]; rz = nextRz;
      }
      totalIterations += iterations; last = { converged, negativeCurvature, residualNorm, shift, status: converged ? 'converged' : negativeCurvature ? 'negative-curvature' : 'max-iterations' };
      if (converged) { for (let i = 0; i < scratchLength; i++) out[i] *= inverseMassRoot[Math.floor(i / 3)]; return { iterations: totalIterations, ...last }; }
      out.fill(0);
    }
    return { iterations: totalIterations, ...last };
  }

  function integrateImplicitOne(dt) {
    const base = implicitCandidate;
    for (let i = 0; i < scratchLength; i++) base[i] = positions[i] + velocities[i] * dt;
    buildImplicitPreconditioner(dt);
    const correctionTolerance = Math.max(state.faceScale * 1e-8, 1e-10), residualTolerance = Math.max(state.faceScale * 1e-7, 1e-9);
    const residualHistory = [], trial = new Float64Array(scratchLength), rhs = new Float64Array(scratchLength);
    let finalCorrection = 0, linearIterations = 0, status = 'maxIterations', currentResidual = implicitResidualAt(base, dt, implicitResidual), linearStatus = 'idle', negativeCurvatureEvents = 0, regularizationHistory = [], weightedCgResidual = 0;
    for (let iteration = 0; iteration < implicitNewtonIterations; iteration++) {
      residualHistory.push(currentResidual);
      if (currentResidual <= residualTolerance) { status = 'converged'; break; }
      for (let i = 0; i < scratchLength; i++) rhs[i] = -implicitResidual[i];
      const linear = solveImplicitLinearSystem(base, dt, rhs, implicitNewtonDelta);
      linearIterations += linear.iterations; linearStatus = linear.status; weightedCgResidual = linear.residualNorm; regularizationHistory.push(linear.shift); if (linear.negativeCurvature) negativeCurvatureEvents++;
      if (!linear.converged) { status = linear.negativeCurvature ? 'negative-curvature' : 'linear-max-iterations'; break; }
      let accepted = false, alpha = 1;
      while (alpha >= implicitLineSearchMin) {
        for (let i = 0; i < scratchLength; i++) trial[i] = base[i] + alpha * implicitNewtonDelta[i];
        if (pin?.hard) { for (let i = 0; i < scratchLength; i++) implicitVelocity[i] = (trial[i] - positions[i]) / dt; projectConstraint(trial, implicitVelocity, pin); }
        const trialResidual = implicitResidualAt(trial, dt, implicitTrialResidual);
        if (trialResidual < currentResidual * (1 - 1e-8) || trialResidual <= residualTolerance) {
          finalCorrection = 0; for (let i = 0; i < scratchLength; i++) { const correction = Math.abs(trial[i] - base[i]); finalCorrection = Math.max(finalCorrection, correction); base[i] = trial[i]; }
          implicitResidual.set(implicitTrialResidual); currentResidual = trialResidual; accepted = true; break;
        }
        alpha *= 0.5;
      }
      if (!accepted) { status = 'stagnated'; break; }
      if (finalCorrection <= correctionTolerance && currentResidual <= residualTolerance) { status = 'converged'; break; }
    }
    for (let i = 0; i < scratchLength; i++) implicitVelocity[i] = (base[i] - positions[i]) / dt;
    if (pin?.hard) projectConstraint(base, implicitVelocity, pin);
    for (let i = 0; i < scratchLength; i++) implicitVelocity[i] = (base[i] - positions[i]) / dt;
    const equationResidual = implicitResidualAt(base, dt, implicitTrialResidual) / Math.max(dt, 1e-12);
    let positionVelocityResidual = 0; for (let i = 0; i < scratchLength; i++) positionVelocityResidual = Math.max(positionVelocityResidual, Math.abs(base[i] - positions[i] - dt * implicitVelocity[i]));
    if (equationResidual <= residualTolerance / Math.max(dt, 1e-12)) status = 'converged';
    implicitDiagnostics = { iterations: residualHistory.length, linearIterations, finalCorrection, equationResidual, positionVelocityResidual, converged: status === 'converged', status, correctionTolerance, residualTolerance, residualHistory, linearStatus, negativeCurvatureEvents, regularizationHistory, weightedCgResidual };
    positions.set(base); velocities.set(implicitVelocity); if (pin?.hard) projectConstraint(positions, velocities, pin);
    for (const value of positions) if (!Number.isFinite(value)) throw new Error('Implicit solve produced nonfinite positions');
    for (const value of velocities) if (!Number.isFinite(value)) throw new Error('Implicit solve produced nonfinite velocities');
  }

  function integrate(dt) {
    // The neutral state is an exact zero-force equilibrium. Keep the requested
    // RK4 step count observable while avoiding four full force allocations for
    // a state whose derivative is analytically zero.
    if (neutralSettled && !pin && innerEnabled) return;
    if (integrator === 'implicit') { integrateImplicitOne(dt); return; }
    const substeps = Math.max(1, Math.ceil(dt / Math.max(stableDt, 1e-7)));
    const h = dt / substeps;
    for (let i = 0; i < substeps; i++) integrateOne(h);
  }

  function energyBreakdown() {
    let surfacePotential = 0, innerPotential = 0, gravityPotential = 0, kinetic = 0;
    for (let i = 0; i < edgeA.length; i++) { const ia = edgeA[i], ib = edgeB[i], length = Math.hypot(positions[ib * 3] - positions[ia * 3], positions[ib * 3 + 1] - positions[ia * 3 + 1], positions[ib * 3 + 2] - positions[ia * 3 + 2]); const extension = (length - edgeInfo.rest[i]) * sourceMetersPerUnit; surfacePotential += 0.5 * surfaceK * extension * extension; }
    if (innerEnabled) for (let i = 0; i < supportAArray.length; i++) { const ia = supportAArray[i], ib = supportBArray[i], length = Math.hypot(anchors[ib * 3] - positions[ia * 3], anchors[ib * 3 + 1] - positions[ia * 3 + 1], anchors[ib * 3 + 2] - positions[ia * 3 + 2]); const extension = (length - supportRestArray[i]) * sourceMetersPerUnit; innerPotential += 0.5 * supportKArray[i] * extension * extension; }
    for (let i = 0; i < vertexCount; i++) {
      const speedM = Math.hypot(velocities[i * 3], velocities[i * 3 + 1], velocities[i * 3 + 2]) * sourceMetersPerUnit; kinetic += 0.5 * masses[i] * speedM * speedM;
      const displacement = new THREE.Vector3(positions[i * 3] - neutral[i * 3], positions[i * 3 + 1] - neutral[i * 3 + 1], positions[i * 3 + 2] - neutral[i * 3 + 2]); gravityPotential -= masses[i] * state.gravity.dot(displacement) * sourceMetersPerUnit;
    }
    return { surfacePotential, innerPotential, gravityPotential, kinetic, total: surfacePotential + innerPotential + gravityPotential + kinetic };
  }
  function energy() { const values = energyBreakdown(); return values.surfacePotential + values.innerPotential + values.gravityPotential; }

  function vertexForce(localId, x = positions, withInner = innerEnabled) {
    let fx = 0, fy = 0, fz = 0;
    for (let i = 0; i < edgeA.length; i++) {
      const ia = edgeA[i], ib = edgeB[i];
      if (ia !== localId && ib !== localId) continue;
      const dx = x[ib * 3] - x[ia * 3], dy = x[ib * 3 + 1] - x[ia * 3 + 1], dz = x[ib * 3 + 2] - x[ia * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const q = surfaceK * ((length - edgeInfo.rest[i]) * sourceMetersPerUnit) / length;
      const sign = ia === localId ? 1 : -1;
      fx += sign * q * dx; fy += sign * q * dy; fz += sign * q * dz;
    }
    if (withInner) for (let i = 0; i < supportAArray.length; i++) if (supportAArray[i] === localId) {
      const dx = anchors[supportBArray[i] * 3] - x[localId * 3], dy = anchors[supportBArray[i] * 3 + 1] - x[localId * 3 + 1], dz = anchors[supportBArray[i] * 3 + 2] - x[localId * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const q = supportKArray[i] * ((length - supportRestArray[i]) * sourceMetersPerUnit) / length;
      fx += q * dx; fy += q * dy; fz += q * dz;
    }
    return new THREE.Vector3(fx, fy, fz);
  }

  function diagnostics() {
    let maxDisplacement = 0, maxStrain = 0;
    const energies = energyBreakdown();
    for (let i = 0; i < vertexCount; i++) maxDisplacement = Math.max(maxDisplacement, Math.hypot(positions[i * 3] - neutral[i * 3], positions[i * 3 + 1] - neutral[i * 3 + 1], positions[i * 3 + 2] - neutral[i * 3 + 2]));
    for (let i = 0; i < edgeA.length; i++) { const length = Math.hypot(positions[edgeB[i] * 3] - positions[edgeA[i] * 3], positions[edgeB[i] * 3 + 1] - positions[edgeA[i] * 3 + 1], positions[edgeB[i] * 3 + 2] - positions[edgeA[i] * 3 + 2]); maxStrain = Math.max(maxStrain, Math.abs(length - edgeInfo.rest[i]) / Math.max(edgeInfo.rest[i], 1e-12)); }
    const minPositiveMass = positiveMasses[0] || 0, maxPositiveMass = positiveMasses[positiveMasses.length - 1] || 0;
    const totalMassKg = masses.reduce((sum, value) => sum + value, 0);
    return {
      vertices: vertexCount, triangles: island.faces.length, surfaceSprings: edgeA.length, duplicateRawEdges: edgeInfo.duplicateRawEdges,
      zeroLengthEdges: edgeInfo.zeroLengthEdges, interIslandSprings: 0, supportSprings: supportAArray.length,
      anchorDepthFactor: depthFactor, anchorDepthMedian: medianEdge, dt: 1 / 600, stableDt, maxDegree, maxLocalStiffness, damping,
      kSurface: surfaceK, kSurfaceBiological: biologicalSurfaceK, kInnerRatio: innerK / Math.max(surfaceK, 1e-18),
      preset: preset.name, sourceMetersPerUnit, rhoEffective: preset.rhoEffective, thicknessMeters: preset.thicknessMeters, massScale: preset.massScale,
      surfaceModulusPa: preset.surfaceModulusPa, innerModulusPa: preset.innerModulusPa, compliantThicknessMeters: preset.compliantThicknessMeters,
      totalAreaM2, totalMassKg, minPositiveMassKg: minPositiveMass, medianMassKg: medianMass, maxPositiveMassKg: maxPositiveMass,
      minPositiveMassMg: minPositiveMass * 1e6, medianMassMg: medianMass * 1e6, maxPositiveMassMg: maxPositiveMass * 1e6,
      zeroMassVertexCount, degenerateFaceCount, areaConservationError: Math.abs(attributedArea.reduce((sum, value) => sum + value, 0) - totalAreaM2),
      numericalMassFloorKg: numericalMassFloor, highestEstimatedNaturalFrequencyHz: Math.sqrt(surfaceK * (maxDegree + neighborCount + 1) / Math.max(minMass, 1e-18)) / (2 * Math.PI),
      integrator, requestedIntegrator, explicitSubstepsPerFrame, implicitNewtonIterations, implicitCgIterations, implicitLineSearchMin,
      substepsPerRenderedFrame: integrator === 'implicit' ? 1 : explicitSubstepsPerFrame,
      energy: energies.total, energyBreakdown: energies, maxDisplacement, maxStrain, finite: true, orientationSign, implicit: { ...implicitDiagnostics },
      faceScaleSourceUnits: state.faceScale, faceScaleMeters: state.faceScale * sourceMetersPerUnit, sourceMetersPerUnit,
      gravityMS2: state.gravity.toArray(), performance: { ...state.performance, averagePhysicsMs: state.performance.physicsSteps ? state.performance.physicsMs / state.performance.physicsSteps : 0, averageFrameMs: state.performance.frames ? state.performance.wallMs / state.performance.frames : 0, simulatedSeconds: state.performance.simTime },
    };
  }

  function geometryDiagnostics() {
    let minAreaRatio = Infinity, minAreaFace = -1, collapsedTriangles = 0, orientationFlips = 0, nonfiniteVertices = 0;
    const orientationFlipDetails = [];
    const strains = new Array(edgeA.length);
    let maxEdgeStrain = 0, maxEdgeIndex = -1, boundaryMaxDisplacement = 0;
    const boundaryVertices = new Set();
    for (let i = 0; i < edgeInfo.boundaryA.length; i++) { const a = localMap.get(edgeInfo.boundaryA[i]), b = localMap.get(edgeInfo.boundaryB[i]); if (a !== undefined) boundaryVertices.add(a); if (b !== undefined) boundaryVertices.add(b); }
    for (let i = 0; i < vertexCount; i++) {
      const dx = positions[i * 3] - neutral[i * 3], dy = positions[i * 3 + 1] - neutral[i * 3 + 1], dz = positions[i * 3 + 2] - neutral[i * 3 + 2];
      if (!Number.isFinite(dx) || !Number.isFinite(dy) || !Number.isFinite(dz)) nonfiniteVertices++;
      if (boundaryVertices.has(i)) boundaryMaxDisplacement = Math.max(boundaryMaxDisplacement, Math.hypot(dx, dy, dz));
    }
    for (let i = 0; i < edgeA.length; i++) {
      const length = Math.hypot(positions[edgeB[i] * 3] - positions[edgeA[i] * 3], positions[edgeB[i] * 3 + 1] - positions[edgeA[i] * 3 + 1], positions[edgeB[i] * 3 + 2] - positions[edgeA[i] * 3 + 2]);
      const strain = Math.abs(length - edgeInfo.rest[i]) / Math.max(edgeInfo.rest[i], 1e-12); strains[i] = strain;
      if (strain > maxEdgeStrain) { maxEdgeStrain = strain; maxEdgeIndex = i; }
    }
    strains.sort((a, b) => a - b);
    for (let fi = 0; fi < island.faces.length; fi++) {
      const ia = localFaceVertices[fi * 3], ib = localFaceVertices[fi * 3 + 1], ic = localFaceVertices[fi * 3 + 2];
      const ax = positions[ia * 3], ay = positions[ia * 3 + 1], az = positions[ia * 3 + 2];
      const abx = positions[ib * 3] - ax, aby = positions[ib * 3 + 1] - ay, abz = positions[ib * 3 + 2] - az;
      const acx = positions[ic * 3] - ax, acy = positions[ic * 3 + 1] - ay, acz = positions[ic * 3 + 2] - az;
      const nx = aby * acz - abz * acy, ny = abz * acx - abx * acz, nz = abx * acy - aby * acx, area2 = Math.hypot(nx, ny, nz), ratio = area2 / Math.max(neutralFaceAreas[fi] * 2, 1e-20);
      if (ratio < minAreaRatio) { minAreaRatio = ratio; minAreaFace = island.faces[fi]; }
      if (ratio <= 1e-3) collapsedTriangles++;
      const neutralDot = (nx * neutralFaceNormals[fi * 3] + ny * neutralFaceNormals[fi * 3 + 1] + nz * neutralFaceNormals[fi * 3 + 2]) / Math.max(area2, 1e-20);
      if (neutralDot < 0) {
        orientationFlips++;
        const originalVertexIds = [island.vertices[ia], island.vertices[ib], island.vertices[ic]];
        const currentVertices = [[ax, ay, az], [positions[ib * 3], positions[ib * 3 + 1], positions[ib * 3 + 2]], [positions[ic * 3], positions[ic * 3 + 1], positions[ic * 3 + 2]]];
        const neutralVertices = [[neutral[ia * 3], neutral[ia * 3 + 1], neutral[ia * 3 + 2]], [neutral[ib * 3], neutral[ib * 3 + 1], neutral[ib * 3 + 2]], [neutral[ic * 3], neutral[ic * 3 + 1], neutral[ic * 3 + 2]]];
        const neighborFaces = faceNeighbors[fi].map(neighbor => {
          const na = localFaceVertices[neighbor * 3], nb = localFaceVertices[neighbor * 3 + 1], nc = localFaceVertices[neighbor * 3 + 2];
          const nx0 = positions[nb * 3] - positions[na * 3], ny0 = positions[nb * 3 + 1] - positions[na * 3 + 1], nz0 = positions[nb * 3 + 2] - positions[na * 3 + 2];
          const nx1 = positions[nc * 3] - positions[na * 3], ny1 = positions[nc * 3 + 1] - positions[na * 3 + 1], nz1 = positions[nc * 3 + 2] - positions[na * 3 + 2];
          const nnx = ny0 * nz1 - nz0 * ny1, nny = nz0 * nx1 - nx0 * nz1, nnz = nx0 * ny1 - ny0 * nx1, narea2 = Math.hypot(nnx, nny, nnz);
          const neutralArea = neutralFaceAreas[neighbor];
          return { faceId: island.faces[neighbor], area: narea2 * 0.5, areaRatio: narea2 / Math.max(neutralArea * 2, 1e-20), normalDotNeutral: (nnx * neutralFaceNormals[neighbor * 3] + nny * neutralFaceNormals[neighbor * 3 + 1] + nnz * neutralFaceNormals[neighbor * 3 + 2]) / Math.max(narea2, 1e-20) };
        });
        orientationFlipDetails.push({ faceId: island.faces[fi], originalVertexIds, neutralVertices, currentVertices, neutralArea: neutralFaceAreas[fi], deformedArea: area2 * 0.5, areaRatio: ratio, normalDotNeutral: neutralDot, neighboringFaces: neighborFaces });
      }
    }
    return { boundaryEdgeCount: edgeInfo.boundaryEdgeCount, boundaryVertexCount: boundaryVertices.size, boundaryMaxDisplacement, boundaryMaxDisplacementPctFaceScale: boundaryMaxDisplacement / Math.max(state.faceScale, 1e-12), maxEdgeStrain, p95EdgeStrain: strains[Math.max(0, Math.floor(strains.length * 0.95) - 1)] || 0, maxEdgeIndex, minAreaRatio: Number.isFinite(minAreaRatio) ? minAreaRatio : null, minAreaFace, collapsedTriangles, orientationFlips, orientationFlipDetails, nonfiniteVertices, valid: nonfiniteVertices === 0 && collapsedTriangles === 0 && orientationFlips === 0 };
  }

  function update() { const attr = geometry.attributes.position; for (let i = 0; i < vertexCount; i++) attr.setXYZ(island.vertices[i], positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]); attr.needsUpdate = true; if (state.springLines) updateLinePositions(); if (state.massHeatmap) updateMassHeatmapPositions(); updatePinVisuals(); }
  state.spring = { edgeInfo, edgeA, edgeB, supportA: supportAArray, supportB: supportBArray, supportRest: supportRestArray, supportK: supportKArray, positions, velocities, neutral, anchors, masses, attributedArea, vertexCount, invMass, sourceMetersPerUnit, step: integrate, energy, diagnostics, geometryDiagnostics, vertexForce, setPin: value => { pin = value; neutralSettled = false; }, clearPin: () => { pin = null; }, setInner: value => { innerEnabled = value; neutralSettled = false; }, getInner: () => innerEnabled, markActive: () => { neutralSettled = false; }, markNeutral: () => { neutralSettled = true; }, update };
  buildDiagnosticsVisuals(); update(); syncGpuBackend();
}

function buildDiagnosticsVisuals() {
  removeDiagnostics();
  const selection = activeData(); if (!selection || !state.spring) return;
  const spring = state.spring, density = Math.max(1, Number(ui.wireDensity.value));
  const springGeometry = new THREE.BufferGeometry(); springGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Math.ceil(spring.edgeA.length / density) * 6), 3));
  state.springLines = new THREE.LineSegments(springGeometry, new THREE.LineBasicMaterial({ color: 0x8af1d1, transparent: true, opacity: 0.72 })); scene.add(state.springLines);
  const strainGeometry = new THREE.BufferGeometry();
  strainGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Math.ceil(spring.edgeA.length / density) * 6), 3));
  strainGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(Math.ceil(spring.edgeA.length / density) * 6), 3));
  state.strainLines = new THREE.LineSegments(strainGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.92 })); scene.add(state.strainLines);
  const innerGeometry = new THREE.BufferGeometry(); innerGeometry.setAttribute('position', new THREE.BufferAttribute(spring.anchors.slice(), 3));
  state.innerPoints = new THREE.Points(innerGeometry, new THREE.PointsMaterial({ color: 0xff9b4a, size: state.faceScale * 0.006, sizeAttenuation: true, transparent: true, opacity: 0.9 })); scene.add(state.innerPoints);
  const tetherGeometry = new THREE.BufferGeometry(); tetherGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Math.ceil(spring.supportA.length / density) * 6), 3));
  state.innerLines = new THREE.LineSegments(tetherGeometry, new THREE.LineBasicMaterial({ color: 0xff9b4a, transparent: true, opacity: 0.55 })); scene.add(state.innerLines);
  buildMassHeatmap(); updateLinePositions(); updateVisuals();
}

function massColor(value, minValue, maxValue) {
  const lo = Math.log(Math.max(minValue, 1e-18)), hi = Math.log(Math.max(maxValue, minValue * 1.000001));
  const t = Math.max(0, Math.min(1, (Math.log(Math.max(value, minValue)) - lo) / Math.max(hi - lo, 1e-9)));
  return new THREE.Color().setHSL(0.68 - 0.68 * t, 0.9, 0.52);
}

function buildMassHeatmap() {
  if (state.massHeatmap) { disposeObject(state.massHeatmap); state.massHeatmap = null; }
  const selection = activeData();
  if (!selection || !state.spring) return;
  const { entry, island } = selection, index = entry.geometry.index.array, position = entry.geometry.attributes.position;
  const localMap = new Map(island.vertices.map((vertex, i) => [vertex, i]));
  const positive = Array.from(state.spring.masses).filter(value => value > 0 && Number.isFinite(value));
  const minValue = Math.min(...positive), maxValue = Math.max(...positive);
  const points = [], colors = [], refs = [];
  const color = new THREE.Color();
  for (const face of island.faces) {
    for (let corner = 0; corner < 3; corner++) {
      const global = index[face * 3 + corner], local = localMap.get(global);
      points.push(position.getX(global), position.getY(global), position.getZ(global));
      color.copy(massColor(state.spring.masses[local], minValue, maxValue)); colors.push(color.r, color.g, color.b); refs.push(global);
    }
  }
  const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3)); geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.68, depthWrite: false, side: THREE.DoubleSide }));
  mesh.renderOrder = 4; mesh.visible = ui.showMass.checked; mesh.userData.refs = refs; state.massHeatmap = mesh; scene.add(mesh);
}

function updateMassHeatmapPositions() {
  if (!state.massHeatmap || !state.selected) return;
  const attr = state.massHeatmap.geometry.attributes.position, position = state.selected.entry.geometry.attributes.position;
  for (let i = 0; i < state.massHeatmap.userData.refs.length; i++) { const global = state.massHeatmap.userData.refs[i]; attr.setXYZ(i, position.getX(global), position.getY(global), position.getZ(global)); }
  attr.needsUpdate = true;
}

function updatePinVisuals() {
  if (!state.pin || !state.selected || !state.spring) return;
  const pin = state.pin, positions = state.spring.positions, actual = new THREE.Vector3();
  for (let j = 0; j < 3; j++) { actual.x += pin.weights[j] * positions[pin.ids[j] * 3]; actual.y += pin.weights[j] * positions[pin.ids[j] * 3 + 1]; actual.z += pin.weights[j] * positions[pin.ids[j] * 3 + 2]; }
  const worldActual = actual.clone().applyMatrix4(state.selected.entry.mesh.matrixWorld), worldTarget = pin.target.clone().applyMatrix4(state.selected.entry.mesh.matrixWorld);
  if (!state.pinMarker) {
    const r = state.faceScale * 0.012;
    state.pinMarker = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8), new THREE.MeshBasicMaterial({ color: 0x46ffb4 }));
    state.targetMarker = new THREE.Mesh(new THREE.SphereGeometry(r * 0.72, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff4bbd }));
    const lineGeometry = new THREE.BufferGeometry(); lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
    state.forceLine = new THREE.Line(lineGeometry, new THREE.LineBasicMaterial({ color: 0xffd34e, linewidth: 2 }));
    scene.add(state.pinMarker, state.targetMarker, state.forceLine);
  }
  state.pinMarker.position.copy(worldActual); state.targetMarker.position.copy(worldTarget);
  const line = state.forceLine.geometry.attributes.position.array, force = pin.currentForce || new THREE.Vector3();
  line[0] = worldActual.x; line[1] = worldActual.y; line[2] = worldActual.z;
  const visualForceScale = state.faceScale * 0.18 / Math.max(pin.peakForce || Math.hypot(force.x, force.y, force.z), 1e-9);
  line[3] = worldActual.x + force.x * visualForceScale; line[4] = worldActual.y + force.y * visualForceScale; line[5] = worldActual.z + force.z * visualForceScale; state.forceLine.geometry.attributes.position.needsUpdate = true;
}

function updateLinePositions() {
  const selection = activeData(); if (!selection || !state.spring) return;
  const spring = state.spring, position = selection.entry.geometry.attributes.position, density = Math.max(1, Number(ui.wireDensity.value));
  const line = state.springLines.geometry.attributes.position.array; let cursor = 0;
  for (let i = 0; i < spring.edgeA.length; i += density) { for (const [offset, local] of [[0, spring.edgeA[i]], [3, spring.edgeB[i]]]) { const global = selection.island.vertices[local]; line[cursor + offset] = position.getX(global); line[cursor + offset + 1] = position.getY(global); line[cursor + offset + 2] = position.getZ(global); } cursor += 6; }
  state.springLines.geometry.attributes.position.needsUpdate = true;
  const strainPosition = state.strainLines.geometry.attributes.position.array;
  const strainColor = state.strainLines.geometry.attributes.color.array;
  const strainColorValue = new THREE.Color();
  cursor = 0;
  for (let i = 0; i < spring.edgeA.length; i += density) {
    const localA = spring.edgeA[i], localB = spring.edgeB[i], globalA = selection.island.vertices[localA], globalB = selection.island.vertices[localB];
    const ax = position.getX(globalA), ay = position.getY(globalA), az = position.getZ(globalA), bx = position.getX(globalB), by = position.getY(globalB), bz = position.getZ(globalB);
    strainPosition[cursor] = ax; strainPosition[cursor + 1] = ay; strainPosition[cursor + 2] = az; strainPosition[cursor + 3] = bx; strainPosition[cursor + 4] = by; strainPosition[cursor + 5] = bz;
    const currentLength = Math.hypot(bx - ax, by - ay, bz - az), strain = Math.abs(currentLength - spring.edgeInfo.rest[i]) / Math.max(spring.edgeInfo.rest[i], 1e-12);
    strainColorValue.setHSL(Math.max(0, 0.62 - Math.min(1, strain * 8) * 0.62), 0.95, 0.55);
    for (let k = 0; k < 2; k++) { strainColor[cursor + k * 3] = strainColorValue.r; strainColor[cursor + k * 3 + 1] = strainColorValue.g; strainColor[cursor + k * 3 + 2] = strainColorValue.b; }
    cursor += 6;
  }
  state.strainLines.geometry.attributes.position.needsUpdate = true; state.strainLines.geometry.attributes.color.needsUpdate = true;
  state.innerPoints.geometry.attributes.position.array.set(spring.anchors); state.innerPoints.geometry.attributes.position.needsUpdate = true;
  const tether = state.innerLines.geometry.attributes.position.array; cursor = 0;
  for (let i = 0; i < spring.supportA.length; i += density) { const localA = spring.supportA[i], localB = spring.supportB[i], globalA = selection.island.vertices[localA]; tether[cursor] = position.getX(globalA); tether[cursor + 1] = position.getY(globalA); tether[cursor + 2] = position.getZ(globalA); tether[cursor + 3] = spring.anchors[localB * 3]; tether[cursor + 4] = spring.anchors[localB * 3 + 1]; tether[cursor + 5] = spring.anchors[localB * 3 + 2]; cursor += 6; }
  state.innerLines.geometry.attributes.position.needsUpdate = true;
}

function updateVisuals() { if (state.overlay) state.overlay.visible = ui.showIslands.checked; if (state.springLines) state.springLines.visible = ui.showSprings.checked; if (state.strainLines) state.strainLines.visible = ui.showStrain.checked; if (state.massHeatmap) state.massHeatmap.visible = ui.showMass.checked; if (state.innerLines) state.innerLines.visible = ui.showInner.checked; if (state.innerPoints) state.innerPoints.visible = ui.showInner.checked; for (const entry of state.entries) entry.mesh.visible = ui.showOriginal.checked; }

function updateMetrics(extra = '') {
  const selection = activeData(); if (!selection) { ui.metrics.textContent = 'Loading original GLB…'; return; }
  const totals = state.entries.reduce((acc, entry) => { acc.vertices += entry.geometry.attributes.position.count; acc.triangles += entry.index.length / 3; acc.islands += entry.islands.length; return acc; }, { vertices: 0, triangles: 0, islands: 0 });
  const d = state.spring ? state.spring.diagnostics() : null;
  const backend = state.gpu.connected ? 'GPU Warp server' : 'CPU JavaScript';
  const backendDetail = state.gpu.error ? `\nGPU note: ${state.gpu.error}` : '';
  ui.metrics.textContent = `${state.model.toUpperCase()}\nBackend: ${backend}${backendDetail}\nOriginal vertices: ${totals.vertices.toLocaleString()}   triangles: ${totals.triangles.toLocaleString()}   islands: ${totals.islands}\nSelected: ${selection.entry.mesh.name} / island ${selection.island.id}\nIsland vertices: ${selection.island.vertices.length.toLocaleString()}   triangles: ${selection.island.faces.length.toLocaleString()}\n${d ? `Unique surface springs: ${d.surfaceSprings.toLocaleString()}\nDuplicate raw triangle edges removed: ${d.duplicateRawEdges.toLocaleString()}\nZero-length edges: ${d.zeroLengthEdges}\nInter-island springs: 0\nSupport springs: ${d.supportSprings.toLocaleString()}\nPreset: ${d.preset}   mass scale: ${d.massScale.toExponential(2)}   scale: ${d.sourceMetersPerUnit} m/source unit\nArea: ${d.totalAreaM2.toExponential(4)} m²   mass: ${(d.totalMassKg * 1000).toFixed(4)} g\nMass min/median/max: ${d.minPositiveMassMg.toExponential(3)} / ${d.medianMassMg.toExponential(3)} / ${d.maxPositiveMassMg.toExponential(3)} mg\nZero-mass vertices: ${d.zeroMassVertexCount}   area error: ${d.areaConservationError.toExponential(2)} m²\nρ: ${d.rhoEffective} kg/m³   thickness: ${(d.thicknessMeters * 1000).toFixed(2)} mm\nRK4 dt: ${d.dt.toExponential(3)}   stable dt: ${d.stableDt.toExponential(3)}   substeps/frame: ${d.explicitSubstepsPerFrame}\nGravity: ${d.gravityMS2.map(value => value.toFixed(2)).join(', ')} m/s²   damping: ${d.damping.toExponential(3)}\nEnergy: ${d.energy.toExponential(4)}   max displacement: ${d.maxDisplacement.toExponential(4)}\nMax edge strain: ${d.maxStrain.toFixed(4)}\nPhysics: ${d.performance.averagePhysicsMs.toFixed(2)} ms/step   frame: ${d.performance.averageFrameMs.toFixed(2)} ms   sim/wall: ${d.performance.simulatedSeconds.toFixed(3)} s\nFinite integrator: ${d.finite ? 'YES' : 'NO'}` : 'Springs not initialized'}${extra ? `\n\n${extra}` : ''}`;
}

function populateIslands() {
  ui.island.innerHTML = '';
  for (const entry of state.entries) for (const island of entry.islands) { const option = document.createElement('option'); option.value = `${entry.mesh.uuid}:${island.id}`; option.textContent = `${entry.mesh.name} · island ${island.id} · ${island.vertices.length}v / ${island.faces.length}f`; ui.island.append(option); }
  const browPoints = [70, 63, 105, 336, 293, 334].map(id => state.attachments?.[id]).filter(Boolean);
  const candidates = state.entries.flatMap(entry => entry.islands.map(island => ({ entry, island })));
  const faceCandidate = candidates.sort((a, b) => {
    const score = item => browPoints.reduce((sum, point) => sum + item.island.bounds.distanceToPoint(point), 0);
    return score(a) - score(b);
  })[0];
  if (faceCandidate) { state.selected = { entry: faceCandidate.entry, island: faceCandidate.island }; ui.island.value = `${faceCandidate.entry.mesh.uuid}:${faceCandidate.island.id}`; buildSystem(); }
}

function setStage(stage) { state.stage = stage; document.querySelectorAll('.tab').forEach(button => button.classList.toggle('active', Number(button.dataset.stage) === stage)); ui.stageText.textContent = STAGE_TEXT[stage]; updateVisuals(); updateMetrics(); }
function resetNeutral() { if (!state.spring) return; state.spring.positions.set(state.spring.neutral); state.spring.velocities.fill(0); state.spring.clearPin(); state.pin = null; state.spring.markNeutral(); state.spring.update(); gpuSend({ type: 'reset' }); state.lastPinch = null; controls.enabled = state.interactionMode === 'explore'; updateMetrics('Neutral reset'); }

async function runTest(kind) {
  if (!state.spring) return;
  resetNeutral(); const spring = state.spring, dt = 1 / 600;
  if (kind === 'rest') {
    spring.markActive();
    for (let i = 0; i < 1000; i++) spring.step(dt);
    spring.update(); state.tests.rest = { drift: spring.diagnostics().maxDisplacement, energies: spring.diagnostics().energyBreakdown, energy: spring.energy(), steps: 1000, implicit: spring.diagnostics().implicit };
    updateMetrics(`NEUTRAL REST\n1000 integration steps\nDrift: ${state.tests.rest.drift.toExponential(4)}\nEnergy: ${state.tests.rest.energy.toExponential(4)}`);
  } else if (kind === 'nudge') {
    spring.positions[0] += state.faceScale * 0.001; spring.markActive(); const initialForce = spring.vertexForce(0); const initialAccelerationSource = initialForce.clone().multiplyScalar(spring.invMass[0] / spring.sourceMetersPerUnit); const energies = [spring.energy()];
    const recoverySteps = 30;
    for (let i = 0; i < recoverySteps; i++) { spring.step(dt); if (i === 0 || (i + 1) % 10 === 0) energies.push(spring.energy()); }
    const neighbors = new Set();
    for (let i = 0; i < spring.edgeA.length; i++) { if (spring.edgeA[i] === 0) neighbors.add(spring.edgeB[i]); if (spring.edgeB[i] === 0) neighbors.add(spring.edgeA[i]); }
    let maxNeighborMovement = 0;
    for (const vertex of neighbors) maxNeighborMovement = Math.max(maxNeighborMovement, Math.hypot(spring.positions[vertex * 3] - spring.neutral[vertex * 3], spring.positions[vertex * 3 + 1] - spring.neutral[vertex * 3 + 1], spring.positions[vertex * 3 + 2] - spring.neutral[vertex * 3 + 2]));
    spring.update(); const nudgeDiagnostics = spring.diagnostics(); state.tests.nudge = { initialNudge: state.faceScale * 0.001, recoverySteps, maxDisplacement: nudgeDiagnostics.maxDisplacement, maxNeighborMovement, neighborCount: neighbors.size, energies, energyBreakdown: nudgeDiagnostics.energyBreakdown, initialForceN: initialForce.toArray(), initialAccelerationSourceUnitsPerS2: initialAccelerationSource.toArray(), initialAccelerationMS2: initialAccelerationSource.clone().multiplyScalar(spring.sourceMetersPerUnit).toArray(), energyDecreased: energies.at(-1) < energies[0], restoredTowardNeutral: nudgeDiagnostics.maxDisplacement < state.faceScale * 0.001, finite: nudgeDiagnostics.finite, implicit: nudgeDiagnostics.implicit };
    updateMetrics(`ONE-VERTEX NUDGE\nNudge: ${(state.faceScale * 0.001).toExponential(4)}\nFinal max displacement: ${state.tests.nudge.maxDisplacement.toExponential(4)}\nNeighbor response: ${state.tests.nudge.maxDisplacement > 0 ? 'YES' : 'NO'}\nEnergy samples: ${energies.slice(0, 4).map(value => value.toExponential(2)).join(', ')}`);
  } else {
    const displacement = state.faceScale * 0.001, recoverySteps = 30;
    const runRecovery = innerEnabled => {
      resetNeutral(); spring.setInner(innerEnabled); spring.positions[0] += displacement; spring.markActive();
      const energies = [spring.energy()];
      for (let i = 0; i < recoverySteps; i++) spring.step(dt);
      const diagnostics = spring.diagnostics();
      const neighbors = new Set(); for (let i = 0; i < spring.edgeA.length; i++) { if (spring.edgeA[i] === 0) neighbors.add(spring.edgeB[i]); if (spring.edgeB[i] === 0) neighbors.add(spring.edgeA[i]); }
      let maxNeighborMovement = 0; for (const vertex of neighbors) maxNeighborMovement = Math.max(maxNeighborMovement, Math.hypot(spring.positions[vertex * 3] - spring.neutral[vertex * 3], spring.positions[vertex * 3 + 1] - spring.neutral[vertex * 3 + 1], spring.positions[vertex * 3 + 2] - spring.neutral[vertex * 3 + 2]));
      return { innerSprings: innerEnabled, recoverySteps, maxDisplacement: diagnostics.maxDisplacement, maxNeighborMovement, neighborCount: neighbors.size, initialEnergy: energies[0], finalEnergy: diagnostics.energy, energyBreakdown: diagnostics.energyBreakdown, restoredTowardNeutral: diagnostics.maxDisplacement < displacement, finite: diagnostics.finite, implicit: diagnostics.implicit };
    };
    const withInner = runRecovery(true), withoutInner = runRecovery(false); spring.setInner(true); resetNeutral(); state.tests.noAnchor = { displacement, withInner, withoutInner, comparison: { innerChangesMaxDisplacement: withInner.maxDisplacement - withoutInner.maxDisplacement, innerChangesNeighborMovement: withInner.maxNeighborMovement - withoutInner.maxNeighborMovement } };
    updateMetrics(`NO ANCHOR COMPARISON\nSame nudge: ${displacement.toExponential(4)}\nWith inner max displacement: ${withInner.maxDisplacement.toExponential(4)}\nWithout inner max displacement: ${withoutInner.maxDisplacement.toExponential(4)}\nNeighbor response: ${withInner.maxNeighborMovement.toExponential(4)} / ${withoutInner.maxNeighborMovement.toExponential(4)}`);
  }
}

function barycentric(point, a, b, c) { const v0 = b.clone().sub(a), v1 = c.clone().sub(a), v2 = point.clone().sub(a), d00 = v0.dot(v0), d01 = v0.dot(v1), d11 = v1.dot(v1), d20 = v2.dot(v0), d21 = v2.dot(v1), denominator = d00 * d11 - d01 * d01, v = (d11 * d20 - d01 * d21) / denominator, w = (d00 * d21 - d01 * d20) / denominator; return [1 - v - w, v, w]; }
function pointerHit(event) { const rect = canvas.getBoundingClientRect(); pointer.x = (event.clientX - rect.left) / rect.width * 2 - 1; pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; raycaster.setFromCamera(pointer, camera); return raycaster.intersectObjects(state.meshes, false)[0]; }
function setInteractionMode(mode) {
  if (mode === 'explore' && state.pin && state.spring) { state.spring.clearPin(); gpuSend({ type: 'release' }); state.pin = null; }
  state.interactionMode = mode;
  ui.exploreMode.classList.toggle('active', mode === 'explore');
  ui.pinchMode.classList.toggle('active', mode === 'pinch');
  ui.interactionHint.textContent = mode === 'pinch'
    ? 'Pinch mode: touch the face, drag, then release. Tap Explore to orbit without deforming.'
    : 'Explore mode: touch and drag to orbit. The face will not deform.';
  canvas.classList.toggle('pinch-mode', mode === 'pinch');
  controls.enabled = mode === 'explore' && !state.pin;
}

function onPointerDown(event) {
  if (state.interactionMode !== 'pinch' || !state.spring || state.pin) return;
  state.pointerDebug = { event: [event.clientX, event.clientY], stateSpring: Boolean(state.spring), statePin: Boolean(state.pin) };
  const hit = pointerHit(event); if (!hit) return;
  state.pointerDebug.hit = { mesh: hit.object.name, faceIndex: hit.faceIndex };
  const entry = state.entries.find(item => item.mesh === hit.object); if (!entry) return;
  state.pointerDebug.entry = entry.mesh.name;
  const face = hit.faceIndex, islandId = entry.faceIsland[face];
  state.pointerDebug.islandId = islandId;
  if (!state.selected || state.selected.entry !== entry || state.selected.island.id !== islandId) { state.selected = { entry, island: entry.islands[islandId] }; ui.island.value = `${entry.mesh.uuid}:${islandId}`; buildSystem(); updateMetrics(`Pinch island selected: ${islandId}`); }
  const index = entry.geometry.index.array, globalIds = [index[face * 3], index[face * 3 + 1], index[face * 3 + 2]], localMap = new Map(state.selected.island.vertices.map((vertex, i) => [vertex, i])), ids = globalIds.map(vertex => localMap.get(vertex));
  if (ids.some(value => value === undefined)) { state.pointerDebug.missingLocalIds = ids; return; }
  const inverse = entry.mesh.matrixWorld.clone().invert(), localHit = hit.point.clone().applyMatrix4(inverse), position = entry.geometry.attributes.position;
  const a = new THREE.Vector3().fromBufferAttribute(position, globalIds[0]), b = new THREE.Vector3().fromBufferAttribute(position, globalIds[1]), c = new THREE.Vector3().fromBufferAttribute(position, globalIds[2]);
  const weights = barycentric(localHit, a, b, c), plane = new THREE.Plane().setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()), hit.point);
  state.pin = { ids, globalIds, weights, target: localHit.clone(), velocity: new THREE.Vector3(), plane, previousWorld: hit.point.clone(), previousLocal: localHit.clone(), lastTime: performance.now(), hard: ui.hardDrag.checked, kp: Number(ui.pinchKp.value), kd: Number(ui.pinchKd.value), currentForce: new THREE.Vector3(), peakForce: 0, peakTrackingError: 0 };
  state.spring.setPin(state.pin); gpuSendPin(state.pin); state.running = true; ui.pause.textContent = 'Pause'; controls.enabled = false;
  state.lastPinch = { down: true, hard: state.pin.hard, kp: state.pin.kp, kd: state.pin.kd, globalIds, weights, initial: hit.point.toArray(), activeIsland: islandId, activeVertices: state.selected.island.vertices.length, activeTriangles: state.selected.island.faces.length, faceIndex: face };
  try { canvas.setPointerCapture(event.pointerId); } catch {}
}
function onPointerMove(event) {
  if (!state.pin) return;
  const rect = canvas.getBoundingClientRect(); pointer.x = (event.clientX - rect.left) / rect.width * 2 - 1; pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; raycaster.setFromCamera(pointer, camera);
  const worldPoint = new THREE.Vector3(); if (!raycaster.ray.intersectPlane(state.pin.plane, worldPoint)) return;
  const inverse = state.selected.entry.mesh.matrixWorld.clone().invert(), localPoint = worldPoint.clone().applyMatrix4(inverse), now = performance.now(), delta = Math.max((now - state.pin.lastTime) / 1000, 1e-3);
  state.pin.velocity.copy(localPoint).sub(state.pin.previousLocal).multiplyScalar(1 / delta); state.pin.target.copy(localPoint); state.pin.previousLocal.copy(localPoint); state.pin.previousWorld.copy(worldPoint); state.pin.lastTime = now; gpuSendPin(state.pin);
}
function onPointerUp(event) {
  if (!state.pin) return;
  const pin = state.pin, ids = pin.ids, weights = pin.weights, positions = state.spring.positions;
  const actual = new THREE.Vector3(); for (let j = 0; j < 3; j++) { actual.x += weights[j] * positions[ids[j] * 3]; actual.y += weights[j] * positions[ids[j] * 3 + 1]; actual.z += weights[j] * positions[ids[j] * 3 + 2]; }
  const trackingErrorMeters = actual.distanceTo(pin.target) * state.spring.sourceMetersPerUnit;
  const moved = state.spring.diagnostics().maxDisplacement; state.spring.clearPin(); controls.enabled = true;
  const forceDistributionN = pin.weights.map(weight => [pin.currentForce.x * weight, pin.currentForce.y * weight, pin.currentForce.z * weight]);
  state.lastPinch = { ...state.lastPinch, down: false, released: true, hard: pin.hard, kp: pin.kp, kd: pin.kd, requestedTarget: pin.target.toArray(), actualAtRelease: actual.toArray(), trackingErrorMeters, peakForceN: pin.peakForce, currentForceN: pin.currentForce.toArray(), forceWeightSum: pin.weights.reduce((sum, weight) => sum + weight, 0), forceDistributionN, forceDistributionSumN: forceDistributionN.reduce((sum, value) => [sum[0] + value[0], sum[1] + value[1], sum[2] + value[2]], [0, 0, 0]), peakTrackingErrorMeters: pin.peakTrackingError, maxDisplacementAtRelease: moved };
  gpuSend({ type: 'release' }); state.pin = null; controls.enabled = state.interactionMode === 'explore'; try { canvas.releasePointerCapture(event.pointerId); } catch {} updateMetrics(`Pin released — force recovery active\nController: ${pin.hard ? 'hard constrained' : `Kp ${pin.kp} N/m, Kd ${pin.kd} N·s/m`}\nPeak force: ${pin.peakForce.toExponential(3)} N\nTracking error: ${trackingErrorMeters.toExponential(3)} m`);
}

async function loadModel(name) {
  closeGpuBackend(); state.model = name; state.pin = null; setInteractionMode('explore'); ui.state.textContent = `Loading ${name}…`; ui.state.classList.remove('ready'); setLoadProgress(2, `Downloading ${name} original GLB...`);
  if (state.root) disposeObject(state.root); if (state.overlay) disposeObject(state.overlay); removeDiagnostics(); state.entries = []; state.meshes = []; state.spring = null;
  const [gltf, attachmentResponse] = await Promise.all([loadGltfWithProgress(MODEL_URLS[name], `${name} GLB`), fetch(ATTACHMENT_URLS[name])]);
  const attachments = await attachmentResponse.json(); state.gltf = gltf; state.root = gltf.scene; scene.add(state.root); state.root.updateMatrixWorld(true); state.entries = [];
  setLoadProgress(62, 'Analyzing original indexed triangles...'); await nextPaint();
  state.root.traverse(object => { if (object.isMesh) { const entry = buildEntry(object); state.entries.push(entry); state.meshes.push(object); } });
  if (!state.entries.length) throw new Error('No mesh objects in GLB');
  setLoadProgress(82, 'Building true disconnected mesh islands...'); await nextPaint();
  loadFaceFrame(attachments); setGravityDirection(ui.gravityDirection?.value || 'none'); buildIslandOverlay();
  setLoadProgress(91, 'Preparing surface springs and inner anchors...'); await nextPaint();
  populateIslands(); setStage(state.stage); setLoadProgress(100, `${name} ready`); ui.state.textContent = `${name} ready`; ui.state.classList.add('ready');
  const other = name === 'female' ? 'male' : 'female';
  if (innerWidth >= 800 && !navigator.connection?.saveData) setTimeout(() => preloadModelAsset(other), 300);
  window.__velaDiagnostics = () => {
    const bounds = new THREE.Box3().setFromObject(state.root);
    const allIslands = state.entries.flatMap(entry => entry.islands.map(island => ({ id: island.id, vertices: island.vertices.length, triangles: island.faces.length })));
    return {
      model: state.model, stage: state.stage, interactionMode: state.interactionMode, lastPinch: state.lastPinch, tests: state.tests,
      metrics: state.spring?.diagnostics(), islands: { count: allIslands.length, minVertices: Math.min(...allIslands.map(item => item.vertices)), maxVertices: Math.max(...allIslands.map(item => item.vertices)), selected: state.selected ? { id: state.selected.island.id, vertices: state.selected.island.vertices.length, triangles: state.selected.island.faces.length, selectedOption: ui.island.value } : null },
      topology: state.entries.map(entry => ({ mesh: entry.mesh.name, ...entry.topology })),
      springTopology: state.spring ? { rawTriangleEdgeUses: state.selected.island.faces.length * 3, uniqueSurfaceEdges: state.spring.edgeA.length, duplicateRawEdgeUsesRemoved: state.spring.edgeInfo.duplicateRawEdges, invariant: state.spring.edgeA.length + state.spring.edgeInfo.duplicateRawEdges === state.selected.island.faces.length * 3 } : null,
      geometry: state.spring?.geometryDiagnostics(), interIslandSprings: 0, pointerDebug: state.pointerDebug,
      render: { bounds: { min: bounds.min.toArray(), max: bounds.max.toArray() }, camera: camera.position.toArray(), target: controls.target.toArray(), meshes: state.meshes.length, visible: state.meshes.filter(mesh => mesh.visible).length, drawCalls: renderer.info.render.calls, pixelRatio: renderer.getPixelRatio(), drawingBuffer: [renderer.domElement.width, renderer.domElement.height], maxTextureSize: renderer.capabilities.maxTextureSize }
    };
  };
  window.__velaSetRunning = value => { state.running = Boolean(value); };
  window.__velaGpuTick = seconds => gpuSendTick(Number(seconds));
  window.__velaSetGravity = direction => setGravityDirection(direction);
  window.__velaStep = (count = 1, dt = 1 / 600) => {
    if (!state.spring) return null;
    state.spring.markActive();
    const stepStart = performance.now();
    for (let i = 0; i < count; i++) state.spring.step(dt);
    const physicsMs = performance.now() - stepStart; state.performance.frames++; state.performance.physicsSteps += count; state.performance.physicsMs += physicsMs; state.performance.wallMs += count * dt * 1000; state.performance.lastPhysicsMs = physicsMs; state.performance.lastFrameMs = count * dt * 1000; state.performance.simTime += count * dt;
    state.spring.update();
    return window.__velaDiagnostics();
  };
  window.__velaPickTest = (clientX, clientY) => {
    const rect = canvas.getBoundingClientRect();
    pointer.x = (clientX - rect.left) / rect.width * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(state.meshes, false)[0];
    return hit ? { mesh: hit.object.name, faceIndex: hit.faceIndex, islandId: state.entries.find(item => item.mesh === hit.object)?.faceIsland[hit.faceIndex], distance: hit.distance, point: hit.point.toArray() } : null;
  };
  window.__velaPlanDrag = (point, fraction = 0.02) => {
    const origin = new THREE.Vector3(...point), target = origin.clone().addScaledVector(state.right, state.faceScale * fraction);
    const project = value => { const ndc = value.project(camera); return { x: (ndc.x + 1) * innerWidth / 2, y: (1 - ndc.y) * innerHeight / 2 }; };
    return { origin: project(origin), target: project(target), sourceDisplacement: state.faceScale * fraction, faceScale: state.faceScale };
  };
}

function frame() {
  requestAnimationFrame(frame);
  const wallStart = performance.now(), now = wallStart, elapsed = Math.min((now - state.lastFrame) / 1000, 0.05); state.lastFrame = now; controls.update();
  if (state.running && state.spring) {
    if (state.gpu.connected) {
      gpuSendTick(elapsed);
    } else {
      const steps = Math.max(1, Math.min(8, Math.ceil(elapsed / (1 / 600)))), stepStart = performance.now();
      for (let i = 0; i < steps; i++) state.spring.step(elapsed / steps);
      state.spring.update();
      const physicsMs = performance.now() - stepStart; state.performance.frames++; state.performance.physicsSteps += steps; state.performance.physicsMs += physicsMs; state.performance.wallMs += elapsed * 1000; state.performance.lastPhysicsMs = physicsMs; state.performance.lastFrameMs = elapsed * 1000; state.performance.simTime += elapsed;
    }
    if (state.frameCount++ % 8 === 0) updateMetrics();
  }
  renderer.render(scene, camera);
  if (state.running) state.performance.wallMs += Math.max(0, performance.now() - wallStart - elapsed * 1000);
}

for (const button of document.querySelectorAll('.tab')) button.addEventListener('click', () => { state.stage = Number(button.dataset.stage); document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', Number(item.dataset.stage) === state.stage)); ui.stageText.textContent = STAGE_TEXT[state.stage]; updateVisuals(); updateMetrics(); });
ui.character.addEventListener('change', () => loadModel(ui.character.value).catch(error => { ui.state.textContent = `Error: ${error.message}`; console.error(error); }));
ui.gravityDirection?.addEventListener('change', () => setGravityDirection(ui.gravityDirection.value));
ui.physicsBackend?.addEventListener('change', () => { if (state.spring) buildSystem(); });
ui.hardDrag?.addEventListener('change', () => { if (state.spring) buildSystem(); });
ui.island?.addEventListener('change', () => {
  const [uuid, idText] = String(ui.island.value).split(':');
  const entry = state.entries.find(item => item.mesh.uuid === uuid), island = entry?.islands[Number(idText)];
  if (entry && island) { state.selected = { entry, island }; buildSystem(); updateMetrics(`Selected island: ${island.id}`); }
});
ui.exploreMode.addEventListener('click', () => setInteractionMode('explore'));
ui.pinchMode.addEventListener('click', () => setInteractionMode('pinch'));
ui.showOriginal.addEventListener('change', updateVisuals); ui.showIslands.addEventListener('change', updateVisuals); ui.showSprings.addEventListener('change', updateVisuals); ui.showStrain.addEventListener('change', updateVisuals); ui.showMass.addEventListener('change', updateVisuals); ui.showInner.addEventListener('change', updateVisuals);
ui.physicsPreset.addEventListener('change', () => { if (state.spring) buildSystem(); });
ui.integrator.addEventListener('change', () => { if (state.spring) buildSystem(); });
ui.pinchKp.addEventListener('input', () => { ui.kpOut.textContent = `${ui.pinchKp.value} N/m`; });
ui.pinchKd.addEventListener('input', () => { ui.kdOut.textContent = `${ui.pinchKd.value} N·s/m`; });
ui.wireDensity.addEventListener('input', () => { if (state.spring) buildDiagnosticsVisuals(); updateVisuals(); });
ui.depth.addEventListener('input', () => { ui.depthOut.textContent = `${ui.depth.value}× edge`; if (state.spring) buildSystem(); });
ui.neighbors.addEventListener('input', () => { ui.neighborsOut.textContent = ui.neighbors.value; if (state.spring) buildSystem(); });
ui.pause.addEventListener('click', () => { state.running = !state.running; ui.pause.textContent = state.running ? 'Pause' : 'Resume'; });
$('resetNeutral').addEventListener('click', resetNeutral); $('resetCamera').addEventListener('click', () => { camera.position.copy(state.faceCenter).addScaledVector(state.front, state.faceScale * 4.1); controls.target.copy(state.faceCenter); controls.update(); });
$('neutralRest').addEventListener('click', () => runTest('rest')); $('oneNudge').addEventListener('click', () => runTest('nudge')); $('noAnchor').addEventListener('click', () => runTest('noAnchor'));
ui.depthOut.textContent = `${ui.depth.value}× edge`; ui.neighborsOut.textContent = ui.neighbors.value; ui.pause.textContent = 'Resume';
setInteractionMode('explore');
canvas.addEventListener('pointerdown', onPointerDown); canvas.addEventListener('pointermove', onPointerMove); canvas.addEventListener('pointerup', onPointerUp); canvas.addEventListener('pointercancel', onPointerUp);
window.addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); resizeRenderer(); });
ui.stageText.textContent = STAGE_TEXT[1];
const initialModel = new URLSearchParams(location.search).get('model') === 'male' ? 'male' : 'female';
loadModel(initialModel).catch(error => { ui.state.textContent = `Error: ${error.message}`; console.error(error); });
frame();
