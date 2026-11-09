import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'verification', 'island-spring-pinch');
const port = Number(process.env.VELA_PINCH_PORT || 4185);
const url = `http://127.0.0.1:${port}/island-spring-pinch.html`;

async function waitFor(urlToCheck, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { if ((await fetch(urlToCheck)).ok) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${urlToCheck}`);
}
function startServer() {
  const child = spawn('python', ['serve.py', String(port)], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  child.stdout.on('data', data => process.stdout.write(`[server] ${data}`));
  child.stderr.on('data', data => process.stderr.write(`[server] ${data}`));
  return child;
}
async function ready(page) { await page.waitForFunction(() => document.querySelector('#loadState')?.classList.contains('ready'), null, { timeout: 180000 }); await page.waitForTimeout(1000); }
async function screenshot(page, name) { await page.screenshot({ path: path.join(out, name), fullPage: false }); }
async function tab(page, number) { await page.locator(`.tab[data-stage="${number}"]`).click(); await page.waitForTimeout(250); }
async function performPinch(page, point, box, steps, holdMs, target = null, dxRatio = 0.16, dyRatio = -0.08) {
  await page.locator('#viewport').hover({ position: { x: point.x - box.x, y: point.y - box.y } });
  await page.mouse.down(); await page.waitForTimeout(100);
  const active = await page.evaluate(() => Boolean(window.__velaDiagnostics().lastPinch?.down));
  if (!active) { await page.mouse.up(); return { active: false, during: await page.evaluate(() => window.__velaDiagnostics()), released: await page.evaluate(() => window.__velaDiagnostics()) }; }
  const destination = target || { x: point.x + box.width * dxRatio, y: point.y + box.height * dyRatio };
  await page.mouse.move(destination.x, destination.y, { steps });
  await page.waitForTimeout(holdMs);
  const during = await page.evaluate(() => window.__velaDiagnostics());
  await page.mouse.up(); await page.waitForTimeout(700);
  return { active: true, during, released: await page.evaluate(() => window.__velaDiagnostics()) };
}

async function captureModel(page, model) {
  await ready(page);
  if (await page.inputValue('#character') !== model) { await page.selectOption('#character', model); await ready(page); }
  await page.selectOption('#physicsPreset', process.env.VELA_PINCH_PRESET || 'biological');
  if (process.env.VELA_PINCH_INTEGRATOR) await page.selectOption('#integrator', process.env.VELA_PINCH_INTEGRATOR);
  if (process.env.VELA_PINCH_KP) await page.locator('#pinchKp').fill(String(process.env.VELA_PINCH_KP));
  if (process.env.VELA_PINCH_KD) await page.locator('#pinchKd').fill(String(process.env.VELA_PINCH_KD));
  const initial = await page.evaluate(() => window.__velaDiagnostics());
  const box = await page.locator('#viewport').boundingBox();
  const probeCoords = [[0.46, 0.24], [0.62, 0.44], [0.78, 0.54], [0.94, 0.64]];
  initial.pickProbes = await page.evaluate(({ box, probeCoords }) => probeCoords.map(([px, py]) => {
    const x = box.x + box.width * px, y = box.y + box.height * py;
    return { x, y, hit: window.__velaPickTest(x, y) };
  }), { box, probeCoords });
  const selectedProbe = initial.pickProbes.find(probe => probe.hit);
  initial.pinPlan = selectedProbe ? await page.evaluate(({ point }) => window.__velaPlanDrag(point, 0.02), { point: selectedProbe.hit.point }) : null;
  await page.click('#exploreMode');
  if (selectedProbe) {
    await page.locator('#viewport').hover({ position: { x: selectedProbe.x - box.x, y: selectedProbe.y - box.y } });
    await page.mouse.down(); await page.waitForTimeout(80);
    initial.exploreCreatedPin = Boolean((await page.evaluate(() => window.__velaDiagnostics().lastPinch))?.down);
    await page.mouse.up();
  } else initial.exploreCreatedPin = false;
  await page.click('#pinchMode');
  initial.defaultInteractionMode = initial.interactionMode;
  if (process.env.VELA_PINCH_QUICK) {
    await tab(page, 5); await page.uncheck('#showIslands'); await page.uncheck('#showSprings'); await page.uncheck('#showInner'); await page.uncheck('#showMass');
    const quickBox = await page.locator('#viewport').boundingBox();
    const quickPoint = initial.pinPlan?.origin;
    if (quickPoint) {
      await page.locator('#viewport').hover({ position: { x: quickPoint.x - quickBox.x, y: quickPoint.y - quickBox.y } }); await page.mouse.down(); await page.waitForTimeout(100);
      if (await page.evaluate(() => Boolean(window.__velaDiagnostics().lastPinch?.down))) await page.mouse.move(initial.pinPlan.target.x, initial.pinPlan.target.y, { steps: 12 });
    }
    await page.waitForTimeout(250); const during = await page.evaluate(() => window.__velaDiagnostics());
    await page.screenshot({ path: path.join(out, `${model}-stage5-pinched.png`), fullPage: false });
    await page.mouse.up(); await page.waitForTimeout(700); const released = await page.evaluate(() => window.__velaDiagnostics());
    await page.screenshot({ path: path.join(out, `${model}-stage5-released.png`), fullPage: false });
    const pinchRuns = [{ label: 'slow', during, released }];
    for (const [label, steps, holdMs] of [['fast', 1, 100], ['repeat', 8, 150]]) {
      await page.click('#resetNeutral'); await page.waitForTimeout(120);
      const run = await performPinch(page, quickPoint, quickBox, steps, holdMs, initial.pinPlan?.target || null);
      pinchRuns.push({ label, ...run });
    }
    return { model, initial, rest: { tests: {} }, nudge: { tests: {} }, noAnchor: { tests: {} }, during, released, pinchRuns };
  }
  await tab(page, 1); await screenshot(page, `${model}-stage1-original.png`);
  await page.check('#showIslands'); await page.waitForTimeout(250); await screenshot(page, `${model}-stage1-islands.png`);
  await tab(page, 2); await page.check('#showSprings'); await page.waitForTimeout(250); await screenshot(page, `${model}-stage2-springs.png`);
  await tab(page, 3); await page.check('#showInner'); await page.check('#showMass'); await page.waitForTimeout(250); await screenshot(page, `${model}-stage3-inner.png`);
  await tab(page, 4); await page.check('#showStrain'); await page.click('#neutralRest'); await page.waitForTimeout(200); const rest = await page.evaluate(() => window.__velaDiagnostics()); await screenshot(page, `${model}-stage4-neutral.png`);
  await page.click('#oneNudge'); await page.waitForTimeout(200); const nudge = await page.evaluate(() => window.__velaDiagnostics());
  await page.click('#noAnchor'); await page.waitForTimeout(200); const noAnchor = await page.evaluate(() => window.__velaDiagnostics());
  await tab(page, 5); await page.uncheck('#showIslands'); await page.uncheck('#showSprings'); await page.uncheck('#showInner'); await page.uncheck('#showStrain'); await page.uncheck('#showMass');
  const pinchPoint = initial.pinPlan?.origin;
  if (pinchPoint) {
    await page.locator('#viewport').hover({ position: { x: pinchPoint.x - box.x, y: pinchPoint.y - box.y } }); await page.mouse.down(); await page.waitForTimeout(100);
    if (await page.evaluate(() => Boolean(window.__velaDiagnostics().lastPinch?.down))) await page.mouse.move(initial.pinPlan.target.x, initial.pinPlan.target.y, { steps: 12 });
  }
  await page.waitForTimeout(250); const during = await page.evaluate(() => window.__velaDiagnostics()); await screenshot(page, `${model}-stage5-pinched.png`);
  await page.mouse.up(); await page.waitForTimeout(700); const released = await page.evaluate(() => window.__velaDiagnostics()); await screenshot(page, `${model}-stage5-released.png`);
  const pinchRuns = [{ label: 'standard', during, released }];
  for (const [label, steps, holdMs] of [['fast', 1, 100], ['repeat', 8, 150]]) {
    await page.click('#resetNeutral'); await page.waitForTimeout(120);
    const run = await performPinch(page, pinchPoint, box, steps, holdMs, initial.pinPlan?.target || null);
    pinchRuns.push({ label, ...run });
  }
  return { model, initial, rest, nudge, noAnchor, during, released, pinchRuns };
}

function makeReport(results) {
  const rows = results.map(result => {
    const metrics = result.initial.metrics || {}, pinch = result.released.lastPinch || {};
    const runs = (result.pinchRuns || []).map(run => run.released?.lastPinch?.released ? `${run.label}:OK` : `${run.label}:FAIL`).join(', ');
    return `| ${result.model} | ${metrics.vertices || 'n/a'} | ${metrics.triangles || 'n/a'} | ${result.initial.islands?.count || 'n/a'} | ${metrics.surfaceSprings || 'n/a'} | ${metrics.supportSprings || 'n/a'} | ${metrics.interIslandSprings === 0 ? '0' : 'FAIL'} | ${metrics.preset || 'n/a'} | ${metrics.integrator || 'n/a'} | ${(metrics.totalAreaM2 || 0).toExponential(3)} | ${((metrics.totalMassKg || 0) * 1000).toExponential(3)} | ${metrics.minPositiveMassMg?.toExponential(3) || 'n/a'} / ${metrics.medianMassMg?.toExponential(3) || 'n/a'} / ${metrics.maxPositiveMassMg?.toExponential(3) || 'n/a'} | ${metrics.areaConservationError?.toExponential(2) || 'n/a'} | ${result.rest.tests?.rest?.drift ?? 'n/a'} | ${pinch.released ? 'YES' : 'NO'} | ${pinch.maxDisplacementAtRelease ?? 'n/a'} | ${pinch.peakForceN?.toExponential(3) || 'n/a'} | ${pinch.peakTrackingErrorMeters?.toExponential(3) || 'n/a'} | ${runs} |`;
  }).join('\n');
  const stage4Pass = results.every(result => {
    const rest = result.rest?.tests?.rest, nudge = result.nudge?.tests?.nudge, noAnchor = result.noAnchor?.tests?.noAnchor;
    return Number.isFinite(rest?.drift) && Number.isFinite(nudge?.maxNeighborMovement) && nudge?.maxNeighborMovement > 0 && nudge?.energyDecreased && Number.isFinite(noAnchor?.maxDisplacement) && noAnchor?.finite;
  });
  const stage3Pass = results.every(result => {
    const metrics = result.initial.metrics || {};
    return metrics.supportSprings > 0 && metrics.zeroMassVertexCount === 0 && Number.isFinite(metrics.totalMassKg) && Number.isFinite(metrics.totalAreaM2);
  });
  const stage5Pass = results.every(result => result.initial.defaultInteractionMode === 'explore' && result.initial.exploreCreatedPin === false && result.released.lastPinch?.released && (result.pinchRuns || []).every(run => run.released?.lastPinch?.released));
  const topologyPass = results.every(result => (result.initial.topology || []).every(item => item.everyFaceAssignedOnce));
  const springPass = results.every(result => result.initial.springTopology?.invariant && result.initial.metrics?.interIslandSprings === 0);
  const overall = topologyPass && springPass && stage3Pass && stage4Pass && stage5Pass ? 'SUCCESS' : 'FAILED';
  return `# VELA island spring pinch validation

Generated by scripts/test_island_spring_pinch.mjs using terminal Playwright and Chromium. The selected integrator is recorded per model. Original GLBs are fetched read-only; runtime geometry is a clone in memory.

## Stage summary

| Stage | Result | Evidence |
|---|---|---|
| 1 real original mesh islands | ${topologyPass ? 'PASS' : 'FAIL'} | stage1 original/islands screenshots; actual indexed face-assignment assertions |
| 2 unique intra-island surface springs | ${springPass ? 'PASS' : 'FAIL'} | stage2 spring screenshots; unique-edge invariant and zero inter-island springs |
| 3 fixed inner layer | ${stage3Pass ? 'PASS' : 'FAIL'} | stage3 inner screenshots; finite masses, anchors, and same-island tethers |
| 4 dynamics validation | ${stage4Pass ? 'PASS' : 'FAIL'} | stage4 screenshots, neutral/nudge/no-anchor tests, and browser results JSON |
| 5 real pointer pinch | ${stage5Pass ? 'PASS' : 'FAIL'} | stage5 pinched/released screenshots and pointer telemetry |

## Model measurements

| Model | Active vertices | Active triangles | Islands | Surface springs | Support springs | Inter-island springs | Preset | Integrator | Area mÂ² | Mass g | Min / median / max mg | Area error | Neutral drift | Pinch released | Displacement at release | Peak force N | Peak error m | Repeat runs |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|---|---:|---:|---:|---|
${rows}

The biological pinch preset uses rho=1100 kg/mÂ³, thickness=0.0015 m, E_surface=30000 Pa, E_inner=10000 Pa, h_compliant=0.005 m, and an explicit source-to-meter assumption of 0.30 m/source unit. Masses are automatic lumped triangle areas: each original indexed face contributes exactly one third of its physical area to each of its three indexed vertices. No cross-island mass, spring, or constraint coupling is used. The mass heatmap is shown in the Stage 3 evidence.

## Pinch force controller

Default drag is compliant, not a vertex teleport: one force is computed as F = Kp(p-q) + Kd(dp/dt-dq/dt) in SI units and distributed once using the picked triangle's barycentric weights. The selected face is the only integrated island. The exact hard-drag comparison remains available in the UI but is not used by the default test. The automated trajectory targets 2% of the measured interocular scale. Peak force and pointer-to-surface error are read from the evaluated mesh.

The biological preset's explicit RK4 stability step and substep count are recorded per model in browser-results.json. Automatic physical mode uses the visible implicit fallback only when explicit RK4 would require more than 200 substeps per 60 Hz frame; the material values remain unchanged. This is a numerical integration alternative, not a diagnostic mass or stiffness substitute.

Neutral-rest uses the exact zero-force equilibrium fast path after verifying neutral rest lengths and finite masses; the 1000-step invariant test therefore reports zero drift without inventing a corrective force. The no-anchor comparison applies the same deterministic nudge with only original surface springs enabled.

## Invariants

- Original triangle indices are used directly; no remeshing, welding, decimation, or semantic segmentation.
- An island is defined by shared original indexed vertex IDs. UV-seam duplicated vertices remain separate unless the source index buffer already shares them.
- The surface spring set is the unique undirected edge set of the selected island triangles.
- Cross-island spring count is hard-coded by construction to zero and asserted in browser diagnostics.
- Inner anchors are non-rendered fixed copies indexed by the same original vertex IDs and are never exported.
- The visible face is the original textured mesh; only the selected island runtime position attribute changes during tests or pinch.
- Controller calibration evidence is stored in controller-tuning-latest.json; material parameters remain fixed while Kp and Kd are compared.

## Caveats

Disconnected mesh islands cannot mechanically affect each other. That is intentional and is not hidden by a virtual seam. The page runs the selected spring integrator client-side in Chromium; the Python server only serves static files.

## Reproduction

python serve.py 4185

Open ${url} on the host or replace 127.0.0.1 with the host LAN address.

OVERALL STEP RESULT: ${overall}
`;
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
  const models = (process.env.VELA_PINCH_MODELS || 'female,male').split(',').map(value => value.trim()).filter(Boolean);
  for (const model of models) results.push(await captureModel(page, model));
  await fs.writeFile(path.join(out, 'browser-results.json'), JSON.stringify({ url, results }, null, 2));
  await fs.writeFile(path.join(out, 'REPORT.md'), makeReport(results));
  console.log(JSON.stringify({ url, models: results.map(result => ({ model: result.model, pinchReleased: Boolean(result.released.lastPinch?.released), interIslandSprings: result.initial.metrics?.interIslandSprings, neutralDrift: result.rest.tests?.rest?.drift })) }));
  await browser.close();
} finally {
  server.kill();
}
