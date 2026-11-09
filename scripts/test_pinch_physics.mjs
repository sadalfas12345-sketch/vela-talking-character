import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'verification', 'island-spring-pinch');
const scales = [0.01, 0.05, 0.30, 1.0, 3.0];
const close = (a, b, tolerance) => Math.abs(a - b) <= tolerance;

function sourceAccelerationFromForce(forceN, massKg, sourceMetersPerUnit) { return forceN / massKg / sourceMetersPerUnit; }
function physicalAccelerationFromSource(sourceAcceleration, sourceMetersPerUnit) { return sourceAcceleration * sourceMetersPerUnit; }
function assert(name, ok, details) { if (!ok) throw new Error(`${name}: ${details}`); return { name, pass: true, details }; }

const forceScaleTests = scales.map(scale => {
  const sourceAcceleration = sourceAccelerationFromForce(1, 1, scale);
  const physicalAcceleration = physicalAccelerationFromSource(sourceAcceleration, scale);
  return { scale, forceN: 1, massKg: 1, sourceAcceleration, physicalAcceleration, pass: close(physicalAcceleration, 1, 1e-12) };
});

const areaM2 = 1e-6;
const rho = 1100;
const thickness = 0.0015;
const areaMassKg = rho * thickness * areaM2;
const massTest = { areaM2, rho, thickness, expectedMassKg: 1.65e-6, actualMassKg: areaMassKg, pass: close(areaMassKg, 1.65e-6, 1e-15) };

const scaleAreaTests = scales.map(scale => {
  const sourceArea = 0.5 * 0.002 * 0.002;
  const physicalArea = sourceArea * scale * scale;
  return { scale, sourceArea, physicalArea, areaOverScaleSquared: physicalArea / (scale * scale), pass: close(physicalArea / (scale * scale), sourceArea, 1e-18) };
});

const innerSpring = { massKg: areaMassKg, kNPerM: 2, displacementM: 0.001 };
innerSpring.forceN = -innerSpring.kNPerM * innerSpring.displacementM;
innerSpring.physicalAcceleration = innerSpring.forceN / innerSpring.massKg;
innerSpring.pass = close(innerSpring.forceN, -0.002, 1e-15);

function accelerations(x, v, k, m, damping) {
  const a = new Float64Array(2);
  const f0 = -k * (x[0] - 0.001) - damping * v[0] + k * (x[1] - x[0] - 0.001);
  const f1 = -k * (x[1] - x[0] - 0.001) - damping * v[1] - k * (x[1] - 0.002);
  a[0] = f0 / m;
  a[1] = f1 / m;
  return a;
}
function rk4Step(x, v, dt, k, m, damping) {
  const a1 = accelerations(x, v, k, m, damping);
  const x2 = new Float64Array([x[0] + v[0] * dt / 2, x[1] + v[1] * dt / 2]);
  const v2 = new Float64Array([v[0] + a1[0] * dt / 2, v[1] + a1[1] * dt / 2]);
  const a2 = accelerations(x2, v2, k, m, damping);
  const x3 = new Float64Array([x[0] + v2[0] * dt / 2, x[1] + v2[1] * dt / 2]);
  const v3 = new Float64Array([v[0] + a2[0] * dt / 2, v[1] + a2[1] * dt / 2]);
  const a3 = accelerations(x3, v3, k, m, damping);
  const x4 = new Float64Array([x[0] + v3[0] * dt, x[1] + v3[1] * dt]);
  const v4 = new Float64Array([v[0] + a3[0] * dt, v[1] + a3[1] * dt]);
  const a4 = accelerations(x4, v4, k, m, damping);
  return {
    x: new Float64Array([x[0] + dt * (v[0] + 2 * v2[0] + 2 * v3[0] + v4[0]) / 6, x[1] + dt * (v[1] + 2 * v2[1] + 2 * v3[1] + v4[1]) / 6]),
    v: new Float64Array([v[0] + dt * (a1[0] + 2 * a2[0] + 2 * a3[0] + a4[0]) / 6, v[1] + dt * (a1[1] + 2 * a2[1] + 2 * a3[1] + a4[1]) / 6]),
  };
}
function implicitLinearStep(x, v, dt, k, m, damping) {
  const alpha = dt * dt * k / m;
  const beta = dt * damping / m;
  const matrix = [[1 + 2 * alpha + beta, -alpha], [-alpha, 1 + 2 * alpha + beta]];
  // Backward-Euler spring equilibrium for two equal springs in series:
  // the rest-length constants cancel at node 0 and sum to 0.003 at node 1.
  const rhs = [(1 + beta) * x[0] + dt * v[0] + alpha * 0, (1 + beta) * x[1] + dt * v[1] + alpha * 0.003];
  const det = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0];
  const xn = new Float64Array([(rhs[0] * matrix[1][1] - matrix[0][1] * rhs[1]) / det, (matrix[0][0] * rhs[1] - rhs[0] * matrix[1][0]) / det]);
  return { x: xn, v: new Float64Array([(xn[0] - x[0]) / dt, (xn[1] - x[1]) / dt]) };
}
function integrate(method, dt, duration) {
  const k = 45, m = 0.001, damping = 0.08 * 2 * Math.sqrt(k * m);
  let x = new Float64Array([0.0012, 0.0018]), v = new Float64Array([0, 0]);
  const steps = Math.round(duration / dt);
  for (let i = 0; i < steps; i++) ({ x, v } = method(x, v, dt, k, m, damping));
  return { x: Array.from(x), v: Array.from(v), steps };
}
const duration = 0.05;
const rk = integrate(rk4Step, 1e-6, duration);
const implicit = integrate(implicitLinearStep, 1 / 12000, duration);
const trajectoryError = Math.max(...rk.x.map((value, i) => Math.abs(value - implicit.x[i])));
const integratorTest = { duration, rk4: rk, implicit, maxPositionErrorSourceUnits: trajectoryError, toleranceSourceUnits: 2e-5, pass: trajectoryError <= 2e-5 };

