import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'verification', 'island-spring-pinch');
const port = Number(process.env.VELA_PINCH_TELEMETRY_PORT || 4187);
const url = `http://127.0.0.1:${port}/island-spring-pinch.html`;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function startServer() {
  const child = spawn('python', ['serve.py', String(port)], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  child.stdout.on('data', data => process.stdout.write(`[server] ${data}`));
  child.stderr.on('data', data => process.stderr.write(`[server] ${data}`));
  return child;
}
async function waitFor(urlToCheck, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { if ((await fetch(urlToCheck)).ok) return; } catch {}
    await sleep(200);
  }
  throw new Error(`Timed out waiting for ${urlToCheck}`);
}
async function waitReady(page) {
  await page.waitForFunction(() => document.querySelector('#loadState')?.classList.contains('ready'), null, { timeout: 180000 });
  await page.waitForTimeout(250);
}
async function snap(page, phase, t0) {
  return page.evaluate(({ phase, t0 }) => {
    const d = window.__velaDiagnostics();
    return { phase, tMs: performance.now() - t0, metrics: d.metrics, geometry: d.geometry, lastPinch: d.lastPinch, interactionMode: d.interactionMode };
  }, { phase, t0 });
}
function maxSample(samples, getter) { return samples.reduce((best, item) => getter(item) > getter(best) ? item : best, samples[0]); }
function minSample(samples, getter) { return samples.reduce((best, item) => getter(item) < getter(best) ? item : best, samples[0]); }
function summary(result) {
  const samples = result.samples;
  const peakStrain = maxSample(samples, s => s.geometry?.maxEdgeStrain ?? -Infinity);
  const peakEnergy = maxSample(samples, s => s.metrics?.energy ?? -Infinity);
  const peakBoundary = maxSample(samples, s => s.geometry?.boundaryMaxDisplacement ?? -Infinity);
  const worstArea = minSample(samples, s => s.geometry?.minAreaRatio ?? Infinity);
  const peak = peakStrain;
  return {
    model: result.model,
    selected: result.initial.islands.selected,
    boundaryEdgeCount: peak.geometry?.boundaryEdgeCount,
    baseline: { geometry: result.initial.geometry, metrics: result.initial.metrics },
    peak: {
      tMs: peak.tMs,
      energy: peak.metrics?.energy,
      maxDisplacement: peak.metrics?.maxDisplacement,
      maxEdgeStrain: peak.geometry?.maxEdgeStrain,
      p95EdgeStrain: peak.geometry?.p95EdgeStrain,
      boundaryMaxDisplacement: peak.geometry?.boundaryMaxDisplacement,
      boundaryMaxDisplacementPctFaceScale: peak.geometry?.boundaryMaxDisplacementPctFaceScale,
      minAreaRatio: peak.geometry?.minAreaRatio,
      collapsedTriangles: peak.geometry?.collapsedTriangles,
      orientationFlips: peak.geometry?.orientationFlips,
      nonfiniteVertices: peak.geometry?.nonfiniteVertices,
    },
    worstObserved: {
      maxEdgeStrain: peak.geometry?.maxEdgeStrain,
      p95EdgeStrain: peak.geometry?.p95EdgeStrain,
      energyAtMax: peakEnergy.metrics?.energy,
      boundaryMaxDisplacement: peakBoundary.geometry?.boundaryMaxDisplacement,
      boundaryMaxDisplacementPctFaceScale: peakBoundary.geometry?.boundaryMaxDisplacementPctFaceScale,
      minAreaRatio: worstArea.geometry?.minAreaRatio,
      collapsedTriangles: worstArea.geometry?.collapsedTriangles,
      orientationFlips: worstArea.geometry?.orientationFlips,
    },
    release: result.released.lastPinch,
    recovery: { final: result.samples.at(-1), finalEnergy: result.samples.at(-1)?.metrics?.energy, finalMaxDisplacement: result.samples.at(-1)?.metrics?.maxDisplacement, finalMaxEdgeStrain: result.samples.at(-1)?.geometry?.maxEdgeStrain, finalBoundaryDisplacement: result.samples.at(-1)?.geometry?.boundaryMaxDisplacement },
  };
}
function makeReport(summaries) {
  const rows = summaries.map(s => `| ${s.model} | ${s.selected.vertices.toLocaleString()} | ${s.selected.triangles.toLocaleString()} | ${s.boundaryEdgeCount} | ${s.peak.maxEdgeStrain.toFixed(6)} | ${s.peak.p95EdgeStrain.toFixed(6)} | ${s.peak.boundaryMaxDisplacement.toExponential(4)} | ${(s.peak.boundaryMaxDisplacementPctFaceScale * 100).toFixed(3)}% | ${s.peak.minAreaRatio.toExponential(4)} | ${s.peak.collapsedTriangles} | ${s.peak.orientationFlips} |`).join('\n');
  return '# Pinch break telemetry\n\nCaptured by collect_pinch_telemetry.mjs with the original GLBs loaded read-only in Chromium. The test uses biological materials, Kp=90 N/m, Kd=0.08 N*s/m, implicit integration, and the existing 2% interocular drag. Samples include the held pinch and 1.2 seconds of release recovery.\n\n| Model | Active vertices | Active triangles | Boundary edges | Peak max edge strain | Peak P95 edge strain | Peak boundary displacement | Boundary displacement / eye width | Minimum triangle-area ratio | Collapsed triangles | Orientation flips |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n' + rows + '\n\nBoundary edges are selected-island edges used by exactly one selected-island triangle. Orientation flips are current-vs-neutral face-normal dot products below zero. Collapsed triangles have area ratio <= 1e-3. These are conservative geometry diagnostics; screenshots remain necessary for visual seams and spikes. The complete time series is in pinch-telemetry.json.\n';
}

