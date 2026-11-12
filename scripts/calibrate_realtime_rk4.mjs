import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = path.join(root, 'verification', 'island-spring-pinch');
const sourceMetersPerUnit = 0.30;
const frameDt = 1 / 60;
const baseDt = 1 / 600;
const anchorDepthFactor = 0.25;
const neighborAnchorCount = 3;
const gravityDirections = ['down', 'up', 'left', 'right', 'forward', 'backward'];
const models = {
  female: {
    glb: path.join(root, 'assets', 'tripo', 'vela-photoreal', 'generated-original.glb'),
    attachments: path.join(root, 'verification', 'plan-a5-subcutaneous-run', 'female-corrected-attachments.json'),
  },
  male: {
    glb: path.join(root, 'assets', 'tripo', 'generalization-male-20261105', 'generated-original.glb'),
    attachments: path.join(root, 'verification', 'plan-a2-hookean-run', 'male-original-attachments.json'),
  },
};

const argv = new Set(process.argv.slice(2));
const requestedModels = (process.env.VELA_CALIBRATION_MODELS || 'female,male').split(',').map(v => v.trim()).filter(v => models[v]);
const generations = Number(process.env.VELA_CALIBRATION_GENERATIONS || 3);
const populationSize = Number(process.env.VELA_CALIBRATION_POPULATION || 6);
const fullSurvivors = Number(process.env.VELA_CALIBRATION_FULL_SURVIVORS || 4);
const maxSubsteps = Number(process.env.VELA_CALIBRATION_MAX_SUBSTEPS || 800);
const maxEstimatedStages = Number(process.env.VELA_CALIBRATION_MAX_STAGES || 250000000);
const maxOfflineStages = Number(process.env.VELA_CALIBRATION_MAX_OFFLINE_STAGES || 1000000000);
const maxOfflineScreenStages = Number(process.env.VELA_CALIBRATION_MAX_OFFLINE_SCREEN_STAGES || 50000000);
const offlineScreenSeconds = Number(process.env.VELA_CALIBRATION_OFFLINE_SCREEN_SECONDS || 0.02);
const offlineMicroSeconds = Number(process.env.VELA_CALIBRATION_OFFLINE_MICRO_SECONDS || 0.005);
const offlineGravitySeconds = Number(process.env.VELA_CALIBRATION_OFFLINE_GRAVITY_SECONDS || 0.02);
const offlineLowSeconds = Number(process.env.VELA_CALIBRATION_OFFLINE_LOW_SECONDS || 0.02);
const offlineFullSeconds = Number(process.env.VELA_CALIBRATION_OFFLINE_FULL_SECONDS || 0.05);
const offlineFinalSeconds = Number(process.env.VELA_CALIBRATION_OFFLINE_FINAL_SECONDS || 0.20);
const offlineModelWallMs = Number(process.env.VELA_CALIBRATION_OFFLINE_MODEL_WALL_MS || 180000);
const empiricalStabilityMultiplier = Number(process.env.VELA_CALIBRATION_STABILITY_MULTIPLIER || 1);
const stressHoldSeconds = Number(process.env.VELA_CALIBRATION_STRESS_HOLD_SECONDS || frameDt);
const stressReleaseSeconds = Number(process.env.VELA_CALIBRATION_STRESS_RELEASE_SECONDS || 0.05);
const seed = Number(process.env.VELA_CALIBRATION_SEED || 20261111);
const noSearch = argv.has('--baseline-only');
const checkpointPath = process.env.VELA_CALIBRATION_CHECKPOINT || path.join(outputDir, 'rk4-calibration-checkpoint.json');
const maxCycles = Number(process.env.VELA_CALIBRATION_MAX_CYCLES || process.env.VELA_CALIBRATION_GENERATIONS || 8);
const maxWallMs = Number(process.env.VELA_CALIBRATION_MAX_WALL_MS || 120000);
const maxGravityStrain = Number(process.env.VELA_CALIBRATION_MAX_GRAVITY_STRAIN || 5);
const maxNormalizedVelocity = Number(process.env.VELA_CALIBRATION_MAX_NORMALIZED_VELOCITY || 0.02);
const maxForceResidualRatio = Number(process.env.VELA_CALIBRATION_MAX_FORCE_RESIDUAL_RATIO || 0.05);
const convergenceTolerance = Number(process.env.VELA_CALIBRATION_CONVERGENCE_TOLERANCE || 1e-3);
const resumeArgIndex = process.argv.indexOf('--resume');
const resumePath = resumeArgIndex >= 0 && process.argv[resumeArgIndex + 1] && !process.argv[resumeArgIndex + 1].startsWith('--')
  ? process.argv[resumeArgIndex + 1] : process.env.VELA_CALIBRATION_RESUME || null;
const resultCache = new Map();
const preparedPhysicsCache = new Map();
const evidenceSuffix = (process.env.VELA_CALIBRATION_EVIDENCE_SUFFIX || '').trim().replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
function evidencePath(stem) { return path.join(outputDir, `${stem}${evidenceSuffix ? `-${evidenceSuffix}` : ''}.json`); }

function rng(seedValue) {
  let state = seedValue >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return (state + 0.5) / 4294967296;
  };
}

function gaussian(random) {
  const u = Math.max(random(), 1e-12), v = Math.max(random(), 1e-12);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function readGlb(buffer) {
  if (buffer.toString('ascii', 0, 4) !== 'glTF') throw new Error('Invalid GLB magic');
  let offset = 12, json = null, binary = null;
  while (offset < buffer.length) {
    const length = buffer.readUInt32LE(offset);
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const chunk = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'JSON') json = JSON.parse(chunk.toString('utf8'));
    if (type === 'BIN\0') binary = chunk;
    offset += 8 + length;
  }
  if (!json || !binary) throw new Error('GLB missing JSON or binary chunk');
  return { json, binary };
}

function accessor(glb, index) {
  const desc = glb.json.accessors[index];
  const view = glb.json.bufferViews[desc.bufferView];
  const componentBytes = ({ 5121: 1, 5123: 2, 5125: 4, 5126: 4 })[desc.componentType];
  const componentCount = ({ SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 })[desc.type];
  const start = (view.byteOffset || 0) + (desc.byteOffset || 0);
  const length = desc.count * componentCount;
  if (desc.componentType === 5126) return new Float32Array(glb.binary.buffer, glb.binary.byteOffset + start, length);
  if (desc.componentType === 5125) return new Uint32Array(glb.binary.buffer, glb.binary.byteOffset + start, length);
  if (desc.componentType === 5123) return new Uint16Array(glb.binary.buffer, glb.binary.byteOffset + start, length);
  if (desc.componentType === 5121) return new Uint8Array(glb.binary.buffer, glb.binary.byteOffset + start, length);
  throw new Error(`Unsupported accessor component ${desc.componentType} ${componentBytes}`);
}

function findIslands(indices, vertexCount) {
  const parent = new Uint32Array(vertexCount);
  for (let i = 0; i < vertexCount; i++) parent[i] = i;
  const find = value => {
    let root = value;
    while (parent[root] !== root) root = parent[root];
    while (parent[value] !== value) { const next = parent[value]; parent[value] = root; value = next; }
    return root;
  };
  const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent[rb] = ra; };
  for (let i = 0; i < indices.length; i += 3) { union(indices[i], indices[i + 1]); union(indices[i + 1], indices[i + 2]); }
  const rootId = new Map();
  const vertexIsland = new Uint32Array(vertexCount);
  const vertices = [];
  const bounds = [];
  for (let i = 0; i < vertexCount; i++) {
    const root = find(i);
    let id = rootId.get(root);
    if (id === undefined) {
      id = vertices.length; rootId.set(root, id); vertices.push([]);
      bounds.push({ min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] });
    }
    vertexIsland[i] = id; vertices[id].push(i);
  }
  const faces = Array.from({ length: vertices.length }, () => []);
  for (let face = 0; face < indices.length / 3; face++) faces[vertexIsland[indices[face * 3]]].push(face);
  return { vertexIsland, vertices, faces, bounds };
}

function bboxDistance(point, bounds) {
  let sum = 0;
  for (let axis = 0; axis < 3; axis++) {
    const delta = point[axis] < bounds.min[axis] ? bounds.min[axis] - point[axis] : point[axis] > bounds.max[axis] ? point[axis] - bounds.max[axis] : 0;
    sum += delta * delta;
  }
  return Math.sqrt(sum);
}

function vecDistance(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
function add3(out, index, x, y, z) { out[index * 3] += x; out[index * 3 + 1] += y; out[index * 3 + 2] += z; }

function makeIslandMesh(name, positions, indices, topology, islandId, points, right, up, front, faceScale, vertexSubset = null, faceSubset = null) {
  const globalVertices = vertexSubset || topology.vertices[islandId];
  const globalToLocal = new Int32Array(positions.length / 3); globalToLocal.fill(-1);
  for (let i = 0; i < globalVertices.length; i++) globalToLocal[globalVertices[i]] = i;
  const localFaces = [];
  for (const face of faceSubset || topology.faces[islandId]) {
    const ia = globalToLocal[indices[face * 3]], ib = globalToLocal[indices[face * 3 + 1]], ic = globalToLocal[indices[face * 3 + 2]];
    if (ia >= 0 && ib >= 0 && ic >= 0) localFaces.push([ia, ib, ic]);
  }
  const neutral = new Float64Array(globalVertices.length * 3);
  for (let i = 0; i < globalVertices.length; i++) for (let axis = 0; axis < 3; axis++) neutral[i * 3 + axis] = positions[globalVertices[i] * 3 + axis];
  const mesh = { name, points, right, up, front, faceScale, neutral, faces: localFaces, globalVertices, allVertexCount: positions.length / 3, islandCount: topology.vertices.length, islandId, sourceIslandId: islandId, domainKind: vertexSubset ? 'connected-subpatch' : 'original-island' };
  mesh.system = buildSystem(mesh);
  return mesh;
}

function selectConnectedPatch(positions, indices, topology, islandId, seedPoints, targetVertexCount) {
  const sourceVertices = topology.vertices[islandId];
  const sourceFaces = topology.faces[islandId];
  if (targetVertexCount >= sourceVertices.length) return { vertices: sourceVertices, faces: sourceFaces };
  const globalToLocal = new Int32Array(positions.length / 3); globalToLocal.fill(-1);
  for (let local = 0; local < sourceVertices.length; local++) globalToLocal[sourceVertices[local]] = local;
  const adjacency = Array.from({ length: sourceVertices.length }, () => []);
  for (const face of sourceFaces) {
    const ga = indices[face * 3], gb = indices[face * 3 + 1], gc = indices[face * 3 + 2];
    const a = globalToLocal[ga], b = globalToLocal[gb], c = globalToLocal[gc];
    if (a < 0 || b < 0 || c < 0) continue;
    adjacency[a].push(b, c); adjacency[b].push(a, c); adjacency[c].push(a, b);
  }
  for (const neighbors of adjacency) neighbors.sort((a, b) => a - b);
  const seedPoint = seedPoints.reduce((sum, point) => sum.map((value, axis) => value + point[axis]), [0, 0, 0]).map(value => value / Math.max(seedPoints.length, 1));
  let seed = 0, seedDistance = Infinity;
  for (let local = 0; local < sourceVertices.length; local++) {
    const global = sourceVertices[local];
    const distance = Math.hypot(positions[global * 3] - seedPoint[0], positions[global * 3 + 1] - seedPoint[1], positions[global * 3 + 2] - seedPoint[2]);
    if (distance < seedDistance) { seed = local; seedDistance = distance; }
  }
  const selected = new Uint8Array(sourceVertices.length), queue = [seed]; selected[seed] = 1;
  for (let cursor = 0; cursor < queue.length && queue.length < targetVertexCount; cursor++) {
    for (const neighbor of adjacency[queue[cursor]]) {
      if (selected[neighbor]) continue;
      selected[neighbor] = 1; queue.push(neighbor);
      if (queue.length >= targetVertexCount) break;
    }
  }
  const vertices = queue.map(local => sourceVertices[local]);
  const selectedGlobal = new Uint8Array(positions.length / 3);
  for (const global of vertices) selectedGlobal[global] = 1;
  const faces = sourceFaces.filter(face => selectedGlobal[indices[face * 3]] && selectedGlobal[indices[face * 3 + 1]] && selectedGlobal[indices[face * 3 + 2]]);
  if (!faces.length) throw new Error(`Connected patch for island ${islandId} contains no complete triangles`);
  return { vertices, faces };
}

async function loadModel(name) {
  const [glbBuffer, attachmentText] = await Promise.all([fs.readFile(models[name].glb), fs.readFile(models[name].attachments, 'utf8')]);
  const glb = readGlb(glbBuffer);
  const primitive = glb.json.meshes[0].primitives[0];
  const positions = accessor(glb, primitive.attributes.POSITION);
  const indices = accessor(glb, primitive.indices);
  const attachments = JSON.parse(attachmentText).records.sort((a, b) => a.index - b.index);
  const points = attachments.map(record => [record.meshXYZ[0], record.meshXYZ[2], -record.meshXYZ[1]]);
  const right = [points[263][0] - points[33][0], points[263][2] - points[33][2], -(points[263][1] - points[33][1])];
  const rightLength = Math.hypot(...right); for (let i = 0; i < 3; i++) right[i] /= rightLength;
  const brow = [70, 63, 105, 336, 293, 334].reduce((sum, id) => sum.map((v, i) => v + points[id][i]), [0, 0, 0]).map(v => v / 6);
  const chin = [152, 175, 199, 396, 421, 428].reduce((sum, id) => sum.map((v, i) => v + points[id][i]), [0, 0, 0]).map(v => v / 6);
  const rawUp = chin.map((v, i) => -(v - brow[i]));
  const projection = rawUp[0] * right[0] + rawUp[1] * right[1] + rawUp[2] * right[2];
  const up = rawUp.map((v, i) => v - right[i] * projection);
  const upLength = Math.hypot(...up); for (let i = 0; i < 3; i++) up[i] /= upLength;
  let front = [right[1] * up[2] - right[2] * up[1], right[2] * up[0] - right[0] * up[2], right[0] * up[1] - right[1] * up[0]];
  const meanNormal = attachments.reduce((sum, record) => sum.map((v, i) => v + (record.surfaceNormal?.[i] || (i === 2 ? 1 : 0))), [0, 0, 0]);
  if (front[0] * meanNormal[0] + front[1] * meanNormal[2] + front[2] * -meanNormal[1] < 0) front = front.map(v => -v);
  const topology = findIslands(indices, positions.length / 3);
  for (let islandId = 0; islandId < topology.vertices.length; islandId++) {
    const bound = topology.bounds[islandId];
    for (const vertex of topology.vertices[islandId]) for (let axis = 0; axis < 3; axis++) {
      const value = positions[vertex * 3 + axis]; bound.min[axis] = Math.min(bound.min[axis], value); bound.max[axis] = Math.max(bound.max[axis], value);
    }
  }
  const browPoints = [70, 63, 105, 336, 293, 334].map(id => points[id]);
  let selectedId = 0, selectedScore = Infinity;
  for (let islandId = 0; islandId < topology.vertices.length; islandId++) {
    const score = browPoints.reduce((sum, point) => sum + bboxDistance([point[0], point[1], point[2]], topology.bounds[islandId]), 0);
    if (score < selectedScore) { selectedScore = score; selectedId = islandId; }
  }
  const faceScale = vecDistance(points[263], points[33]);
  const mesh = makeIslandMesh(name, positions, indices, topology, selectedId, points, right, up, front, faceScale);
  const screenPatch = selectConnectedPatch(positions, indices, topology, selectedId, browPoints, 1000);
  mesh.screenMesh = makeIslandMesh(`${name}-screen-facial-patch`, positions, indices, topology, selectedId, points, right, up, front, faceScale, screenPatch.vertices, screenPatch.faces);
  const microPatch = selectConnectedPatch(positions, indices, topology, selectedId, browPoints, 128);
  mesh.microMesh = makeIslandMesh(`${name}-micro-facial-patch`, positions, indices, topology, selectedId, points, right, up, front, faceScale, microPatch.vertices, microPatch.faces);
  return mesh;
}

function stressDomain(mesh) {
  const fidelity = process.env.VELA_CALIBRATION_STRESS_FIDELITY || 'micro';
  if (fidelity === 'full') return mesh;
  if (fidelity === 'screen') return mesh.screenMesh || mesh;
  return mesh.microMesh || mesh.screenMesh || mesh;
}

function buildSystem(mesh) {
  const { neutral, faces } = mesh;
  const vertexCount = neutral.length / 3;
  const edgeMap = new Map(), edgeA = [], edgeB = [], edgeRest = [];
  const key = (a, b) => a < b ? `${a}:${b}` : `${b}:${a}`;
  const faceAreas = new Float64Array(faces.length), faceNormals = new Float64Array(faces.length * 3);
  const attributedArea = new Float64Array(vertexCount);
  for (let fi = 0; fi < faces.length; fi++) {
    const [ia, ib, ic] = faces[fi];
    const ax = neutral[ia * 3], ay = neutral[ia * 3 + 1], az = neutral[ia * 3 + 2];
    const abx = neutral[ib * 3] - ax, aby = neutral[ib * 3 + 1] - ay, abz = neutral[ib * 3 + 2] - az;
    const acx = neutral[ic * 3] - ax, acy = neutral[ic * 3 + 1] - ay, acz = neutral[ic * 3 + 2] - az;
    const nx = aby * acz - abz * acy, ny = abz * acx - abx * acz, nz = abx * acy - aby * acx, length = Math.hypot(nx, ny, nz);
    faceAreas[fi] = length * 0.5; if (length > 1e-15) { faceNormals[fi * 3] = nx / length; faceNormals[fi * 3 + 1] = ny / length; faceNormals[fi * 3 + 2] = nz / length; }
    const areaM2 = faceAreas[fi] * sourceMetersPerUnit ** 2;
    attributedArea[ia] += areaM2 / 3; attributedArea[ib] += areaM2 / 3; attributedArea[ic] += areaM2 / 3;
    for (const [a, b] of [[ia, ib], [ib, ic], [ic, ia]]) {
      const edgeKey = key(a, b); if (edgeMap.has(edgeKey)) continue;
      edgeMap.set(edgeKey, edgeA.length); edgeA.push(Math.min(a, b)); edgeB.push(Math.max(a, b));
      edgeRest.push(Math.hypot(neutral[a * 3] - neutral[b * 3], neutral[a * 3 + 1] - neutral[b * 3 + 1], neutral[a * 3 + 2] - neutral[b * 3 + 2]));
    }
  }
  const adjacency = Array.from({ length: vertexCount }, () => []);
  for (let i = 0; i < edgeA.length; i++) { adjacency[edgeA[i]].push(edgeB[i]); adjacency[edgeB[i]].push(edgeA[i]); }
  const edgeFaces = new Map();
  for (let fi = 0; fi < faces.length; fi++) {
    const [ia, ib, ic] = faces[fi];
    for (const [a, b] of [[ia, ib], [ib, ic], [ic, ia]]) {
      const edgeKey = key(a, b); const list = edgeFaces.get(edgeKey) || []; list.push(fi); edgeFaces.set(edgeKey, list);
    }
  }
  const faceNeighbors = Array.from({ length: faces.length }, () => new Set());
  for (const list of edgeFaces.values()) for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) { faceNeighbors[list[i]].add(list[j]); faceNeighbors[list[j]].add(list[i]); }
  const normals = new Float64Array(vertexCount * 3);
  for (let fi = 0; fi < faces.length; fi++) for (const vertex of faces[fi]) { normals[vertex * 3] += faceNormals[fi * 3]; normals[vertex * 3 + 1] += faceNormals[fi * 3 + 1]; normals[vertex * 3 + 2] += faceNormals[fi * 3 + 2]; }
  for (let i = 0; i < vertexCount; i++) { const length = Math.hypot(normals[i * 3], normals[i * 3 + 1], normals[i * 3 + 2]) || 1; normals[i * 3] /= length; normals[i * 3 + 1] /= length; normals[i * 3 + 2] /= length; }
  const anchors = new Float64Array(vertexCount * 3);
  const sortedEdges = [...edgeRest].sort((a, b) => a - b); const medianEdge = sortedEdges[Math.floor(sortedEdges.length / 2)] || mesh.faceScale * 0.005;
  let orientation = 0; const centroid = [0, 0, 0];
  for (let i = 0; i < vertexCount; i++) for (let axis = 0; axis < 3; axis++) centroid[axis] += neutral[i * 3 + axis];
  for (let axis = 0; axis < 3; axis++) centroid[axis] /= vertexCount;
  for (let i = 0; i < vertexCount; i++) orientation += normals[i * 3] * (neutral[i * 3] - centroid[0]) + normals[i * 3 + 1] * (neutral[i * 3 + 1] - centroid[1]) + normals[i * 3 + 2] * (neutral[i * 3 + 2] - centroid[2]);
  const orientationSign = orientation >= 0 ? 1 : -1;
  for (let i = 0; i < vertexCount; i++) { anchors[i * 3] = neutral[i * 3] - orientationSign * normals[i * 3] * medianEdge * anchorDepthFactor; anchors[i * 3 + 1] = neutral[i * 3 + 1] - orientationSign * normals[i * 3 + 1] * medianEdge * anchorDepthFactor; anchors[i * 3 + 2] = neutral[i * 3 + 2] - orientationSign * normals[i * 3 + 2] * medianEdge * anchorDepthFactor; }
  const systems = { vertexCount, faces, neutral, anchors, faceAreas, faceNormals, attributedArea, edgeA: Uint32Array.from(edgeA), edgeB: Uint32Array.from(edgeB), edgeRest: Float64Array.from(edgeRest), adjacency, faceNeighbors: faceNeighbors.map(neighbors => Array.from(neighbors)), medianEdge };
  return systems;
}

