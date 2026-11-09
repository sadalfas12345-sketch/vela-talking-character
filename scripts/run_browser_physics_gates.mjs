import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'verification', 'island-spring-pinch');
const port = Number(process.env.VELA_GATE_PORT || 4188);
const baseUrl = `http://127.0.0.1:${port}/island-spring-pinch.html`;
const models = ['female', 'male'];
const report = { gates: [], models: {} };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function startServer() { return spawn('python', ['serve.py', String(port)], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true }); }
async function waitFor(url, timeout = 30000) { const end = Date.now() + timeout; while (Date.now() < end) { try { if ((await fetch(url)).ok) return; } catch {} await sleep(250); } throw new Error(`Timed out waiting for ${url}`); }
async function writeAndStop(server, browser, exitCode = 0) {
  await fs.mkdir(outDir, { recursive: true });
  await fs.writeFile(path.join(outDir, 'browser-mathematical-gates.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(outDir, 'BROWSER_GATES.md'), `# Browser mathematical gates\n\n${report.gates.map(g => `- Gate ${g.gate}: **${g.pass ? 'PASS' : 'FAIL'}** — ${g.name}`).join('\n')}\n\nFull measurements: browser-mathematical-gates.json\n`);
  await browser?.close().catch(() => {}); server?.kill();
  process.exit(exitCode);
}
function addGate(number, name, pass, measurements) { const gate = { gate: number, name, pass, measurements }; report.gates.push(gate); console.log(`Browser gate ${number}: ${pass ? 'PASS' : 'FAIL'} — ${name}`); return pass; }
async function loadModel(page, model) { await page.goto(`${baseUrl}?model=${model}`, { waitUntil: 'domcontentloaded', timeout: 30000 }); await page.waitForFunction(() => document.querySelector('#loadState')?.classList.contains('ready'), null, { timeout: 180000 }); await page.waitForTimeout(250); await page.selectOption('#physicsPreset', 'biological'); await page.selectOption('#integrator', 'implicit'); }

const server = startServer();
await waitFor(baseUrl);
const browser = await chromium.launch({ headless: true, args: ['--enable-webgl', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
await page.addInitScript(() => { try { Object.defineProperty(navigator, 'connection', { configurable: true, value: { saveData: true } }); } catch {} });
page.setDefaultTimeout(180000);
page.on('console', message => { if (message.type() === 'error') console.error(`[browser] ${message.text()}`); });
page.on('pageerror', error => console.error(`[pageerror] ${error.stack || error}`));

try {
  // Gate 6: one actual original island, not a synthetic mesh.
  for (const model of models) {
    await loadModel(page, model);
    await page.click('#oneNudge');
    await page.waitForFunction(() => Boolean(window.__velaDiagnostics().tests?.nudge), null, { timeout: 180000 });
    const d = await page.evaluate(() => window.__velaDiagnostics());
    report.models[model] = { gate6: d };
  }
  const gate6Pass = models.every(model => {
    const d = report.models[model].gate6, n = d.tests.nudge, m = d.metrics, topo = d.springTopology;
    return topo?.invariant && m.interIslandSprings === 0 && m.zeroMassVertexCount === 0 && m.supportSprings > 0 && n.finite && n.maxNeighborMovement > 0 && n.energyDecreased && n.restoredTowardNeutral && n.initialAccelerationMS2.some(value => Math.abs(value) > 0);
  });
  if (!addGate(6, 'One actual Tripo island', gate6Pass, report.models)) { await writeAndStop(server, browser, 1); }

  // Gate 7: one barycentric controller force, hold, drag, release.
  for (const model of models) {
    await loadModel(page, model); await page.click('#pinchMode'); await page.click('[data-stage="5"]');
    const box = await page.locator('#viewport').boundingBox();
    let probe = null;
    for (const [px, py] of [[0.46, 0.24], [0.62, 0.44], [0.78, 0.54], [0.94, 0.64]]) {
      const x = box.x + box.width * px, y = box.y + box.height * py, hit = await page.evaluate(({ x, y }) => window.__velaPickTest(x, y), { x, y });
      if (hit) { probe = { x, y, hit }; break; }
    }
    if (!probe) { report.models[model].gate7 = { error: 'no face raycast hit' }; continue; }
    const plan = await page.evaluate(point => window.__velaPlanDrag(point, 0.02), probe.hit.point);
    await page.mouse.move(probe.x, probe.y); await page.mouse.down(); await page.waitForTimeout(80);
    const down = await page.evaluate(() => window.__velaDiagnostics());
    await page.mouse.move(plan.target.x, plan.target.y, { steps: 12 }); await page.waitForTimeout(300);
    const held = await page.evaluate(() => window.__velaDiagnostics()); await page.screenshot({ path: path.join(outDir, `${model}-gate7-held.png`), fullPage: false });
    await page.mouse.up(); await page.waitForTimeout(800);
    const released = await page.evaluate(() => window.__velaDiagnostics()); await page.screenshot({ path: path.join(outDir, `${model}-gate7-released.png`), fullPage: false });
    report.models[model].gate7 = { plan, down, held, released };
  }
  const gate7Pass = models.every(model => {
    const item = report.models[model].gate7, d = item?.held, r = item?.released, p = r?.lastPinch;
    if (!d || !r || !p?.released) return false;
    const forceSum = p.forceDistributionSumN || [], force = p.currentForceN || [];
    return Math.abs((p.forceWeightSum || 0) - 1) < 1e-9 && forceSum.length === 3 && force.length === 3 && Math.hypot(...forceSum.map((value, i) => value - force[i])) < 1e-9 && d.lastPinch.activeIsland === d.islands.selected.id && d.lastPinch.activeVertices === d.islands.selected.vertices && d.islands.selected.selectedOption?.endsWith(`:${d.lastPinch.activeIsland}`) && p.trackingErrorMeters >= 0 && Number.isFinite(p.peakForceN);
  });
  if (!addGate(7, 'Barycentric pinch controller', gate7Pass, report.models)) { await writeAndStop(server, browser, 1); }

  // Gate 8: actual original textured faces, with geometry checks during and after release.
  const gate8Pass = models.every(model => {
    const item = report.models[model].gate7, held = item?.held, released = item?.released;
    const valid = geometry => geometry && geometry.nonfiniteVertices === 0 && geometry.collapsedTriangles === 0 && geometry.orientationFlips === 0 && geometry.minAreaRatio > 0;
    return valid(held?.geometry) && valid(released?.geometry) && held.metrics?.implicit?.converged === true && released.metrics?.implicit?.converged === true;
  });
  addGate(8, 'Original 3D face pinch and recovery', gate8Pass, report.models);
  await writeAndStop(server, browser, gate8Pass ? 0 : 1);
} catch (error) {
  report.error = { message: error.message, stack: error.stack };
  await writeAndStop(server, browser, 1);
}
