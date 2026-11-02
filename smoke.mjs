import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1365, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('console', msg => { if (msg.type() === 'error') errors.push(`console: ${msg.text()}`); else if (msg.type() === 'log') console.log(`browser: ${msg.text()}`); });
page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
await page.goto('http://127.0.0.1:4174', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#speak', { state: 'attached', timeout: 15000 });
await page.waitForTimeout(20000);
const loaded = await page.evaluate(() => ({
  status: document.querySelector('#statusText')?.textContent,
  progressText: document.querySelector('#progress')?.textContent,
  button: document.querySelector('#speak')?.textContent,
  disabled: document.querySelector('#speak')?.disabled,
  avatarReady: Boolean(window.talkingHead),
  ttsReady: Boolean(window.headtts),
  rig: window.talkingHead?.scene?.traverse ? (() => { let nodes=0, meshes=0, morph=0, names=[]; window.talkingHead.scene.traverse(o => { nodes++; if (o.isMesh) { meshes++; if (o.morphTargetDictionary) { const keys=Object.keys(o.morphTargetDictionary); morph += keys.length; names.push(...keys); } } }); return { nodes, meshes, morphTargets:morph, hasOculusVisemes:['viseme_aa','viseme_E','viseme_I','viseme_O','viseme_U','viseme_PP','viseme_SS'].every(k => names.includes(k)), sample:names.slice(0,16) }; })() : null
}));
if (!loaded.disabled) {
  const input = page.locator('#text');
  await input.fill('Hello from the local talking character.');
  await page.locator('#emotion').selectOption('happy');
  await page.locator('#speak').click();
  await page.waitForTimeout(10000);
  const speaking = await page.evaluate(() => ({ progress: document.querySelector('#progress')?.textContent, mood: window.talkingHead?.moodName }));
  console.log('speaking', JSON.stringify(speaking));
}
await page.screenshot({ path: 'artifacts-smoke.png', fullPage: true });
console.log(JSON.stringify({ loaded, errors }, null, 2));
await browser.close();

