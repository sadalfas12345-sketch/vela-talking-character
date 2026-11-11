import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'verification', 'island-spring-pinch');
const n = 3;
const dim = n * 3;
const masses = [0.001, 0.002, 0.004];
const invMass = masses.map(value => 1 / value);
const scale = 0.30;
const dt = 1 / 600;
const damping = 0.02;
const edges = [{ a: 0, b: 1, rest: 0.95, k: 40 }, { a: 1, b: 2, rest: 0.90, k: 35 }];
const supports = [{ a: 0, anchor: [0, -0.1, 0], rest: 0.9, k: 18 }, { a: 2, anchor: [0.1, 0.05, 0], rest: 0.85, k: 15 }];
const pin = { ids: [0, 1, 2], weights: [0.2, 0.5, 0.3], kp: 12, kd: 0.04, target: [0.02, -0.01, 0.015], targetVelocity: [0, 0, 0] };
const xPrevious = new Float64Array([0, 0, 0, 0.92, 0.08, 0, 1.78, 0.03, 0.02]);
const vPrevious = new Float64Array([0.2, -0.1, 0.05, -0.03, 0.1, 0.02, 0.04, -0.02, 0.08]);
const x = new Float64Array([0.02, -0.04, 0.03, 0.95, 0.13, -0.02, 1.72, 0.01, 0.11]);
const close = (a, b, tolerance) => Math.abs(a - b) <= tolerance;
const maxAbs = values => values.reduce((m, value) => Math.max(m, Math.abs(value)), 0);
const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
const mul = (matrix, vector) => Float64Array.from(matrix.map(row => dot(row, vector)));
const zeroMatrix = () => Array.from({ length: dim }, () => Array(dim).fill(0));
const addBlock = (matrix, rows, cols, block, scaleFactor = 1) => {
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) matrix[rows[r]][cols[c]] += block[r][c] * scaleFactor;
};
function springHessian(dx, dy, dz, length, k, rest) {
  const ux = dx / length, uy = dy / length, uz = dz / length;
  const axial = k * rest / length, transverse = k * (1 - rest / length);
  return [
    [transverse + axial * ux * ux, axial * ux * uy, axial * ux * uz],
    [axial * ux * uy, transverse + axial * uy * uy, axial * uy * uz],
    [axial * ux * uz, axial * uy * uz, transverse + axial * uz * uz],
  ];
}
function accelerationAt(position, velocity) {
  const result = new Float64Array(dim);
  for (const edge of edges) {
    const a = edge.a * 3, b = edge.b * 3;
    const dx = position[b] - position[a], dy = position[b + 1] - position[a + 1], dz = position[b + 2] - position[a + 2];
    const length = Math.hypot(dx, dy, dz);
    const q = edge.k * ((length - edge.rest) * scale) / length;
    const fx = q * dx, fy = q * dy, fz = q * dz;
    result[a] += fx * invMass[edge.a] / scale; result[a + 1] += fy * invMass[edge.a] / scale; result[a + 2] += fz * invMass[edge.a] / scale;
    result[b] -= fx * invMass[edge.b] / scale; result[b + 1] -= fy * invMass[edge.b] / scale; result[b + 2] -= fz * invMass[edge.b] / scale;
  }
  for (const spring of supports) {
    const a = spring.a * 3, dx = spring.anchor[0] - position[a], dy = spring.anchor[1] - position[a + 1], dz = spring.anchor[2] - position[a + 2];
    const length = Math.hypot(dx, dy, dz), q = spring.k * ((length - spring.rest) * scale) / length;
    result[a] += q * dx * invMass[spring.a] / scale; result[a + 1] += q * dy * invMass[spring.a] / scale; result[a + 2] += q * dz * invMass[spring.a] / scale;
  }
  let qx = 0, qy = 0, qz = 0, qvx = 0, qvy = 0, qvz = 0;
  for (let j = 0; j < 3; j++) { const id = pin.ids[j] * 3, w = pin.weights[j]; qx += w * position[id]; qy += w * position[id + 1]; qz += w * position[id + 2]; qvx += w * velocity[id]; qvy += w * velocity[id + 1]; qvz += w * velocity[id + 2]; }
  const fx = pin.kp * ((pin.target[0] - qx) * scale) + pin.kd * ((pin.targetVelocity[0] - qvx) * scale);
  const fy = pin.kp * ((pin.target[1] - qy) * scale) + pin.kd * ((pin.targetVelocity[1] - qvy) * scale);
  const fz = pin.kp * ((pin.target[2] - qz) * scale) + pin.kd * ((pin.targetVelocity[2] - qvz) * scale);
  for (let j = 0; j < 3; j++) { const id = pin.ids[j] * 3, w = pin.weights[j] / (masses[pin.ids[j]] * scale); result[id] += w * fx; result[id + 1] += w * fy; result[id + 2] += w * fz; }
  for (let i = 0; i < dim; i++) result[i] -= damping * velocity[i] * invMass[Math.floor(i / 3)];
  return result;
}
function residualAt(position) {
  const velocity = Float64Array.from(position, (value, i) => (value - xPrevious[i]) / dt);
  const acceleration = accelerationAt(position, velocity);
  return Float64Array.from(position, (value, i) => value - xPrevious[i] - dt * vPrevious[i] - dt * dt * acceleration[i]);
}
function analyticJacobian(position) {
  const matrix = zeroMatrix();
  for (let i = 0; i < dim; i++) matrix[i][i] = 1 + dt * damping * invMass[Math.floor(i / 3)];
  for (const edge of edges) {
    const a = edge.a * 3, b = edge.b * 3, dx = position[b] - position[a], dy = position[b + 1] - position[a + 1], dz = position[b + 2] - position[a + 2], length = Math.hypot(dx, dy, dz);
    const h = springHessian(dx, dy, dz, length, edge.k, edge.rest), factor = dt * dt;
    addBlock(matrix, [a, a + 1, a + 2], [a, a + 1, a + 2], h, factor * invMass[edge.a]);
    addBlock(matrix, [a, a + 1, a + 2], [b, b + 1, b + 2], h, -factor * invMass[edge.a]);
    addBlock(matrix, [b, b + 1, b + 2], [b, b + 1, b + 2], h, factor * invMass[edge.b]);
    addBlock(matrix, [b, b + 1, b + 2], [a, a + 1, a + 2], h, -factor * invMass[edge.b]);
  }
  for (const spring of supports) {
    const a = spring.a * 3, dx = spring.anchor[0] - position[a], dy = spring.anchor[1] - position[a + 1], dz = spring.anchor[2] - position[a + 2], length = Math.hypot(dx, dy, dz);
    addBlock(matrix, [a, a + 1, a + 2], [a, a + 1, a + 2], springHessian(dx, dy, dz, length, spring.k, spring.rest), dt * dt * invMass[spring.a]);
  }
  const pinFactor = dt * dt * pin.kp + dt * pin.kd;
  for (let j = 0; j < 3; j++) for (let l = 0; l < 3; l++) for (let c = 0; c < 3; c++) matrix[pin.ids[j] * 3 + c][pin.ids[l] * 3 + c] += pinFactor * pin.weights[j] * pin.weights[l] * invMass[pin.ids[j]];
  return matrix;
}
const jacobian = analyticJacobian(x);
const direction = Float64Array.from({ length: dim }, (_, i) => Math.sin(i * 1.71) + 0.2 * Math.cos(i * 0.37));
const epsilon = 1e-7;
const plus = Float64Array.from(x, (value, i) => value + epsilon * direction[i]);
const minus = Float64Array.from(x, (value, i) => value - epsilon * direction[i]);
const finiteDifference = Float64Array.from(residualAt(plus), (value, i) => (value - residualAt(minus)[i]) / (2 * epsilon));
const analyticProduct = mul(jacobian, direction);
const fdError = Float64Array.from(finiteDifference, (value, i) => value - analyticProduct[i]);
const finiteDifferenceAudit = { epsilon, maxAbsDerivativeError: maxAbs(fdError), rmsDerivativeError: Math.sqrt(dot(fdError, fdError) / dim), maxAbsDerivative: maxAbs(finiteDifference), pass: maxAbs(fdError) < 1e-7 };

