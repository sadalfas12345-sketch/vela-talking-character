import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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

function makeIslandMesh(name, positions, indices, topology, islandId, points, right, up, front, faceScale) {
  const globalVertices = topology.vertices[islandId];
  const globalToLocal = new Int32Array(positions.length / 3); globalToLocal.fill(-1);
  for (let i = 0; i < globalVertices.length; i++) globalToLocal[globalVertices[i]] = i;
  const localFaces = [];
  for (const face of topology.faces[islandId]) {
    const ia = globalToLocal[indices[face * 3]], ib = globalToLocal[indices[face * 3 + 1]], ic = globalToLocal[indices[face * 3 + 2]];
    if (ia >= 0 && ib >= 0 && ic >= 0) localFaces.push([ia, ib, ic]);
  }
  const neutral = new Float64Array(globalVertices.length * 3);
  for (let i = 0; i < globalVertices.length; i++) for (let axis = 0; axis < 3; axis++) neutral[i * 3 + axis] = positions[globalVertices[i] * 3 + axis];
  const mesh = { name, points, right, up, front, faceScale, neutral, faces: localFaces, globalVertices, allVertexCount: positions.length / 3, islandCount: topology.vertices.length, islandId };
  mesh.system = buildSystem(mesh);
  return mesh;
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
  const smallCandidates = topology.vertices.map((vertices, islandId) => ({ islandId, size: vertices.length })).filter(item => item.size >= 128 && item.size <= Math.min(4000, topology.vertices[selectedId].length));
  const screenChoice = smallCandidates.sort((a, b) => Math.abs(a.size - 1000) - Math.abs(b.size - 1000))[0];
  mesh.screenMesh = screenChoice && screenChoice.islandId !== selectedId ? makeIslandMesh(`${name}-screen-island-${screenChoice.islandId}`, positions, indices, topology, screenChoice.islandId, points, right, up, front, faceScale) : mesh;
  return mesh;
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
  const systems = { vertexCount, faces, neutral, anchors, faceAreas, faceNormals, attributedArea, edgeA: Uint32Array.from(edgeA), edgeB: Uint32Array.from(edgeB), edgeRest: Float64Array.from(edgeRest), adjacency, medianEdge };
  return systems;
}

const defaultLogBounds = [[0, 8], [-2, 2], [-2, 4], [-1, 2], [-1, 1]];
function createCandidate(logs, bounds = defaultLogBounds) {
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  const bounded = logs.map((value, index) => clamp(Number(value), bounds[index][0], bounds[index][1]));
  return {
    massMultiplier: 10 ** bounded[0],
    surfaceMultiplier: 10 ** bounded[1],
    innerMultiplier: 10 ** bounded[2],
    dampingMultiplier: 10 ** bounded[3],
    dtMultiplier: 10 ** bounded[4],
    logParameters: bounded,
  };
}

function preparePhysics(mesh, candidate) {
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
  const stableDt = Math.min(requestedDt, 0.12 * Math.sqrt(minMass / Math.max(maxLocalK, 1e-18)));
  const damping = 0.08 * candidate.dampingMultiplier * 2 * Math.sqrt(Math.max(surfaceK * medianMass, 1e-18));
  return { ...base, masses, surfaceK, supportA: Uint32Array.from(supportA), supportB: Uint32Array.from(supportB), supportRest: Float64Array.from(supportRest), supportK: Float64Array.from(supportK), stableDt, requestedDt, damping, totalMass, minMass, medianMass, maxLocalK, explicitSubsteps: Math.max(1, Math.ceil(frameDt / Math.max(stableDt, 1e-18))) };
}