const server = startServer();
try {
  await fs.mkdir(out, { recursive: true });
  await waitFor(url);
  const browser = await chromium.launch({ headless: true, args: ['--enable-webgl', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(180000);
  page.on('console', message => { if (message.type() === 'error') console.error(`[browser] ${message.text()}`); });
  page.on('pageerror', error => console.error(`[pageerror] ${error.stack || error}`));
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  const results = [];
  for (const model of ['female', 'male']) {
    await page.selectOption('#character', model);
    await waitReady(page);
    await page.selectOption('#physicsPreset', 'biological');
    await page.selectOption('#integrator', 'implicit');
    await page.locator('#pinchKp').fill('90');
    await page.locator('#pinchKd').fill('0.08');
    await page.click('#pinchMode');
    await page.click('[data-stage="5"]');
    for (const selector of ['#showIslands', '#showSprings', '#showInner', '#showStrain', '#showMass']) await page.locator(selector).uncheck().catch(() => {});
    const initial = await page.evaluate(() => window.__velaDiagnostics());
    const box = await page.locator('#viewport').boundingBox();
    const probe = await page.evaluate(box => {
      for (const [px, py] of [[0.46, 0.24], [0.62, 0.44], [0.78, 0.54], [0.94, 0.64]]) { const x = box.x + box.width * px, y = box.y + box.height * py, hit = window.__velaPickTest(x, y); if (hit) return { x, y, hit }; }
      return null;
    }, box);
    if (!probe) throw new Error(`No face hit for ${model}`);
    const plan = await page.evaluate(point => window.__velaPlanDrag(point, 0.02), probe.hit.point);
    const t0 = await page.evaluate(() => performance.now());
    const samples = [];
    const push = phase => snap(page, phase, t0).then(value => samples.push(value));
    await page.locator('#viewport').hover({ position: { x: probe.x - box.x, y: probe.y - box.y } });
    await page.mouse.down();
    await page.waitForTimeout(80);
    await push('down');
    await page.mouse.move(plan.target.x, plan.target.y, { steps: 12 });
    for (let i = 0; i < 12; i++) { await sleep(50); await push('held'); }
    await page.screenshot({ path: path.join(out, `${model}-telemetry-peak.png`), fullPage: false });
    await page.mouse.up();
    for (let i = 0; i < 24; i++) { await sleep(50); await push('recovery'); }
    const released = await page.evaluate(() => window.__velaDiagnostics());
    await page.screenshot({ path: path.join(out, `${model}-telemetry-released.png`), fullPage: false });
    results.push({ model, plan, initial, released, samples });
    await page.click('#resetNeutral');
    await page.waitForTimeout(150);
  }
  const summaries = results.map(summary);
  await fs.writeFile(path.join(out, 'pinch-telemetry.json'), JSON.stringify({ url, config: { preset: 'biological', integrator: 'implicit', kpNPerM: 90, kdNsPerM: 0.08, targetFractionOfFaceScale: 0.02, sampleIntervalMs: 50 }, results, summaries }, null, 2));
  await fs.writeFile(path.join(out, 'PINCH_TELEMETRY.md'), makeReport(summaries));
  console.log(JSON.stringify(summaries, null, 2));
  await browser.close();
} finally { server.kill(); }