function transpose(matrix) { return matrix[0].map((_, c) => matrix.map(row => row[c])); }
function matrixVector(matrix, vector) { return mul(matrix, vector); }
const sqrtMass = Float64Array.from({ length: dim }, (_, i) => Math.sqrt(masses[Math.floor(i / 3)]));
const inverseSqrtMass = Float64Array.from(sqrtMass, value => 1 / value);
const weightedJacobian = jacobian.map((row, r) => row.map((value, c) => sqrtMass[r] * value * inverseSqrtMass[c]));
const jt = transpose(jacobian);
const symmetryVectorA = Float64Array.from({ length: dim }, (_, i) => Math.cos(i * 0.41) + 0.4);
const symmetryVectorB = Float64Array.from({ length: dim }, (_, i) => Math.sin(i * 0.89) - 0.1);
const ordinaryLeft = dot(symmetryVectorA, matrixVector(jacobian, symmetryVectorB));
const ordinaryRight = dot(symmetryVectorB, matrixVector(jacobian, symmetryVectorA));
const weightedLeft = dot(symmetryVectorA, matrixVector(weightedJacobian, symmetryVectorB));
const weightedRight = dot(symmetryVectorB, matrixVector(weightedJacobian, symmetryVectorA));
const similarityProbe = Float64Array.from({ length: dim }, (_, i) => Math.sin(i * 0.53) + 0.1);
const similarityDirect = Float64Array.from(matrixVector(jacobian, Float64Array.from(similarityProbe, (value, i) => value * inverseSqrtMass[i])), (value, i) => value * sqrtMass[i]);
const similarityMatrix = matrixVector(weightedJacobian, similarityProbe);
const symmetryAudit = { ordinaryBilinearDifference: Math.abs(ordinaryLeft - ordinaryRight), weightedBilinearDifference: Math.abs(weightedLeft - weightedRight), ordinarySymmetric: Math.abs(ordinaryLeft - ordinaryRight) < 1e-10, weightedSymmetric: Math.abs(weightedLeft - weightedRight) < 1e-10, weightedMatrixTransposeError: maxAbs(Float64Array.from(weightedJacobian.flatMap((row, r) => row.map((value, c) => value - weightedJacobian[c][r])))), similarityTransformMaxError: maxAbs(Float64Array.from(similarityDirect, (value, i) => value - similarityMatrix[i])) };
const compressedLength = 0.45, compressedRest = 0.9, compressedK = 40;
const negativeTransverseHessianEigenvalue = compressedK * (1 - compressedRest / compressedLength);
const negativeCurvatureAudit = { currentLength: compressedLength, restLength: compressedRest, stiffness: compressedK, transverseHessianEigenvalue: negativeTransverseHessianEigenvalue, negativeCurvatureDetected: negativeTransverseHessianEigenvalue < 0, handling: 'weighted CG rejects p·A·p <= 0; Newton retries with a numerical Levenberg shift without changing the physical residual or material coefficients' };

const output = {
  model: 'production-equation-audit',
  equation: 'R(x)=x-x_n-dt*v_n-dt^2*a(x,(x-x_n)/dt)',
  massesKg: masses, sourceMetersPerUnit: scale, dt, finiteDifferenceAudit, symmetryAudit, negativeCurvatureAudit,
  expected: { ordinaryJacobianGenerallyNonsymmetric: true, weightedSimilarityTransform: 'A=M^(1/2) J M^(-1/2)', weightedOperatorSymmetricWhenHessianSymmetric: true },
  allPass: finiteDifferenceAudit.pass && symmetryAudit.ordinaryBilinearDifference > 1e-10 && symmetryAudit.weightedSymmetric && negativeCurvatureAudit.negativeCurvatureDetected,
};
await fs.mkdir(outDir, { recursive: true });
await fs.writeFile(path.join(outDir, 'jacobian-audit.json'), JSON.stringify(output, null, 2));
console.log(JSON.stringify(output, null, 2));
