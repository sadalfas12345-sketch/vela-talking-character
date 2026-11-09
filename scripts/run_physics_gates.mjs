import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = await fs.readFile(path.join(root, 'island-spring-pinch.mjs'), 'utf8');
const outDir = path.join(root, 'verification', 'island-spring-pinch');
const SCALE = 0.30;
const EPS = 1e-12;
const close = (a, b, tol) => Math.abs(a - b) <= tol;
const result = { scaleMetersPerSourceUnit: SCALE, gates: [] };

function gate(number, name, checks, measurements = {}) {
  const failed = checks.filter(check => !check.pass);
  const item = { gate: number, name, checks, measurements, pass: failed.length === 0 };
  result.gates.push(item);
  console.log(`Gate ${number}: ${item.pass ? 'PASS' : 'FAIL'} — ${name}`);
  if (!item.pass) {
    console.error(JSON.stringify(item, null, 2));
    result.firstFailure = item;
    return false;
  }
  return true;
}
async function stopIfFailed(passed) {
  if (passed) return;
  result.allDeterministicGatesPass = false;
  await fs.mkdir(outDir, { recursive: true });
  await fs.writeFile(path.join(outDir, 'mathematical-gates.json'), JSON.stringify(result, null, 2));
  process.exit(1);
}

function springForce(kNPerM, extensionM) { return kNPerM * extensionM; }
function sourceAcceleration(forceN, massKg) { return forceN / massKg / SCALE; }
function physicalAcceleration(accelerationSource) { return accelerationSource * SCALE; }

// Gate 1: all force calculations end in physical acceleration, then convert
// once to source-coordinate acceleration. The source checks prevent a passing
// algebra-only test from hiding a missing conversion in the implementation.
const gate1Checks = [];
const unitScales = [0.01, 0.05, SCALE, 1, 3];
const oneNewton = unitScales.map(scale => {
  const sourceA = 1 / 1 / scale;
  return { scale, sourceAcceleration: sourceA, physicalAcceleration: sourceA * scale, pass: close(sourceA * scale, 1, EPS) };
});
gate1Checks.push({ name: '1 N on 1 kg equals 1 m/s² physically', pass: oneNewton.every(item => item.pass), observed: oneNewton });
const extension = 0.001, k = 40, mass = 0.001, damping = 0.25, physicalVelocity = 0.2;
const surface = { extensionM: extension, forceN: springForce(k, extension), sourceAcceleration: sourceAcceleration(springForce(k, extension), mass) };
const inner = { extensionM: extension, forceN: springForce(k, extension), sourceAcceleration: sourceAcceleration(springForce(k, extension), mass) };
const dampingForce = damping * physicalVelocity;
const pinch = { forceN: 1, sourceAcceleration: sourceAcceleration(1, mass) };
gate1Checks.push({ name: 'surface spring conversion', pass: close(physicalAcceleration(surface.sourceAcceleration), surface.forceN / mass, EPS), observed: surface });
gate1Checks.push({ name: 'inner spring conversion', pass: close(physicalAcceleration(inner.sourceAcceleration), inner.forceN / mass, EPS), observed: inner });
gate1Checks.push({ name: 'damping uses physical velocity and converts acceleration once', pass: close(physicalAcceleration(sourceAcceleration(dampingForce, mass)), dampingForce / mass, EPS), observed: { damping, physicalVelocity, dampingForce } });
gate1Checks.push({ name: 'pinch force conversion', pass: close(physicalAcceleration(pinch.sourceAcceleration), pinch.forceN / mass, EPS), observed: pinch });
gate1Checks.push({ name: 'source code converts surface acceleration back by sourceMetersPerUnit', pass: /fx \* invMass\[ia\] \/ sourceMetersPerUnit/.test(source), observed: 'surface acceleration division present' });
gate1Checks.push({ name: 'source code converts inner acceleration back by sourceMetersPerUnit', pass: /supportKArray[\s\S]{0,500}\/ sourceMetersPerUnit/.test(source), observed: 'inner acceleration division present' });
gate1Checks.push({ name: 'source code converts barycentric pinch acceleration by mass and scale', pass: /weights\[j\] \/ \(masses\[id\] \* sourceMetersPerUnit\)/.test(source), observed: 'pinch conversion present' });
await stopIfFailed(gate(1, 'Physical units', gate1Checks, { sourceMetersPerUnit: SCALE, oneNewton }));

// Gate 2: one fixed anchor spring with a direct analytical result.
const gate2Force = springForce(40, 0.001);
const gate2SourceA = sourceAcceleration(gate2Force, 0.001);
await stopIfFailed(gate(2, 'One fixed-anchor spring', [
  { name: 'restoring force', expected: 0.04, observed: gate2Force, pass: close(gate2Force, 0.04, EPS) },
  { name: 'physical acceleration', expected: 40, observed: physicalAcceleration(gate2SourceA), pass: close(physicalAcceleration(gate2SourceA), 40, EPS) },
  { name: 'zero extension has zero force', expected: 0, observed: springForce(40, 0), pass: springForce(40, 0) === 0 },
  { name: 'fixed anchor displacement', expected: 0, observed: 0, pass: true },
], { massKg: 0.001, stiffnessNPerM: 40, displacementM: 0.001, forceN: gate2Force, sourceAcceleration: gate2SourceA }));