// Offline physical search bounds. Mass multipliers above 1 are explicitly effective
// numerical masses, not claims about anatomical density. The ranges keep the search
// near the biological baseline while allowing a documented numerical calibration.
const defaultLogBounds = [[-0.3, 0.3], [-1, 1], [-2, 2], [-1, 5], [-5, 1], [-3, 1], [-3, 1]];
const legacyLogBounds = [[0, 8], [-2, 2], [-2, 4], [-1, 2], [-1, 1], [-1, 1], [-1, 1]];
function createCandidate(logs, bounds = defaultLogBounds) {
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  const bounded = Array.from({ length: 7 }, (_, index) => clamp(Number(logs[index] ?? 0), bounds[index]?.[0] ?? defaultLogBounds[index][0], bounds[index]?.[1] ?? defaultLogBounds[index][1]));
  return {
    massMultiplier: 10 ** bounded[0],
    surfaceMultiplier: 10 ** bounded[1],
    innerMultiplier: 10 ** bounded[2],
    dampingMultiplier: 10 ** bounded[3],
    dtMultiplier: 10 ** bounded[4],
    pinchKpMultiplier: 10 ** bounded[5],
    pinchKdMultiplier: 10 ** bounded[6],
    logParameters: bounded,
  };
}

function preparePhysics(mesh, candidate) {
  const cacheKey = `${mesh.name}|${candidateKey(candidate)}`;
  const cached = preparedPhysicsCache.get(cacheKey);
  if (cached) return cached;
  const base = mesh.system, n = base.vertexCount;
  const surfaceK = 30000 * 0.0015 * candidate.surfaceMultiplier;
  const innerModulus = 10000 * candidate.innerMultiplier;
  const masses = new Float64Array(n);
  let totalMass = 0, minMass = Infinity;
  for (let i = 0; i < n; i++) { masses[i] = 1100 * 0.0015 * base.attributedArea[i] * candidate.massMultiplier; totalMass += masses[i]; minMass = Math.min(minMass, masses[i]); }
  const positive = [...masses].sort((a, b) => a - b); const medianMass = positive[Math.floor(n / 2)];
  const supportA = [], supportB = [], supportRest = [], supportK = [];
  for (let i = 0; i < n; i++) {
    const neighbors = [...new Set(base.adjacency[i])].sort((a, b) => {
      const da = Math.hypot(base.neutral[a * 3] - base.neutral[i * 3], base.neutral[a * 3 + 1] - base.neutral[i * 3 + 1], base.neutral[a * 3 + 2] - base.neutral[i * 3 + 2]);
      const db = Math.hypot(base.neutral[b * 3] - base.neutral[i * 3], base.neutral[b * 3 + 1] - base.neutral[i * 3 + 1], base.neutral[b * 3 + 2] - base.neutral[i * 3 + 2]); return da - db;
    }).slice(0, neighborAnchorCount);
    const tetherCount = 1 + neighbors.length, foundationK = innerModulus * base.attributedArea[i] / 0.005, perTether = foundationK / tetherCount;
    supportA.push(i); supportB.push(i); supportRest.push(Math.hypot(base.neutral[i * 3] - base.anchors[i * 3], base.neutral[i * 3 + 1] - base.anchors[i * 3 + 1], base.neutral[i * 3 + 2] - base.anchors[i * 3 + 2])); supportK.push(perTether);
    for (const neighbor of neighbors) { supportA.push(i); supportB.push(neighbor); supportRest.push(Math.hypot(base.neutral[i * 3] - base.anchors[neighbor * 3], base.neutral[i * 3 + 1] - base.anchors[neighbor * 3 + 1], base.neutral[i * 3 + 2] - base.anchors[neighbor * 3 + 2])); supportK.push(perTether); }
  }
  let maxDegree = 1; for (const neighbors of base.adjacency) maxDegree = Math.max(maxDegree, neighbors.length);
  const localK = new Float64Array(n);
  for (let i = 0; i < base.edgeA.length; i++) { localK[base.edgeA[i]] += surfaceK; localK[base.edgeB[i]] += surfaceK; }
  for (let i = 0; i < supportA.length; i++) localK[supportA[i]] += supportK[i];
  let maxLocalK = 0; for (const value of localK) maxLocalK = Math.max(maxLocalK, value);
  const requestedDt = baseDt * candidate.dtMultiplier;
  const damping = 0.08 * candidate.dampingMultiplier * 2 * Math.sqrt(Math.max(surfaceK * medianMass, 1e-18));
  const springStabilityEstimateDt = 0.12 * Math.sqrt(minMass / Math.max(maxLocalK, 1e-18));
  const dampingRate = damping / Math.max(minMass, 1e-18);
  const dampingStabilityEstimateDt = 0.12 / Math.max(dampingRate, 1e-18);
  const stabilityEstimateDt = Math.min(springStabilityEstimateDt, dampingStabilityEstimateDt);
  const stableDt = Math.min(requestedDt, stabilityEstimateDt * empiricalStabilityMultiplier);
  const prepared = { ...base, masses, surfaceK, supportA: Uint32Array.from(supportA), supportB: Uint32Array.from(supportB), supportRest: Float64Array.from(supportRest), supportK: Float64Array.from(supportK), stableDt, stabilityEstimateDt, springStabilityEstimateDt, dampingStabilityEstimateDt, dampingRate, empiricalStabilityMultiplier, requestedDt, timestepLimitedByEstimate: requestedDt > stableDt, damping, totalMass, minMass, medianMass, maxLocalK, explicitSubsteps: Math.max(1, Math.ceil(frameDt / Math.max(stableDt, 1e-18))) };
  preparedPhysicsCache.set(cacheKey, prepared);
  return prepared;
}

function quantile(values, fraction) {
  const sorted = Array.from(values).sort((a, b) => a - b);
  if (!sorted.length) return 0;
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.floor(fraction * sorted.length)))];
}

function domainAudit(mesh, candidate) {
  const prepared = preparePhysics(mesh, candidate), base = mesh.system;
  const faceAreas = base.faceAreas;
  const edgeRest = base.edgeRest;
  const areaRatios = [];
  for (let i = 0; i < faceAreas.length; i++) areaRatios.push(faceAreas[i]);
  const massValues = Array.from(prepared.masses);
  const edgeValues = Array.from(edgeRest);
  let zeroAreaFaces = 0;
  for (const area of faceAreas) if (area <= 1e-15) zeroAreaFaces++;
  const minValue = values => values.reduce((minimum, value) => Math.min(minimum, value), Infinity);
  const maxValue = values => values.reduce((maximum, value) => Math.max(maximum, value), -Infinity);
  return {
    domain: mesh.name,
    domainKind: mesh.domainKind,
    sourceIslandId: mesh.sourceIslandId,
    vertices: prepared.vertexCount,
    triangles: base.faces.length,
    surfaceSprings: prepared.edgeA.length,
    supportSprings: prepared.supportA.length,
    zeroAreaFaces,
    faceArea: { min: minValue(areaRatios), p01: quantile(areaRatios, 0.01), median: quantile(areaRatios, 0.5), p99: quantile(areaRatios, 0.99), max: maxValue(areaRatios) },
    edgeRestLength: { min: minValue(edgeValues), p01: quantile(edgeValues, 0.01), median: quantile(edgeValues, 0.5), p99: quantile(edgeValues, 0.99), max: maxValue(edgeValues) },
    massKg: { min: minValue(massValues), p01: quantile(massValues, 0.01), median: quantile(massValues, 0.5), p99: quantile(massValues, 0.99), max: maxValue(massValues), total: prepared.totalMass },
    localStiffness: { max: prepared.maxLocalK },
    damping: { coefficientNsPerM: prepared.damping, ratePerSecondAtMinMass: prepared.dampingRate, springStabilityEstimateDt: prepared.springStabilityEstimateDt, dampingStabilityEstimateDt: prepared.dampingStabilityEstimateDt },
    requestedDt: prepared.requestedDt,
    stabilityEstimateDt: prepared.stabilityEstimateDt,
    empiricalStabilityMultiplier: prepared.empiricalStabilityMultiplier,
    explicitSubstepsPerFrame: prepared.explicitSubsteps,
    timestepLimitedByEstimate: prepared.timestepLimitedByEstimate,
    parameterInterpretation: { massMultiplier: candidate.massMultiplier, surfaceMultiplier: candidate.surfaceMultiplier, innerMultiplier: candidate.innerMultiplier, effectiveMassNotAnatomicalDensity: true },
  };
}

