import { chromium } from 'playwright';

const baseUrl = process.env.VELA_URL || 'http://127.0.0.1:4174';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  await page.locator('#characterSelect').selectOption('tripo');
  await page.getByText('vela-photoreal-faced.glb:', { exact: false }).waitFor({ timeout: 120000 });
  await page.waitForFunction(() => window.talkingHead?.avatar?.url?.startsWith('blob:'), null, { timeout: 120000 });
  await page.waitForTimeout(1200);
  const report = await page.evaluate(() => {
    const h = window.talkingHead;
    const canvas = document.querySelector('#avatar canvas');
    const rect = canvas.getBoundingClientRect();
    const camera = { aspect: h.camera.aspect, position: h.camera.position.toArray(), target: h.controls.target.toArray() };
    const eyes = {};
    for (const [name, eye] of [['left', h.objectLeftEye], ['right', h.objectRightEye]]) {
      const point = eye?.getWorldPosition(new h.camera.position.constructor());
      if (point) eyes[name] = point.project(h.camera).toArray();
    }
    return {
      viewport: [innerWidth, innerHeight], canvas: [canvas.width, canvas.height], canvasRect: [rect.x, rect.y, rect.width, rect.height],
      selected: document.querySelector('#characterSelect').value, avatar: h.avatar.url,
      compatibility: document.querySelector('#compatibility').textContent, trackedMorphMeshes: h.morphs.length,
      camera, eyes, horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    };
  });
  await page.screenshot({ path: 'assets/tripo/vela-photoreal/verification/vela-photoreal-mobile-initial.png', fullPage: true });
  if (report.viewport[0] !== 412 || report.canvasRect[2] !== 412 || report.selected !== 'tripo' || report.trackedMorphMeshes < 2 || report.horizontalOverflow || errors.length) {
    throw new Error(`Mobile character check failed: ${JSON.stringify({ report, errors })}`);
  }
  console.log(JSON.stringify({ ...report, errors }, null, 2));
} finally { await browser.close(); }
