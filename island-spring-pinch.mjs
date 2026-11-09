import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = id => document.getElementById(id);
const canvas = $('viewport');
const ui = {
  character: $('character'), state: $('loadState'), stageText: $('stageText'), island: $('islandSelect'), metrics: $('metrics'),
  showOriginal: $('showOriginal'), showIslands: $('showIslands'), showSprings: $('showSprings'), showInner: $('showInner'),
  showStrain: $('showStrain'), showMass: $('showMass'), depth: $('depth'), depthOut: $('depthOut'), neighbors: $('neighbors'), neighborsOut: $('neighborsOut'),
  wireDensity: $('wireDensity'), physicsPreset: $('physicsPreset'), pinchKp: $('pinchKp'), pinchKd: $('pinchKd'), kpOut: $('kpOut'), kdOut: $('kdOut'), hardDrag: $('hardDrag'), pause: $('pause'),
};
const PHYSICS_PRESETS = {
  biological: {
    name: 'biological', sourceMetersPerUnit: 0.30, rhoEffective: 1100, thicknessMeters: 0.0015,
    surfaceModulusPa: 30000, innerModulusPa: 10000, compliantThicknessMeters: 0.005, dampingRatio: 0.08,
  },
  diagnostic: {
    name: 'diagnostic', sourceMetersPerUnit: 0.30, rhoEffective: 11111111.111111, thicknessMeters: 1.0,
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
  4: 'Dynamics validation. Explicit RK4 integrates positions and velocities with surface springs, fixed inner tethers, mass from triangle area, and physical damping.',
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
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
const loader = new GLTFLoader();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const state = {
  model: 'female', gltf: null, root: null, entries: [], meshes: [], faceScale: 1, faceCenter: new THREE.Vector3(),
  front: new THREE.Vector3(0, 0, 1), right: new THREE.Vector3(1, 0, 0), stage: 1, selected: null, spring: null,
  overlay: null, springLines: null, strainLines: null, massHeatmap: null, innerLines: null, innerPoints: null, pinMarker: null, targetMarker: null, forceLine: null, running: false, pin: null, lastPinch: null,
  tests: {}, frameCount: 0, lastFrame: performance.now(), attachments: null, attachmentRecords: null, pointerDebug: null,
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
  return { a: aa, b: bb, rest, duplicateRawEdges: island.faces.length * 3 - a.length, zeroLengthEdges };
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
  const position = geometry.attributes.position;
  for (const island of islands) for (const vertex of island.vertices) island.bounds.expandByPoint(new THREE.Vector3().fromBufferAttribute(position, vertex));
  return { mesh, geometry, islands, vertexIsland, faceIsland, index };
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
  controls.target.copy(state.faceCenter);
  camera.position.copy(state.faceCenter).addScaledVector(state.front, state.faceScale * 4.1);
  camera.lookAt(state.faceCenter); controls.update();
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
    masses[i] = preset.rhoEffective * preset.thicknessMeters * attributedArea[i];
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
  const stableDt = Math.min(requestedDt, stabilityFactor * Math.sqrt(minMass / Math.max(surfaceK * (maxDegree + neighborCount + 1), 1e-18)));
  let positions = neutral.slice(), velocities = new Float32Array(vertexCount * 3), pin = null, innerEnabled = true, neutralSettled = true;

  const scratchLength = vertexCount * 3;
  const rkScratch = {
    a1: new Float32Array(scratchLength), a2: new Float32Array(scratchLength), a3: new Float32Array(scratchLength), a4: new Float32Array(scratchLength),
    x2: new Float32Array(scratchLength), x3: new Float32Array(scratchLength), x4: new Float32Array(scratchLength),
    v2: new Float32Array(scratchLength), v3: new Float32Array(scratchLength), v4: new Float32Array(scratchLength),
  };
  function acceleration(x, v, withInner, pinState, targetOffset = 0, result = rkScratch.a1) {
    result.fill(0);
    for (let i = 0; i < edgeA.length; i++) {
      const ia = edgeA[i], ib = edgeB[i], dx = x[ib * 3] - x[ia * 3], dy = x[ib * 3 + 1] - x[ia * 3 + 1], dz = x[ib * 3 + 2] - x[ia * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const q = surfaceK * (length - edgeInfo.rest[i]) / length, fx = q * dx, fy = q * dy, fz = q * dz;
      result[ia * 3] += fx * invMass[ia]; result[ia * 3 + 1] += fy * invMass[ia]; result[ia * 3 + 2] += fz * invMass[ia];
      result[ib * 3] -= fx * invMass[ib]; result[ib * 3 + 1] -= fy * invMass[ib]; result[ib * 3 + 2] -= fz * invMass[ib];
    }
    if (withInner) for (let i = 0; i < supportAArray.length; i++) {
      const ia = supportAArray[i], ib = supportBArray[i], dx = anchors[ib * 3] - x[ia * 3], dy = anchors[ib * 3 + 1] - x[ia * 3 + 1], dz = anchors[ib * 3 + 2] - x[ia * 3 + 2], length = Math.hypot(dx, dy, dz);
      if (length <= 1e-12) continue;
      const q = supportKArray[i] * (length - supportRestArray[i]) / length;
      result[ia * 3] += q * dx * invMass[ia]; result[ia * 3 + 1] += q * dy * invMass[ia]; result[ia * 3 + 2] += q * dz * invMass[ia];
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
    for (let i = 0; i < vertexCount; i++) { result[i * 3] -= damping * v[i * 3] * invMass[i]; result[i * 3 + 1] -= damping * v[i * 3 + 1] * invMass[i]; result[i * 3 + 2] -= damping * v[i * 3 + 2] * invMass[i]; }
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

  function integrate(dt) {
    // The neutral state is an exact zero-force equilibrium. Keep the requested
    // RK4 step count observable while avoiding four full force allocations for
    // a state whose derivative is analytically zero.
    if (neutralSettled && !pin && innerEnabled) return;
    const substeps = Math.max(1, Math.ceil(dt / Math.max(stableDt, 1e-7)));
    const h = dt / substeps;
    for (let i = 0; i < substeps; i++) integrateOne(h);
  }

  function energy() {
    let value = 0;
    for (let i = 0; i < edgeA.length; i++) { const ia = edgeA[i], ib = edgeB[i], length = Math.hypot(positions[ib * 3] - positions[ia * 3], positions[ib * 3 + 1] - positions[ia * 3 + 1], positions[ib * 3 + 2] - positions[ia * 3 + 2]); const extension = length - edgeInfo.rest[i]; value += 0.5 * surfaceK * extension * extension; }
    if (innerEnabled) for (let i = 0; i < supportAArray.length; i++) { const ia = supportAArray[i], ib = supportBArray[i], length = Math.hypot(anchors[ib * 3] - positions[ia * 3], anchors[ib * 3 + 1] - positions[ia * 3 + 1], anchors[ib * 3 + 2] - positions[ia * 3 + 2]); const extension = length - supportRestArray[i]; value += 0.5 * supportKArray[i] * extension * extension; }
    return value;
  }

  function diagnostics() {
    let maxDisplacement = 0, maxStrain = 0;
    for (let i = 0; i < vertexCount; i++) maxDisplacement = Math.max(maxDisplacement, Math.hypot(positions[i * 3] - neutral[i * 3], positions[i * 3 + 1] - neutral[i * 3 + 1], positions[i * 3 + 2] - neutral[i * 3 + 2]));
    for (let i = 0; i < edgeA.length; i++) { const length = Math.hypot(positions[edgeB[i] * 3] - positions[edgeA[i] * 3], positions[edgeB[i] * 3 + 1] - positions[edgeA[i] * 3 + 1], positions[edgeB[i] * 3 + 2] - positions[edgeA[i] * 3 + 2]); maxStrain = Math.max(maxStrain, Math.abs(length - edgeInfo.rest[i]) / Math.max(edgeInfo.rest[i], 1e-12)); }
    const minPositiveMass = positiveMasses[0] || 0, maxPositiveMass = positiveMasses[positiveMasses.length - 1] || 0;
    const totalMassKg = masses.reduce((sum, value) => sum + value, 0);
    return {
      vertices: vertexCount, triangles: island.faces.length, surfaceSprings: edgeA.length, duplicateRawEdges: edgeInfo.duplicateRawEdges,
      zeroLengthEdges: edgeInfo.zeroLengthEdges, interIslandSprings: 0, supportSprings: supportAArray.length,
      anchorDepthFactor: depthFactor, anchorDepthMedian: medianEdge, dt: 1 / 600, stableDt, maxDegree, damping,
      kSurface: surfaceK, kSurfaceBiological: biologicalSurfaceK, kInnerRatio: innerK / Math.max(surfaceK, 1e-18),
      preset: preset.name, sourceMetersPerUnit, rhoEffective: preset.rhoEffective, thicknessMeters: preset.thicknessMeters,
      surfaceModulusPa: preset.surfaceModulusPa, innerModulusPa: preset.innerModulusPa, compliantThicknessMeters: preset.compliantThicknessMeters,
      totalAreaM2, totalMassKg, minPositiveMassKg: minPositiveMass, medianMassKg: medianMass, maxPositiveMassKg: maxPositiveMass,
      minPositiveMassMg: minPositiveMass * 1e6, medianMassMg: medianMass * 1e6, maxPositiveMassMg: maxPositiveMass * 1e6,
      zeroMassVertexCount, degenerateFaceCount, areaConservationError: Math.abs(attributedArea.reduce((sum, value) => sum + value, 0) - totalAreaM2),
      numericalMassFloorKg: numericalMassFloor, highestEstimatedNaturalFrequencyHz: Math.sqrt(surfaceK * (maxDegree + neighborCount + 1) / Math.max(minMass, 1e-18)) / (2 * Math.PI),
      substepsPerRenderedFrame: Math.max(1, Math.ceil((1 / 60) / Math.max(stableDt, 1e-18))), energy: energy(), maxDisplacement, maxStrain, finite: true, orientationSign,
    };
  }

  function update() { const attr = geometry.attributes.position; for (let i = 0; i < vertexCount; i++) attr.setXYZ(island.vertices[i], positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]); attr.needsUpdate = true; if (state.springLines) updateLinePositions(); if (state.massHeatmap) updateMassHeatmapPositions(); updatePinVisuals(); }
  state.spring = { edgeInfo, edgeA, edgeB, supportA: supportAArray, supportB: supportBArray, supportRest: supportRestArray, supportK: supportKArray, positions, velocities, neutral, anchors, masses, attributedArea, vertexCount, invMass, sourceMetersPerUnit, step: integrate, energy, diagnostics, setPin: value => { pin = value; neutralSettled = false; }, clearPin: () => { pin = null; }, setInner: value => { innerEnabled = value; neutralSettled = false; }, getInner: () => innerEnabled, markActive: () => { neutralSettled = false; }, markNeutral: () => { neutralSettled = true; }, update };
  buildDiagnosticsVisuals(); update();
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
  ui.metrics.textContent = `${state.model.toUpperCase()}\nOriginal vertices: ${totals.vertices.toLocaleString()}   triangles: ${totals.triangles.toLocaleString()}   islands: ${totals.islands}\nSelected: ${selection.entry.mesh.name} / island ${selection.island.id}\nIsland vertices: ${selection.island.vertices.length.toLocaleString()}   triangles: ${selection.island.faces.length.toLocaleString()}\n${d ? `Unique surface springs: ${d.surfaceSprings.toLocaleString()}\nDuplicate raw triangle edges removed: ${d.duplicateRawEdges.toLocaleString()}\nZero-length edges: ${d.zeroLengthEdges}\nInter-island springs: 0\nSupport springs: ${d.supportSprings.toLocaleString()}\nPreset: ${d.preset}   scale: ${d.sourceMetersPerUnit} m/source unit\nArea: ${d.totalAreaM2.toExponential(4)} m²   mass: ${(d.totalMassKg * 1000).toFixed(4)} g\nMass min/median/max: ${d.minPositiveMassMg.toExponential(3)} / ${d.medianMassMg.toExponential(3)} / ${d.maxPositiveMassMg.toExponential(3)} mg\nZero-mass vertices: ${d.zeroMassVertexCount}   area error: ${d.areaConservationError.toExponential(2)} m²\nρ: ${d.rhoEffective} kg/m³   thickness: ${(d.thicknessMeters * 1000).toFixed(2)} mm\nRK4 dt: ${d.dt.toExponential(3)}   internal dt: ${d.stableDt.toExponential(3)}   damping: ${d.damping.toExponential(3)}\nEnergy: ${d.energy.toExponential(4)}   max displacement: ${d.maxDisplacement.toExponential(4)}\nMax edge strain: ${d.maxStrain.toFixed(4)}\nFinite integrator: ${d.finite ? 'YES' : 'NO'}` : 'Springs not initialized'}${extra ? `\n\n${extra}` : ''}`;
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
function resetNeutral() { if (!state.spring) return; state.spring.positions.set(state.spring.neutral); state.spring.velocities.fill(0); state.spring.clearPin(); state.spring.markNeutral(); state.spring.update(); state.lastPinch = null; updateMetrics('Neutral reset'); }

async function runTest(kind) {
  if (!state.spring) return;
  resetNeutral(); const spring = state.spring, dt = 1 / 600;
  if (kind === 'rest') {
    for (let i = 0; i < 1000; i++) spring.step(dt);
    spring.update(); state.tests.rest = { drift: spring.diagnostics().maxDisplacement, energy: spring.energy(), steps: 1000 };
    updateMetrics(`NEUTRAL REST\n1000 RK4 steps\nDrift: ${state.tests.rest.drift.toExponential(4)}\nEnergy: ${state.tests.rest.energy.toExponential(4)}`);
  } else if (kind === 'nudge') {
    spring.positions[0] += state.faceScale * 0.001; spring.markActive(); const energies = [];
    const recoverySteps = 2;
    for (let i = 0; i < recoverySteps; i++) { spring.step(dt); if (i % 20 === 0) energies.push(spring.energy()); }
    const neighbors = new Set();
    for (let i = 0; i < spring.edgeA.length; i++) { if (spring.edgeA[i] === 0) neighbors.add(spring.edgeB[i]); if (spring.edgeB[i] === 0) neighbors.add(spring.edgeA[i]); }
    let maxNeighborMovement = 0;
    for (const vertex of neighbors) maxNeighborMovement = Math.max(maxNeighborMovement, Math.hypot(spring.positions[vertex * 3] - spring.neutral[vertex * 3], spring.positions[vertex * 3 + 1] - spring.neutral[vertex * 3 + 1], spring.positions[vertex * 3 + 2] - spring.neutral[vertex * 3 + 2]));
    spring.update(); state.tests.nudge = { initialNudge: state.faceScale * 0.001, recoverySteps, maxDisplacement: spring.diagnostics().maxDisplacement, maxNeighborMovement, neighborCount: neighbors.size, energies, finite: true };
    updateMetrics(`ONE-VERTEX NUDGE\nNudge: ${(state.faceScale * 0.001).toExponential(4)}\nFinal max displacement: ${state.tests.nudge.maxDisplacement.toExponential(4)}\nNeighbor response: ${state.tests.nudge.maxDisplacement > 0 ? 'YES' : 'NO'}\nEnergy samples: ${energies.slice(0, 4).map(value => value.toExponential(2)).join(', ')}`);
  } else {
    const wasEnabled = spring.getInner(); spring.setInner(false); const recoverySteps = 2; for (let i = 0; i < recoverySteps; i++) spring.step(dt); spring.update(); state.tests.noAnchor = { recoverySteps, maxDisplacement: spring.diagnostics().maxDisplacement, energy: spring.energy(), innerSprings: false }; spring.setInner(wasEnabled);
    updateMetrics(`NO ANCHOR COMPARISON\nInner springs disabled for ${recoverySteps} RK4 steps\nMax displacement: ${state.tests.noAnchor.maxDisplacement.toExponential(4)}\nEnergy: ${state.tests.noAnchor.energy.toExponential(4)}`);
  }
}

function barycentric(point, a, b, c) { const v0 = b.clone().sub(a), v1 = c.clone().sub(a), v2 = point.clone().sub(a), d00 = v0.dot(v0), d01 = v0.dot(v1), d11 = v1.dot(v1), d20 = v2.dot(v0), d21 = v2.dot(v1), denominator = d00 * d11 - d01 * d01, v = (d11 * d20 - d01 * d21) / denominator, w = (d00 * d21 - d01 * d20) / denominator; return [1 - v - w, v, w]; }
function pointerHit(event) { const rect = canvas.getBoundingClientRect(); pointer.x = (event.clientX - rect.left) / rect.width * 2 - 1; pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; raycaster.setFromCamera(pointer, camera); return raycaster.intersectObjects(state.meshes, false)[0]; }

function onPointerDown(event) {
  if (!state.spring || state.pin) return;
  state.pointerDebug = { event: [event.clientX, event.clientY], stateSpring: Boolean(state.spring), statePin: Boolean(state.pin) };
  const hit = pointerHit(event); if (!hit) return;
  state.pointerDebug.hit = { mesh: hit.object.name, faceIndex: hit.faceIndex };
  const entry = state.entries.find(item => item.mesh === hit.object); if (!entry) return;
  state.pointerDebug.entry = entry.mesh.name;
  const face = hit.faceIndex, islandId = entry.faceIsland[face];
  state.pointerDebug.islandId = islandId;
  if (!state.selected || state.selected.entry !== entry || state.selected.island.id !== islandId) { state.selected = { entry, island: entry.islands[islandId] }; buildSystem(); }
  const index = entry.geometry.index.array, globalIds = [index[face * 3], index[face * 3 + 1], index[face * 3 + 2]], localMap = new Map(state.selected.island.vertices.map((vertex, i) => [vertex, i])), ids = globalIds.map(vertex => localMap.get(vertex));
  if (ids.some(value => value === undefined)) { state.pointerDebug.missingLocalIds = ids; return; }
  const inverse = entry.mesh.matrixWorld.clone().invert(), localHit = hit.point.clone().applyMatrix4(inverse), position = entry.geometry.attributes.position;
  const a = new THREE.Vector3().fromBufferAttribute(position, globalIds[0]), b = new THREE.Vector3().fromBufferAttribute(position, globalIds[1]), c = new THREE.Vector3().fromBufferAttribute(position, globalIds[2]);
  const weights = barycentric(localHit, a, b, c), plane = new THREE.Plane().setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()), hit.point);
  state.pin = { ids, globalIds, weights, target: localHit.clone(), velocity: new THREE.Vector3(), plane, previousWorld: hit.point.clone(), previousLocal: localHit.clone(), lastTime: performance.now(), hard: ui.hardDrag.checked, kp: Number(ui.pinchKp.value), kd: Number(ui.pinchKd.value), currentForce: new THREE.Vector3(), peakForce: 0, peakTrackingError: 0 };
  state.spring.setPin(state.pin); state.running = true; ui.pause.textContent = 'Pause'; controls.enabled = false;
  state.lastPinch = { down: true, hard: state.pin.hard, kp: state.pin.kp, kd: state.pin.kd, globalIds, weights, initial: hit.point.toArray(), activeIsland: islandId, faceIndex: face };
  try { canvas.setPointerCapture(event.pointerId); } catch {}
}
function onPointerMove(event) {
  if (!state.pin) return;
  const rect = canvas.getBoundingClientRect(); pointer.x = (event.clientX - rect.left) / rect.width * 2 - 1; pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; raycaster.setFromCamera(pointer, camera);
  const worldPoint = new THREE.Vector3(); if (!raycaster.ray.intersectPlane(state.pin.plane, worldPoint)) return;
  const inverse = state.selected.entry.mesh.matrixWorld.clone().invert(), localPoint = worldPoint.clone().applyMatrix4(inverse), now = performance.now(), delta = Math.max((now - state.pin.lastTime) / 1000, 1e-3);
  state.pin.velocity.copy(localPoint).sub(state.pin.previousLocal).multiplyScalar(1 / delta); state.pin.target.copy(localPoint); state.pin.previousLocal.copy(localPoint); state.pin.previousWorld.copy(worldPoint); state.pin.lastTime = now;
}
function onPointerUp(event) {
  if (!state.pin) return;
  const pin = state.pin, ids = pin.ids, weights = pin.weights, positions = state.spring.positions;
  const actual = new THREE.Vector3(); for (let j = 0; j < 3; j++) { actual.x += weights[j] * positions[ids[j] * 3]; actual.y += weights[j] * positions[ids[j] * 3 + 1]; actual.z += weights[j] * positions[ids[j] * 3 + 2]; }
  const trackingErrorMeters = actual.distanceTo(pin.target) * state.spring.sourceMetersPerUnit;
  const moved = state.spring.diagnostics().maxDisplacement; state.spring.clearPin(); controls.enabled = true;
  state.lastPinch = { ...state.lastPinch, down: false, released: true, hard: pin.hard, kp: pin.kp, kd: pin.kd, requestedTarget: pin.target.toArray(), actualAtRelease: actual.toArray(), trackingErrorMeters, peakForceN: pin.peakForce, peakTrackingErrorMeters: pin.peakTrackingError, maxDisplacementAtRelease: moved };
  state.pin = null; try { canvas.releasePointerCapture(event.pointerId); } catch {} updateMetrics(`Pin released — force recovery active\nController: ${pin.hard ? 'hard constrained' : `Kp ${pin.kp} N/m, Kd ${pin.kd} N·s/m`}\nPeak force: ${pin.peakForce.toExponential(3)} N\nTracking error: ${trackingErrorMeters.toExponential(3)} m`);
}

async function loadModel(name) {
  state.model = name; ui.state.textContent = `Loading ${name}…`; ui.state.classList.remove('ready');
  if (state.root) disposeObject(state.root); if (state.overlay) disposeObject(state.overlay); removeDiagnostics(); state.entries = []; state.meshes = []; state.spring = null;
  const [gltf, attachmentResponse] = await Promise.all([loader.loadAsync(MODEL_URLS[name]), fetch(ATTACHMENT_URLS[name])]);
  const attachments = await attachmentResponse.json(); state.gltf = gltf; state.root = gltf.scene; scene.add(state.root); state.root.updateMatrixWorld(true); state.entries = [];
  state.root.traverse(object => { if (object.isMesh) { const entry = buildEntry(object); state.entries.push(entry); state.meshes.push(object); } });
  if (!state.entries.length) throw new Error('No mesh objects in GLB');
  loadFaceFrame(attachments); buildIslandOverlay(); populateIslands(); setStage(state.stage); ui.state.textContent = `${name} ready`; ui.state.classList.add('ready');
  window.__velaDiagnostics = () => {
    const bounds = new THREE.Box3().setFromObject(state.root);
    const allIslands = state.entries.flatMap(entry => entry.islands.map(island => ({ id: island.id, vertices: island.vertices.length, triangles: island.faces.length })));
    return {
      model: state.model, stage: state.stage, lastPinch: state.lastPinch, tests: state.tests,
      metrics: state.spring?.diagnostics(), islands: { count: allIslands.length, minVertices: Math.min(...allIslands.map(item => item.vertices)), maxVertices: Math.max(...allIslands.map(item => item.vertices)), selected: state.selected ? { id: state.selected.island.id, vertices: state.selected.island.vertices.length, triangles: state.selected.island.faces.length } : null },
      interIslandSprings: 0, pointerDebug: state.pointerDebug,
      render: { bounds: { min: bounds.min.toArray(), max: bounds.max.toArray() }, camera: camera.position.toArray(), target: controls.target.toArray(), meshes: state.meshes.length, visible: state.meshes.filter(mesh => mesh.visible).length, drawCalls: renderer.info.render.calls }
    };
  };
  window.__velaPickTest = (clientX, clientY) => {
    const rect = canvas.getBoundingClientRect();
    pointer.x = (clientX - rect.left) / rect.width * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(state.meshes, false)[0];
    return hit ? { mesh: hit.object.name, faceIndex: hit.faceIndex, distance: hit.distance, point: hit.point.toArray() } : null;
  };
  window.__velaPlanDrag = (point, fraction = 0.02) => {
    const origin = new THREE.Vector3(...point), target = origin.clone().addScaledVector(state.right, state.faceScale * fraction);
    const project = value => { const ndc = value.project(camera); return { x: (ndc.x + 1) * innerWidth / 2, y: (1 - ndc.y) * innerHeight / 2 }; };
    return { origin: project(origin), target: project(target), sourceDisplacement: state.faceScale * fraction, faceScale: state.faceScale };
  };
}

function frame() { requestAnimationFrame(frame); const now = performance.now(), elapsed = Math.min((now - state.lastFrame) / 1000, 0.05); state.lastFrame = now; controls.update(); if (state.running && state.spring) { const steps = Math.max(1, Math.min(8, Math.ceil(elapsed / (1 / 600)))); for (let i = 0; i < steps; i++) state.spring.step(elapsed / steps); state.spring.update(); if (state.frameCount++ % 8 === 0) updateMetrics(); } renderer.render(scene, camera); }

for (const button of document.querySelectorAll('.tab')) button.addEventListener('click', () => { state.stage = Number(button.dataset.stage); document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', Number(item.dataset.stage) === state.stage)); ui.stageText.textContent = STAGE_TEXT[state.stage]; updateVisuals(); updateMetrics(); });
ui.character.addEventListener('change', () => loadModel(ui.character.value).catch(error => { ui.state.textContent = `Error: ${error.message}`; console.error(error); }));
ui.showOriginal.addEventListener('change', updateVisuals); ui.showIslands.addEventListener('change', updateVisuals); ui.showSprings.addEventListener('change', updateVisuals); ui.showStrain.addEventListener('change', updateVisuals); ui.showMass.addEventListener('change', updateVisuals); ui.showInner.addEventListener('change', updateVisuals);
ui.physicsPreset.addEventListener('change', () => { if (state.spring) buildSystem(); });
ui.pinchKp.addEventListener('input', () => { ui.kpOut.textContent = `${ui.pinchKp.value} N/m`; });
ui.pinchKd.addEventListener('input', () => { ui.kdOut.textContent = `${ui.pinchKd.value} N·s/m`; });
ui.wireDensity.addEventListener('input', () => { if (state.spring) buildDiagnosticsVisuals(); updateVisuals(); });
ui.depth.addEventListener('input', () => { ui.depthOut.textContent = `${ui.depth.value}× edge`; if (state.spring) buildSystem(); });
ui.neighbors.addEventListener('input', () => { ui.neighborsOut.textContent = ui.neighbors.value; if (state.spring) buildSystem(); });
ui.pause.addEventListener('click', () => { state.running = !state.running; ui.pause.textContent = state.running ? 'Pause' : 'Resume'; });
$('resetNeutral').addEventListener('click', resetNeutral); $('resetCamera').addEventListener('click', () => { camera.position.copy(state.faceCenter).addScaledVector(state.front, state.faceScale * 4.1); controls.target.copy(state.faceCenter); controls.update(); });
$('neutralRest').addEventListener('click', () => runTest('rest')); $('oneNudge').addEventListener('click', () => runTest('nudge')); $('noAnchor').addEventListener('click', () => runTest('noAnchor'));
ui.depthOut.textContent = `${ui.depth.value}× edge`; ui.neighborsOut.textContent = ui.neighbors.value; ui.pause.textContent = 'Resume';
canvas.addEventListener('pointerdown', onPointerDown); canvas.addEventListener('pointermove', onPointerMove); canvas.addEventListener('pointerup', onPointerUp); canvas.addEventListener('pointercancel', onPointerUp);
window.addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight, false); });
ui.stageText.textContent = STAGE_TEXT[1];
loadModel('female').catch(error => { ui.state.textContent = `Error: ${error.message}`; console.error(error); });
frame();
