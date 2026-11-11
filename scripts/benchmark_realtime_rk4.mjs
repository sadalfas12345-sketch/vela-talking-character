import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'verification', 'island-spring-pinch');
const port = Number(process.env.VELA_RT_PORT || 4191);
const models = (process.env.VELA_RT_MODELS || 'female,male').split(',').map(value => value.trim()).filter(Boolean);
const gravityDirections = ['none', 'down', 'up', 'left', 'right', 'forward', 'backward'];
const gravitySteps = Number(process.env.VELA_RT_GRAVITY_STEPS || 12);
const pinch = process.env.VELA_RT_PINCH === '1';
const compact = d => ({ model: d.model, metrics: d.metrics, geometry: d.geometry ? { orientationFlips: d.geometry.orientationFlips, collapsedTriangles: d.geometry.collapsedTriangles, nonfiniteVertices: d.geometry.nonfiniteVertices, maxEdgeStrain: d.geometry.maxEdgeStrain, p95EdgeStrain: d.geometry.p95EdgeStrain, minAreaRatio: d.geometry.minAreaRatio, boundaryMaxDisplacement: d.geometry.boundaryMaxDisplacement, valid: d.geometry.valid } : null, lastPinch: d.lastPinch });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const server = spawn('python', ['serve.py', String(port)], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
const stop = async () => { server.kill(); };
try {
  const url = `http://127.0.0.1:${port}/island-spring-pinch.html`;
  for (let i = 0; i < 120; i++) { try { if ((await fetch(url)).ok) break; } catch {} await sleep(250); }
  const browser = await chromium.launch({ headless: true, args: ['--enable-webgl', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(180000);
  const report = { configuration: { preset: 'realtime', integrator: 'rk4', gravitySteps, pinch }, models: {} };
  for (const model of models) {
    await page.goto(`${url}?model=${model}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => document.querySelector('#loadState')?.classList.contains('ready'), null, { timeout: 180000 });
    await page.selectOption('#physicsPreset', 'realtime');
    await page.selectOption('#integrator', 'rk4');
    await page.evaluate(() => window.__velaSetRunning(false));
    const initial = compact(await page.evaluate(() => window.__velaDiagnostics()));
    const oneStepStart = Date.now();
    const oneStep = compact(await page.evaluate(() => window.__velaStep(1, 1 / 60)));
    const oneStepWallMs = Date.now() - oneStepStart;
    const gravity = {};
    for (const direction of gravityDirections) {
      await page.evaluate(() => document.querySelector('#resetNeutral')?.click());
      await page.evaluate(directionValue => window.__velaSetGravity(directionValue), direction);
      const started = Date.now();
      const samples = [];
      for (let i = 0; i < gravitySteps; i++) {
        const d = await page.evaluate(() => window.__velaStep(1, 1 / 60));
        samples.push(compact(d));
      }
      gravity[direction] = { wallMs: Date.now() - started, samples, final: samples.at(-1) };
    }
    let pinchResult = null;
    if (pinch) {
      await page.evaluate(() => document.querySelector('#resetNeutral')?.click());
      await page.evaluate(() => document.querySelector('#pinchMode')?.click());
      const box = await page.locator('#viewport').boundingBox();
      let probe = null;
      for (const [px, py] of [[0.46, 0.24], [0.62, 0.44], [0.78, 0.54], [0.94, 0.64]]) {
        const x = box.x + box.width * px, y = box.y + box.height * py;
        const hit = await page.evaluate(({ x: clientX, y: clientY }) => window.__velaPickTest(clientX, clientY), { x, y });
        if (hit) { probe = { x, y, hit }; break; }
      }
      if (probe) {
        const plan = await page.evaluate(point => window.__velaPlanDrag(point, 0.01), probe.hit.point);
        await page.mouse.move(probe.x, probe.y); await page.mouse.down(); await page.mouse.move(plan.target.x, plan.target.y, { steps: 6 });
        await page.evaluate(() => window.__velaSetRunning(false));
        const heldStart = Date.now();
        for (let i = 0; i < gravitySteps; i++) await page.evaluate(() => window.__velaStep(1, 1 / 60));
        const held = compact(await page.evaluate(() => window.__velaDiagnostics()));
        await page.mouse.up();
        const releaseStart = Date.now();
        for (let i = 0; i < gravitySteps * 2; i++) await page.evaluate(() => window.__velaStep(1, 1 / 60));
        const released = compact(await page.evaluate(() => window.__velaDiagnostics()));
        pinchResult = { plan, heldWallMs: Date.now() - heldStart, releaseWallMs: Date.now() - releaseStart, held, released };
      }
    }
    report.models[model] = { initial, oneStepWallMs, oneStep, gravity, pinch: pinchResult };
  }
  await fs.mkdir(outDir, { recursive: true });
  await fs.writeFile(path.join(outDir, 'realtime-rk4-browser-baseline.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  await browser.close(); await stop();
} catch (error) { await stop(); console.error(error.stack || error); process.exitCode = 1; }