function simulate(model, candidate, options = {}) {
  const simulationStarted = performance.now(), system = preparePhysics(model, candidate), n = system.vertexCount, length = n * 3;
  const positions = new Float64Array(options.initialPositions || system.neutral), velocities = new Float64Array(options.initialVelocities || length), a1 = new Float64Array(length), a2 = new Float64Array(length), a3 = new Float64Array(length), a4 = new Float64Array(length), x2 = new Float64Array(length), x3 = new Float64Array(length), x4 = new Float64Array(length), v2 = new Float64Array(length), v3 = new Float64Array(length), v4 = new Float64Array(length), forceN = new Float64Array(length);
  const gravity = options.gravity || [0, 0, 0]; const seconds = options.seconds ?? 0.05; const usePinch = options.pinch || null;
  const substepsPerFrame = options.substepsOverride || system.explicitSubsteps; const defaultH = options.timeStepOverride || system.stableDt; const wallClockLimitMs = options.wallClockLimitMs ?? Infinity;
  const neutral = system.neutral, edgeCount = system.edgeA.length; let forceEvaluations = 0;
  const forces = (x, v, out) => {
    forceEvaluations++;
    out.fill(0);
    for (let i = 0; i < edgeCount; i++) {
      const ia = system.edgeA[i], ib = system.edgeB[i], ia3 = ia * 3, ib3 = ib * 3;
      const dx = x[ib3] - x[ia3], dy = x[ib3 + 1] - x[ia3 + 1], dz = x[ib3 + 2] - x[ia3 + 2];
      const len = Math.sqrt(dx * dx + dy * dy + dz * dz); if (len <= 1e-12) continue;
      const q = system.surfaceK * ((len - system.edgeRest[i]) * sourceMetersPerUnit) / len;
      const fx = q * dx, fy = q * dy, fz = q * dz;
      out[ia3] += fx; out[ia3 + 1] += fy; out[ia3 + 2] += fz;
      out[ib3] -= fx; out[ib3 + 1] -= fy; out[ib3 + 2] -= fz;
    }
    for (let i = 0; i < system.supportA.length; i++) {
      const ia = system.supportA[i], ib = system.supportB[i], ia3 = ia * 3, ib3 = ib * 3;
      const dx = system.anchors[ib3] - x[ia3], dy = system.anchors[ib3 + 1] - x[ia3 + 1], dz = system.anchors[ib3 + 2] - x[ia3 + 2];
      const len = Math.sqrt(dx * dx + dy * dy + dz * dz); if (len <= 1e-12) continue;
      const q = system.supportK[i] * ((len - system.supportRest[i]) * sourceMetersPerUnit) / len;
      out[ia3] += q * dx; out[ia3 + 1] += q * dy; out[ia3 + 2] += q * dz;
    }
    if (usePinch) {
      const { ids, weights, target, velocity, kp, kd } = usePinch; let qx = 0, qy = 0, qz = 0, qvx = 0, qvy = 0, qvz = 0;
      for (let j = 0; j < 3; j++) { const id = ids[j]; qx += weights[j] * x[id * 3]; qy += weights[j] * x[id * 3 + 1]; qz += weights[j] * x[id * 3 + 2]; qvx += weights[j] * v[id * 3]; qvy += weights[j] * v[id * 3 + 1]; qvz += weights[j] * v[id * 3 + 2]; }
      const force = [kp * ((target[0] - qx) * sourceMetersPerUnit) + kd * ((velocity[0] - qvx) * sourceMetersPerUnit), kp * ((target[1] - qy) * sourceMetersPerUnit) + kd * ((velocity[1] - qvy) * sourceMetersPerUnit), kp * ((target[2] - qz) * sourceMetersPerUnit) + kd * ((velocity[2] - qvz) * sourceMetersPerUnit)];
      usePinch.force = force; usePinch.error = Math.hypot((target[0] - qx) * sourceMetersPerUnit, (target[1] - qy) * sourceMetersPerUnit, (target[2] - qz) * sourceMetersPerUnit); usePinch.peakForce = Math.max(usePinch.peakForce || 0, Math.hypot(...force));
      for (let j = 0; j < 3; j++) { const id = ids[j], w = weights[j]; add3(out, id, w * force[0], w * force[1], w * force[2]); }
    }
    for (let i = 0; i < n; i++) { add3(out, i, system.masses[i] * gravity[0] - system.damping * v[i * 3] * sourceMetersPerUnit, system.masses[i] * gravity[1] - system.damping * v[i * 3 + 1] * sourceMetersPerUnit, system.masses[i] * gravity[2] - system.damping * v[i * 3 + 2] * sourceMetersPerUnit); }
  };
  const acceleration = (x, v, out) => { forces(x, v, forceN); for (let i = 0; i < length; i++) out[i] = forceN[i] / system.masses[Math.floor(i / 3)] / sourceMetersPerUnit; };
  let nonfinite = false, wallClockExceeded = false, maxVelocity = 0, steps = 0, elapsed = 0;
  const rk4 = h => {
    acceleration(positions, velocities, a1);
    for (let i = 0; i < length; i++) { x2[i] = positions[i] + velocities[i] * h * 0.5; v2[i] = velocities[i] + a1[i] * h * 0.5; }
    acceleration(x2, v2, a2);
    for (let i = 0; i < length; i++) { x3[i] = positions[i] + v2[i] * h * 0.5; v3[i] = velocities[i] + a2[i] * h * 0.5; }
    acceleration(x3, v3, a3);
    for (let i = 0; i < length; i++) { x4[i] = positions[i] + v3[i] * h; v4[i] = velocities[i] + a3[i] * h; }
    acceleration(x4, v4, a4);
    for (let i = 0; i < length; i++) { positions[i] += h * (velocities[i] + 2 * v2[i] + 2 * v3[i] + v4[i]) / 6; velocities[i] += h * (a1[i] + 2 * a2[i] + 2 * a3[i] + a4[i]) / 6; if (!Number.isFinite(positions[i]) || !Number.isFinite(velocities[i])) nonfinite = true; }
    for (let i = 0; i < length; i += 3) maxVelocity = Math.max(maxVelocity, Math.hypot(velocities[i], velocities[i + 1], velocities[i + 2]));
    steps++;
  };
  while (elapsed < seconds - 1e-15 && !nonfinite) {
    if (performance.now() - simulationStarted >= wallClockLimitMs) { wallClockExceeded = true; break; }
    const h = Math.min(defaultH, seconds - elapsed); rk4(h); elapsed += h;
  }
  forces(positions, velocities, forceN);
  let maxNetForce = 0, forceRms = 0, finalVelocity = 0, velocityRms = 0;
  for (let i = 0; i < n; i++) { const fm = Math.hypot(forceN[i * 3], forceN[i * 3 + 1], forceN[i * 3 + 2]); const vm = Math.hypot(velocities[i * 3], velocities[i * 3 + 1], velocities[i * 3 + 2]); maxNetForce = Math.max(maxNetForce, fm); forceRms += fm * fm; finalVelocity = Math.max(finalVelocity, vm); velocityRms += vm * vm; }
  const geometry = geometryMetrics(system, positions);
  const maxDisplacement = maxVertexDisplacement(neutral, positions);
  const totalGravityForce = system.totalMass * Math.hypot(...gravity);
  return { positions, velocities, system, geometry: { ...geometry, maxDisplacement, maxVelocity, finalVelocity, normalizedVelocity: finalVelocity * frameDt / Math.max(model.faceScale, 1e-12), maxNetForceN: maxNetForce, rmsNetForceN: Math.sqrt(forceRms / Math.max(n, 1)), forceResidualRatio: maxNetForce / Math.max(totalGravityForce / Math.max(n, 1), 1e-12) }, steps, seconds: elapsed, complete: !nonfinite && !wallClockExceeded && elapsed >= seconds - 1e-15, nonfinite, wallClockExceeded, pinch: usePinch ? { ...usePinch } : null, runtimeMs: performance.now() - simulationStarted, forceEvaluations };
}

function maxVertexDisplacement(a, b) { let max = 0; for (let i = 0; i < a.length; i += 3) max = Math.max(max, Math.hypot(b[i] - a[i], b[i + 1] - a[i + 1], b[i + 2] - a[i + 2])); return max; }
function geometryMetrics(system, positions) {
  const strains = new Float64Array(system.edgeA.length); let maxStrain = 0;
  for (let i = 0; i < system.edgeA.length; i++) { const a = system.edgeA[i] * 3, b = system.edgeB[i] * 3, len = Math.hypot(positions[b] - positions[a], positions[b + 1] - positions[a + 1], positions[b + 2] - positions[a + 2]); strains[i] = Math.abs(len - system.edgeRest[i]) / Math.max(system.edgeRest[i], 1e-12); maxStrain = Math.max(maxStrain, strains[i]); }
  const sorted = [...strains].sort((a, b) => a - b); const p95 = sorted[Math.floor(sorted.length * 0.95)] || 0; let flips = 0, collapses = 0, minAreaRatio = Infinity;
  for (let fi = 0; fi < system.faces.length; fi++) {
    const [ia, ib, ic] = system.faces[fi], a = ia * 3, b = ib * 3, c = ic * 3;
    const abx = positions[b] - positions[a], aby = positions[b + 1] - positions[a + 1], abz = positions[b + 2] - positions[a + 2], acx = positions[c] - positions[a], acy = positions[c + 1] - positions[a + 1], acz = positions[c + 2] - positions[a + 2];
    const nx = aby * acz - abz * acy, ny = abz * acx - abx * acz, nz = abx * acy - aby * acx, area = Math.hypot(nx, ny, nz) * 0.5, ratio = area / Math.max(system.faceAreas[fi], 1e-18); minAreaRatio = Math.min(minAreaRatio, ratio); if (ratio < 1e-3) collapses++; const dot = nx * system.faceNormals[fi * 3] + ny * system.faceNormals[fi * 3 + 1] + nz * system.faceNormals[fi * 3 + 2]; if (dot < 0) flips++;
  }
  const currentNormals = new Float64Array(system.faces.length * 3);
  for (let fi = 0; fi < system.faces.length; fi++) {
    const [ia, ib, ic] = system.faces[fi], a = ia * 3, b = ib * 3, c = ic * 3;
    const abx = positions[b] - positions[a], aby = positions[b + 1] - positions[a + 1], abz = positions[b + 2] - positions[a + 2];
    const acx = positions[c] - positions[a], acy = positions[c + 1] - positions[a + 1], acz = positions[c + 2] - positions[a + 2];
    const nx = aby * acz - abz * acy, ny = abz * acx - abx * acz, nz = abx * acy - aby * acx, length = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
    currentNormals[fi * 3] = nx / length; currentNormals[fi * 3 + 1] = ny / length; currentNormals[fi * 3 + 2] = nz / length;
  }
  const genuineFoldFaces = [];
  for (let fi = 0; fi < system.faces.length; fi++) {
    const neighbors = system.faceNeighbors?.[fi] || [];
    if (!neighbors.length) continue;
    let ax = 0, ay = 0, az = 0;
    for (const neighbor of neighbors) { ax += currentNormals[neighbor * 3]; ay += currentNormals[neighbor * 3 + 1]; az += currentNormals[neighbor * 3 + 2]; }
    const averageLength = Math.sqrt(ax * ax + ay * ay + az * az);
    if (averageLength > 1e-12) {
      const neighborDot = (currentNormals[fi * 3] * ax + currentNormals[fi * 3 + 1] * ay + currentNormals[fi * 3 + 2] * az) / averageLength;
      if (neighborDot < 0) genuineFoldFaces.push(fi);
    }
  }
  return { maxEdgeStrain: maxStrain, p95EdgeStrain: p95, orientationFlips: flips, genuineFolds: genuineFoldFaces.length, genuineFoldFaces, collapsedTriangles: collapses, minAreaRatio, finite: positions.every(Number.isFinite) };
}

function directions(mesh) {
  return {
    down: mesh.up.map(v => -v), up: mesh.up, left: mesh.right.map(v => -v), right: mesh.right, forward: mesh.front, backward: mesh.front.map(v => -v),
  };
}

function gravityTest(mesh, candidate, seconds, fidelity = 'full', wallClockLimitMs = offlineModelWallMs) {
  const results = {};
  const testedDirections = fidelity === 'screen' || fidelity === 'micro' ? ['down'] : gravityDirections;
  for (const direction of testedDirections) {
    const unit = directions(mesh)[direction]; const result = simulate(mesh, candidate, { gravity: unit.map(v => v * 9.81), seconds, wallClockLimitMs });
    results[direction] = { geometry: result.geometry, steps: result.steps, simulatedSeconds: result.seconds, complete: result.complete, wallClockExceeded: result.wallClockExceeded, wallMs: result.runtimeMs, settled: result.complete && result.geometry.normalizedVelocity <= maxNormalizedVelocity && result.geometry.forceResidualRatio <= maxForceResidualRatio };
  }
  const all = Object.values(results); return { directions: results, worstFlips: Math.max(...all.map(v => v.geometry.orientationFlips)), worstCollapses: Math.max(...all.map(v => v.geometry.collapsedTriangles)), worstStrain: Math.max(...all.map(v => v.geometry.maxEdgeStrain)), maxDisplacement: Math.max(...all.map(v => v.geometry.maxDisplacement)), maxVelocity: Math.max(...all.map(v => v.geometry.maxVelocity)), maxFinalVelocity: Math.max(...all.map(v => v.geometry.finalVelocity)), maxForceResidualRatio: Math.max(...all.map(v => v.geometry.forceResidualRatio)), allComplete: all.every(v => v.complete), allSettled: all.every(v => v.settled), finite: all.every(v => v.geometry.finite), fidelity };
}

function forceResponse(mesh, candidate, wallClockLimitMs = offlineModelWallMs) {
  const system = preparePhysics(mesh, candidate), face = system.faces[Math.floor(system.faces.length / 2)], ids = face, weights = [1 / 3, 1 / 3, 1 / 3];
  const origin = [0, 0, 0]; for (let j = 0; j < 3; j++) for (let axis = 0; axis < 3; axis++) origin[axis] += weights[j] * system.neutral[ids[j] * 3 + axis];
  const target = origin.slice(); target[1] += mesh.faceScale * 0.001;
  const result = simulate(mesh, candidate, { gravity: [0, 0, 0], seconds: 0.02, wallClockLimitMs, pinch: { ids, weights, target, velocity: [0, 0, 0], kp: 90 * candidate.pinchKpMultiplier, kd: 0.08 * candidate.pinchKdMultiplier, peakForce: 0 } });
  return { displacement: result.geometry.maxDisplacement, targetMeters: mesh.faceScale * 0.001 * sourceMetersPerUnit, finite: result.geometry.finite, flips: result.geometry.orientationFlips, strain: result.geometry.maxEdgeStrain, forceN: result.pinch?.peakForce || 0 };
}

function convergenceTest(mesh, candidate, requestedSeconds = 0.03333333333333333, wallClockLimitMs = offlineModelWallMs, startingMultiplier = null) {
  const gravity = directions(mesh).down.map(v => v * 9.81);
  const seconds = requestedSeconds;
  const prepared = preparePhysics(mesh, candidate);
  const stableDt = prepared.stabilityEstimateDt * (startingMultiplier ?? empiricalStabilityMultiplier);
  const solves = [stableDt, stableDt * 0.5, stableDt * 0.25].map(timeStepOverride => simulate(mesh, candidate, { gravity, seconds, timeStepOverride, wallClockLimitMs }));
  const compare = (a, b) => { let sumP = 0, sumV = 0, maxP = 0, maxV = 0; for (let i = 0; i < a.positions.length; i += 3) { const dp = Math.hypot(a.positions[i] - b.positions[i], a.positions[i + 1] - b.positions[i + 1], a.positions[i + 2] - b.positions[i + 2]); const dv = Math.hypot(a.velocities[i] - b.velocities[i], a.velocities[i + 1] - b.velocities[i + 1], a.velocities[i + 2] - b.velocities[i + 2]); sumP += dp * dp; sumV += dv * dv; maxP = Math.max(maxP, dp); maxV = Math.max(maxV, dv); } return { rmsPositionSource: Math.sqrt(sumP / (a.positions.length / 3)), maxPositionSource: maxP, rmsVelocitySource: Math.sqrt(sumV / (a.positions.length / 3)), maxVelocitySource: maxV }; };
  const hVsH2 = compare(solves[0], solves[1]), h2VsH4 = compare(solves[1], solves[2]);
  const positionOrder = h2VsH4.rmsPositionSource > 0 ? hVsH2.rmsPositionSource / h2VsH4.rmsPositionSource : Infinity;
  const velocityOrder = h2VsH4.rmsVelocitySource > 0 ? hVsH2.rmsVelocitySource / h2VsH4.rmsVelocitySource : Infinity;
  return { durationSeconds: seconds, steps: solves.map(result => result.steps), timeSteps: [stableDt, stableDt * 0.5, stableDt * 0.25], hVsH2, h2VsH4, positionOrder, velocityOrder, complete: solves.every(result => result.complete), converged: solves.every(result => result.complete) && h2VsH4.rmsPositionSource / Math.max(mesh.faceScale, 1e-12) < convergenceTolerance && h2VsH4.rmsVelocitySource * frameDt / Math.max(mesh.faceScale, 1e-12) < convergenceTolerance, samples: solves.map(result => ({ orientationFlips: result.geometry.orientationFlips, collapsedTriangles: result.geometry.collapsedTriangles, finalVelocity: result.geometry.finalVelocity, maxNetForceN: result.geometry.maxNetForceN, complete: result.complete, wallClockExceeded: result.wallClockExceeded })) };
}

function timestepRangeTest(mesh, candidate, seconds, wallClockLimitMs = offlineModelWallMs, factors = [4, 2, 1, 0.5, 0.25]) {
  const h = preparePhysics(mesh, candidate).stableDt;
  const samples = factors.map(factor => {
    const result = simulate(mesh, candidate, { gravity: directions(mesh).down.map(v => v * 9.81), seconds: Math.min(seconds, 0.02), timeStepOverride: h * factor, wallClockLimitMs });
    return { factor, timeStep: h * factor, steps: result.steps, complete: result.complete, wallClockExceeded: result.wallClockExceeded, finite: result.geometry.finite, orientationFlips: result.geometry.orientationFlips, collapsedTriangles: result.geometry.collapsedTriangles, maxStrain: result.geometry.maxEdgeStrain, finalVelocity: result.geometry.finalVelocity, forceResidualRatio: result.geometry.forceResidualRatio };
  });
  const stable = samples.filter(sample => sample.finite && sample.orientationFlips === 0 && sample.collapsedTriangles === 0);
  return { startingEstimate: h, samples, largestTestedStableMultiplier: stable.length ? Math.max(...stable.map(sample => sample.factor)) : null, smallestTestedStableMultiplier: stable.length ? Math.min(...stable.map(sample => sample.factor)) : null };
}