function simulate(model, candidate, options = {}) {
  const system = preparePhysics(model, candidate), n = system.vertexCount, length = n * 3;
  const positions = new Float64Array(options.initialPositions || system.neutral), velocities = new Float64Array(options.initialVelocities || length), a1 = new Float64Array(length), a2 = new Float64Array(length), a3 = new Float64Array(length), a4 = new Float64Array(length), x2 = new Float64Array(length), x3 = new Float64Array(length), x4 = new Float64Array(length), v2 = new Float64Array(length), v3 = new Float64Array(length), v4 = new Float64Array(length), forceN = new Float64Array(length);
  const gravity = options.gravity || [0, 0, 0]; const seconds = options.seconds ?? 0.05; const usePinch = options.pinch || null;
  const substepsPerFrame = options.substepsOverride || system.explicitSubsteps; const defaultH = options.timeStepOverride || frameDt / substepsPerFrame;
  const neutral = system.neutral, edgeCount = system.edgeA.length;
  const forces = (x, v, out) => {
    out.fill(0);
    for (let i = 0; i < edgeCount; i++) {
      const ia = system.edgeA[i], ib = system.edgeB[i], dx = x[ib * 3] - x[ia * 3], dy = x[ib * 3 + 1] - x[ia * 3 + 1], dz = x[ib * 3 + 2] - x[ia * 3 + 2], len = Math.hypot(dx, dy, dz); if (len <= 1e-12) continue;
      const q = system.surfaceK * ((len - system.edgeRest[i]) * sourceMetersPerUnit) / len;
      add3(out, ia, q * dx, q * dy, q * dz); add3(out, ib, -q * dx, -q * dy, -q * dz);
    }
    for (let i = 0; i < system.supportA.length; i++) {
      const ia = system.supportA[i], ib = system.supportB[i], dx = system.anchors[ib * 3] - x[ia * 3], dy = system.anchors[ib * 3 + 1] - x[ia * 3 + 1], dz = system.anchors[ib * 3 + 2] - x[ia * 3 + 2], len = Math.hypot(dx, dy, dz); if (len <= 1e-12) continue;
      const q = system.supportK[i] * ((len - system.supportRest[i]) * sourceMetersPerUnit) / len; add3(out, ia, q * dx, q * dy, q * dz);
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
  let nonfinite = false, maxVelocity = 0, steps = 0, elapsed = 0;
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
  while (elapsed < seconds - 1e-15 && !nonfinite) { const h = Math.min(defaultH, seconds - elapsed); rk4(h); elapsed += h; }
  forces(positions, velocities, forceN);
  let maxNetForce = 0, forceRms = 0, finalVelocity = 0, velocityRms = 0;
  for (let i = 0; i < n; i++) { const fm = Math.hypot(forceN[i * 3], forceN[i * 3 + 1], forceN[i * 3 + 2]); const vm = Math.hypot(velocities[i * 3], velocities[i * 3 + 1], velocities[i * 3 + 2]); maxNetForce = Math.max(maxNetForce, fm); forceRms += fm * fm; finalVelocity = Math.max(finalVelocity, vm); velocityRms += vm * vm; }
  const geometry = geometryMetrics(system, positions);
  const maxDisplacement = maxVertexDisplacement(neutral, positions);
  const totalGravityForce = system.totalMass * Math.hypot(...gravity);
  return { positions, velocities, system, geometry: { ...geometry, maxDisplacement, maxVelocity, finalVelocity, normalizedVelocity: finalVelocity * frameDt / Math.max(model.faceScale, 1e-12), maxNetForceN: maxNetForce, rmsNetForceN: Math.sqrt(forceRms / Math.max(n, 1)), forceResidualRatio: maxNetForce / Math.max(totalGravityForce / Math.max(n, 1), 1e-12) }, steps, seconds: elapsed, nonfinite, pinch: usePinch ? { ...usePinch } : null };
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
  return { maxEdgeStrain: maxStrain, p95EdgeStrain: p95, orientationFlips: flips, collapsedTriangles: collapses, minAreaRatio, finite: positions.every(Number.isFinite) };
}

function directions(mesh) {
  return {
    down: mesh.up.map(v => -v), up: mesh.up, left: mesh.right.map(v => -v), right: mesh.right, forward: mesh.front, backward: mesh.front.map(v => -v),
  };
}

function gravityTest(mesh, candidate, seconds, fidelity = 'full') {
  const results = {};
  const testedDirections = fidelity === 'screen' ? ['down'] : gravityDirections;
  for (const direction of testedDirections) {
    const unit = directions(mesh)[direction]; const result = simulate(mesh, candidate, { gravity: unit.map(v => v * 9.81), seconds });
    results[direction] = { geometry: result.geometry, steps: result.steps, simulatedSeconds: result.seconds, wallMs: 0, settled: result.geometry.normalizedVelocity <= maxNormalizedVelocity && result.geometry.forceResidualRatio <= maxForceResidualRatio };
  }
  const all = Object.values(results); return { directions: results, worstFlips: Math.max(...all.map(v => v.geometry.orientationFlips)), worstCollapses: Math.max(...all.map(v => v.geometry.collapsedTriangles)), worstStrain: Math.max(...all.map(v => v.geometry.maxEdgeStrain)), maxDisplacement: Math.max(...all.map(v => v.geometry.maxDisplacement)), maxVelocity: Math.max(...all.map(v => v.geometry.maxVelocity)), maxFinalVelocity: Math.max(...all.map(v => v.geometry.finalVelocity)), maxForceResidualRatio: Math.max(...all.map(v => v.geometry.forceResidualRatio)), allSettled: all.every(v => v.settled), finite: all.every(v => v.geometry.finite), fidelity };
}

function forceResponse(mesh, candidate) {
  const system = preparePhysics(mesh, candidate), face = system.faces[Math.floor(system.faces.length / 2)], ids = face, weights = [1 / 3, 1 / 3, 1 / 3];
  const origin = [0, 0, 0]; for (let j = 0; j < 3; j++) for (let axis = 0; axis < 3; axis++) origin[axis] += weights[j] * system.neutral[ids[j] * 3 + axis];
  const target = origin.slice(); target[1] += mesh.faceScale * 0.001;
  const result = simulate(mesh, candidate, { gravity: [0, 0, 0], seconds: 0.02, pinch: { ids, weights, target, velocity: [0, 0, 0], kp: 90, kd: 0.08, peakForce: 0 } });
  return { displacement: result.geometry.maxDisplacement, targetMeters: mesh.faceScale * 0.001 * sourceMetersPerUnit, finite: result.geometry.finite, flips: result.geometry.orientationFlips, strain: result.geometry.maxEdgeStrain, forceN: result.pinch?.peakForce || 0 };
}

function convergenceTest(mesh, candidate) {
  const gravity = directions(mesh).down.map(v => v * 9.81);
  const seconds = 0.03333333333333333;
  const stableDt = preparePhysics(mesh, candidate).stableDt;
  const solves = [stableDt, stableDt * 0.5, stableDt * 0.25].map(timeStepOverride => simulate(mesh, candidate, { gravity, seconds, timeStepOverride }));
  const compare = (a, b) => { let sumP = 0, sumV = 0, maxP = 0, maxV = 0; for (let i = 0; i < a.positions.length; i += 3) { const dp = Math.hypot(a.positions[i] - b.positions[i], a.positions[i + 1] - b.positions[i + 1], a.positions[i + 2] - b.positions[i + 2]); const dv = Math.hypot(a.velocities[i] - b.velocities[i], a.velocities[i + 1] - b.velocities[i + 1], a.velocities[i + 2] - b.velocities[i + 2]); sumP += dp * dp; sumV += dv * dv; maxP = Math.max(maxP, dp); maxV = Math.max(maxV, dv); } return { rmsPositionSource: Math.sqrt(sumP / (a.positions.length / 3)), maxPositionSource: maxP, rmsVelocitySource: Math.sqrt(sumV / (a.positions.length / 3)), maxVelocitySource: maxV }; };
  const hVsH2 = compare(solves[0], solves[1]), h2VsH4 = compare(solves[1], solves[2]);
  const positionOrder = h2VsH4.rmsPositionSource > 0 ? hVsH2.rmsPositionSource / h2VsH4.rmsPositionSource : Infinity;
  const velocityOrder = h2VsH4.rmsVelocitySource > 0 ? hVsH2.rmsVelocitySource / h2VsH4.rmsVelocitySource : Infinity;
  return { durationSeconds: seconds, steps: solves.map(result => result.steps), timeSteps: [stableDt, stableDt * 0.5, stableDt * 0.25], hVsH2, h2VsH4, positionOrder, velocityOrder, converged: h2VsH4.rmsPositionSource / Math.max(mesh.faceScale, 1e-12) < convergenceTolerance && h2VsH4.rmsVelocitySource * frameDt / Math.max(mesh.faceScale, 1e-12) < convergenceTolerance, samples: solves.map(result => ({ orientationFlips: result.geometry.orientationFlips, collapsedTriangles: result.geometry.collapsedTriangles, finalVelocity: result.geometry.finalVelocity, maxNetForceN: result.geometry.maxNetForceN })) };
}

function randomPinchStress(mesh, candidate, count = 20, stressSeed = seed) {
  const random = rng(stressSeed), system = preparePhysics(mesh, candidate), results = [];
  const directionsByName = directions(mesh);
  const directionNames = Object.keys(directionsByName);
  const started = performance.now();
  for (let sequence = 0; sequence < count; sequence++) {
    const face = system.faces[Math.floor(random() * system.faces.length)], ids = face.slice();
    let u = random(), v = random(); if (u + v > 1) { u = 1 - u; v = 1 - v; }
    const weights = [1 - u - v, u, v], origin = [0, 0, 0];
    for (let j = 0; j < 3; j++) for (let axis = 0; axis < 3; axis++) origin[axis] += weights[j] * system.neutral[ids[j] * 3 + axis];
    const directionName = directionNames[Math.floor(random() * directionNames.length)];
    const direction = directionsByName[directionName];
    const magnitude = mesh.faceScale * (0.002 + random() * 0.01), target = origin.map((value, axis) => value + direction[axis] * magnitude);
    let positions = new Float64Array(system.neutral), velocities = new Float64Array(system.vertexCount * 3), heldGeometry = null, maxForce = 0, maxTrackingError = 0, invalid = false;
    for (let phase = 1; phase <= 4; phase++) {
      const phaseTarget = origin.map((value, axis) => value + (target[axis] - value) * phase / 4);
      const pin = { ids, weights, target: phaseTarget, velocity: direction.map(value => value * magnitude * 4), kp: 90, kd: 0.08, peakForce: 0 };
      const segment = simulate(mesh, candidate, { gravity: direction.map(value => value * 9.81), seconds: 1 / 60, initialPositions: positions, initialVelocities: velocities, pinch: pin });
      positions = segment.positions; velocities = segment.velocities; heldGeometry = segment.geometry; maxForce = Math.max(maxForce, pin.peakForce || 0); maxTrackingError = Math.max(maxTrackingError, pin.error || 0); invalid ||= segment.nonfinite || segment.geometry.orientationFlips > 0 || segment.geometry.collapsedTriangles > 0;
    }
    const release = simulate(mesh, candidate, { gravity: direction.map(value => value * 9.81), seconds: 0.20, initialPositions: positions, initialVelocities: velocities });
    const recoveredDisplacement = maxVertexDisplacement(system.neutral, release.positions);
    results.push({ sequence, face, direction: directionName, magnitudeSource: magnitude, held: heldGeometry, released: release.geometry, recoveredDisplacement, peakForceN: maxForce, peakTrackingErrorMeters: maxTrackingError, valid: !invalid && release.geometry.finite && release.geometry.orientationFlips === 0 && release.geometry.collapsedTriangles === 0 });
  }
  return { count, valid: results.every(result => result.valid), results, runtimeMs: performance.now() - started };
}

function candidateKey(candidate) { return JSON.stringify([candidate.massMultiplier, candidate.surfaceMultiplier, candidate.innerMultiplier, candidate.dampingMultiplier, candidate.dtMultiplier]); }
function evaluationKey(meshes, candidate, fidelity) { return `${requestedModels.join(',')}|${fidelity}|${candidateKey(candidate)}`; }

function diagnoseModel(value) {
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
    const evalMesh = fidelity === 'full' ? mesh : mesh.screenMesh || mesh;
    const prepared = preparePhysics(evalMesh, candidate);
    const seconds = fidelity === 'screen' ? 0.05 : fidelity === 'full' ? 0.10 : 0.03333333333333333;
    const frameCount = Math.max(1, Math.ceil(seconds / frameDt));
    const directionCount = fidelity === 'screen' ? 1 : gravityDirections.length;
    const estimatedStages = prepared.explicitSubsteps * frameCount * directionCount * 4 * (prepared.edgeA.length + prepared.supportA.length);
    if (prepared.explicitSubsteps > maxSubsteps) {
      perModel[mesh.name] = { rejected: 'substep-budget', evaluatedIsland: evalMesh.name, evaluatedVertices: prepared.vertexCount, triangles: prepared.faces.length, surfaceSprings: prepared.edgeA.length, supportSprings: prepared.supportA.length, estimatedStages, stableDt: prepared.stableDt, substepsPerFrame: prepared.explicitSubsteps, totalMassKg: prepared.totalMass };
      continue;
    }
    if (estimatedStages > maxEstimatedStages) {
      perModel[mesh.name] = { rejected: 'operation-budget', evaluatedIsland: evalMesh.name, evaluatedVertices: prepared.vertexCount, triangles: prepared.faces.length, surfaceSprings: prepared.edgeA.length, supportSprings: prepared.supportA.length, estimatedStages, maxEstimatedStages, stableDt: prepared.stableDt, substepsPerFrame: prepared.explicitSubsteps, totalMassKg: prepared.totalMass };
      continue;
    }
    const gravity = gravityTest(evalMesh, candidate, seconds, fidelity);
    const response = forceResponse(evalMesh, candidate);
    const convergence = fidelity === 'full' ? convergenceTest(evalMesh, candidate) : null;
    const invalid = !gravity.finite || gravity.worstFlips > 0 || gravity.worstCollapses > 0 || gravity.worstStrain > maxGravityStrain || !gravity.allSettled || response.flips > 0 || !response.finite;
    perModel[mesh.name] = { gravity, response, convergence, evaluatedIsland: evalMesh.name, evaluatedVertices: prepared.vertexCount, triangles: prepared.faces.length, surfaceSprings: prepared.edgeA.length, supportSprings: prepared.supportA.length, estimatedStages, runtimeMs: performance.now() - started, stableDt: prepared.stableDt, substepsPerFrame: prepared.explicitSubsteps, totalMassKg: prepared.totalMass };
    if (invalid && fidelity !== 'full') break;
  }
  const values = Object.values(perModel); const valid = values.length === meshes.length && values.every(v => !v.rejected && v.gravity.finite && v.gravity.worstFlips === 0 && v.gravity.worstCollapses === 0 && v.gravity.worstStrain <= maxGravityStrain && v.gravity.allSettled && v.response.flips === 0 && v.response.displacement > v.response.targetMeters * 0.01 && (v.convergence ? v.convergence.converged : true));
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
  const ranked = results.filter(result => result.diagnosis).slice().sort((a, b) => b.diagnosis.failureDistance - a.diagnosis.failureDistance);
  return ranked[0]?.diagnosis || { dominantMechanism: 'unknown', failureDistance: 1, modelDiagnoses: {} };
}

function adaptSearchState(state, results, phase) {
  const diagnosis = resultDominantMechanism(results);
  const amount = Math.max(0.2, Math.min(1.5, diagnosis.failureDistance || 0.2));
  const shifts = {
    'operation-budget': [0.65, -0.35, -0.25, 0.05, 0.85],
    'substep-budget': [0.55, -0.30, -0.20, 0.05, 0.75],
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
  if (diagnosis.dominantMechanism === 'operation-budget' || diagnosis.dominantMechanism === 'substep-budget') {
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
  const deterministicSeeds = [[0, 0, 3, 1, 0], [2, 1, 3, 1, 0], [3, 2, 4, 1, 1], [4, 1, 4, 2, 1], [5, 0, 4, 2, 1], [5, 1, 4, 2, 1], [6, 0, 4, 2, 1]];
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
  for (const [name, value] of Object.entries(result.models || {})) out.models[name] = value.rejected ? { rejected: value.rejected, evaluatedIsland: value.evaluatedIsland, evaluatedVertices: value.evaluatedVertices, triangles: value.triangles, surfaceSprings: value.surfaceSprings, supportSprings: value.supportSprings, estimatedStages: value.estimatedStages, maxEstimatedStages: value.maxEstimatedStages, stableDt: value.stableDt, substepsPerFrame: value.substepsPerFrame, totalMassKg: value.totalMassKg } : { gravity: { worstFlips: value.gravity.worstFlips, worstCollapses: value.gravity.worstCollapses, worstStrain: value.gravity.worstStrain, maxDisplacement: value.gravity.maxDisplacement, maxVelocity: value.gravity.maxVelocity, maxFinalVelocity: value.gravity.maxFinalVelocity, maxForceResidualRatio: value.gravity.maxForceResidualRatio, allSettled: value.gravity.allSettled, finite: value.gravity.finite }, response: value.response, convergence: value.convergence, evaluatedIsland: value.evaluatedIsland, evaluatedVertices: value.evaluatedVertices, triangles: value.triangles, surfaceSprings: value.surfaceSprings, supportSprings: value.supportSprings, estimatedStages: value.estimatedStages, stableDt: value.stableDt, substepsPerFrame: value.substepsPerFrame, totalMassKg: value.totalMassKg, runtimeMs: value.runtimeMs };
  return out;
}

async function main() {
  const started = performance.now(), random = rng(seed), loaded = {};
  for (const name of requestedModels) { console.log(JSON.stringify({ phase: 'load', model: name })); loaded[name] = await loadModel(name); console.log(JSON.stringify({ phase: 'loaded', model: name, islandVertices: loaded[name].system.vertexCount, islandTriangles: loaded[name].system.faces.length, islandCount: loaded[name].islandCount })); }
  const meshes = Object.values(loaded), baselineCandidate = createCandidate([0, 0, 0, 0, 0]), existingCandidate = createCandidate([6, Math.log10(0.25), Math.log10(800), Math.log10(0.18 / 0.08), 0]);
  const baseline = evaluateCandidate(meshes, baselineCandidate, 'screen'); baseline.source = 'biological-baseline'; baseline.generation = -1;
  const existing = evaluateCandidate(meshes, existingCandidate, 'screen'); existing.source = 'existing-realtime'; existing.generation = -1;
  console.log(JSON.stringify({ phase: 'baseline', biological: compactResult(baseline), existingRealtime: compactResult(existing) }));
  const resumed = await loadCheckpoint(resumePath);
  if (resumePath) console.log(JSON.stringify({ phase: 'resume', path: resumePath, loaded: Boolean(resumed), cycle: resumed?.cycle ?? null, cachedResults: resultCache.size }));
  const search = noSearch ? { state: { cycle: 0, history: [], generationSummaries: [], feedbackHistory: [], outstandingConstraints: [], feedbackDemo: feedbackDemo() }, best: null, exhausted: false } : await adaptiveSearch(meshes, random, resumed);
  const history = (search.state.history || []).map(normalizeCompactResult);
  const fullHistory = history.filter(result => result.fidelity === 'full');
  const bestRecord = search.best ? compactResult(search.best) : sortResults(fullHistory)[0] || sortResults([compactResult(baseline), compactResult(existing)])[0] || null;
  const bestCandidate = bestRecord?.candidate || null;
  const finalValidation = [];
  if (bestCandidate && bestRecord && Object.values(bestRecord.models || {}).every(value => !value.rejected)) {
    for (const mesh of meshes) {
      const gravity = gravityTest(mesh, bestCandidate, 0.20, 'final');
      const convergence = convergenceTest(mesh, bestCandidate);
      const response = forceResponse(mesh, bestCandidate);
      finalValidation.push({ model: mesh.name, gravity, convergence, response, realTime: { stableDt: preparePhysics(mesh, bestCandidate).stableDt, substepsPerFrame: preparePhysics(mesh, bestCandidate).explicitSubsteps } });
    }
  }
  const pinchStress = bestRecord?.valid && bestCandidate && Object.values(bestRecord.models || {}).every(value => !value.rejected)
    ? Object.fromEntries(meshes.map((mesh, index) => [mesh.name, randomPinchStress(mesh, bestCandidate, 20, seed + index + 1)]))
    : { status: 'not-run', reason: 'No full candidate passed both-character gravity, geometry, convergence, and compute gates.' };
  const report = { schema: 'vela-realtime-rk4-calibration-v2', generatedAt: new Date().toISOString(), seed, requestedModels, architecture: { sourceMetersPerUnit, frameDt, baseDt, anchorDepthFactor, neighborAnchorCount, originalTopology: true, crossIslandSprings: 0, integrator: 'RK4', massFromTriangleArea: true, fixedInnerAnchors: true }, gates: { maxGravityStrain, maxNormalizedVelocity, maxForceResidualRatio, convergenceTolerance }, search: { cycles: search.state.cycle, maxCycles, maxWallMs, populationSize, fullSurvivors, maxSubsteps, maxEstimatedStages, algorithm: 'adaptive bounded log-space CMA-ES with failure-distance feedback, multi-fidelity promotion, caching, and checkpoints', parameterBounds: defaultLogBounds.map(pair => pair.slice()), finalBounds: search.state.bounds || defaultLogBounds, baseline: compactResult(baseline), existingRealtime: compactResult(existing), history, generationSummaries: search.state.generationSummaries || [], feedbackHistory: search.state.feedbackHistory || [], outstandingConstraints: search.state.outstandingConstraints || [], feedbackDemo: search.state.feedbackDemo, best: bestRecord, finalValidation, pinchStress, checkpointPath, resumeCommand: `node scripts/calibrate_realtime_rk4.mjs --resume "${checkpointPath}"`, elapsedMs: performance.now() - started }, overall: bestRecord?.valid ? 'SUCCESS' : 'FAILED' };
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'rk4-calibration-report.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(outputDir, 'rk4-calibration-summary.md'), `# Automated RK4 calibration\n\nGenerated ${report.generatedAt}.\n\n- Seed: ${seed}\n- Algorithm: ${report.search.algorithm}\n- Models: ${requestedModels.join(', ')}\n- Cycles completed: ${search.state.cycle} of ${maxCycles}\n- Best feasible candidate: ${bestRecord?.valid ? 'YES' : 'NO'}\n- Best parameters: \`${JSON.stringify(bestCandidate)}\`\n- Dominant final diagnosis: ${bestRecord?.diagnosis?.dominantMechanism || 'none'}\n- Full validation: ${bestRecord?.valid ? 'completed' : 'no candidate passed all numerical gates'}\n- Checkpoint: [rk4-calibration-checkpoint.json](./rk4-calibration-checkpoint.json)\n- Resume: \`${report.search.resumeCommand}\`\n\nThe complete candidate history, feedback decisions, convergence diagnostics, and rejection metrics are in [rk4-calibration-report.json](./rk4-calibration-report.json).\n\nFeedback demonstration: first generation deliberately failed all candidates, detected operation-budget as the dominant mechanism, and changed the next-generation mean and bounds: ${search.state.feedbackDemo?.passed ? 'PASS' : 'FAIL'}.\n\nOVERALL STEP RESULT: ${report.overall}`);
  console.log(JSON.stringify({ phase: 'complete', best: bestRecord, cycles: search.state.cycle, checkpoint: checkpointPath, report: path.relative(root, path.join(outputDir, 'rk4-calibration-report.json')), elapsedMs: performance.now() - started, overall: report.overall }));
}

if (argv.has('--feedback-demo')) {
  console.log(JSON.stringify({ phase: 'feedback-demo', ...feedbackDemo() }, null, 2));
} else {
  main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
}