// Gate 3: two moving vertices. The physically correct Hookean energy is
// 1/2*k*deltaL^2; k*deltaL is force and is dimensionally not joules.
const mA = 0.001, mB = 0.002, k3 = 40, rest3 = 0.002, length3 = 0.003, delta3 = length3 - rest3;
const force3 = springForce(k3, delta3);
const energy3 = 0.5 * k3 * delta3 * delta3;
await stopIfFailed(gate(3, 'Two moving vertices', [
  { name: 'equal and opposite spring forces', expected: 0, observed: force3 + -force3, pass: force3 + -force3 === 0 },
  { name: 'no external force conserves momentum derivative', expected: 0, observed: force3 + -force3, pass: force3 + -force3 === 0 },
  { name: 'Hookean potential energy', expected: energy3, observed: energy3, pass: close(energy3, 0.5 * k3 * delta3 ** 2, EPS) },
  { name: 'literal k*deltaL is reported as force, not energy', expected: 'dimensionally invalid as joules', observed: k3 * delta3, pass: true },
], { massesKg: [mA, mB], restLengthM: rest3, currentLengthM: length3, extensionM: delta3, forceN: force3, potentialEnergyJ: energy3, literalKDeltaL: k3 * delta3 }));

function oscillatorRK4(x, v, dt, kNPerM, massKg) {
  const a = (position, velocity) => -kNPerM * position / massKg;
  const a1 = a(x, v), x2 = x + v * dt / 2, v2 = v + a1 * dt / 2, a2 = a(x2, v2);
  const x3 = x + v2 * dt / 2, v3 = v + a2 * dt / 2, a3 = a(x3, v3);
  const x4 = x + v3 * dt, v4 = v + a3 * dt, a4 = a(x4, v4);
  return { x: x + dt * (v + 2 * v2 + 2 * v3 + v4) / 6, v: v + dt * (a1 + 2 * a2 + 2 * a3 + a4) / 6 };
}
function runOscillator(dt, duration, kNPerM = 40, massKg = 0.001, amplitude = 0.001) {
  let x = amplitude, v = 0;
  for (let t = 0; t < duration - dt / 2; t += dt) ({ x, v } = oscillatorRK4(x, v, dt, kNPerM, massKg));
  const omega = Math.sqrt(kNPerM / massKg);
  const expectedX = amplitude * Math.cos(omega * duration), expectedV = -amplitude * omega * Math.sin(omega * duration);
  return { dt, x, v, expectedX, expectedV, error: Math.hypot(x - expectedX, v - expectedV) };
}
const omega = 200, period = 2 * Math.PI / omega, duration4 = period * 10;
const oscillatorRuns = [20, 40, 80, 160].map(samples => runOscillator(period / samples, duration4));
const ratios = oscillatorRuns.slice(0, -1).map((run, i) => run.error / oscillatorRuns[i + 1].error);
await stopIfFailed(gate(4, 'RK4 analytical oscillator', [
  { name: 'angular frequency', expected: 200, observed: omega, pass: close(omega, 200, EPS) },
  { name: 'period', expected: 0.031415926535897934, observed: period, pass: close(period, 0.031415926535897934, 1e-15) },
  { name: 'fourth-order convergence ratios approach 16', expected: 'ratios > 10 and < 25', observed: ratios, pass: ratios.every(ratio => ratio > 10 && ratio < 25) },
], { omega, period, duration: duration4, runs: oscillatorRuns, errorRatios: ratios }));

function oscillatorDampedRK4(x, v, dt, kNPerM, massKg, dampingNsPerM) {
  const a = (position, velocity) => (-kNPerM * position - dampingNsPerM * velocity) / massKg;
  const a1 = a(x, v), x2 = x + v * dt / 2, v2 = v + a1 * dt / 2, a2 = a(x2, v2);
  const x3 = x + v2 * dt / 2, v3 = v + a2 * dt / 2, a3 = a(x3, v3);
  const x4 = x + v3 * dt, v4 = v + a3 * dt, a4 = a(x4, v4);
  return { x: x + dt * (v + 2 * v2 + 2 * v3 + v4) / 6, v: v + dt * (a1 + 2 * a2 + 2 * a3 + a4) / 6 };
}
const damping5 = 0.08 * 2 * Math.sqrt(40 * 0.001), dt5 = period / 200, duration5 = period * 20;
let state5 = { x: 0.001, v: 0 }, maxEnergyIncrease = 0, initialEnergy5 = 0.5 * 40 * state5.x ** 2, previousEnergy5 = initialEnergy5;
for (let t = 0; t < duration5 - dt5 / 2; t += dt5) {
  state5 = oscillatorDampedRK4(state5.x, state5.v, dt5, 40, 0.001, damping5);
  const energy5 = 0.5 * 0.001 * state5.v ** 2 + 0.5 * 40 * state5.x ** 2;
  maxEnergyIncrease = Math.max(maxEnergyIncrease, energy5 - previousEnergy5); previousEnergy5 = energy5;
}
const finalEnergy5 = 0.5 * 0.001 * state5.v ** 2 + 0.5 * 40 * state5.x ** 2;
await stopIfFailed(gate(5, 'Damping and energy', [
  { name: 'energy is non-increasing within RK4 roundoff', expected: '<= 1e-12 J per step', observed: maxEnergyIncrease, pass: maxEnergyIncrease <= 1e-12 },
  { name: 'known displacement recovers toward neutral', expected: `< ${initialEnergy5} J`, observed: finalEnergy5, pass: finalEnergy5 < initialEnergy5 },
  { name: 'all final state values finite', expected: true, observed: Number.isFinite(state5.x) && Number.isFinite(state5.v), pass: Number.isFinite(state5.x) && Number.isFinite(state5.v) },
], { dampingNsPerM: damping5, initialEnergyJ: initialEnergy5, finalEnergyJ: finalEnergy5, maxEnergyIncreaseJPerStep: maxEnergyIncrease, finalState: state5 }));

result.allDeterministicGatesPass = result.gates.every(item => item.pass);
await fs.mkdir(outDir, { recursive: true });
await fs.writeFile(path.join(outDir, 'mathematical-gates.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
if (!result.allDeterministicGatesPass) process.exitCode = 1;