function randomPinchStress(mesh, candidate, count = 20, stressSeed = seed, options = {}) {
  const random = rng(stressSeed), system = preparePhysics(mesh, candidate), results = [];
  const directionsByName = directions(mesh);
  const directionNames = Object.keys(directionsByName);
  const started = performance.now();
  const holdSeconds = options.holdSeconds ?? stressHoldSeconds;
  const releaseSeconds = options.releaseSeconds ?? stressReleaseSeconds;
  const wallClockLimitMs = options.wallClockLimitMs ?? offlineModelWallMs;
  const startSequence = Math.max(0, Number(options.startSequence || 0));
  for (let skipped = 0; skipped < startSequence * 5; skipped++) random();
  for (let sequence = 0; sequence < count; sequence++) {
    const face = system.faces[Math.floor(random() * system.faces.length)], ids = face.slice();
    let u = random(), v = random(); if (u + v > 1) { u = 1 - u; v = 1 - v; }
    const weights = [1 - u - v, u, v], origin = [0, 0, 0];
    for (let j = 0; j < 3; j++) for (let axis = 0; axis < 3; axis++) origin[axis] += weights[j] * system.neutral[ids[j] * 3 + axis];
    const directionName = directionNames[Math.floor(random() * directionNames.length)];
    const direction = directionsByName[directionName];
    const magnitude = mesh.faceScale * (0.002 + random() * 0.01), target = origin.map((value, axis) => value + direction[axis] * magnitude);
    let positions = new Float64Array(system.neutral), velocities = new Float64Array(system.vertexCount * 3), heldGeometry = null, maxForce = 0, maxTrackingError = 0, invalid = false, heldComplete = true;
    for (let phase = 1; phase <= 4; phase++) {
      const phaseTarget = origin.map((value, axis) => value + (target[axis] - value) * phase / 4);
      const pin = { ids, weights, target: phaseTarget, velocity: direction.map(value => value * magnitude * 4), kp: 90 * candidate.pinchKpMultiplier, kd: 0.08 * candidate.pinchKdMultiplier, peakForce: 0 };
      const segment = simulate(mesh, candidate, { gravity: direction.map(value => value * 9.81), seconds: holdSeconds, initialPositions: positions, initialVelocities: velocities, pinch: pin, wallClockLimitMs });
      positions = segment.positions; velocities = segment.velocities; heldGeometry = segment.geometry; heldComplete &&= segment.complete && !segment.wallClockExceeded; maxForce = Math.max(maxForce, pin.peakForce || 0); maxTrackingError = Math.max(maxTrackingError, pin.error || 0); invalid ||= segment.nonfinite || segment.geometry.genuineFolds > 0 || segment.geometry.collapsedTriangles > 0;
    }
    const release = simulate(mesh, candidate, { gravity: direction.map(value => value * 9.81), seconds: releaseSeconds, initialPositions: positions, initialVelocities: velocities, wallClockLimitMs });
    const recoveredDisplacement = maxVertexDisplacement(system.neutral, release.positions);
    const segmentsComplete = heldComplete && release.complete && !release.wallClockExceeded;
    results.push({ sequence: sequence + startSequence, face, direction: directionName, magnitudeSource: magnitude, held: heldGeometry, released: release.geometry, heldComplete, releaseComplete: release.complete, wallClockExceeded: Boolean(!heldComplete || release.wallClockExceeded), recoveredDisplacement, peakForceN: maxForce, peakTrackingErrorMeters: maxTrackingError, valid: !invalid && segmentsComplete && release.geometry.finite && release.geometry.genuineFolds === 0 && release.geometry.collapsedTriangles === 0 });
  }
  return { count, holdSeconds, releaseSeconds, valid: results.every(result => result.valid), results, runtimeMs: performance.now() - started };
}

function candidateFromEnvironment(base = createCandidate([0, 0, 0, 2, -1, -1, -2])) {
  const updates = {};
  for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
  return withParameterBlock(base, updates);
}

async function runParallelStress() {
  const checkpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
  const candidate = candidateFromEnvironment(checkpoint?.current || undefined);
  const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 20));
  const workerCount = Math.max(1, Math.min(Number(process.env.VELA_CALIBRATION_STRESS_WORKERS || 4), count));
  const requestedChunkSize = Number(process.env.VELA_CALIBRATION_STRESS_CHUNK_SIZE || 0);
  const fidelity = process.env.VELA_CALIBRATION_STRESS_FIDELITY || 'full';
  const ranges = [];
  for (const modelName of requestedModels) {
    const modelIndex = requestedModels.indexOf(modelName);
    const chunk = requestedChunkSize > 0 ? Math.min(requestedChunkSize, count) : Math.ceil(count / workerCount);
    for (let start = 0; start < count; start += chunk) ranges.push({ modelName, modelIndex, start, count: Math.min(chunk, count - start) });
  }
  const workerResults = await Promise.all(ranges.map(range => new Promise((resolve, reject) => {
    const env = { ...process.env, VELA_CALIBRATION_MODELS: range.modelName, VELA_CALIBRATION_STRESS_FIDELITY: fidelity, VELA_CALIBRATION_STRESS_COUNT: String(range.count), VELA_CALIBRATION_STRESS_START: String(range.start), VELA_CALIBRATION_STRESS_MODEL_INDEX: String(range.modelIndex), ...Object.fromEntries(candidate.logParameters.map((value, index) => [
      ['VELA_CALIBRATION_MASS_LOG', 'VELA_CALIBRATION_SURFACE_LOG', 'VELA_CALIBRATION_INNER_LOG', 'VELA_CALIBRATION_DAMPING_LOG', 'VELA_CALIBRATION_DT_LOG', 'VELA_CALIBRATION_PINCH_KP_LOG', 'VELA_CALIBRATION_PINCH_KD_LOG'][index], value,
    ])) };
    const child = spawn(process.execPath, [fileURLToPath(import.meta.url), '--stress-worker'], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk.toString(); });
    child.stderr.on('data', chunk => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', code => {
      if (code !== 0) return reject(new Error(`stress worker failed for ${range.modelName} ${range.start}-${range.start + range.count - 1}: ${stderr || stdout}`));
      try { resolve({ range, payload: JSON.parse(stdout.trim()) }); } catch (error) { reject(new Error(`stress worker returned invalid JSON for ${range.modelName} ${range.start}: ${error.message}\n${stdout}`)); }
    });
  })));
  const models = {};
  for (const modelName of requestedModels) {
    const parts = workerResults.filter(item => item.range.modelName === modelName).sort((a, b) => a.range.start - b.range.start);
    const first = parts[0]?.payload?.stress;
    const results = parts.flatMap(item => item.payload.stress.results);
    models[modelName] = { ...first, count, valid: results.length === count && results.every(result => result.valid), results, workerRanges: parts.map(item => item.range), runtimeMs: parts.reduce((sum, item) => sum + (item.payload.stress.runtimeMs || 0), 0) };
  }
  const result = { schema: 'vela-rk4-controller-stress-parallel-v1', generatedAt: new Date().toISOString(), seed, candidate, fidelity, count, workerCount, models, parallelWallMs: Math.max(...workerResults.map(item => item.payload.stress.runtimeMs || 0), 0), overall: Object.values(models).every(value => value.valid) ? 'SUCCESS' : 'FAILED' };
  const resultPath = evidencePath(`rk4-controller-stress-parallel-${fidelity}-n-${count}-w-${workerCount}`);
  await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(resultPath, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ phase: 'parallel-stress-complete', path: path.relative(root, resultPath), candidate, fidelity, count, workerCount, models: Object.fromEntries(Object.entries(models).map(([name, value]) => [name, { valid: value.valid, runtimeMs: value.runtimeMs, genuineFolds: value.results.reduce((sum, item) => sum + (item.held?.genuineFolds || 0) + (item.released?.genuineFolds || 0), 0), collapsedTriangles: value.results.reduce((sum, item) => sum + (item.held?.collapsedTriangles || 0) + (item.released?.collapsedTriangles || 0), 0) }])), overall: result.overall }));
}

function candidateKey(candidate) { return JSON.stringify([candidate.massMultiplier, candidate.surfaceMultiplier, candidate.innerMultiplier, candidate.dampingMultiplier, candidate.dtMultiplier, candidate.pinchKpMultiplier, candidate.pinchKdMultiplier]); }
function evaluationKey(meshes, candidate, fidelity) { return `${meshes.map(mesh => mesh.name).join(',')}|${fidelity}|${candidateKey(candidate)}`; }

function diagnoseModel(value) {
  if (value.incomplete === 'wall-clock-limit') return { mechanism: 'wall-clock-limit', distance: 1, evidence: { runtimeMs: value.runtimeMs, estimatedStages: value.estimatedStages, offlineModelWallMs } };
  if (value.deferred === 'offline-wall-limit') { const limit = value.maxOfflineStages || maxOfflineStages; return { mechanism: 'deferred-offline-compute', distance: Math.max(0, value.estimatedStages / limit - 1), requiredReduction: value.estimatedStages / limit, evidence: { estimatedStages: value.estimatedStages, maxOfflineStages: limit } }; }
  if (value.rejected === 'operation-budget') return { mechanism: 'operation-budget', distance: Math.max(0, value.estimatedStages / maxEstimatedStages - 1), requiredReduction: value.estimatedStages / maxEstimatedStages, evidence: { estimatedStages: value.estimatedStages, maxEstimatedStages } };
  if (value.rejected === 'substep-budget') return { mechanism: 'substep-budget', distance: Math.max(0, value.substepsPerFrame / maxSubsteps - 1), requiredReduction: value.substepsPerFrame / maxSubsteps, evidence: { substepsPerFrame: value.substepsPerFrame, maxSubsteps } };
  const failures = [];
  if (!value.gravity?.finite || !value.response?.finite) failures.push({ mechanism: 'nonfinite-state', distance: 10, evidence: {} });
  if ((value.gravity?.worstFlips || 0) > 0 || (value.gravity?.worstCollapses || 0) > 0 || (value.response?.flips || 0) > 0) failures.push({ mechanism: 'geometry-failure', distance: 1 + (value.gravity?.worstFlips || 0) + (value.gravity?.worstCollapses || 0) + (value.response?.flips || 0), evidence: { gravityFlips: value.gravity?.worstFlips, gravityCollapses: value.gravity?.worstCollapses, responseFlips: value.response?.flips } });
  if ((value.gravity?.worstStrain || 0) > maxGravityStrain) failures.push({ mechanism: 'excessive-strain', distance: value.gravity.worstStrain / maxGravityStrain - 1, evidence: { worstStrain: value.gravity.worstStrain, maxGravityStrain } });
  if (value.gravity && !value.gravity.allSettled) { const distance = Math.max(value.gravity.maxFinalVelocity / maxNormalizedVelocity, value.gravity.maxForceResidualRatio / maxForceResidualRatio) - 1; failures.push({ mechanism: 'not-settled', distance: Number.isFinite(distance) ? distance : 1e6, evidence: { maxNormalizedVelocity: value.gravity.maxFinalVelocity, maxForceResidualRatio: value.gravity.maxForceResidualRatio } }); }
  if (value.convergence && !value.convergence.converged) failures.push({ mechanism: 'rk4-convergence', distance: Math.max((value.convergence.h2VsH4.rmsPositionSource / 1e-12) / Math.max(convergenceTolerance * 1e3, 1e-12), 1) - 1, evidence: value.convergence });
  if (value.response && value.response.displacement <= value.response.targetMeters * 0.01) failures.push({ mechanism: 'insufficient-force-response', distance: 1 - value.response.displacement / Math.max(value.response.targetMeters * 0.01, 1e-18), evidence: value.response });
  if (!failures.length) return { mechanism: 'passed', distance: 0, evidence: {} };
  return failures.sort((a, b) => b.distance - a.distance)[0];
}

function diagnoseResult(result) {
  const modelDiagnoses = Object.fromEntries(Object.entries(result.models || {}).map(([name, value]) => [name, diagnoseModel(value)]));
  const ranked = Object.entries(modelDiagnoses).sort((a, b) => b[1].distance - a[1].distance);
  const dominant = ranked[0]?.[1] || { mechanism: 'unknown', distance: 1, evidence: {} };
  const failureDistance = ranked.reduce((sum, [, value]) => sum + (Number.isFinite(value.distance) ? value.distance : 1e6), 0);
  return { dominantMechanism: dominant.mechanism, failureDistance, modelDiagnoses };
}

function evaluateCandidate(meshes, candidate, fidelity) {
  const cacheKey = evaluationKey(meshes, candidate, fidelity);
  const cached = resultCache.get(cacheKey);
  if (cached) return { ...cached, cacheHit: true };
  const started = performance.now(); const perModel = {};
  for (const mesh of meshes) {
    const evalMesh = fidelity === 'full' ? mesh : fidelity === 'micro' || fidelity === 'micro6' ? mesh.microMesh || mesh.screenMesh || mesh : mesh.screenMesh || mesh;
    const prepared = preparePhysics(evalMesh, candidate);
    const seconds = fidelity === 'micro6' ? offlineGravitySeconds : fidelity === 'micro' ? offlineMicroSeconds : fidelity === 'screen' ? offlineScreenSeconds : fidelity === 'full' ? offlineFullSeconds : offlineLowSeconds;
    const frameCount = Math.max(1, Math.ceil(seconds / frameDt));
    const directionCount = fidelity === 'screen' || fidelity === 'micro' ? 1 : gravityDirections.length;
    const estimatedSteps = Math.max(1, Math.ceil(seconds / Math.max(prepared.stableDt, 1e-18)));
    const estimatedStages = estimatedSteps * directionCount * 4 * (prepared.edgeA.length + prepared.supportA.length);
    const gravity = gravityTest(evalMesh, candidate, seconds, fidelity, offlineModelWallMs);
    const response = forceResponse(evalMesh, candidate, offlineModelWallMs);
    const convergence = fidelity === 'full' || fidelity === 'micro' ? convergenceTest(evalMesh, candidate, seconds, offlineModelWallMs, empiricalStabilityMultiplier) : null;
    const timestepRange = fidelity === 'full' || fidelity === 'micro' ? timestepRangeTest(evalMesh, candidate, seconds, offlineModelWallMs) : null;
    const timestepMainSamples = timestepRange?.samples?.filter(sample => sample.factor <= 1) || [];
    const timestepMainComplete = timestepMainSamples.every(sample => sample.complete);
    const incomplete = !gravity.allComplete || Boolean(convergence && !convergence.complete) || Boolean(timestepRange && !timestepMainComplete);
    const wallClockExceeded = Object.values(gravity.directions || {}).some(direction => direction.wallClockExceeded) || Boolean(convergence?.samples?.some(sample => sample.wallClockExceeded)) || Boolean(timestepRange?.samples?.some(sample => sample.wallClockExceeded));
    const incompleteReason = incomplete ? (wallClockExceeded ? 'wall-clock-limit' : 'solver-incomplete') : null;
    const invalid = incomplete || !gravity.finite || gravity.worstFlips > 0 || gravity.worstCollapses > 0 || gravity.worstStrain > maxGravityStrain || !gravity.allSettled || response.flips > 0 || !response.finite;
    perModel[mesh.name] = { gravity, response, convergence, timestepRange, timestepMainComplete, incomplete: incompleteReason, evaluatedIsland: evalMesh.name, evaluatedVertices: prepared.vertexCount, triangles: prepared.faces.length, surfaceSprings: prepared.edgeA.length, supportSprings: prepared.supportA.length, estimatedStages, runtimeMs: performance.now() - started, stableDt: prepared.stableDt, stabilityEstimateDt: prepared.stabilityEstimateDt, springStabilityEstimateDt: prepared.springStabilityEstimateDt, dampingStabilityEstimateDt: prepared.dampingStabilityEstimateDt, dampingRate: prepared.dampingRate, empiricalStabilityMultiplier: prepared.empiricalStabilityMultiplier, requestedDt: prepared.requestedDt, timestepLimitedByEstimate: prepared.timestepLimitedByEstimate, substepsPerFrame: prepared.explicitSubsteps, totalMassKg: prepared.totalMass };
    if (invalid && fidelity === 'screen') break;
  }
  const values = Object.values(perModel); const valid = values.length === meshes.length && values.every(v => !v.rejected && !v.deferred && !v.incomplete && v.gravity.finite && v.gravity.worstFlips === 0 && v.gravity.worstCollapses === 0 && v.gravity.worstStrain <= maxGravityStrain && v.gravity.allSettled && v.response.flips === 0 && v.response.displacement > v.response.targetMeters * 0.01 && (v.convergence ? v.convergence.converged : true));
  const preliminary = { candidate, fidelity, valid, score: 0, evaluatedAt: new Date().toISOString(), models: perModel, runtimeMs: performance.now() - started };
  const diagnosis = diagnoseResult(preliminary);
  const score = valid ? values.reduce((sum, v) => sum + v.gravity.worstStrain + (v.convergence?.h2VsH4?.rmsPositionSource || 0) / Math.max(v.evaluatedVertices, 1), 0) + values.reduce((sum, v) => sum + v.runtimeMs / 1000, 0) * 0.01 : 1e6 * diagnosis.failureDistance + diagnosis.failureDistance;
  const result = { ...preliminary, score, diagnosis };
  resultCache.set(cacheKey, result);
  return result;
}

function sortResults(results) { return results.slice().sort((a, b) => a.score - b.score); }

function cloneBounds(bounds) { return bounds.map(pair => pair.slice()); }

