import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const root = new URL('..', import.meta.url).pathname.replace(/^\//, '').replaceAll('/', '\\');
const out = `${root}verification\\island-spring-pinch`;
const islandId = Number(process.env.VELA_GPU_BROWSER_ISLAND || 35);
const url = `http://127.0.0.1:4174/island-spring-pinch.html?model=male&gpuIsland=${islandId}&gpuServer=ws://127.0.0.1:8765`;

const browser = await chromium.launch({ headless: true, args: ['--enable-webgl', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(180000);
page.on('pageerror', error => console.error(`[pageerror] ${error.stack || error}`));
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
console.log('page-domcontentloaded');
await page.waitForFunction(() => document.querySelector('#loadState')?.classList.contains('ready'), null, { timeout: 180000 });
console.log('model-ready');
await page.waitForTimeout(15000);
const initial = await page.evaluate(() => window.__velaDiagnostics());
const metricsText = await page.locator('#metrics').innerText();
if (!metricsText.includes('Backend: GPU Warp server')) throw new Error(`GPU backend was not connected: ${metricsText.slice(0, 300)}`);
console.log('gpu-backend-ready');

await page.click('#pinchMode');
const box = await page.locator('#viewport').boundingBox();
const probes = [];
for (let py = 0.16; py <= 0.82; py += 0.08) for (let px = 0.24; px <= 0.88; px += 0.08) probes.push([px, py]);
const pickProbes = await page.evaluate(({ box, probes, islandId }) => probes.map(([px, py]) => {
  const x = box.x + box.width * px;
  const y = box.y + box.height * py;
  return { x, y, hit: window.__velaPickTest(x, y, islandId) };
}), { box, probes, islandId });
const selected = pickProbes.find(probe => probe.hit);
console.log('pick-probes', JSON.stringify(pickProbes));
if (!selected) throw new Error(`No pick hit from probe set: ${JSON.stringify(pickProbes)}`);
const plan = await page.evaluate(({ point }) => window.__velaPlanDrag(point, 0.02), { point: selected.hit.point });
await page.locator('#viewport').hover({ position: { x: selected.x - box.x, y: selected.y - box.y } });
await page.mouse.down();
await page.waitForTimeout(150);
const down = await page.evaluate(() => window.__velaDiagnostics());
if (!down.lastPinch?.down) throw new Error(`Pointer down did not create a pinch: ${JSON.stringify(down.lastPinch)}`);
await page.mouse.move(plan.target.x, plan.target.y, { steps: 12 });
await page.waitForTimeout(1000);
const held = await page.evaluate(() => window.__velaDiagnostics());
await page.screenshot({ path: `${out}\\gpu-browser-male-island35-pinched.png` });
await page.mouse.up();
await page.waitForTimeout(1500);
const released = await page.evaluate(() => window.__velaDiagnostics());
await page.screenshot({ path: `${out}\\gpu-browser-male-island35-pinched-released.png` });
const result = {
  url,
  backend: 'GPU Warp server',
  initial: { vertices: initial.metrics?.vertices, triangles: initial.metrics?.triangles, island: initial.islands?.selected },
  pick: { screen: { x: selected.x, y: selected.y }, triangle: selected.hit.triangle, point: selected.hit.point },
  plan,
  held: { lastPinch: held.lastPinch, geometry: held.geometry, finite: held.metrics?.finite },
  released: { lastPinch: released.lastPinch, geometry: released.geometry, finite: released.metrics?.finite },
  screenshots: ['gpu-browser-male-island35-pinched.png', 'gpu-browser-male-island35-pinched-released.png'],
};
await fs.writeFile(`${out}\\gpu-browser-male-island35.json`, JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
await browser.close();