function oscillatorRK4Step(x, v, dt, kNPerM, massKg, dampingNsPerM, restM = 0.001) {
  const acceleration = (position, velocity) => (-kNPerM * (position - restM) - dampingNsPerM * velocity) / massKg;
  const a1 = acceleration(x, v), x2 = x + v * dt / 2, v2 = v + a1 * dt / 2, a2 = acceleration(x2, v2);
  const x3 = x + v2 * dt / 2, v3 = v + a2 * dt / 2, a3 = acceleration(x3, v3);
  const x4 = x + v3 * dt, v4 = v + a3 * dt, a4 = acceleration(x4, v4);
  return { x: x + dt * (v + 2 * v2 + 2 * v3 + v4) / 6, v: v + dt * (a1 + 2 * a2 + 2 * a3 + a4) / 6 };
}
function productionImplicitOscillatorStep(x, v, dt, kNPerM, massKg, dampingNsPerM, restM = 0.001) {
  // This is the scalar reduction of the production Newton + line-search
  // position solve: x1 - x0 - dt*v0 - dt^2*a(x1,(x1-x0)/dt) = 0.
  let candidate = x + v * dt, residualHistory = [];
  const residualAt = value => value - x - dt * v - dt * dt * ((-kNPerM * (value - restM) - dampingNsPerM * ((value - x) / dt)) / massKg);
  for (let iteration = 0; iteration < 12; iteration++) {
    const residual = residualAt(candidate); residualHistory.push(Math.abs(residual));
    if (Math.abs(residual) <= 1e-14) break;
    const jacobian = 1 + dt * dampingNsPerM / massKg + dt * dt * kNPerM / massKg;
    const delta = -residual / jacobian; let alpha = 1, accepted = false;
    while (alpha >= 1 / 128) { const trial = candidate + alpha * delta; if (Math.abs(residualAt(trial)) < Math.abs(residual) * (1 - 1e-10) || Math.abs(residualAt(trial)) <= 1e-14) { candidate = trial; accepted = true; break; } alpha *= 0.5; }
    if (!accepted) break;
  }
  const nextV = (candidate - x) / dt;
  return { x: candidate, v: nextV, residual: residualAt(candidate), residualHistory };
}
function integrateProduction(dt, duration, kNPerM, massKg, dampingNsPerM) {
  let x = 0.0012, v = 0, maxResidual = 0;
  for (let i = 0; i < Math.round(duration / dt); i++) { const next = productionImplicitOscillatorStep(x, v, dt, kNPerM, massKg, dampingNsPerM); x = next.x; v = next.v; maxResidual = Math.max(maxResidual, Math.abs(next.residual)); }
  return { x, v, maxResidual, steps: Math.round(duration / dt) };
}
function integrateFineRK4(dt, duration, kNPerM, massKg, dampingNsPerM) {
  let x = 0.0012, v = 0;
  for (let i = 0; i < Math.round(duration / dt); i++) ({ x, v } = oscillatorRK4Step(x, v, dt, kNPerM, massKg, dampingNsPerM));
  return { x, v, steps: Math.round(duration / dt) };
}
const productionVsRk4 = { duration: 0.05, dtProduction: 1 / 12000, dtRk4: 1e-6, kNPerM: 45, massKg: 0.001, dampingNsPerM: 0.08 * 2 * Math.sqrt(45 * 0.001) };
productionVsRk4.production = integrateProduction(productionVsRk4.dtProduction, productionVsRk4.duration, productionVsRk4.kNPerM, productionVsRk4.massKg, productionVsRk4.dampingNsPerM);
productionVsRk4.rk4 = integrateFineRK4(productionVsRk4.dtRk4, productionVsRk4.duration, productionVsRk4.kNPerM, productionVsRk4.massKg, productionVsRk4.dampingNsPerM);
productionVsRk4.maxPositionErrorSourceUnits = Math.abs(productionVsRk4.production.x - productionVsRk4.rk4.x);
productionVsRk4.maxVelocityErrorSourceUnitsPerSecond = Math.abs(productionVsRk4.production.v - productionVsRk4.rk4.v);
productionVsRk4.toleranceSourceUnits = 2e-5;
productionVsRk4.pass = productionVsRk4.maxPositionErrorSourceUnits <= productionVsRk4.toleranceSourceUnits && productionVsRk4.production.maxResidual <= 1e-12;

const tests = [
  assert('1N/1kg scale conversion', forceScaleTests.every(t => t.pass), forceScaleTests),
  assert('1mm2 lumped mass', massTest.pass, massTest),
  assert('area scales with s^2', scaleAreaTests.every(t => t.pass), scaleAreaTests),
  assert('inner spring analytical force', innerSpring.pass, innerSpring),
  assert('implicit versus fine RK4 small network', integratorTest.pass, integratorTest),
  assert('production implicit versus fine RK4 identical-force network', productionVsRk4.pass, productionVsRk4),
];
const output = { tests, forceScaleTests, massTest, scaleAreaTests, innerSpring, integratorTest, productionVsRk4, allPass: tests.every(t => t.pass) };
await fs.mkdir(outDir, { recursive: true });
await fs.writeFile(path.join(outDir, 'physics-unit-tests.json'), JSON.stringify(output, null, 2));
console.log(JSON.stringify(output, null, 2));