function resultDominantMechanism(results) {
  const ranked = sortResults(results.filter(result => result.diagnosis));
  if (!ranked.length) return { dominantMechanism: 'unknown', failureDistance: 1, modelDiagnoses: {}, selection: 'none' };
  // Use the promising frontier, not the worst rejected candidate. This prevents one
  // catastrophic outlier from steering the distribution away from candidates that
  // are numerically closer to every gate.
  const frontier = ranked.slice(0, Math.max(1, Math.ceil(ranked.length * 0.4)));
  const weighted = new Map();
  for (const result of frontier) {
    const mechanism = result.diagnosis.dominantMechanism;
    const weight = 1 / (1 + Math.max(0, Number(result.diagnosis.failureDistance) || 0));
    weighted.set(mechanism, (weighted.get(mechanism) || 0) + weight);
  }
  const dominantMechanism = [...weighted.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || frontier[0].diagnosis.dominantMechanism;
  const matching = frontier.filter(result => result.diagnosis.dominantMechanism === dominantMechanism);
  const failureDistance = matching.reduce((sum, result) => sum + (Number.isFinite(result.diagnosis.failureDistance) ? result.diagnosis.failureDistance : 1e6), 0) / Math.max(1, matching.length);
  return { dominantMechanism, failureDistance, modelDiagnoses: matching[0]?.diagnosis.modelDiagnoses || {}, selection: 'promising-frontier', frontierSize: frontier.length, mechanismWeights: Object.fromEntries(weighted) };
}

function adaptSearchState(state, results, phase) {
  const diagnosis = resultDominantMechanism(results);
  const amount = Math.max(0.2, Math.min(1.5, diagnosis.failureDistance || 0.2));
  const shifts = {
    'operation-budget': [0.65, -0.35, -0.25, 0.05, 0.85],
    'substep-budget': [0.55, -0.30, -0.20, 0.05, 0.75],
    'deferred-offline-compute': [0.35, -0.25, -0.35, 0.05, 0.75],
    'geometry-failure': [0.20, 0.20, 0.20, 0.55, -0.55],
    'excessive-strain': [0.15, 0.25, 0.20, 0.45, -0.35],
    'not-settled': [0.30, -0.10, -0.10, 0.50, 0.15],
    'rk4-convergence': [0.20, -0.15, -0.15, 0.30, -0.60],
    'insufficient-force-response': [-0.35, -0.25, -0.25, -0.20, 0.10],
    'passed': [0, 0, 0, 0, 0],
  };
  const shift = shifts[diagnosis.dominantMechanism] || [0, 0, 0, 0, 0];
  const baseMean = state.mean.slice();
  const nextMean = baseMean.map((value, index) => value + shift[index] * amount);
  const nextBounds = cloneBounds(state.bounds);
  if (diagnosis.dominantMechanism === 'operation-budget' || diagnosis.dominantMechanism === 'substep-budget' || diagnosis.dominantMechanism === 'deferred-offline-compute') {
    nextBounds[0][0] = Math.min(nextBounds[0][1], nextBounds[0][0] + 0.25);
    nextBounds[4][0] = Math.min(nextBounds[4][1], nextBounds[4][0] + 0.25);
    nextBounds[1][1] = Math.min(nextBounds[1][1], 1.5);
    nextBounds[2][1] = Math.min(nextBounds[2][1], 3.5);
  } else if (diagnosis.dominantMechanism === 'geometry-failure' || diagnosis.dominantMechanism === 'excessive-strain') {
    nextBounds[3][0] = Math.min(nextBounds[3][1], nextBounds[3][0] + 0.15);
    nextBounds[4][1] = Math.min(nextBounds[4][1], 0.5);
  } else if (diagnosis.dominantMechanism === 'not-settled') {
    nextBounds[3][0] = Math.min(nextBounds[3][1], nextBounds[3][0] + 0.15);
  }
  const nextSigma = diagnosis.dominantMechanism === 'passed' ? Math.max(0.20, state.sigma * 0.82) : Math.min(2.5, Math.max(0.25, state.sigma * 1.02));
  return { ...state, mean: nextMean.map((value, index) => Math.max(nextBounds[index][0], Math.min(nextBounds[index][1], value))), sigma: nextSigma, bounds: nextBounds, lastFeedback: { phase, dominantMechanism: diagnosis.dominantMechanism, failureDistance: diagnosis.failureDistance, shift, amount, meanBefore: baseMean, meanAfter: nextMean, boundsAfter: nextBounds }, feedbackHistory: [...state.feedbackHistory, { phase, dominantMechanism: diagnosis.dominantMechanism, failureDistance: diagnosis.failureDistance, shift, amount, meanBefore: baseMean, meanAfter: nextMean, boundsAfter: nextBounds }] };
}

function normalizeCompactResult(value) {
  if (!value) return value;
  const score = Number.isFinite(value.score) ? value.score : 1e300;
  const diagnosis = value.diagnosis ? { ...value.diagnosis, failureDistance: Number.isFinite(value.diagnosis.failureDistance) ? value.diagnosis.failureDistance : 1e6 } : value.diagnosis;
  return { ...value, score, diagnosis };
}

async function writeCheckpoint(state, reason = 'generation') {
  const checkpoint = {
    schema: 'vela-realtime-rk4-calibration-checkpoint-v2',
    generatedAt: new Date().toISOString(),
    reason,
    config: { requestedModels, seed, populationSize, fullSurvivors, maxSubsteps, maxEstimatedStages, maxCycles, maxWallMs, thresholds: { maxGravityStrain, maxNormalizedVelocity, maxForceResidualRatio, convergenceTolerance } },
    state: { cycle: state.cycle, mean: state.mean, sigma: state.sigma, bounds: state.bounds, best: state.best, feedbackHistory: state.feedbackHistory, outstandingConstraints: state.outstandingConstraints, generationSummaries: state.generationSummaries },
    history: state.history.map(normalizeCompactResult),
    cache: [...resultCache.entries()].map(([key, value]) => [key, normalizeCompactResult(compactResult(value))]),
    feedbackDemo: state.feedbackDemo,
  };
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(checkpointPath, JSON.stringify(checkpoint, null, 2));
}

async function loadCheckpoint(filePath) {
  if (!filePath) return null;
  try {
    const parsed = JSON.parse(await fs.readFile(filePath, 'utf8'));
    if (parsed.schema !== 'vela-realtime-rk4-calibration-checkpoint-v2') throw new Error(`Unsupported checkpoint schema ${parsed.schema}`);
    for (const [key, value] of parsed.cache || []) resultCache.set(key, normalizeCompactResult(value));
    return { ...parsed.state, history: (parsed.history || []).map(normalizeCompactResult), feedbackDemo: parsed.feedbackDemo };
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function feedbackDemo() {
  const initial = { mean: [0, 0, 0, 0, -1], sigma: 0.2, bounds: cloneBounds(defaultLogBounds), feedbackHistory: [] };
  const failed = Array.from({ length: 4 }, (_, index) => ({ candidate: createCandidate([0, 0, 0, 0, -1]), fidelity: 'screen', valid: false, score: 1, generation: 0, source: `deliberate-failure-${index}`, diagnosis: { dominantMechanism: 'operation-budget', failureDistance: 4, modelDiagnoses: {} }, models: {} }));
  const adapted = adaptSearchState(initial, failed, 'feedback-demo');
  return { firstGeneration: { allFailed: failed.every(result => !result.valid), dominantMechanism: adapted.lastFeedback.dominantMechanism }, nextGeneration: { meanChanged: JSON.stringify(initial.mean) !== JSON.stringify(adapted.mean), meanBefore: initial.mean, meanAfter: adapted.mean, boundsBefore: initial.bounds, boundsAfter: adapted.bounds }, passed: failed.every(result => !result.valid) && adapted.lastFeedback.dominantMechanism === 'operation-budget' && JSON.stringify(initial.mean) !== JSON.stringify(adapted.mean) };
}

async function adaptiveSearch(meshes, random, resumed) {
  const dimension = 5, lambda = populationSize, mu = Math.max(2, Math.floor(lambda / 2));
  let state = resumed || { cycle: 0, mean: [2, 1, 3, 0, 0], sigma: 1.35, bounds: cloneBounds(defaultLogBounds), history: [], feedbackHistory: [], outstandingConstraints: [], generationSummaries: [], best: null, feedbackDemo: feedbackDemo() };
  if (!state.feedbackDemo) state.feedbackDemo = feedbackDemo();
  const weights = Array.from({ length: mu }, (_, i) => Math.log(mu + 0.5) - Math.log(i + 1)); const weightSum = weights.reduce((a, b) => a + b, 0); for (let i = 0; i < mu; i++) weights[i] /= weightSum;
  const deterministicSeeds = [[3, -1, -2, 2, 1], [3, -1, -1, 2, 1], [2, -1, -2, 2, 1], [3, 0, -2, 2, 1], [2, 0, -1, 2, 1], [3, 1, -1, 2, 1], [2, 1, 0, 2, 1]];
  const started = performance.now();
  while (state.cycle < maxCycles && performance.now() - started < maxWallMs) {
    const cycle = state.cycle, population = [], seen = new Set(state.history.map(result => candidateKey(result.candidate)));
    if (cycle === 0 && state.history.length === 0) {
      population.push({ logs: [0, 0, 0, 0, 0], source: 'biological-baseline' }, { logs: [6, -0.6, 2.9, 0.35, 0], source: 'existing-realtime' });
      for (const [index, logs] of deterministicSeeds.entries()) if (population.length < lambda) population.push({ logs, source: `seed-${index}` });
    } else {
      population.push({ logs: state.best?.candidate?.logParameters || state.mean, source: 'feedback-elite' });
    }
    let attempts = 0;
    while (population.length < lambda && attempts++ < lambda * 20) {
      const logs = state.mean.map(value => value + gaussian(random) * state.sigma); const candidate = createCandidate(logs, state.bounds); if (!seen.has(candidateKey(candidate))) population.push({ logs: candidate.logParameters, source: `adaptive-${cycle}` });
    }
    while (population.length < lambda) population.push({ logs: state.mean, source: `adaptive-cache-${cycle}` });
    const low = [];
    for (const item of population) {
      const candidate = createCandidate(item.logs, state.bounds); const result = evaluateCandidate(meshes, candidate, cycle === 0 ? 'screen' : 'low'); const decorated = { ...result, generation: cycle, phase: cycle === 0 ? 'screen' : 'low', source: item.source }; low.push(decorated); console.log(JSON.stringify({ phase: 'candidate', generation: cycle, fidelity: decorated.fidelity, source: item.source, candidate, valid: result.valid, score: result.score, dominantMechanism: result.diagnosis.dominantMechanism, failureDistance: result.diagnosis.failureDistance, cacheHit: result.cacheHit || false, runtimeMs: result.runtimeMs }));
    }
    const rankedLow = sortResults(low), promoted = rankedLow.slice(0, Math.min(fullSurvivors, rankedLow.length)), full = [];
    for (const item of promoted) {
      const result = evaluateCandidate(meshes, item.candidate, 'full'); const decorated = { ...result, generation: cycle, phase: 'full', source: 'promoted-full' }; full.push(decorated); console.log(JSON.stringify({ phase: 'full-promote', generation: cycle, candidate: item.candidate, valid: result.valid, score: result.score, dominantMechanism: result.diagnosis.dominantMechanism, failureDistance: result.diagnosis.failureDistance, cacheHit: result.cacheHit || false, runtimeMs: result.runtimeMs }));
    }
    const cycleResults = [...low, ...full], rankedCycle = sortResults(cycleResults), validFull = full.find(result => result.valid);
    if (rankedCycle[0]) state.best = compactResult(rankedCycle[0]);
    state.history.push(...cycleResults.map(compactResult));
    const elite = rankedCycle.slice(0, mu); const cmaMean = Array(dimension).fill(0); for (let i = 0; i < elite.length; i++) for (let d = 0; d < dimension; d++) cmaMean[d] += (weights[i] || 0) * elite[i].candidate.logParameters[d]; if (elite.length) state.mean = cmaMean;
    state = adaptSearchState(state, full.length ? full : low, full.length ? 'full' : 'low');
    state.outstandingConstraints = rankedCycle.filter(result => !result.valid).slice(0, 10).map(result => ({ candidate: result.candidate, fidelity: result.fidelity, dominantMechanism: result.diagnosis.dominantMechanism, failureDistance: result.diagnosis.failureDistance }));
    state.generationSummaries.push({ generation: cycle, evaluated: cycleResults.length, lowEvaluated: low.length, fullEvaluated: full.length, cacheHits: cycleResults.filter(result => result.cacheHit).length, best: compactResult(rankedCycle[0]), feedback: state.lastFeedback, validFull: Boolean(validFull) });
    state.cycle = cycle + 1;
    await writeCheckpoint(state, `generation-${cycle}`);
    console.log(JSON.stringify({ phase: 'generation', generation: cycle, best: rankedCycle[0]?.candidate, bestScore: rankedCycle[0]?.score, bestValid: rankedCycle[0]?.valid, promoted: full.length, feedback: state.lastFeedback, nextMean: state.mean, sigma: state.sigma, cycle: state.cycle, checkpoint: checkpointPath }));
    if (validFull) return { state, best: validFull, exhausted: false };
  }
  return { state, best: null, exhausted: true };
}

function compactResult(result) {
  const out = { candidate: result.candidate, fidelity: result.fidelity, valid: result.valid, score: Number.isFinite(result.score) ? result.score : 1e300, generation: result.generation, phase: result.phase, source: result.source, runtimeMs: result.runtimeMs, diagnosis: result.diagnosis ? { ...result.diagnosis, failureDistance: Number.isFinite(result.diagnosis.failureDistance) ? result.diagnosis.failureDistance : 1e6 } : result.diagnosis, models: {} };
  for (const [name, value] of Object.entries(result.models || {})) out.models[name] = value.rejected || value.deferred ? { rejected: value.rejected, deferred: value.deferred, evaluatedIsland: value.evaluatedIsland, evaluatedVertices: value.evaluatedVertices, triangles: value.triangles, surfaceSprings: value.surfaceSprings, supportSprings: value.supportSprings, estimatedStages: value.estimatedStages, maxEstimatedStages: value.maxEstimatedStages, maxOfflineStages: value.maxOfflineStages, stableDt: value.stableDt, substepsPerFrame: value.substepsPerFrame, totalMassKg: value.totalMassKg } : { gravity: { worstFlips: value.gravity.worstFlips, worstCollapses: value.gravity.worstCollapses, worstStrain: value.gravity.worstStrain, maxDisplacement: value.gravity.maxDisplacement, maxVelocity: value.gravity.maxVelocity, maxFinalVelocity: value.gravity.maxFinalVelocity, maxForceResidualRatio: value.gravity.maxForceResidualRatio, allSettled: value.gravity.allSettled, finite: value.gravity.finite }, response: value.response, convergence: value.convergence, timestepRange: value.timestepRange, evaluatedIsland: value.evaluatedIsland, evaluatedVertices: value.evaluatedVertices, triangles: value.triangles, surfaceSprings: value.surfaceSprings, supportSprings: value.supportSprings, estimatedStages: value.estimatedStages, stableDt: value.stableDt, substepsPerFrame: value.substepsPerFrame, totalMassKg: value.totalMassKg, runtimeMs: value.runtimeMs };
  for (const [name, value] of Object.entries(result.models || {})) if (value.incomplete) out.models[name].incomplete = value.incomplete;
  for (const [name, value] of Object.entries(result.models || {})) if (!value.rejected && !value.deferred) {
    out.models[name].gravity.allComplete = value.gravity.allComplete;
    out.models[name].timestepMainComplete = value.timestepMainComplete;
    out.models[name].stabilityEstimateDt = value.stabilityEstimateDt;
    out.models[name].springStabilityEstimateDt = value.springStabilityEstimateDt;
    out.models[name].dampingStabilityEstimateDt = value.dampingStabilityEstimateDt;
    out.models[name].dampingRate = value.dampingRate;
    out.models[name].empiricalStabilityMultiplier = value.empiricalStabilityMultiplier;
  }
  return out;
}

function withParameterBlock(base, updates) {
  const logs = base.logParameters.slice();
  for (const [index, value] of Object.entries(updates)) logs[Number(index)] = value;
  return createCandidate(logs, defaultLogBounds);
}

function stageDistance(result, stage) {
  const values = Object.values(result.models || {});
  if (values.some(value => value.deferred || value.rejected || value.incomplete)) return result.diagnosis?.failureDistance || 1e6;
  if (stage === 'timestep') return values.reduce((sum, value) => sum + (value.convergence?.converged ? 0 : 1) + (value.timestepRange?.largestTestedStableMultiplier ? 0 : 1), 0);
  if (stage === 'gravity') return values.reduce((sum, value) => sum + (value.gravity?.worstFlips || 0) + (value.gravity?.worstCollapses || 0) + Math.max(0, (value.gravity?.worstStrain || 0) - maxGravityStrain) + Math.max(0, (value.gravity?.maxForceResidualRatio || 0) - maxForceResidualRatio) + Math.max(0, (value.gravity?.maxFinalVelocity || 0) * 0 + (value.gravity?.allSettled ? 0 : 1)), 0);
  if (stage === 'damping') return values.reduce((sum, value) => sum + (value.gravity?.worstFlips || 0) + (value.gravity?.worstCollapses || 0) + Math.max(0, (value.gravity?.worstStrain || 0) - maxGravityStrain) + Math.max(0, (value.gravity?.maxForceResidualRatio || 0) - maxForceResidualRatio) + (value.gravity?.allSettled ? (value.gravity.maxFinalVelocity || 0) / Math.max(maxNormalizedVelocity, 1e-18) + (value.gravity.maxForceResidualRatio || 0) / Math.max(maxForceResidualRatio, 1e-18) : 1e3), 0);
  if (stage === 'pinch') return values.reduce((sum, value) => sum + Math.max(0, 0.5 - (value.response?.displacement || 0) / Math.max(value.response?.targetMeters || 1e-18, 1e-18)) + (value.response?.flips || 0), 0);
  return result.diagnosis?.failureDistance || 1e6;
}

function stagePass(result, stage) {
  const values = Object.values(result.models || {});
  if (!values.length || values.some(value => value.deferred || value.rejected || value.incomplete || !value.gravity?.finite)) return false;
  if (stage === 'timestep') return values.every(value => value.convergence?.converged && value.timestepRange?.largestTestedStableMultiplier !== null && value.timestepRange?.largestTestedStableMultiplier !== undefined && value.gravity.worstFlips === 0 && value.gravity.worstCollapses === 0);
  if (stage === 'gravity' || stage === 'damping') return values.every(value => value.gravity.allSettled && value.gravity.worstFlips === 0 && value.gravity.worstCollapses === 0 && value.gravity.worstStrain <= maxGravityStrain && value.gravity.maxForceResidualRatio <= maxForceResidualRatio);
  if (stage === 'pinch') return values.every(value => value.response.finite && value.response.flips === 0 && value.response.displacement >= value.response.targetMeters * 0.5);
  return false;
}

async function runWaterfallStage(name, baseCandidate, varyingIndices, fidelity, meshes, passStage, resource) {
  const started = performance.now(), evaluations = [], tested = new Set(), deterministic = [];
  if (name === 'timestep') for (const value of [-1, -0.5, 0, 0.5, 1]) deterministic.push(withParameterBlock(baseCandidate, { 4: value }));
  if (name === 'gravity') for (const [surface, inner] of [[-1, -2], [-0.5, -1], [0, 0], [0.5, 0], [1, 1], [-1, -1], [0, -2], [1, -2]]) deterministic.push(withParameterBlock(baseCandidate, { 1: surface, 2: inner }));
  if (name === 'damping') for (const value of [-1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 4]) deterministic.push(withParameterBlock(baseCandidate, { 3: value }));
  if (name === 'pinch') for (const [kp, kd] of [[-2, -2], [-1.5, -2], [-1.2, -2], [-1, -2], [-1, -1], [-0.5, 0], [0, 0], [0.5, 0.5], [1, 1], [1, 0]]) deterministic.push(withParameterBlock(baseCandidate, { 5: kp, 6: kd }));
  let iteration = 0, best = null;
  while (performance.now() - started < resource.stageWallMs && evaluations.length < resource.stageEvaluationBudget) {
    let candidate = deterministic[iteration];
    if (!candidate) {
      const logs = baseCandidate.logParameters.slice(); for (const index of varyingIndices) logs[index] += (resource.random() - 0.5) * resource.sigma;
      candidate = createCandidate(logs, defaultLogBounds);
    }
    iteration++;
    const key = `${fidelity}|${candidateKey(candidate)}`;
    if (tested.has(key)) continue;
    tested.add(key);
    const result = evaluateCandidate(meshes, candidate, fidelity);
    const record = { stage: name, candidate, fidelity, passed: stagePass(result, passStage), distance: stageDistance(result, passStage), result: compactResult(result) };
    evaluations.push(record);
    const better = !best || Number(record.passed) > Number(best.passed) || (record.passed === best.passed && (record.distance < best.distance || (record.distance === best.distance && (record.result?.score || Infinity) < (best.result?.score || Infinity))));
    if (better) best = record;
    console.log(JSON.stringify({ phase: 'waterfall-stage', stage: name, evaluation: evaluations.length, candidate, passed: record.passed, distance: record.distance, dominantMechanism: result.diagnosis?.dominantMechanism, runtimeMs: result.runtimeMs }));
  }
  const passedRecords = evaluations.filter(record => record.passed);
  if (name === 'timestep' && passedRecords.length) {
    passedRecords.sort((a, b) => Math.max(...Object.values(b.result.models).map(value => value.timestepRange?.samples?.find(sample => sample.factor === 1)?.timeStep || 0)) - Math.max(...Object.values(a.result.models).map(value => value.timestepRange?.samples?.find(sample => sample.factor === 1)?.timeStep || 0)));
    best = passedRecords[0];
  }
  return { name, passed: Boolean(best?.passed), candidate: best?.candidate || baseCandidate, evaluations, best, elapsedMs: performance.now() - started, reason: best?.passed ? 'stage-complete' : (performance.now() - started >= resource.stageWallMs ? 'stage-wall-budget' : 'stage-evaluation-budget') };
}

async function loadWaterfallCheckpoint(filePath) {
  try {
    const parsed = JSON.parse(await fs.readFile(filePath, 'utf8'));
    if (parsed.schema !== 'vela-rk4-waterfall-checkpoint-v1') throw new Error(`Unsupported waterfall checkpoint schema ${parsed.schema}`);
    return parsed;
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function profileCandidate(meshes, candidate) {
  return Object.fromEntries(meshes.map(mesh => {
    const prepared = preparePhysics(mesh, candidate);
    const seconds = Math.min(offlineFullSeconds, 0.01);
    const estimatedSteps = Math.max(1, Math.ceil(seconds / Math.max(prepared.stableDt, 1e-18)));
    const estimatedStages = estimatedSteps * 4 * (prepared.edgeA.length + prepared.supportA.length);
    if (estimatedStages > maxOfflineStages) return [mesh.name, { deferred: 'profile-wall-limit', estimatedStages, maxOfflineStages, vertices: prepared.vertexCount, surfaceSprings: prepared.edgeA.length, supportSprings: prepared.supportA.length, stableDt: prepared.stableDt }];
    const result = simulate(mesh, candidate, { gravity: directions(mesh).down.map(v => v * 9.81), seconds });
    return [mesh.name, { vertices: prepared.vertexCount, triangles: prepared.faces.length, surfaceSprings: prepared.edgeA.length, supportSprings: prepared.supportA.length, estimatedSteps, measuredSteps: result.steps, rk4Stages: result.forceEvaluations, runtimeMs: result.runtimeMs, msPerForceEvaluation: result.runtimeMs / Math.max(result.forceEvaluations, 1), msPerVertexUpdate: result.runtimeMs / Math.max(result.steps * prepared.vertexCount, 1), peakMemoryBytes: process.memoryUsage().heapUsed, geometry: result.geometry }];
  }));
}

function pinchPreflight(meshes, baseCandidate) {
  const pairs = [[-2, -2], [-1.5, -2], [-1.2, -2], [-1, -2], [-1, -1], [-0.5, 0], [0, 0], [0.5, 0.5], [1, 1], [1, 0]];
  const count = Math.max(1, Number(process.env.VELA_CALIBRATION_PINCH_PREFLIGHT_COUNT || 1));
  const evaluations = [];
  for (let index = 0; index < pairs.length; index++) {
    const [kp, kd] = pairs[index];
    const candidate = withParameterBlock(baseCandidate, { 5: kp, 6: kd });
    const models = Object.fromEntries(meshes.map((mesh, modelIndex) => {
      const stress = randomPinchStress(mesh.microMesh || mesh.screenMesh || mesh, candidate, count, seed + 700 + index * 11 + modelIndex, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds });
      const response = forceResponse(mesh.microMesh || mesh.screenMesh || mesh, candidate, offlineModelWallMs);
      return [mesh.name, { stress, response }];
    }));
    const results = Object.values(models);
    const folds = results.reduce((sum, value) => sum + value.stress.results.reduce((inner, result) => inner + (result.held?.genuineFolds || 0) + (result.released?.genuineFolds || 0), 0), 0);
    const collapses = results.reduce((sum, value) => sum + value.stress.results.reduce((inner, result) => inner + (result.held?.collapsedTriangles || 0) + (result.released?.collapsedTriangles || 0), 0), 0);
    const maxStrain = Math.max(...results.flatMap(value => value.stress.results.map(result => Math.max(result.held?.maxEdgeStrain || 0, result.released?.maxEdgeStrain || 0))), 0);
    const responseRatios = results.map(value => value.response.displacement / Math.max(value.response.targetMeters, 1e-18));
    const responsePassed = results.length === meshes.length && results.every(value => value.response.finite && value.response.flips === 0 && value.response.displacement >= value.response.targetMeters * 0.5);
    const passed = results.length === meshes.length && results.every(value => value.stress.valid) && responsePassed;
    const record = { candidate, passed, responsePassed, responseRatios, folds, collapses, maxStrain, models };
    evaluations.push(record);
    console.log(JSON.stringify({ phase: 'pinch-preflight', evaluation: evaluations.length, candidate, passed, responsePassed, responseRatios, folds, collapses, maxStrain }));
  }
  const best = evaluations.slice().sort((a, b) => Number(!a.passed) - Number(!b.passed) || a.folds - b.folds || a.collapses - b.collapses || a.maxStrain - b.maxStrain || Math.min(...b.responseRatios) - Math.min(...a.responseRatios))[0];
  return { name: 'pinch-preflight', passed: Boolean(best?.passed), candidate: best?.candidate || baseCandidate, evaluations, best, count };
}

async function runWaterfall(meshes, resource, resumed = null) {
  const stages = resumed?.stages || [], checkpoints = resumed?.checkpoints || [];
  let current = resumed?.current || createCandidate([0, 0, 0, 0, 0, 0, 0]);
  const passed = new Set(checkpoints.filter(checkpoint => checkpoint.passed).map(checkpoint => checkpoint.stage));
  const persist = async stage => { await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(path.join(outputDir, 'rk4-waterfall-checkpoint.json'), JSON.stringify({ schema: 'vela-rk4-waterfall-checkpoint-v1', generatedAt: new Date().toISOString(), stage, current, stages, checkpoints }, null, 2)); };
  const execute = async (name, varyingIndices, fidelity, passStage) => {
    if (passed.has(name)) return stages.find(stage => stage.name === name);
    const stage = await runWaterfallStage(name, current, varyingIndices, fidelity, meshes, passStage, resource);
    const previous = stages.findIndex(item => item.name === name); if (previous >= 0) stages[previous] = stage; else stages.push(stage);
    current = stage.candidate; checkpoints.push({ stage: name, current, passed: stage.passed }); await persist(name); return stage;
  };
  const stage1 = await execute('timestep', [4], 'micro', 'timestep'); if (!stage1?.passed) return { stages, checkpoints, current, completedStage: 'timestep', overall: 'FAILED' };
  const stage2 = await execute('gravity', [1, 2], 'micro6', 'gravity'); if (!stage2?.passed) return { stages, checkpoints, current, completedStage: 'gravity', overall: 'FAILED' };
  const stage3 = await execute('damping', [3], 'micro6', 'damping'); if (!stage3?.passed) return { stages, checkpoints, current, completedStage: 'damping', overall: 'FAILED' };
  const stage3Recheck = await execute('timestep-recheck', [4], 'micro', 'timestep'); if (!stage3Recheck?.passed) return { stages, checkpoints, current, completedStage: 'timestep-recheck', overall: 'FAILED' };
  const stage4 = await execute('pinch', [5, 6], 'micro6', 'pinch'); if (!stage4?.passed) return { stages, checkpoints, current, completedStage: 'pinch', overall: 'FAILED' };
  if (!passed.has('pinch-preflight') || argv.has('--pinch-preflight-recheck')) {
    const preflight = pinchPreflight(meshes, current);
    const previousPreflight = stages.findIndex(stage => stage.name === 'pinch-preflight');
    if (previousPreflight >= 0) stages[previousPreflight] = preflight; else stages.push(preflight);
    current = preflight.candidate; checkpoints.push({ stage: 'pinch-preflight', current, passed: preflight.passed }); await persist('pinch-preflight');
    if (argv.has('--pinch-preflight-only')) return { stages, checkpoints, current, completedStage: 'pinch-preflight', overall: preflight.passed ? 'PREFLIGHT_PASS' : 'FAILED' };
    if (!preflight.passed) return { stages, checkpoints, current, completedStage: 'pinch-preflight', overall: 'FAILED' };
  }
  const robustness = Object.fromEntries(meshes.map((mesh, index) => [mesh.name, { fidelity: 'micro6', randomPinch: randomPinchStress(mesh.microMesh || mesh.screenMesh || mesh, current, 20, seed + 100 + index, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds }), gravity: gravityTest(mesh.microMesh || mesh.screenMesh || mesh, current, offlineGravitySeconds, 'full') }]));
  const robustnessPassed = Object.values(robustness).every(value => value.randomPinch.valid && value.gravity.finite && value.gravity.allComplete && value.gravity.worstFlips === 0 && value.gravity.worstCollapses === 0 && value.gravity.allSettled);
  const robustnessStage = { name: 'robustness', passed: robustnessPassed, candidate: current, evaluations: [{ candidate: current, passed: robustnessPassed, robustness }] };
  const existingRobustness = stages.findIndex(stage => stage.name === 'robustness'); if (existingRobustness >= 0) stages[existingRobustness] = robustnessStage; else stages.push(robustnessStage);
  checkpoints.push({ stage: 'robustness', current, passed: robustnessPassed }); await persist('robustness');
  if (!robustnessPassed) return { stages, checkpoints, current, completedStage: 'robustness', robustness, overall: 'FAILED' };
  const fullValidation = Object.fromEntries(meshes.map(mesh => { const result = evaluateCandidate([mesh], current, 'full'); return [mesh.name, compactResult(result)]; }));
  const profile = profileCandidate(meshes, current);
  await persist('complete');
  return { stages, checkpoints, current, completedStage: 'performance', robustness, fullValidation, profile, overall: Object.values(fullValidation).every(value => value.valid) && Object.values(robustness).every(value => value.randomPinch.valid) ? 'SUCCESS' : 'FAILED' };
}

async function main() {
  if (argv.has('--stress-worker')) {
    const modelName = requestedModels[0];
    const mesh = await loadModel(modelName);
    const candidate = candidateFromEnvironment();
    const startSequence = Math.max(0, Number(process.env.VELA_CALIBRATION_STRESS_START || 0));
    const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 1));
    const modelIndex = Number(process.env.VELA_CALIBRATION_STRESS_MODEL_INDEX || requestedModels.indexOf(modelName));
    const fidelity = process.env.VELA_CALIBRATION_STRESS_FIDELITY || 'full';
    const stress = randomPinchStress(stressDomain(mesh), candidate, count, seed + 100 + modelIndex, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds, startSequence });
    const partPath = evidencePath(`rk4-controller-stress-part-${modelName}-start-${startSequence}-n-${count}`);
    await fs.mkdir(outputDir, { recursive: true });
    await fs.writeFile(partPath, JSON.stringify({ schema: 'vela-rk4-controller-stress-part-v1', generatedAt: new Date().toISOString(), modelName, modelIndex, startSequence, count, fidelity, candidate, stress }, null, 2));
    console.log(JSON.stringify({ modelName, startSequence, count, fidelity, partPath: path.relative(root, partPath), stress }));
    return;
  }
  if (argv.has('--stress-parallel')) { await runParallelStress(); return; }
  const started = performance.now(), loaded = {};
  for (const name of requestedModels) { console.log(JSON.stringify({ phase: 'load', model: name })); loaded[name] = await loadModel(name); console.log(JSON.stringify({ phase: 'loaded', model: name, islandVertices: loaded[name].system.vertexCount, islandTriangles: loaded[name].system.faces.length, screenIslandVertices: loaded[name].screenMesh?.system.vertexCount, screenDomainKind: loaded[name].screenMesh?.domainKind, screenSourceIslandId: loaded[name].screenMesh?.sourceIslandId, microIslandVertices: loaded[name].microMesh?.system.vertexCount, microDomainKind: loaded[name].microMesh?.domainKind, microSourceIslandId: loaded[name].microMesh?.sourceIslandId, islandCount: loaded[name].islandCount })); }
  const meshes = Object.values(loaded);
  if (argv.has('--export-gpu-cpu-references')) {
    const candidate = candidateFromEnvironment();
    const seconds = Number(process.env.VELA_GPU_REFERENCE_SECONDS || 0.0001);
    const referenceDir = path.join(outputDir, 'gpu-cpu-references');
    await fs.mkdir(referenceDir, { recursive: true });
    const writeTyped = async (file, array) => { await fs.writeFile(file, Buffer.from(array.buffer, array.byteOffset, array.byteLength)); return path.basename(file); };
    const manifest = { schema: 'vela-rk4-gpu-cpu-reference-manifest-v1', generatedAt: new Date().toISOString(), sourceMetersPerUnit, frameDt, seconds, candidate, models: {} };
    for (const mesh of meshes) {
      manifest.models[mesh.name] = {};
      for (const [domain, evalMesh] of [['full', mesh], ['screen', mesh.screenMesh], ['micro', mesh.microMesh]]) {
        if (!evalMesh) continue;
        const face = evalMesh.system.faces[Math.floor(evalMesh.system.faces.length / 2)];
        const ids = face.slice();
        const weights = [1 / 3, 1 / 3, 1 / 3];
        const origin = ids.reduce((sum, id, index) => sum.map((value, axis) => value + evalMesh.neutral[id * 3 + axis] * weights[index]), [0, 0, 0]);
        const target = origin.map((value, axis) => value + evalMesh.up[axis] * evalMesh.faceScale * 0.001);
        const pinch = { ids, weights, target, velocity: [0, 0, 0], kp: 0.1, kd: 0.01, peakForce: 0 };
        const gravity = directions(evalMesh).down.map(value => value * 9.81);
        const gravityResult = simulate(evalMesh, candidate, { gravity, seconds, wallClockLimitMs: Infinity });
        const holdResult = simulate(evalMesh, candidate, { gravity, seconds, pinch, wallClockLimitMs: Infinity });
        const releaseResult = simulate(evalMesh, candidate, { gravity, seconds, initialPositions: holdResult.positions, initialVelocities: holdResult.velocities, wallClockLimitMs: Infinity });
        const basePath = path.join(referenceDir, `${mesh.name}-${domain}`);
        const stages = {};
        for (const [stage, result] of [['gravity', gravityResult], ['pinchHold', holdResult], ['pinchRelease', releaseResult]]) {
          stages[stage] = {
            positions: await writeTyped(`${basePath}-${stage}-positions.bin`, result.positions),
            velocities: await writeTyped(`${basePath}-${stage}-velocities.bin`, result.velocities),
            runtimeMs: result.runtimeMs,
            steps: result.steps,
            forceEvaluations: result.forceEvaluations,
            complete: result.complete,
            geometry: result.geometry,
            pinch: result.pinch ? { error: result.pinch.error, peakForce: result.pinch.peakForce } : null,
          };
        }
        manifest.models[mesh.name][domain] = { vertexCount: evalMesh.system.vertexCount, triangleCount: evalMesh.system.faces.length, faceScale: evalMesh.faceScale, anatomicalAxes: { right: evalMesh.right, up: evalMesh.up, front: evalMesh.front }, pinch: { ids, weights, target, kp: pinch.kp, kd: pinch.kd }, stages };
      }
    }
    const manifestPath = path.join(referenceDir, 'manifest.json');
    await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2));
    console.log(JSON.stringify({ phase: 'gpu-cpu-references-complete', path: path.relative(root, manifestPath), seconds }));
    return;
  }
  if (argv.has('--export-gpu-fixtures')) {
    const candidate = candidateFromEnvironment();
    const fixtureDir = path.join(outputDir, 'gpu-fixtures');
    await fs.mkdir(fixtureDir, { recursive: true });
    const manifest = { schema: 'vela-rk4-gpu-fixture-manifest-v1', generatedAt: new Date().toISOString(), sourceMetersPerUnit, frameDt, candidate, models: {} };
    const writeArray = async (basePath, array) => {
      const file = `${basePath}.bin`;
      await fs.writeFile(file, Buffer.from(array.buffer, array.byteOffset, array.byteLength));
      return path.basename(file);
    };
    for (const mesh of meshes) {
      manifest.models[mesh.name] = {};
      for (const [domain, evalMesh] of [['full', mesh], ['screen', mesh.screenMesh], ['micro', mesh.microMesh]]) {
        if (!evalMesh) continue;
        const prepared = preparePhysics(evalMesh, candidate);
        const basePath = path.join(fixtureDir, `${mesh.name}-${domain}`);
        const faceFlat = new Uint32Array(evalMesh.system.faces.length * 3);
        evalMesh.system.faces.forEach((face, index) => face.forEach((vertex, axis) => { faceFlat[index * 3 + axis] = vertex; }));
        const arrays = {
          neutral: evalMesh.system.neutral,
          anchors: evalMesh.system.anchors,
          masses: prepared.masses,
          edgeA: prepared.edgeA,
          edgeB: prepared.edgeB,
          edgeRest: prepared.edgeRest,
          supportA: prepared.supportA,
          supportB: prepared.supportB,
          supportRest: prepared.supportRest,
          supportK: prepared.supportK,
          faces: faceFlat,
        };
        const files = {};
        for (const [name, array] of Object.entries(arrays)) files[name] = await writeArray(basePath + `-${name}`, array);
        manifest.models[mesh.name][domain] = {
          name: evalMesh.name,
          domainKind: evalMesh.domainKind,
          sourceIslandId: evalMesh.sourceIslandId,
          faceScale: evalMesh.faceScale,
          anatomicalAxes: { right: evalMesh.right, up: evalMesh.up, front: evalMesh.front },
          vertexCount: prepared.vertexCount,
          triangleCount: prepared.faces.length,
          surfaceSpringCount: prepared.edgeA.length,
          supportSpringCount: prepared.supportA.length,
          surfaceK: prepared.surfaceK,
          damping: prepared.damping,
          stableDt: prepared.stableDt,
          requestedDt: prepared.requestedDt,
          explicitSubsteps: prepared.explicitSubsteps,
          totalMass: prepared.totalMass,
          files,
        };
      }
    }
    const manifestPath = path.join(fixtureDir, 'manifest.json');
    await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2));
    console.log(JSON.stringify({ phase: 'gpu-fixtures-complete', path: path.relative(root, manifestPath), models: manifest.models }));
    return;
  }
  if (argv.has('--domain-audit')) {
    const candidateCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = candidateCheckpoint?.current || createCandidate([0, 0, 0, 2, -1, -1, -2]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const domains = {};
    for (const mesh of meshes) {
      domains[mesh.name] = {
        full: domainAudit(mesh, candidate),
        screen: mesh.screenMesh ? domainAudit(mesh.screenMesh, candidate) : null,
        micro: mesh.microMesh ? domainAudit(mesh.microMesh, candidate) : null,
      };
    }
    const audit = { schema: 'vela-rk4-domain-audit-v1', generatedAt: new Date().toISOString(), sourceMetersPerUnit, frameDt, candidate, domains };
    const auditPath = evidencePath('rk4-domain-audit');
    await fs.mkdir(outputDir, { recursive: true });
    await fs.writeFile(auditPath, JSON.stringify(audit, null, 2));
    console.log(JSON.stringify({ phase: 'domain-audit-complete', path: path.relative(root, auditPath), domains }));
    return;
  }
  if (argv.has('--timestep-audit')) {
    const candidateCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = candidateCheckpoint?.current || createCandidate([0, 0, 0, 2, -1, -1, -2]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const fidelity = process.env.VELA_CALIBRATION_TIMESTEP_FIDELITY || 'micro';
    const seconds = Number(process.env.VELA_CALIBRATION_TIMESTEP_SECONDS || (fidelity === 'full' ? 0.002 : 0.02));
    const factors = (process.env.VELA_CALIBRATION_TIMESTEP_FACTORS || '32,16,8,4,2,1,0.5,0.25').split(',').map(Number).filter(value => Number.isFinite(value) && value > 0);
    const domains = Object.fromEntries(meshes.map(mesh => {
      const evalMesh = fidelity === 'full' ? mesh : fidelity === 'screen' ? mesh.screenMesh || mesh : mesh.microMesh || mesh.screenMesh || mesh;
      return [mesh.name, { domain: evalMesh.name, fidelity, vertices: evalMesh.system.vertexCount, triangles: evalMesh.system.faces.length, timestep: timestepRangeTest(evalMesh, candidate, seconds, offlineModelWallMs, factors) }];
    }));
    const result = { schema: 'vela-rk4-timestep-audit-v1', generatedAt: new Date().toISOString(), candidate, fidelity, seconds, factors, domains, sourceMetersPerUnit };
    const resultPath = evidencePath('rk4-timestep-audit');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(resultPath, JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ phase: 'timestep-audit-complete', path: path.relative(root, resultPath), fidelity, seconds, domains }));
    return;
  }
  if (argv.has('--convergence-audit')) {
    const candidateCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = candidateCheckpoint?.current || createCandidate([0, 0, 0, 2, -1, -1, -2]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const fidelity = process.env.VELA_CALIBRATION_TIMESTEP_FIDELITY || 'full';
    const seconds = Number(process.env.VELA_CALIBRATION_TIMESTEP_SECONDS || (fidelity === 'full' ? 0.002 : 0.02));
    const startingMultiplier = Number(process.env.VELA_CALIBRATION_CONVERGENCE_MULTIPLIER || 32);
    const domains = Object.fromEntries(meshes.map(mesh => {
      const evalMesh = fidelity === 'full' ? mesh : fidelity === 'screen' ? mesh.screenMesh || mesh : mesh.microMesh || mesh.screenMesh || mesh;
      return [mesh.name, { domain: evalMesh.name, fidelity, vertices: evalMesh.system.vertexCount, triangles: evalMesh.system.faces.length, convergence: convergenceTest(evalMesh, candidate, seconds, offlineModelWallMs, startingMultiplier) }];
    }));
    const result = { schema: 'vela-rk4-convergence-audit-v1', generatedAt: new Date().toISOString(), candidate, fidelity, seconds, startingMultiplier, domains, sourceMetersPerUnit };
    const resultPath = evidencePath('rk4-convergence-audit');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(resultPath, JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ phase: 'convergence-audit-complete', path: path.relative(root, resultPath), fidelity, seconds, startingMultiplier, domains }));
    return;
  }
  if (argv.has('--full-domain-evaluation')) {
    const candidateCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = candidateCheckpoint?.current || createCandidate([0, 0, 0, 2, -1, -1, -2]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const evaluations = {};
    for (const mesh of meshes) {
      const result = evaluateCandidate([mesh], candidate, 'full');
      evaluations[mesh.name] = compactResult(result);
    }
    const result = { schema: 'vela-rk4-full-domain-evaluation-v1', generatedAt: new Date().toISOString(), candidate, empiricalStabilityMultiplier, offlineFullSeconds, offlineModelWallMs, evaluations, overall: Object.values(evaluations).every(value => value.valid) ? 'SUCCESS' : 'FAILED' };
    const resultPath = evidencePath('rk4-full-domain-evaluation');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(resultPath, JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ phase: 'full-domain-evaluation-complete', path: path.relative(root, resultPath), candidate, empiricalStabilityMultiplier, evaluations, overall: result.overall }));
    return;
  }
  if (argv.has('--gravity-audit')) {
    const candidateCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = candidateCheckpoint?.current || createCandidate([0, 0, 0, 2, -1, -1, -2]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const seconds = Number(process.env.VELA_CALIBRATION_GRAVITY_AUDIT_SECONDS || offlineGravitySeconds);
    const fidelity = process.env.VELA_CALIBRATION_GRAVITY_AUDIT_FIDELITY || 'full';
    const evaluations = {};
    for (const mesh of meshes) {
      const evalMesh = fidelity === 'micro' ? mesh.microMesh || mesh.screenMesh || mesh : fidelity === 'screen' ? mesh.screenMesh || mesh : mesh;
      evaluations[mesh.name] = { domain: evalMesh.name, fidelity, seconds, vertices: evalMesh.system.vertexCount, triangles: evalMesh.system.faces.length, gravity: gravityTest(evalMesh, candidate, seconds, fidelity, offlineModelWallMs) };
    }
    const result = { schema: 'vela-rk4-gravity-audit-v1', generatedAt: new Date().toISOString(), candidate, fidelity, seconds, offlineModelWallMs, evaluations, overall: Object.values(evaluations).every(value => value.gravity.finite && value.gravity.allComplete && value.gravity.allSettled && value.gravity.worstFlips === 0 && value.gravity.worstCollapses === 0) ? 'SUCCESS' : 'FAILED' };
    const resultPath = evidencePath('rk4-gravity-audit');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(resultPath, JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ phase: 'gravity-audit-complete', path: path.relative(root, resultPath), candidate, fidelity, seconds, evaluations, overall: result.overall }));
    return;
  }
  if (argv.has('--waterfall-candidate')) {
    const candidateCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = candidateCheckpoint?.current || createCandidate([0, 0, 0, 0, -1, -1, -1]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const preflight = pinchPreflight(meshes, candidate);
    const robustness = Object.fromEntries(meshes.map((mesh, index) => [mesh.name, { fidelity: process.env.VELA_CALIBRATION_STRESS_FIDELITY || 'micro', randomPinch: randomPinchStress(stressDomain(mesh), candidate, 20, seed + 100 + index, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds }), gravity: gravityTest(stressDomain(mesh), candidate, offlineGravitySeconds, 'full') }]));
    const robustnessPassed = Object.values(robustness).every(value => value.randomPinch.valid && value.gravity.finite && value.gravity.allComplete && value.gravity.worstFlips === 0 && value.gravity.worstCollapses === 0 && value.gravity.allSettled);
    const fullValidation = robustnessPassed ? Object.fromEntries(meshes.map(mesh => { const result = evaluateCandidate([mesh], candidate, 'full'); return [mesh.name, compactResult(result)]; })) : null;
    const profile = robustnessPassed ? profileCandidate(meshes, candidate) : null;
    const domains = Object.fromEntries(meshes.map(mesh => [mesh.name, { full: { vertexCount: mesh.system.vertexCount, triangleCount: mesh.system.faces.length, islandId: mesh.islandId, domainKind: mesh.domainKind }, screen: { vertexCount: mesh.screenMesh?.system.vertexCount, triangleCount: mesh.screenMesh?.system.faces.length, sourceIslandId: mesh.screenMesh?.sourceIslandId, domainKind: mesh.screenMesh?.domainKind }, micro: { vertexCount: mesh.microMesh?.system.vertexCount, triangleCount: mesh.microMesh?.system.faces.length, sourceIslandId: mesh.microMesh?.sourceIslandId, domainKind: mesh.microMesh?.domainKind } }]));
    const result = { schema: 'vela-rk4-waterfall-candidate-verification-v1', generatedAt: new Date().toISOString(), seed, candidate, domains, preflight, robustness, robustnessPassed, fullValidation, profile, overall: robustnessPassed && fullValidation && Object.values(fullValidation).every(value => value.valid) ? 'SUCCESS' : 'FAILED' };
    const resultPath = path.join(outputDir, 'rk4-waterfall-candidate-verification.json');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(resultPath, JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ phase: 'waterfall-candidate-complete', path: path.relative(root, resultPath), candidate, preflightPassed: preflight.passed, robustnessPassed, fullValidationRan: Boolean(fullValidation), overall: result.overall }));
    return;
  }
  if (argv.has('--material-stress-sweep')) {
    const sweepCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = sweepCheckpoint?.current || createCandidate([0, 0, 0, 0, -1, -1, -1]);
    const pairs = (process.env.VELA_CALIBRATION_MATERIAL_PAIRS || '0,0;0.5,0;0,0.5;0.5,0.5;1,1').split(';').map(pair => pair.split(',').map(Number)).filter(pair => pair.length === 2 && pair.every(Number.isFinite));
    const pinchKpLog = Number(process.env.VELA_CALIBRATION_PINCH_KP_LOG ?? -1);
    const pinchKdLog = Number(process.env.VELA_CALIBRATION_PINCH_KD_LOG ?? -1);
    const dampingLog = Number(process.env.VELA_CALIBRATION_DAMPING_LOG ?? base.logParameters[3] ?? 0);
    const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 3));
    const evaluations = [];
    for (let index = 0; index < pairs.length; index++) {
      const [surfaceLog, innerLog] = pairs[index];
      const candidate = withParameterBlock(base, { 1: surfaceLog, 2: innerLog, 3: dampingLog, 5: pinchKpLog, 6: pinchKdLog });
      const physical = evaluateCandidate(meshes, candidate, 'micro6');
      const stress = Object.fromEntries(meshes.map((mesh, modelIndex) => [mesh.name, randomPinchStress(stressDomain(mesh), candidate, count, seed + 100 + modelIndex, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds })]));
      const record = { candidate, gravity: compactResult(physical), stress };
      evaluations.push(record);
      console.log(JSON.stringify({ phase: 'material-stress-sweep', evaluation: index + 1, candidate, gravityValid: physical.valid, stressValid: Object.values(stress).every(value => value.valid) }));
    }
    const sweep = { schema: 'vela-rk4-material-stress-sweep-v1', generatedAt: new Date().toISOString(), seed, count, holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds, evaluations };
    const sweepPath = path.join(outputDir, 'rk4-material-stress-sweep.json');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(sweepPath, JSON.stringify(sweep, null, 2));
    console.log(JSON.stringify({ phase: 'material-stress-complete', path: path.relative(root, sweepPath), evaluations: evaluations.length }));
    return;
  }
  if (argv.has('--damping-stress-sweep')) {
    const sweepCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = sweepCheckpoint?.current || createCandidate([0, 0.5, 0.5, 0, -1, -1, -1]);
    const surfaceLog = Number(process.env.VELA_CALIBRATION_SURFACE_LOG ?? 0.5);
    const innerLog = Number(process.env.VELA_CALIBRATION_INNER_LOG ?? 0.5);
    const pinchKpLog = Number(process.env.VELA_CALIBRATION_PINCH_KP_LOG ?? -1);
    const pinchKdLog = Number(process.env.VELA_CALIBRATION_PINCH_KD_LOG ?? -1);
    const dampingLogs = (process.env.VELA_CALIBRATION_DAMPING_LOGS || '0,0.5,1,1.5,2').split(',').map(Number).filter(Number.isFinite);
    const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 3));
    const evaluations = [];
    for (let index = 0; index < dampingLogs.length; index++) {
      const candidate = withParameterBlock(base, { 1: surfaceLog, 2: innerLog, 3: dampingLogs[index], 5: pinchKpLog, 6: pinchKdLog });
      const physical = evaluateCandidate(meshes, candidate, 'micro6');
      const stress = Object.fromEntries(meshes.map((mesh, modelIndex) => [mesh.name, randomPinchStress(stressDomain(mesh), candidate, count, seed + 100 + modelIndex, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds })]));
      const record = { candidate, gravity: compactResult(physical), stress };
      evaluations.push(record);
      console.log(JSON.stringify({ phase: 'damping-stress-sweep', evaluation: index + 1, candidate, gravityValid: physical.valid, stressValid: Object.values(stress).every(value => value.valid) }));
    }
    const sweep = { schema: 'vela-rk4-damping-stress-sweep-v1', generatedAt: new Date().toISOString(), seed, count, holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds, fixedSurfaceMultiplier: 10 ** surfaceLog, fixedInnerMultiplier: 10 ** innerLog, evaluations };
    const sweepPath = path.join(outputDir, 'rk4-damping-stress-sweep.json');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(sweepPath, JSON.stringify(sweep, null, 2));
    console.log(JSON.stringify({ phase: 'damping-stress-complete', path: path.relative(root, sweepPath), evaluations: evaluations.length }));
    return;
  }
  if (argv.has('--physical-progression')) {
    const progressionCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = progressionCheckpoint?.current || createCandidate([0, 0, 0, 0, -1, 0, 0]);
    const levels = [
      ['micro', mesh => mesh.microMesh || mesh.screenMesh || mesh],
      ['screen', mesh => mesh.screenMesh || mesh],
      ['full', mesh => mesh],
    ];
    const evaluations = [];
    for (const [fidelity, select] of levels) {
      for (const mesh of meshes) {
        const result = evaluateCandidate([select(mesh)], base, fidelity);
        evaluations.push({ fidelity, model: mesh.name, result: compactResult(result) });
        console.log(JSON.stringify({ phase: 'physical-progression', fidelity, model: mesh.name, valid: result.valid, diagnosis: result.diagnosis, runtimeMs: result.runtimeMs, models: Object.fromEntries(Object.entries(result.models).map(([name, value]) => [name, { incomplete: value.incomplete, evaluatedVertices: value.evaluatedVertices, estimatedStages: value.estimatedStages, stableDt: value.stableDt, requestedDt: value.requestedDt }])) }));
      }
    }
    const progression = { schema: 'vela-rk4-physical-progression-v1', generatedAt: new Date().toISOString(), candidate: base, wallClockLimitMs: offlineModelWallMs, levels: evaluations };
    const progressionPath = path.join(outputDir, 'rk4-physical-progression.json');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(progressionPath, JSON.stringify(progression, null, 2));
    console.log(JSON.stringify({ phase: 'physical-progression-complete', path: path.relative(root, progressionPath), evaluations: evaluations.length }));
    return;
  }
  if (argv.has('--candidate-verify')) {
    const verificationCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = verificationCheckpoint?.current || createCandidate([0, 0, 0, 0, -1, -1, -1]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const physical = evaluateCandidate(meshes, candidate, 'micro6');
    const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 20));
    const stress = Object.fromEntries(meshes.map((mesh, index) => [mesh.name, randomPinchStress(stressDomain(mesh), candidate, count, seed + 100 + index, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds })]));
    const verification = { schema: 'vela-rk4-candidate-verification-v1', generatedAt: new Date().toISOString(), candidate, physical: compactResult(physical), stress };
    const verificationPath = path.join(outputDir, 'rk4-candidate-verification.json');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(verificationPath, JSON.stringify(verification, null, 2));
    console.log(JSON.stringify({ phase: 'candidate-verify-complete', path: path.relative(root, verificationPath), candidate, physicalValid: physical.valid, stressValid: Object.values(stress).every(value => value.valid) }));
    return;
  }
  if (argv.has('--controller-probe')) {
    const probeCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = probeCheckpoint?.current || createCandidate([0, 0, 0, 0, -1, -1, -1]);
    const updates = {};
    for (const [index, variable] of [[0, 'VELA_CALIBRATION_MASS_LOG'], [1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 3));
    const response = Object.fromEntries(meshes.map(mesh => [mesh.name, forceResponse(stressDomain(mesh), candidate, offlineModelWallMs)]));
    const stress = Object.fromEntries(meshes.map((mesh, index) => [mesh.name, randomPinchStress(stressDomain(mesh), candidate, count, seed + 100 + index, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds })]));
    const domains = Object.fromEntries(meshes.map(mesh => [mesh.name, { full: { vertexCount: mesh.system.vertexCount, triangleCount: mesh.system.faces.length, islandId: mesh.islandId, domainKind: mesh.domainKind }, screen: { vertexCount: mesh.screenMesh?.system.vertexCount, triangleCount: mesh.screenMesh?.system.faces.length, sourceIslandId: mesh.screenMesh?.sourceIslandId, domainKind: mesh.screenMesh?.domainKind }, micro: { vertexCount: mesh.microMesh?.system.vertexCount, triangleCount: mesh.microMesh?.system.faces.length, sourceIslandId: mesh.microMesh?.sourceIslandId, domainKind: mesh.microMesh?.domainKind } }]));
    const probe = { schema: 'vela-rk4-controller-response-probe-v1', generatedAt: new Date().toISOString(), seed, candidate, count, holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds, domains, response, stress };
    const probePath = path.join(outputDir, 'rk4-controller-response-probe.json');
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(probePath, JSON.stringify(probe, null, 2));
    console.log(JSON.stringify({ phase: 'controller-probe-complete', path: path.relative(root, probePath), candidate, response: Object.fromEntries(Object.entries(response).map(([name, value]) => [name, { displacement: value.displacement, targetMeters: value.targetMeters, ratio: value.displacement / Math.max(value.targetMeters, 1e-18), flips: value.flips, strain: value.strain }])), stress: Object.fromEntries(Object.entries(stress).map(([name, value]) => [name, { valid: value.valid, rawFolds: value.results.reduce((sum, result) => sum + (result.held?.orientationFlips || 0) + (result.released?.orientationFlips || 0), 0), genuineFolds: value.results.reduce((sum, result) => sum + (result.held?.genuineFolds || 0) + (result.released?.genuineFolds || 0), 0), collapses: value.results.reduce((sum, result) => sum + (result.held?.collapsedTriangles || 0) + (result.released?.collapsedTriangles || 0), 0) }])) }));
    return;
  }
  if (argv.has('--stress-controller-only')) {
    const probeCheckpoint = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
    const base = probeCheckpoint?.current || createCandidate([0, 0, 0, 0, -1, 0, 0]);
    const updates = {};
    for (const [index, variable] of [[1, 'VELA_CALIBRATION_SURFACE_LOG'], [2, 'VELA_CALIBRATION_INNER_LOG'], [3, 'VELA_CALIBRATION_DAMPING_LOG'], [4, 'VELA_CALIBRATION_DT_LOG'], [5, 'VELA_CALIBRATION_PINCH_KP_LOG'], [6, 'VELA_CALIBRATION_PINCH_KD_LOG']]) if (process.env[variable] !== undefined) updates[index] = Number(process.env[variable]);
    const candidate = withParameterBlock(base, updates);
    const count = Math.max(1, Number(process.env.VELA_CALIBRATION_STRESS_COUNT || 20));
    const domains = Object.fromEntries(meshes.map(mesh => [mesh.name, { full: { vertexCount: mesh.system.vertexCount, triangleCount: mesh.system.faces.length, islandId: mesh.islandId, domainKind: mesh.domainKind }, screen: { vertexCount: mesh.screenMesh?.system.vertexCount, triangleCount: mesh.screenMesh?.system.faces.length, sourceIslandId: mesh.screenMesh?.sourceIslandId, domainKind: mesh.screenMesh?.domainKind }, micro: { vertexCount: mesh.microMesh?.system.vertexCount, triangleCount: mesh.microMesh?.system.faces.length, sourceIslandId: mesh.microMesh?.sourceIslandId, domainKind: mesh.microMesh?.domainKind } }]));
    const fidelity = process.env.VELA_CALIBRATION_STRESS_FIDELITY || 'micro';
    const probe = { schema: 'vela-rk4-controller-stress-probe-v1', generatedAt: new Date().toISOString(), seed, candidate, fidelity, count, holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds, models: Object.fromEntries(meshes.map((mesh, index) => [mesh.name, randomPinchStress(stressDomain(mesh), candidate, count, seed + 100 + index, { holdSeconds: stressHoldSeconds, releaseSeconds: stressReleaseSeconds })])) };
    const probePath = evidencePath(`rk4-controller-stress-probe-f-${fidelity}-s-${String(candidate.surfaceMultiplier).replaceAll('.', '_')}-i-${String(candidate.innerMultiplier).replaceAll('.', '_')}-d-${String(candidate.dampingMultiplier).replaceAll('.', '_')}-kp-${String(candidate.pinchKpMultiplier).replaceAll('.', '_')}-kd-${String(candidate.pinchKdMultiplier).replaceAll('.', '_')}-n-${count}`);
    await fs.mkdir(outputDir, { recursive: true }); await fs.writeFile(probePath, JSON.stringify(probe, null, 2));
    console.log(JSON.stringify({ phase: 'stress-controller-complete', probe: path.relative(root, probePath), candidate, models: Object.fromEntries(Object.entries(probe.models).map(([name, value]) => [name, { valid: value.valid, count: value.count, runtimeMs: value.runtimeMs, rawFolds: value.results.reduce((sum, result) => sum + (result.held?.orientationFlips || 0) + (result.released?.orientationFlips || 0), 0), genuineFolds: value.results.reduce((sum, result) => sum + (result.held?.genuineFolds || 0) + (result.released?.genuineFolds || 0), 0), collapses: value.results.reduce((sum, result) => sum + (result.held?.collapsedTriangles || 0) + (result.released?.collapsedTriangles || 0), 0) }])) }));
    return;
  }
  const resource = { stageWallMs: Number(process.env.VELA_CALIBRATION_STAGE_WALL_MS || 90000), stageEvaluationBudget: Number(process.env.VELA_CALIBRATION_STAGE_EVALUATIONS || 12), sigma: Number(process.env.VELA_CALIBRATION_STAGE_SIGMA || 0.45), random: rng(seed + 17) };
  const waterfallCheckpointPath = path.join(outputDir, 'rk4-waterfall-checkpoint.json');
  const resumedWaterfall = resumePath ? await loadWaterfallCheckpoint(resumePath) : null;
  if (resumedWaterfall) console.log(JSON.stringify({ phase: 'waterfall-resume', path: resumePath || waterfallCheckpointPath, stage: resumedWaterfall.stage, completedStages: resumedWaterfall.checkpoints.filter(checkpoint => checkpoint.passed).map(checkpoint => checkpoint.stage) }));
  const waterfall = await runWaterfall(meshes, resource, resumedWaterfall);
  const report = { schema: 'vela-realtime-rk4-calibration-waterfall-v1', generatedAt: new Date().toISOString(), seed, requestedModels, architecture: { sourceMetersPerUnit, frameDt, baseDt, anchorDepthFactor, neighborAnchorCount, originalTopology: true, crossIslandSprings: 0, integrator: 'RK4', massFromTriangleArea: true, fixedInnerAnchors: true }, massPolicy: { referenceMassMultiplier: 1, effectiveMassSearchBounds: defaultLogBounds[0], anatomicalInterpretation: 'Area-derived relative masses are preserved. Multipliers above 1 are effective numerical mass calibration, not anatomical density claims.', surfaceModulusBaselinePa: 30000, innerModulusBaselinePa: 10000, surfaceMultiplierBounds: defaultLogBounds[1], innerMultiplierBounds: defaultLogBounds[2] }, timestepPolicy: { conservativeEstimateFactor: 0.12, includesSpringAndDampingRates: true, empiricalStabilityMultiplier, empiricalMultiplierIsOnlyEnabledAfterConvergenceAudit: true }, offlineCalibration: { realTimeGatesDisabled: true, estimatedStageCountsAreInformational: true, offlineStageLimit: maxOfflineStages, screenStageLimit: maxOfflineScreenStages, wallClockProtectionOnly: true, perModelWallClockLimitMs: offlineModelWallMs, maxSubstepsRetainedForPerformanceReport: maxSubsteps, maxEstimatedStagesRetainedForPerformanceReport: maxEstimatedStages }, stageResource: resource, waterfall, reproduction: { command: 'node scripts/calibrate_realtime_rk4.mjs', checkpoint: waterfallCheckpointPath, resumeCommand: `node scripts/calibrate_realtime_rk4.mjs --resume "${waterfallCheckpointPath}"`, physicalProgressionCommand: `VELA_CALIBRATION_OFFLINE_MODEL_WALL_MS=${offlineModelWallMs} node scripts/calibrate_realtime_rk4.mjs --resume "${waterfallCheckpointPath}" --physical-progression` }, elapsedMs: performance.now() - started, overall: waterfall.overall };
  report.offlineCalibration.gravitySeconds = offlineGravitySeconds;
  report.offlineCalibration.stressHoldSeconds = stressHoldSeconds;
  report.offlineCalibration.stressReleaseSeconds = stressReleaseSeconds;
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'rk4-calibration-report.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(outputDir, 'rk4-calibration-summary.md'), `# Staged RK4 waterfall calibration\n\nGenerated ${report.generatedAt}.\n\n- Stages completed through: ${waterfall.completedStage}\n- Reference mass multiplier: 1\n- Offline physical gates excluded the real-time operation estimate.\n- Screen and full-island performance are reported separately.\n- Checkpoint: [rk4-waterfall-checkpoint.json](./rk4-waterfall-checkpoint.json)\n- Resume: \`${report.reproduction.resumeCommand}\`\n\nStage results:\n\n${waterfall.stages.map(stage => `- ${stage.name}: ${stage.passed ? 'PASS' : 'FAILED'} with ${stage.evaluations.length} evaluations`).join('\n')}\n\nFull validation and stress results are in [rk4-calibration-report.json](./rk4-calibration-report.json).\n\nOVERALL STEP RESULT: ${report.overall}`);
  if (waterfall.stages.some(stage => !stage.passed)) {
    const summaryPath = path.join(outputDir, 'rk4-calibration-summary.md');
    const summary = await fs.readFile(summaryPath, 'utf8');
    await fs.writeFile(summaryPath, summary.replace('Full validation and stress results are in', 'Stages after the first failed gate were NOT RUN. Their status and the full-island validation fields are recorded in'));
  }
  console.log(JSON.stringify({ phase: 'complete', completedStage: waterfall.completedStage, stages: waterfall.stages.map(stage => ({ name: stage.name, passed: stage.passed, evaluations: stage.evaluations.length })), checkpoint: path.join(outputDir, 'rk4-waterfall-checkpoint.json'), report: path.relative(root, path.join(outputDir, 'rk4-calibration-report.json')), elapsedMs: performance.now() - started, overall: report.overall }));
}

if (argv.has('--feedback-demo')) {
  console.log(JSON.stringify({ phase: 'feedback-demo', ...feedbackDemo() }, null, 2));
} else {
  main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
}
